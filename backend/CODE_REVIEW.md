# 代码 Review 指南

给 reviewer 的入口。**不要按文件顺序读** —— 按「demo 输出 → 代码」倒着读,效率高得多。

---

## 第 0 步:先跑起来(3 分钟)

```bash
cd backend
../.venv/bin/python -m pytest -q          # 期望:50 passed
../.venv/bin/python -m app.demo_pipeline  # 看 L1 生成
../.venv/bin/python -m app.demo_edit      # 看 L2 编辑
```

**三个都不需要 API key。** 跑不起来就不用往下看了,先修环境。

---

## 第 1 步:对着 demo 输出反查代码

这是最有效的 review 路径 —— 每行输出都能定位到代码,看完就知道系统在干什么。

| demo 输出 | 代码位置 | 该质疑什么 |
| --- | --- | --- |
| `[  5%] 摄取材料 — …` | `pipeline.py` `generate_course()` 阶段 1 | 进度百分比会不会倒退? |
| `[ 41%] 分节生成 — 1/3 节…` | `pipeline.py` `one_section()` | 并发下进度会不会乱? |
| `(工具调用 4 次,terminal)` | `agent.py` `AgentResult.stopped_by` | 为什么是 `terminal` 而不是 `max_turns`? |
| `第 1 节: ['search_materials', …]` | `agent.py` 的 `result.calls` | 序列合理吗?有没有跳步? |
| `[pt-1] slide → s3 状态=proposed` | `patches.py` `Patch` + `edit.py propose_patch()` | 状态机对不对? |
| `理由:教师反馈这一页太难…` | `tools.py` `_PATCH_PARAMS` 里的 `reason` | reason 是不是必填? |
| `差异: - speakerNotes: '…'` | `edit.py _current_values()` + `patches.py make_diff()` | 改前值取得对吗? |
| **`★ 产物是否已被改动? 否 ✅`** | `edit.py propose_patch()` | **这条最重要,见下** |
| `已 apply pt-1` / `是 ✅` | `patches.py apply_patch()` | 是不是只有它能改产物? |
| `驳回 … 否 ✅` | `patches.py reject_patch()` | 驳回会不会误改内容? |

---

## 第 2 步:五个重点(按重要性排序)

### ① 不变式:未确认的改动不得改变产物

**这是整个设计最核心的一条** —— 对应 NFR-04。

| 看哪里 | 看什么 |
| --- | --- |
| `edit.py` `edit_artifact()` 的 docstring | 它明确说明「本函数不改变 package 内容」 |
| `edit.py` `propose_patch()` | 只调 `store.propose()`,**没有一行碰 package** |
| `patches.py` `apply_patch()` | 唯一写产物的函数 |
| `tests/test_edit.py::test_proposed_patch_does_not_change_the_package` | 断言提议后产物 `model_dump_json()` 一字未变 |
| `tests/test_edit.py::test_apply_is_the_only_way_to_change_the_package` | 断言 apply 后**确实**变了 |

**review 时该问的:**

- 有没有别的路径能改产物?(grep `\.slides\[`、`setattr`、`\.payload`)
- `apply_patch` 里的 `model_validate` 如果去掉会怎样?(会绕过 schema 校验)
- 内存版换成数据库版时,这条不变式还守得住吗?

### ② 失败隔离:单个失败不能搞挂整包

| 看哪里 | 看什么 |
| --- | --- |
| `agent.py` `except Exception` 那一段 | 工具抛异常时是**回喂错误给模型**,不是往上抛 |
| `agent.py` 未知工具的处理 | 模型编出不存在的工具,循环继续而不是崩 |
| `tests/test_agent.py::test_tool_exception_does_not_kill_the_pipeline` | 断言循环没死 |

**该问的:** 回喂错误会不会导致模型反复重试同一个坏工具?轮数上限能兜住吗?

### ③ 提示词与工具 schema

模型的行为边界全靠这两样,不是靠代码。

| 看哪里 | 看什么 |
| --- | --- |
| `pipeline.py` `SECTION_SYSTEM_PROMPT` | L1 的四条要求(先检索、图走 Mermaid、用终止工具、标来源) |
| `edit.py` `EDIT_SYSTEM_PROMPT` | L2 的四条要求(先读再改、改动只暂存、必填 reason) |
| `tools.py` `SLIDE_SCHEMA` | **写得很细**。只写 `{"type":"object"}` 的话,真模型必然产出过不了校验的 dict |
| `tools.py` `_PATCH_PARAMS` | `reason` 是 `required` |

**该问的:** 换个模型(比如 Gemini)还守得住吗?这是接真模型后第一个要测的。

### ④ 数据结构:IR 与 camelCase

| 看哪里 | 看什么 |
| --- | --- |
| `schemas/ir.py` `_IRBase` | 内部 snake_case,序列化 camelCase —— 和设计规格 §5.1 的 JSON 对齐 |
| `schemas/ir.py` `CoursePackage.validate_integrity()` | §6.4 的 7 条交叉引用检查 |
| `schemas/ir.py` `Slide._sourced_needs_refs` | 模型级校验:`origin=sourced` 必须给 `sourceRefs` |
| `edit.py _current_values()` | **必须用 `by_alias=True`** —— 否则 diff 会显示成 `None`(这里踩过坑) |

**该问的:** 新增一个产物类型要改哪几处?(`ir.py` 加模型 → `pipeline.py` 装配 → `tools.py` 加工具)

### ⑤ 测试覆盖

| 文件 | 测什么 | 数量 |
| --- | --- | --- |
| `test_ir.py` | IR 校验规则(§6.4) | 14 |
| `test_agent.py` | agent 循环:终止工具、轮数上限、序列记录、失败隔离 | 10 |
| `test_pipeline.py` | 六阶段、进度单调、并发一致、产物齐全 | 9 |
| `test_edit.py` | **暂存不变式**、apply/reject、先读再改、重新校验 | 13 |
| `test_config.py` | 配置优先级、密钥默认为空 | 4 |

**该问的:** 有没有测试是「为了通过而写的」?断言的是行为还是实现细节?(应该断言**工具调用序列**,不是输出文本)

---

## 第 3 步:已知取舍(不是 bug,别报)

| 现象 | 为什么这样 | 什么时候补 |
| --- | --- | --- |
| `pipeline.py` 阶段 1/4/5 是空壳 | 真实实现要 PyMuPDF / Kroki / 对象存储 | 接真实现时 |
| `fake_search` / `fake_make_diagram` | 让 demo 不需要 key 就能跑通 | 同上 |
| `InMemoryPatchStore` 不持久化 | 先验证机制,再换数据库 | 建 `patches` 表时 |
| 校验失败只丢一节 | §6.4 明确要求「保存部分草稿,不整包丢弃」 | 已经是最终行为 |
| `apply_patch` 里重新 `model_validate` | **故意**的 —— 不能让「教师确认了」成为绕过 schema 的理由 | 已经是最终行为 |
| `deps.py` 一律返回 401 | 认证没接好之前,宁可不可用也不能放行 | 接 JWT 时 |

## 第 4 步:已知缺口(真债,该报)

| 缺口 | 影响 |
| --- | --- |
| 没有数据库、没有 Alembic 迁移 | patch 和产物重启即丢 |
| 没有 HTTP 端点(`/edit`、`/apply`、`/reject`) | 前端接不上 |
| 没有认证 | 所有接口都不可用 |
| 检索与 Mermaid 渲染是假实现 | 生成的图不是真图 |
| 没有导出(pptx/docx/pdf) | 产物出不去 |
| 前端还是 Next.js 默认页 | 没有界面 |

---

## 附:怎么加一个新产物类型(检验你读懂了吗)

以「加一种 `ExamPaper` 生成」为例:

1. `schemas/ir.py` —— 模型已存在(`ExamPaper`)
2. `tools.py` —— 加一个终止工具 `write_exam_paper`,或在 `write_section` 里扩展
3. `pipeline.py` —— 阶段 6 装配时把它塞进 `CoursePackage`
4. `patches.py` `apply_patch()` —— 加一个 `kind` 分支
5. `tests/` —— 加校验测试

**如果你能不看代码说出这 5 步,说明这个 codebase 你已经读懂了。**
