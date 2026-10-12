"""用**真实 DeepSeek** 跑一遍 L1 流水线。

前置:先确认能连通 —— `../.venv/bin/python -m app.check_deepseek`

    cd backend && ../.venv/bin/python -m app.demo_deepseek

═══════════════════════════════════════════════════════════════════
这次要验证的是什么
═══════════════════════════════════════════════════════════════════
不是「检索准不准」,也不是「Mermaid 好不好看」——
检索和渲染在这两个 demo 里**仍然是内存假实现**。

这次要看的是**真模型的行为**:

  1. 它会不会按约定调工具(先检索、再画图、最后 write_section)?
  2. 它会不会正确收尾(调用终止工具),而不是一直调下去?
  3. 它产出的 slides 能不能**通过 IR 校验**(§6.4)?
  4. 一次生成花多少 token?

这四条里有任何一条不过,就应该回头改**提示词或工具 schema**,
而不是改 agent 循环 —— 循环已经是对的。
"""

from __future__ import annotations

import asyncio
import sys

from app.config import settings
from app.demo_pipeline import fake_illustration, fake_make_diagram, fake_search
from app.llm.client import OpenAICompatClient, build_deepseek_client
from app.services.pipeline import GenerationRequest, PipelineDeps, generate_course


def _hr(title: str) -> None:
    """打一条分隔线,让输出好读。"""

    print()
    print("═" * 64)
    print(title)
    print("═" * 64)


async def main() -> int:
    """用真实 DeepSeek 跑一遍 L1,打印工具序列、校验结果与 token 成本。"""

    if not settings.deepseek_api_key:
        print("❌ 没有 DEEPSEEK_API_KEY。先跑:")
        print("     ../.venv/bin/python -m app.check_deepseek")
        return 2

    client = build_deepseek_client()

    req = GenerationRequest(
        topic="Git 分支管理",
        audience="非计算机专业初学者",
        duration_min=45,
        objectives=["解释分支与主干的关系", "完成一次安全的合并"],
    )
    deps = PipelineDeps(
        client=client,
        model=settings.deepseek_model,
        # 注意:这三个仍是假实现。真实现是 MaterialIngestor 和 Kroki 渲染。
        search_materials=fake_search,
        make_diagram=fake_make_diagram,
        request_illustration=fake_illustration,
        section_concurrency=3,
    )

    print(f"真实模型:{settings.deepseek_model} @ {settings.deepseek_base_url}")

    try:
        result = await generate_course(req, deps, on_event=lambda ev: print("  " + str(ev)))
    except Exception as exc:  # noqa: BLE001
        print(f"\n❌ 流水线失败:{type(exc).__name__}: {exc}")
        return 1

    _hr("每个 SectionAgent 的工具调用序列")
    for i, agent in enumerate(result.agents, 1):
        print(f"  第 {i} 节: {agent.call_names}")
        print(f"          轮数 {agent.turns} · 结束原因 {agent.stopped_by}")
        for call in agent.calls:
            mark = "✗" if call.error else "✓"
            print(f"          {mark} {call.name}")
            if call.error:
                print(f"             错误:{call.error}")
        if agent.stopped_by != "terminal":
            print("          ⚠️  这一节没调用终止工具 —— 模型没按约定收尾")

    _hr("产出的 IR")
    pkg = result.package
    print(f"  幻灯片:{len(pkg.slide_deck.slides)} 页")
    for s in pkg.slide_deck.slides:
        print(f"    · {s.id} [{s.layout}] {s.title}")
        print(f"        origin={s.origin}  来源={[(r.material_id, r.page) for r in s.source_refs]}")
        print(f"        要点={s.bullets}")
        for v in s.visuals:
            print(f"        视觉:{v.kind} → {v.asset_id}")
    print(f"  资产池:{len(pkg.assets)} 个 {[a.id for a in pkg.assets]}")

    _hr("§6.4 交叉引用校验")
    issues = result.integrity_issues
    if issues:
        for issue in issues:
            print(f"  ❌ {issue}")
    else:
        print("  ✅ 通过")

    _hr("成本")
    u = client.usage
    print(f"  请求 {u['requests']} 次")
    print(
        f"  输入 {u['prompt_tokens']} tokens"
        f" · 输出 {u['completion_tokens']} tokens"
        f" · 合计 {u['total_tokens']} tokens"
    )
    print("  (把 token 数乘上官网单价,就是这一次生成的成本)")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
