# 一次完整交互:从「生成」到「确认」

把 `python -m app.demo_edit` 的输出逐行追回代码。**这是运行时流程,不是代码 review。**

---

## 参与者

| 角色 | 代码位置 |
| --- | --- |
| 管道(六阶段编排) | `services/pipeline.py` |
| Agent 循环 | `services/agent.py` |
| 工具集 | `services/tools.py` |
| 暂存区 | `services/patches.py` |
| L2 依赖实现 | `services/edit.py` |
| 产物 | `schemas/ir.py` 的 `CoursePackage` |

---

## A. L1 生成

### A1. 入口

```python
generate_course(req, deps, on_event)      # pipeline.py
```

`deps` 里装的是可替换的实现(假模型 / 假检索 / 假渲染)。

### A2–A3. 阶段 1–2:摄取材料、规划大纲

输出里的 `[ 5%]` `[10%]` `[15%]` `[25%]`。

- 阶段 1 是**空壳** —— 真实实现要 PyMuPDF 解析 + 分块 + 向量化
- 阶段 2 简单版把章节写死成 3 节;真实实现由模型产出大纲

**为什么顺序写死:** 没有大纲就不知道要写几节,没有节内容就不知道要配几张图。写死才能算进度。

### A4. 阶段 3:分节生成(输出里的 `[ 41%]` `[ 58%]` `[ 75%]`)

```python
sem = asyncio.Semaphore(deps.section_concurrency)     # 默认 3
pairs = await asyncio.gather(*(one_section(i, t) for i, t in enumerate(sections)))
```

**三节并发跑**,但用信号量限流。进度按「已完成节数」线性推进:

```
41% = 25 + (75-25) × 1/3
58% = 25 + (75-25) × 2/3
75% = 25 + (75-25) × 3/3
```

### A5. 每节内部:一个 agent 循环(`agent.py:106`)

这是**唯一有自主性的一步**。工具调用序列:

| 轮 | 模型要求调用 | 我们的代码执行 | 结果回喂给模型 |
| --- | --- | --- | --- |
| 1 | `search_materials` | `deps.search_materials(query)` | 两条带页码的片段 |
| 2 | `make_diagram` | `deps.make_diagram(mermaid)` | `asset_id`,同时登记资产 |
| 3 | `write_plan_entry` | 追加到 `deps.written_plan` | `{ok: true}` |
| 4 | `write_section` | 追加到 `deps.written_slides` | — **终止工具,循环立即结束** |

**为什么必须有终止工具:** 如果只靠「模型不再调工具」结束,它可能一直调下去烧光 token。调 `write_section` 即结束,这是确定的。

**每条记录都进 `result.calls`** —— 这就是输出里那行 `['search_materials', 'make_diagram', ...]`,也是测试断言的对象。

### A6. 阶段 4–5:视觉需求与资产(输出里的 `3 处视觉需求` `3 个资产入池`)

简单版里资产在 A5 调 `make_diagram` 时就已经产生。真实实现要按决策树判断 diagram/chart/icon/illustration,只有最后一种才可能走生图。

### A7. 阶段 6:装配与校验(输出里的 `产出 课件+教案;校验通过`)

```python
assets_by_id  ← 各节的 sd.assets,按 id 去重
lesson_plan   ← 各节的 sd.written_plan → TimelineEntry
slides        ← 各节的 sd.written_slides → Slide,按 order 排序
package = CoursePackage(project, assets, lesson_plan, slide_deck)
issues = package.validate_integrity()      # §6.4 那 7 条
```

**并发跑完必须重排** —— 否则课件页码是乱的。

---

## B. L2 编辑

### B1. 入口

```python
edit_artifact(client, model, package, message, store)     # edit.py:153
```

它建 `EditDeps(package, store)`,然后跑**同一个** `run_agent`,只是换成 6 个编辑工具、`max_turns=8`。

### B2. Agent 循环的两轮

| 轮 | 模型要求调用 | `EditDeps` 里发生了什么 |
| --- | --- | --- |
| 1 | `read_slide("s3")` | `find_slide(...).model_dump(by_alias=True)` → 返回 camelCase 的当前内容 |
| 2 | `patch_slide(s3, {...}, reason)` | `propose_patch()` → 取改前值 → `store.propose()` → 建一个 `proposed` 的 patch |
| 3 | (不再调工具) | 循环以 `stopped_by="no_tool_calls"` 结束 |

**关键:`propose_patch` 里没有一行碰 `package`。** 它只做三件事:

1. 从参数里取出 `patch` / `reason` / `slide_id`
2. 取这几字段的**当前值**(为了生成 diff)
3. `store.propose(...)` 建一个 `Patch(id="pt-1", status="proposed")`

### B3. 产出:待确认的 patch

```
[pt-1] slide → s3  状态=proposed
  理由:教师反馈这一页太难…
  差异: - title: '动手示例' / + title: '分支是什么(入门版)' …
```

**此时输出里那句 `★ 产物是否已被改动? 否 ✅`** —— 因为整个 B 段没有任何写路径。

> 这不是「碰巧没变」,而是 `edit_artifact()` 的 docstring 里明文规定的:
> **本函数不改变 package 内容。**

---

## C. 教师确认(apply)

```python
apply_patch(package, store, "pt-1")        # patches.py:167
```

四步:

1. `store.get("pt-1")` —— 取 patch,检查还是 `proposed`(不许重复确认)
2. 找到 `s3` 在 `deck.slides` 里的下标
3. `merged = {**slide.model_dump(), **patch.payload}` → `Slide.model_validate(merged)`
4. 写回 `deck.slides[index]`,然后 `store.mark("pt-1", "applied")`

**第 3 步为什么用 `model_validate` 而不是 `setattr`:** 直接改属性会绕过 schema 校验 ——
等于在编辑路径上又给「AI 输出必须合规」这条规则开了个口子。用 `model_validate`
意味着**一个会让产物非法的 patch 会在 apply 时被挡住**,不会因为「教师点了确认」就放行。

输出里的 `★ 产物是否已被改动? 是 ✅`。

---

## D. 对照:驳回

```python
reject_patch(store, "pt-1")                # patches.py:209
```

只做一件事:把状态改成 `rejected`。

**产物本来就没被动过,所以驳回不需要「撤销」任何东西。** 输出里的 `否 ✅`。

---

## 三个设计点,一句话各一

| 设计 | 为什么 |
| --- | --- |
| **终止工具** | 不靠模型自觉收尾 —— 那不可靠,而且烧 token |
| **改动只暂存** | NFR-04 在**每次编辑**上都成立,而不只是在发布时成立 |
| **apply 时重新校验** | 「教师确认了」不能成为绕过 schema 的理由 |

---

## 一句话概括这条链

```
教师说话 → agent 提议(只写暂存区)→ 教师确认 → apply 才写产物
                    ↑
              产物此刻一字未变
```

**`apply_patch()` 是唯一能改变产物内容的函数。** 其余任何地方都不许碰它。
