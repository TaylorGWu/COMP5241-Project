# Midterm prompt source appendix

Snapshot: 2026-10-26, working tree codex/teacher-courses (includes uncommitted changes).

Mechanically excerpted source templates and dynamic builders, not historical model-request logs. f-string schemas and request fields expand at runtime; tool schemas also form part of the model contract. No environment files, API keys, user data or hidden model reasoning are included. No separate image-model prompt is wired in the current demo: make_diagram accepts Mermaid code, while request_illustration remains a stub. These are review materials, not a claim that AI-generated slides satisfy the course submission requirements without personal editing.

## PLANNER_PROMPT

Source: `backend/app/services/planner.py:93`

Source-file SHA-256: `6bbbb9dc71c3673c1e963fdd43d5aea66aa990929ad283308db0a692585afc7d`

```python
PLANNER_PROMPT = """你是课程设计助手。为下面的迷你课程设计章节骨架。

只输出一个 JSON 对象,不要任何解释文字、不要 Markdown 围栏。格式:

{
  "objectives": ["学习目标1", "学习目标2"],
    "sections": [
    {"title": "章节标题", "minutes": 15, "objectiveIds": ["LO1"],
     "teachingArc": {"situation": "具体工程情境", "misconception": "常见误解",
                     "practice": "可检查练习", "transferPrompt": "迁移提问"}},
    {"title": "章节标题", "minutes": 15, "objectiveIds": ["LO2"],
     "teachingArc": {"situation": "具体工程情境", "misconception": "常见误解",
                     "practice": "可检查练习", "transferPrompt": "迁移提问"}}
  ],
  "rationale": "一句话说明为什么这样安排章节顺序"
}

硬性要求:
1. 学习目标用 id 表示时必须与 objectives 数组的顺序对应:第一个是 LO1,第二个是 LO2,以此类推。
2. 所有 sections 的 minutes 之和必须**恰好等于**给定课时。
3. 章节数量 2–6 节,每节 3–60 分钟。
4. 面向非专业学习者时,先讲「为什么」再讲「怎么做」。
5. 章节标题要具体,不要「第一章」这种。
6. 整门课要形成「真实工程情境 → 概念与证据 → 决策或操作 → 练习与反馈」的学习弧线。
   不要把章节只排成概念名词列表;至少安排一个真实工程情境和一个可检验的练习环节。
7. 自动拟定的目标须可观察：说明学生在什么条件下能解释、比较、诊断或完成什么，
   避免只用“了解”“掌握”加主题名。教师给定的目标保留原意，不擅自扩展教学范围。
8. 每节 teachingArc 必须针对具体主题：situation 写明任务和初始状态，misconception
   写出具体错误判断及其原因，practice 写出学生要交出的答案/操作结果和判断依据，
   transferPrompt 改变原情境的一个条件。案例及练习只能使用本节或前节已教的知识。
   各节应逐步增加深度，不能把相同的团队失败案例仅替换章节名反复使用。
"""
```

## plan_outline

Source: `backend/app/services/planner.py:219`

Source-file SHA-256: `6bbbb9dc71c3673c1e963fdd43d5aea66aa990929ad283308db0a692585afc7d`

```python
async def plan_outline(
    req: PlannerRequest, *, client: ChatClient, model: str, temperature: float = 0.4
) -> Outline:
    """让模型产出章节骨架。**失败一律降级,不抛异常。**"""
    objectives_hint = (
        "教师指定的学习目标:" + "、".join(req.requested_objectives)
        if req.requested_objectives
        else "教师没指定学习目标,请你根据主题拟定 2–3 条。"
    )
    user = (
        f"课程主题:{req.topic}\n"
        f"学习者:{req.audience}\n"
        f"课时:{req.duration_min} 分钟\n"
        f"语言:{req.language}\n"
        f"{objectives_hint}"
    )

    try:
        reply = await client.complete(
            model=model,
            messages=[
                {"role": "system", "content": PLANNER_PROMPT},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
    except Exception as exc:  # noqa: BLE001
        return _fallback(req, f"模型调用失败({type(exc).__name__})")

    data = extract_json(reply.content)
    if data is None:
        return _fallback(req, "模型没有返回可解析的 JSON")

    try:
        outline = Outline.model_validate(data)
    except Exception as exc:  # noqa: BLE001
        return _fallback(req, f"大纲结构不合法({type(exc).__name__})")

    if not outline.sections:
        return _fallback(req, "模型给出的章节为空")

    # 先归一化,再校验 —— 顺序不能反。
    # 模型给的原始时长可能整体偏大(单位理解错了),但比例是对的;
    # 按比例缩放后再看是否落在合理区间,才不会误杀可用的大纲。
    outline.sections = _normalize_minutes(outline.sections, req.duration_min)

    total = sum(s.minutes for s in outline.sections)
    if total != req.duration_min:
        return _fallback(req, f"无法把章节时长调整到 {req.duration_min} 分钟(得到 {total})")
    for s in outline.sections:
        if not (MIN_SECTION_MINUTES <= s.minutes <= MAX_SECTION_MINUTES):
            return _fallback(req, f"章节时长不合理({s.title} {s.minutes} 分钟)")
    if not outline.objectives:
        outline.objectives = list(req.requested_objectives) or list(DEFAULT_OBJECTIVES)
    if req.requested_objectives:
        # 教师给的目标优先 —— 他们比模型更清楚要教什么
        outline.objectives = list(req.requested_objectives)
    return outline
```

## SECTION_SYSTEM_PROMPT

Source: `backend/app/services/pipeline.py:91`

Source-file SHA-256: `ae1f55a5e1aafcc9c75022f58867fe80a27195b93b36804fa94cd7ae8925dc5e`

```python
SECTION_SYSTEM_PROMPT = """你在为软件工程迷你课程撰写一节内容。

要求:
1. 先用 search_materials 查一下教师上传的讲义,基于材料写,不要凭空编。
2. 有文字标注的示意图必须用 make_diagram(传 Mermaid 代码),不要用生图。
3. 写完后调用 write_section 提交。这是本节的最后一步。
4. 如果某句话来自讲义,在 sourceRefs 里标注页码,并把 origin 设为 "sourced";
   如果是你自己补充的,origin 设为 "ai"。不要声称有来源却拿不出来。
5. **一节固定写 4 页**：explain → worked_example → check_understanding → transfer/recap。
   每页写 3–5 条彼此不同、能支持教师讲解或学生判断的要点；每条用一至两句表达
   一个完整信息单元，包含结论及其依据、条件或具体例子。中文通常 25–60 字，英文通常
   12–28 词；这是可读性参考，不要为凑字数删掉技术前提或添加废话。
   speakerNotes 应足以支持这一页的实际授课：写清如何引入、如何解释、预期学生回答
   以及如何追问或纠错。通常中文 120–220 字、英文 80–140 词，避免只复述 bullets。
   `write_section` 的参数是一次性提交的 JSON,内容太长会被截断导致提交失败。
6. 传 Mermaid 代码时,**字符串里的换行必须写成 \\n 两个字符**,
   不能出现真正的换行符 —— 否则 JSON 不合法,提交会失败。
7. **本节只调用一次 write_plan_entry**,写一条教案环节概括这一节怎么上。
   时长不用纠结 —— 系统会按大纲统一调整。
8. 每节必须包含至少一页**具体工程情境**或失败案例:交代角色、约束和后果,
   不能只写抽象定义。随后用图、代码或材料证据解释原因,让学生作出一个明确的**决策**或判断。
9. 每节必须有一页 layout="quiz" 的随堂**练习**。题干放在 title,选项或判断线索放在 bullets;
   speakerNotes 必须给出正确判断、一个常见错误思路及其**反馈**。这不是期末题,是检查理解。
10. 每页只承担一个教学动作:引出问题、解释证据、比较决策、指导操作或检查理解。
    不要用空泛总结、重复结论或超过 3 条的同义 bullet 凑页数。
11. 本节必须按 teachingArc 形成：explain → worked_example → guided_practice 或
    check_understanding → transfer 或 recap。案例页写出角色、约束、证据和后果；
    练习页写出学生可执行的判断/操作及讲稿反馈。
12. visualPurpose=sequence/mechanism 时才调用 make_diagram；
    comparison/scenario/evidence/none 不得为了配图调用流程图。
13. Mermaid 图不是装饰：节点必须是当前页的真实角色、对象或动作，边要写出
    关系（例如提交、查看、比较、确认）。禁止 Step 1/2、概念图、应用、开始/结束
    这类占位标签；若说不清一个具体关系，就不要调用 make_diagram。
    每节最多生成一张解释核心关系的图。拿到 asset_id 后写入 visual.assetId 即可，
    不要反复调用图示工具寻求更漂亮的图；图示失败只修正一次，仍失败改用文字/比较页。
    优先完成教案与 write_section 提交，不能耗尽轮数仍没有可读的教学内容。
14. `animation` 是可选的教师预览元数据，不会改变页面内容。仅在已有内容适合按步骤讲解时使用：
    target 只能是 title、bullet:0 这类已有 bullet，或 visual:已有视觉 id；
    kind 只能是 reveal/emphasis/sequence，且 sequence 只能指向 visual。不要为封面或 quiz 添加 animation。
15. 内容深度按教学动作区分：
    explain：解释概念是什么、解决什么问题、如何运作及一个适用边界；首次出现术语时解释。
    worked_example：沿用本节情境，给出具体输入/初始状态 → 判断依据 → 操作 → 可观察结果；
    不能只有角色、限制、后果的标签。关键推理必须在页面可见，补充解释放讲稿。
    check_understanding：让学生针对已教过的情境作出判断；干扰项对应真实误解、长度相近；
    正确选项不能总在 B，也不能靠措辞明显更完整来猜。讲稿解释正确与错误选项的依据。
    transfer/recap：改变案例的一个条件，让学生说明原来的做法是否仍适用及原因；
    不要只写“学以致用”“总结所学”或再次罗列名词。
16. 技术准确性优先：命令、代码、版本、前置条件和副作用须明确；给出操作后的验证方式。
    区分本地/远端、未提交/已提交、一般规则/例外，避免“永远”“一定”等无条件断言。
    不确定的数值、研究结论或 API 行为不编造；材料不足时说明假设，留给教师核对。
    操作链必须闭合：本地修改不等于远端已更新，保存不等于已发布；若结果涉及他人，
    不得遗漏同步/发布步骤。验证只声称能实际观察到的结果，不保证“不会冲突”或“必然成功”。
    对未提交、未跟踪、已提交的状态分别检查；不要声称一个命令会保护它并未覆盖的状态。
    表述“删除历史”时区分分支引用变化与对象物理消失。只有在前提明确且排除其他可行方案时，
    才把练习写成唯一正确答案；否则要求比较方案并说明取舍。
17. 标题表达本页要回答的问题或核心判断，避免“机制：”“案例：”后机械复用章节名。
    各页沿用一致的人物、文件、输入和术语，让练习承接案例；每页必须增加新的解释或决策。
18. 视觉必须提供可读的证据：图中对象和连线须对应本页机制，讲稿指出学生应看哪条关系、
    从图中推导什么判断。比较用并列条件与结果，操作示例给真实命令与结果；不强行画流程图。
19. 提交前自检：学习目标有可观察证据吗？案例推理可复现吗？练习信息充分且答案唯一吗？
    讲稿解释了为什么吗？是否遗漏前提、重复要点或编造来源？先修正，再调用 write_section。
"""
```

## NO_MATERIAL_SECTION_SYSTEM_PROMPT

Source: `backend/app/services/pipeline.py:154`

Source-file SHA-256: `ae1f55a5e1aafcc9c75022f58867fe80a27195b93b36804fa94cd7ae8925dc5e`

```python
NO_MATERIAL_SECTION_SYSTEM_PROMPT = SECTION_SYSTEM_PROMPT.replace(
    "1. 先用 search_materials 查一下教师上传的讲义,基于材料写,不要凭空编。",
    "1. 教师没有上传材料。根据可靠的软件工程常识起草，不要编造讲义、页码或来源；所有页面使用 origin=\"ai\"、sourceRefs=[]。",
)
```

## section_user_prompt

Source: `backend/app/services/pipeline.py:242`

Source-file SHA-256: `ae1f55a5e1aafcc9c75022f58867fe80a27195b93b36804fa94cd7ae8925dc5e`

```python
def section_user_prompt(
    index: int, section: "PlannedSection", req: "GenerationRequest",
    objectives: list[str] | None = None,
) -> str:
    """写给某一节的 user 消息。

    ═══════════════════════════════════════════════════════════════
    为什么单独抽成一个函数
    ═══════════════════════════════════════════════════════════════
    这段消息是**模型能看到的契约**的一部分。原来的版本只说了受众,
    没说语言 —— 于是 `language` 参数虽然被 API 和 PlannerRequest 接上了,
    真正写课件的 SectionAgent 却完全不知道要写哪种语言,内容语言
    实际由模型自己决定。「教材语言」这个开关是假的。

    抽出来是为了能被测试钉住:任何模型看得到的契约都必须有测试守着,
    否则它会在某次重构里被悄悄丢掉,而且不会有任何单元测试变红。
    """
    objective_texts = objectives if objectives is not None else req.objectives
    objective_map = {f"LO{i + 1}": text for i, text in enumerate(objective_texts)}
    assigned = [oid for oid in section.objective_ids if oid in objective_map]
    targets = assigned or list(objective_map)
    objective_brief = "；".join(f"{oid}: {objective_map[oid]}" for oid in targets)
    return (
        f"课程主题:{req.topic}。"
        f"写第 {index + 1} 节:{section.title}。"
        f"建议时长 {section.minutes} 分钟。"
        f"课程受众:{req.audience}。"
        f"**标题、要点、讲稿全部用 {req.language} 书写。**"
        f"本节学习目标（objectiveIds 只使用这里的 ID）：{objective_brief or '未指定；围绕本节主题设计可检查的学习结果'}。"
        "先确定学生在本节结束时能解释、比较或完成什么，再安排页面；"
        "页面中的例子、练习与教案的 checkUnderstanding 必须检验同一学习结果。"
        f"教学蓝图：情境={section.teaching_arc.situation}；"
        f"常见误解={section.teaching_arc.misconception}；"
        f"练习={section.teaching_arc.practice}；"
        f"迁移提问={section.teaching_arc.transfer_prompt}。"
    )
```

## EDIT_SYSTEM_PROMPT

Source: `backend/app/services/edit.py:42`

Source-file SHA-256: `c3fc9f19d565281f4d2b6b5b7069d763ff3eb625b18ebd567c70ff6d23f975ed`

```python
EDIT_SYSTEM_PROMPT = """你在帮一位教师修改一份已经生成好的教学材料。

必须遵守:
1. **先读再改。** 修改课件用 read_slide,修改题目用 read_question,修改试卷用 read_paper。
   不要凭猜测对没读过的内容提改动。
2. 所有改动通过对应的 patch 工具提出。**改动不会立刻生效** ——
   教师确认之后才会写入,所以你可以放心提议。
3. 每次改动都要填 reason,说明为什么这么改(会记入版本历史供教师审查)。
4. 提完改动后,用一到两句话说明你做了什么。不要反复提同一个改动。
5. 教师要求逐步讲解概念时，可以提出 `animation` patch；它只能编排当前页已有的
   title、bullet:索引或 visual:视觉 id，不能用它偷偷新增内容。先 read_slide 再确认目标存在。
"""
```

## edit_artifact

Source: `backend/app/services/edit.py:232`

Source-file SHA-256: `c3fc9f19d565281f4d2b6b5b7069d763ff3eb625b18ebd567c70ff6d23f975ed`

```python
async def edit_artifact(
    *,
    client: ChatClient,
    model: str,
    package: CoursePackage,
    message: str,
    images: list[str] | None = None,
    target: str = "slides",
    slide_id: str | None = None,
    store: PatchStore | None = None,
    max_turns: int = 8,
    on_step: Callable[[AgentStep], None] | None = None,
) -> EditResult:
    """让 agent 根据教师的话提出改动。

    **注意:这个函数不会改变 `package` 的内容。**
    它只是把改动暂存成 patch。要让改动生效,必须由上层显式调用
    `apply_patch()` —— 那才是唯一能改产物的路径(§7.2)。

    `on_step` 是可选观察者,原样转交给 agent 循环(§6.1.2)。
    L2 尤其值得看过程:教师能看见 agent 先读了哪一页、为什么这么改。
    不传就没有任何开销,现有调用方一个字都不用改。
    """
    store = store if store is not None else InMemoryPatchStore()
    if slide_id is not None:
        if target != "slides":
            raise ValueError("Slide scope requires the slides material")
        selected = find_slide(package, slide_id)
    deps = EditDeps(package=package, store=store, slide_id=slide_id)
    artifact_id = deps.artifact_id_for({"slides": "slide", "questions": "question", "paper": "paper"}.get(target, "slide"))
    previous_ids = {patch.id for patch in store.list(artifact_id, status="proposed")}

    extra: dict[str, Any] = {}
    if on_step is not None:
        extra["on_step"] = on_step

    user: str | list[dict[str, Any]] = f"[revision target: {target}]\n{message}"
    scope = ""
    if slide_id is not None:
        scope = f"\nSelected slide scope: id={slide_id}, current page={selected.order}, title={selected.title}. Only this stable ID may be patched; page numbers are not IDs."
        user += scope
    if images:
        user = [
            {"type": "text", "text": user},
            *[{"type": "image_url", "image_url": {"url": image}} for image in images],
        ]

    agent_result = await run_agent(
        client=client,
        model=model,
        system=f"{EDIT_SYSTEM_PROMPT}\n\n本次只能修改: {target}。请只使用匹配该材料的 read / patch 工具。{scope}",
        user=user,
        tools=build_edit_tools(deps),
        max_turns=max_turns,
        **extra,
    )

    return EditResult(
        reply=agent_result.content,
        proposed=[patch for patch in store.list(artifact_id, status="proposed") if patch.id not in previous_ids],
        agent=agent_result,
    )
```

## plan_edit

Source: `backend/app/services/edit_planning.py:53`

Source-file SHA-256: `8dd06250403a7e5028eea37d3043aea7fad25011b93f9b2431543d5ac791cd2b`

```python
def plan_edit(package: CoursePackage, request: str, target: str = "slides", slide_id: str | None = None) -> EditPlan:
    """Inspect IR only; selecting a result later still uses the existing patch review flow."""
    slides = package.slide_deck.slides if package.slide_deck else []
    findings: list[EditFinding] = []
    actions: list[PlannedAction] = []
    if slide_id is not None:
        if target != "slides":
            raise ValueError("Slide scope requires the slides material")
        selected = next((slide for slide in slides if slide.id == slide_id), None)
        if selected is None:
            raise KeyError("Selected slide no longer exists")
        animation = "animation" in request.lower()
        return EditPlan(
            request=request, slide_id=slide_id,
            summary=f"Review is limited to slide {selected.order}: {selected.title}. Changes still require your approval.",
            actions=[PlannedAction(
                id=f"{'animate' if animation else 'edit'}-{slide_id}",
                title=f"{'Animate' if animation else 'Improve'} slide {selected.order}",
                detail=selected.title,
                prompt=(f"Teacher request: {request}. First read slide {slide_id} ({selected.title}). "
                        + ("Propose an animation patch only using existing content. Do not change text, notes, visuals, or objectives. " if animation else "Propose only the requested improvements as reviewable patches. ")
                        + "Do not modify any other slide or material."),
                target_id=slide_id,
            )],
        )
    if target != "slides":
        findings.append(EditFinding(id="target", title="Review the selected material", detail="The Agent will inspect the selected assessment material before proposing an editable patch."))
        actions.append(PlannedAction(id="review-selected", title="Improve the selected material", detail="Read the selected material and propose only the smallest useful changes.", prompt=f"Teacher request: {request}. First read the selected {target} material. Then propose only the smallest useful patches, explaining the teaching reason for each."))
        return EditPlan(request=request, target=target, summary="This is a read-only plan. Selected actions still create reviewable proposed patches only.", findings=findings, actions=actions)
    if not slides:
        return EditPlan(request=request, summary="There are no slides to inspect yet.", findings=[EditFinding(id="no-slides", title="No slides available", detail="Generate courseware before asking the Agent to plan an edit.", tone="warning")])
    animation_target = _animation_target(slides, request)
    if animation_target is not None:
        return EditPlan(
            request=request,
            summary=f"Animation proposal is limited to slide {animation_target.order}; its teaching content will not be changed.",
            findings=[EditFinding(
                id=f"animation-{animation_target.id}",
                title=f"Animate slide {animation_target.order}",
                detail="Reveal only existing content in a teaching order. The resulting patch remains reviewable before it applies.",
                tone="info",
            )],
            actions=[PlannedAction(
                id=f"animate-{animation_target.id}",
                title=f"Generate animation for slide {animation_target.order}",
                detail="Read this slide, then propose a short reveal or emphasis sequence without changing its teaching content.",
                prompt=(
                    f"First read slide {animation_target.id} ({animation_target.title}). "
                    "Propose an animation patch only: reveal or emphasize existing title, bullets, or visuals in a teaching order. "
                    "Do not change text, notes, visuals, objectives, or any other slide."
                ),
                target_id=animation_target.id,
            )],
        )
    covered = {oid for slide in slides for oid in slide.objective_ids}
    for objective in package.project.learning_objectives:
        if objective.id not in covered:
            findings.append(EditFinding(id=f"coverage-{objective.id}", title=f"{objective.id} has no slide coverage", detail=f"{objective.id} — {objective.text} has no connected slide yet.", tone="warning"))
            actions.append(PlannedAction(id=f"cover-{objective.id}", title=f"Add evidence for {objective.id}", detail="Choose an appropriate slide and connect a concrete explanation or activity to this objective.", prompt=f"First inspect the most appropriate slide for {objective.id}: {objective.text}. Then propose the smallest patch that adds a concrete explanation or activity and links that slide to the objective."))
    dense = _densest_slide(slides)
    if dense is not None:
        if len(dense.bullets) >= 4:
            findings.append(EditFinding(id=f"density-{dense.id}", title=f"Slide {dense.order} may be dense", detail=f"{dense.title} has {len(dense.bullets)} main points for {package.project.meta.audience}.", tone="info"))
        actions.append(PlannedAction(id=f"teach-{dense.id}", title=f"Strengthen the teaching on slide {dense.order}", detail="Read the slide first; improve it with a concrete scenario, prompt, or speaker-note cue instead of merely rewriting text.", prompt=f"Teacher request: {request}. First read slide {dense.id} ({dense.title}). Improve this slide for teaching with a concrete scenario, guiding question, or speaker-note cue. Propose only reviewable patches and explain how each helps learners." ,target_id=dense.id))
    if package.lesson_plan is not None:
        actions.append(PlannedAction(id="align-plan", title="Align the lesson-plan facilitation", detail="Check whether the lesson plan includes a clear teacher prompt or understanding check after this change.", prompt=f"Teacher request: {request}. Inspect the relevant lesson-plan entry and propose at most one minimal patch that keeps the teacher guidance aligned with the slide changes."))
    return EditPlan(request=request, summary=f"Checked {len(slides)} slides and {len(package.project.learning_objectives)} learning objectives. Select actions to run; every resulting change still waits for your approval.", findings=findings, actions=actions)
```

## QUESTION_SCHEMA

Source: `backend/app/services/questions.py:55`

Source-file SHA-256: `ce90140b89dc5c61fc8669178ef510cb160a1294066f0ae1144e17cb56bb9a90`

```python
QUESTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "题目唯一 id,如 q1。不要重复"},
        "type": {
            "type": "string",
            "enum": ["mcq", "short", "code", "scenario"],
            "description": (
                "题型:mcq=单选(必须有 options 和 answer),short=简答,"
                "code=写代码,scenario=情境分析"
            ),
        },
        "stem": {"type": "string", "description": "题干,一句话说清在问什么"},
        "options": {
            "type": "array",
            "description": "选项。mcq 必填,其余题型留空数组",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "选项编号,如 A / B / C / D"},
                    "text": {"type": "string", "description": "选项文字"},
                },
                "required": ["id", "text"],
            },
        },
        "answer": {
            "type": "string",
            "description": "正确答案。mcq 填选项 id(如 A);其余题型填参考答案",
        },
        "explanation": {
            "type": "string",
            "description": "解析:为什么这个答案对,其余选项错在哪",
        },
        "difficulty": {
            "type": "integer",
            "description": f"难度 {MIN_DIFFICULTY} 到 {MAX_DIFFICULTY},{MIN_DIFFICULTY} 最简单",
        },
        "objectiveIds": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "这道题考的是哪几个学习目标。**必须用给定的目标 id**"
                "(如 LO1),不要自己编号,也不要发明不存在的 id"
            ),
        },
        "points": {"type": "integer", "description": "分值,正整数"},
        "visuals": {
            "type": "array",
            "description": "题目配图。一般留空数组",
            "items": {"type": "object"},
        },
        "sourceRefs": {
            "type": "array",
            "description": (
                "题干如果来自讲义,在这里标出文件名和页码;自己编的就留空数组"
            ),
            "items": {
                "type": "object",
                "properties": {
                    "materialId": {"type": "string", "description": "讲义文件名"},
                    "page": {"type": "integer", "description": "页码,从 1 开始"},
                },
                "required": ["materialId"],
            },
        },
    },
    "required": ["id", "type", "stem"],
}
```

## QUESTION_SYSTEM_PROMPT

Source: `backend/app/services/questions.py:125`

Source-file SHA-256: `ce90140b89dc5c61fc8669178ef510cb160a1294066f0ae1144e17cb56bb9a90`

```python
QUESTION_SYSTEM_PROMPT = f"""你在为一份软件工程迷你课程出题。

只输出一个 JSON 对象,不要写解释、不要加前后缀:

{{"questions": [ ...题目... ]}}

每道题的字段定义:

{json.dumps(QUESTION_SCHEMA, ensure_ascii=False, indent=2)}

要求:

1. **每道题都要标 objectiveIds**,值必须是下面给出的目标 id(如 LO1)。
   不要自己编号,不要发明不存在的 id。
2. **mcq 必须有 3 到 4 个选项和一个正确答案。**answer 填选项 id(如 "A")。
   干扰项要像真的错法,不要一眼假。
3. **explanation 要说出为什么。**只写「选 A」不算解析 —— 要说清 A 对在哪、
   其他选项错在哪。学生答错之后主要靠这段文字。
4. **难度分布要分散。**不要所有题都是同一个难度。
5. **题干用给定的语言书写。**
6. 不要出需要查资料才能答的题 —— 学生看完这课件就该会。"""
```

## build_user_message

Source: `backend/app/services/questions.py:179`

Source-file SHA-256: `ce90140b89dc5c61fc8669178ef510cb160a1294066f0ae1144e17cb56bb9a90`

```python
def build_user_message(req: QuestionRequest) -> str:
    """写给模型的用户消息。

    单独抽成函数是为了能被测试钉住:这段文字是**模型能看到的契约**的一部分。
    原来的版本漏了语言,于是「教材语言」这个开关是假的,而且所有单元测试都是绿的。
    """
    lines = [
        f"学习者:{req.audience}",
        f"每个学习目标出 {req.count_per_objective} 道题。",
        f"**题干、选项和解析全部用 {req.language} 书写。**",
        "",
        "要覆盖的学习目标:",
    ]
    lines += [f"  {o.id}  {o.text}" for o in req.objectives]

    if req.material_context.strip():
        lines += ["", "可以参考的课件正文:", req.material_context.strip()]

    if req.source_material_ids:
        lines += ["", "仅可引用这些真实上传材料的 id:", ", ".join(req.source_material_ids)]
    else:
        lines += ["", "没有上传的参考材料。不要编造讲义、文件名或页码,解析里也不要声称出自讲义;所有题目的 sourceRefs 必须是空数组。"]

    return "\n".join(lines)
```

## GLOSSARY_ENTRY_SCHEMA

Source: `backend/app/services/glossary.py:36`

Source-file SHA-256: `c3b0464b665ff88caa057e2a49bba47d94c6d7ac6ac7fd92b6e6fef1fb0529a1`

```python
GLOSSARY_ENTRY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "term": {
            "type": "string",
            "description": "课件里出现的专业词,如「分支」「合并冲突」",
        },
        "plain": {
            "type": "string",
            "description": (
                "一句话白话解释。**不能用到别的专业术语** —— "
                "用一个读的人不认识的词去解释另一个词等于没解释"
            ),
        },
        "objectiveIds": {
            "type": "array",
            "items": {"type": "string"},
            "description": "这个词跟哪个学习目标有关。只能用给定的目标 id,没有就留空数组",
        },
    },
    "required": ["term", "plain"],
}
```

## ALT_TEXT_SCHEMA

Source: `backend/app/services/glossary.py:60`

Source-file SHA-256: `c3b0464b665ff88caa057e2a49bba47d94c6d7ac6ac7fd92b6e6fef1fb0529a1`

```python
ALT_TEXT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "assetId": {"type": "string", "description": "图上标的资产 id,原样返回"},
        "altText": {
            "type": "string",
            "description": (
                "一句话说明这张图在讲什么。**要讲清它的意思,不要罗列图中元素** —— "
                "「左边一个圆、右边一个方框」对读屏用户没有用"
            ),
        },
    },
    "required": ["assetId", "altText"],
}
```

## GLOSSARY_SYSTEM_PROMPT

Source: `backend/app/services/glossary.py:76`

Source-file SHA-256: `c3b0464b665ff88caa057e2a49bba47d94c6d7ac6ac7fd92b6e6fef1fb0529a1`

```python
GLOSSARY_SYSTEM_PROMPT = f"""你在替一份课程材料做术语表,让没背景的读者也能看懂。

只输出一个 JSON 对象,不要写解释、不要加前后缀:

{{"glossary": [ ...词条... ]}}

每个词条的字段定义:

{json.dumps(GLOSSARY_ENTRY_SCHEMA, ensure_ascii=False, indent=2)}

要求:

1. **只挑真正的专业词。**「分支」「合并冲突」要收;「代码」「文件」不用收。
2. **一句话解释完。**不要写成一段话 —— 读者是在阅读中间扫一眼。
3. **解释里不能出现别的没解释过的专业术语。**这是硬要求:
   用一个读的人不认识的词去解释另一个词,等于把他从一个坑推到另一个坑。
4. **用给定的语言书写。**
5. 最多 12 条,挑最影响理解的。"""
```

## ALT_TEXT_SYSTEM_PROMPT

Source: `backend/app/services/glossary.py:96`

Source-file SHA-256: `c3b0464b665ff88caa057e2a49bba47d94c6d7ac6ac7fd92b6e6fef1fb0529a1`

```python
ALT_TEXT_SYSTEM_PROMPT = f"""你在为课程材料里的图写替代文本,给用读屏软件的人听。

只输出一个 JSON 对象,不要写解释、不要加前后缀:

{{"descriptions": [ ... ]}}

每一项的字段定义:

{json.dumps(ALT_TEXT_SCHEMA, ensure_ascii=False, indent=2)}

要求:

1. **说这张图要表达什么**,不是图里有什么。
   反例:「左边一个圆,右边一个方框,箭头从左指向右」
   正例:「改动在分支上进行,确认后再合回主干」
2. **一句话。**读屏用户要听完才能继续,别写太长。
3. 图里的文字可以读出来,但不要逐字念 —— 挑关键的那几个。
4. **用给定的语言书写。**"""
```

## build_glossary_message

Source: `backend/app/services/glossary.py:152`

Source-file SHA-256: `c3b0464b665ff88caa057e2a49bba47d94c6d7ac6ac7fd92b6e6fef1fb0529a1`

```python
def build_glossary_message(req: GlossaryRequest) -> str:
    """写给模型的用户消息。

    单独抽成函数是为了能被测试钉住 —— 这段文字是模型能看到的契约的一部分。
    「教材语言」那个开关曾经就是在这里断掉的。
    """
    lines = [
        f"**全部用 {req.language} 书写。**",
        "",
        "课件正文:",
        req.content.strip() or "(还没有内容)",
    ]
    if req.objectives:
        lines += ["", "这门课的学习目标:"]
        lines += [f"  {o.id}  {o.text}" for o in req.objectives]
    return "\n".join(lines)
```

## build_alt_text_message

Source: `backend/app/services/glossary.py:170`

Source-file SHA-256: `c3b0464b665ff88caa057e2a49bba47d94c6d7ac6ac7fd92b6e6fef1fb0529a1`

```python
def build_alt_text_message(req: VisualRequest) -> str:
    """写给模型的用户消息,列出每一处视觉需求。"""
    lines = [f"**全部用 {req.language} 书写。**", "", "需要描述的图:"]
    for visual in req.visuals:
        spec = visual.spec or {}
        detail = spec.get("code") or spec.get("prompt") or ""
        lines.append(f"  assetId={visual.asset_id}  kind={visual.kind}  内容:{detail}")
    return "\n".join(lines)
```

## OCR_PROMPT

Source: `backend/app/llm/ocr.py:34`

Source-file SHA-256: `c20638c8426d86b9dbe00bbd4463614e275f955204a2e5a9175f26eb1c271552`

```python
OCR_PROMPT = """把这张图片里的内容**完整地转成文字**。

要求:
1. 逐字转录,不要概括、不要改写、不要补充你自己的知识。
2. 保持原有的层次:标题、列表、表格都按原结构输出。
3. 表格用 Markdown 表格;公式转成可读的纯文本形式。
4. 如果图里有流程图或结构图,在文字之后用一段话说明它表达的关系。
5. 图片模糊到无法辨认的部分,写 [无法辨认],不要猜。
6. 如果这张图里没有任何文字(纯装饰图),只回复:[无文字内容]

直接输出内容,不要加「以下是识别结果」之类的开场白。"""
```
