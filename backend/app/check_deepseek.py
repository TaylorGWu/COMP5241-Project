"""最小连通性检查 —— 确认 key 能用、模型名写对。

    cd backend && ../.venv/bin/python -m app.check_deepseek

它只发一次请求,花不了几分钱,但能把「key 不对 / 余额不足 / 模型名写错」
和「代码有问题」区分开 —— 排查时这一步能省很多时间。
"""

from __future__ import annotations

import asyncio
import sys

from app.config import settings


async def main() -> int:
    """检查 key / 模型名 / 网络是否可用。返回退出码,便于脚本判断。"""

    # ── 先检查 key 是否存在,给出可照做的指引 ──────────────────
    if not settings.deepseek_api_key:
        print("❌ 没有找到 DEEPSEEK_API_KEY")
        print()
        print("   照这样做:")
        print("     1. cp env.yaml.example env.yaml")
        print('     2. 编辑 env.yaml,把 deepseek_api_key: "" 填上你的 key')
        print("     3. 重新运行本脚本")
        print()
        print("   env.yaml 已被 .gitignore 忽略,不会被提交。")
        print("   也可以改用环境变量(优先级更高):")
        print("     export DEEPSEEK_API_KEY=sk-...")
        print("   注意:请在编辑器里直接改,不要把 key 贴进聊天记录。")
        return 2

    key_tail = settings.deepseek_api_key[-4:]
    print("  目标:")
    print(f"    base_url : {settings.deepseek_base_url}")
    print(f"    model    : {settings.deepseek_model}")
    print(f"    api_key  : ****{key_tail}(只显示末 4 位)")
    # 延迟导入:没装 openai 包时先给清楚的提示,而不是 ImportError 堆栈
    try:
        from app.llm.client import build_deepseek_client
    except ImportError as exc:
        print(f"❌ 缺少依赖:{exc}")
        print("   ../.venv/bin/pip install -r requirements.txt")
        return 1

    # 注意:`openai` 是在 OpenAICompatClient.__init__ 里延迟导入的,
    # 所以「缺依赖」要在这里接,而不是在 import 那一行。
    try:
        client = build_deepseek_client()
    except ImportError as exc:
        print(f"❌ 缺少依赖:{exc}")
        print("   ../.venv/bin/pip install -r requirements.txt")
        return 1

    # ── 先列出这个 key 实际能用的模型 ──────────────────────
    # 「模型名写错」是最常见也最难猜的失败原因,先排掉它。
    models = await client.list_models()
    if models:
        print()
        print("  这个 key 可用的模型:")
        for name in models:
            mark = "   ← 当前配置" if name == settings.deepseek_model else ""
            print(f"    · {name}{mark}")
        if settings.deepseek_model not in models:
            print()
            print(f"  ❌ 当前配置的 {settings.deepseek_model!r} 不在上面的列表里!")
            print("     改 env.yaml 的 deepseek_model,或从上面挑一个。")
            return 1
    else:
        print()
        print("  (/models 端点不可用,跳过模型列表检查)")
    print()
    print("  发送一次最小请求…")

    try:
        reply = await client.complete(
            model=settings.deepseek_model,
            messages=[{"role": "user", "content": "只回复两个字:可用"}],
            temperature=0.0,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 调用失败:{type(exc).__name__}")
        print(f"   {exc}")
        print()
        print("   常见原因:")
        print("     · key 无效或已过期")
        print("     · 账户余额不足")
        print(f"     · 模型名不对(当前是 {settings.deepseek_model!r})")
        print("     · 网络到不了 api.deepseek.com")
        return 1

    print(f"✅ 通了")
    print(f"   模型回复:{reply.content!r}")
    print(f"   用量:{client.usage}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
