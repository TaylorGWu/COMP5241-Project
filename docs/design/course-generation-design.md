# AI 课程材料生成 — 设计规格

| 项 | 内容 |
| --- | --- |
| 项目 | COMP5241 — AI 辅助软件工程迷你课程平台 |
| 功能 | 教师输入需求 → agent 生成课件 / 教案 / 考题 / 模拟卷 / 视频 |
| 状态 | 设计稿,待团队评审 |
| 日期 | 2026-09-30 |
| 关联需求 | FR-05、FR-06、NFR-02、NFR-03、NFR-04、NFR-05、NFR-06 |

> 本文档是设计规格,不是实现计划。评审通过后再转成分步实施计划。

---

## 1. 背景与目标

### 1.1 项目背景

COMP5241 项目要做的是一个 AI 辅助的软件工程迷你课程平台。学生端按自身背景和目标获得个性化学习路径;教师端用 AI 生成可编辑的课程内容,审核后发布给学生。

### 1.2 本功能解决的问题

教师为同一份内容要产出课件、教案、考题、模拟卷,有时还要录讲解视频 —— 内容重复劳动,而且配图困难。现有竞品都没有把这几种产物从**同一份内容源**派生出来。

这既是痛点,也是我们刻意选择的差异化点。需要注意:竞品分析已明确把「AI 导师 / 通用聊天」列为**不做**(*Too broad, hard to validate, and not differentiated*)。本设计同样不做通用聊天机器人 —— 我们要做的是一个**工具干净、每步可审、可导出多种产物**的内容生产 agent。

### 1.3 设计目标

1. 教师用自然语言描述需求,得到**可编辑、可审核、可导出**的教学材料。
2. 同一份内容源派生多种产物,保证教案与课件不会互相矛盾。
3. AI 产出必须经教师确认才能发布。
4. AI 输出必须可校验、可重试、失败可恢复。
5. 视觉资产的成本要低 —— 且大部分视觉需求**根本不需要生成模型**。

### 1.4 与既有需求的关系

| 既有需求 | 本设计如何落实 |
| --- | --- |
| FR-05 教师可用 AI 生成结构化、可编辑的课程草稿 | 扩展为多产物生成,输出结构化 IR 而非自由文本 |
| NFR-02 后端强制角色权限 | 所有生成 / 编辑接口按 instructor 角色鉴权 |
| NFR-03 LLM key 只在后端环境变量 | `ModelRouter` 统一读环境变量,前端永不接触 key |
| NFR-04 AI 内容标记为草稿直到发布 | artifact 状态机 `draft → published`;L2 写操作也需确认 |
| NFR-05 AI 错误可恢复、不泄露密钥 | 分节失败隔离 + 结构化错误提示 + 重试 |
| NFR-06 AI 输出可预测、可校验 | Pydantic schema 校验 + 交叉引用完整性检查 |
| FR-06 教师可查看完成率与常见错误 | 第 9.1 节把该数据变成生成补救内容的触发源,形成闭环 |

---

## 2. 范围

### 2.1 本设计覆盖

| 产物 | 说明 |
| --- | --- |
| 教案 `LessonPlan` | 教学环节、时间分配、提问设计、差异化教学 |
| 课件 `SlideDeck` | 逐页内容 + 讲稿 + 视觉需求 |
| 考题 `QuestionSet` | 题库,按知识点组织 |
| 模拟卷 `ExamPaper` | 组卷结果,含卷面结构与答案卷 |
| 视频 `VideoScript` | 逐页旁白 + 时间轴,渲染成 mp4 |

支撑能力:材料上传与检索、视觉资产生成、网页预览与编辑、导出 pptx / docx / pdf / mp4。

**管理员端**(第 10 节):用户管理、课程管理、**AI 生成审计**。

需求编号、优先级与验收标准见 [../requirements.md](../requirements.md)。本文件只描述**如何实现**,不重复定义需求。

增值功能(见第 9 节):错题驱动的补救内容生成、内容溯源、教学目标覆盖率检查、术语白话化与无障碍。

### 2.2 明确不做

| 不做 | 原因 |
| --- | --- |
| 学生端对话式 AI tutor | 竞品分析已判定 out of scope,过于宽泛且无差异化 |
| 文生视频模型(Sora / 可灵 / Veo) | 贵、慢、画面会幻觉;教学视频需要清晰图表,不需要"像在上课"的画面 |
| agent 全自主发布 | 违反 NFR-04 |
| 实时多人协作编辑 | 成本高,与 MVP 无关 |
| 任意排版的 pptx 导出 | 先只支持有限固定版式,避免排版不可控 |

---

## 3. 核心概念

### 3.1 四个抽象

**Artifact(产物)** — 一种可独立预览、编辑、版本化、发布、导出的教学材料。一个项目下可以有多个产物。

**IR(中间表示)** — 描述产物内容的**纯数据**(JSON)。只描述「有什么」,不描述「长什么样」。它是唯一真相源。

**渲染器(Renderer)** — 把 IR 转成某种形态的**纯转换**:网页组件、pptx 导出器、docx 导出器、视频渲染器。输入固定是 IR,输出固定是某种形态,**内部不含 AI**。

**管道(Pipeline) vs Agent**

| | 管道 | Agent |
| --- | --- | --- |
| 谁决定步骤顺序 | 你的代码 | 模型 |
| 可控性 | 高 | 低 |
| 可测试性 | 容易 | 需要专门手段 |
| 适合 | 流程确定的阶段 | 需要临场判断的阶段 |

两者**不是二选一,是包含关系**:

```
[管道]  上传 → 解析 → 检索 → ┌────────────────────┐ → 资产 → 组装
                             │ [agent] 这一节      │
                             │  自己决定:          │
                             │   · 检索几次        │
                             │   · 要不要画图      │
                             │   · 什么时候算写完  │
                             └────────────────────┘
```

**管道是外壳,agent 是内核。**

### 3.2 为什么必须用 IR

如果让 AI 直接产出 HTML 或 pptx 文件:

1. **不一致** — 分别生成「网页版课件」和「PPT 版课件」,两次内容可能不同。
2. **改了不同步** — 教师改了网页版,导出的 pptx 还是旧的。
3. **无法测试** — 「AI 生成的 PPT 是对的」这句话无法写成断言。

用 IR 之后,AI 只产出结构化数据,渲染和导出都是**确定性转换**,可以写单元测试。

> 类比:Markdown 就是一种 IR。写一份 `.md`,可以渲染成网页、PDF、Word,不需要重写内容。这里的 `SlideDeck` / `LessonPlan` 就是我们的 "Markdown"。

### 3.3 产物依赖链

```
教案 ──→ 课件 ──→ 视频
知识点 ─→ 考题 ──→ 模拟卷
```

上面的产物是下面的原料。这意味着**不是五次独立开发**:第一条产物最贵(要从零建立管道),之后每加一种产物只需增加 IR + 渲染器 + 工具。

---

## 4. 架构

### 4.1 总览

```
        ┌───────────── Instructor (Next.js) ─────────────┐
        │  生成表单(prompt + 上传材料)   编辑聊天框 + diff  │
        └────────┬────────────────────────────┬──────────┘
                 │ POST /generation/jobs      │ POST /edit   (L2)
                 ▼                            ▼
  ┌────────────────────── FastAPI ─────────────────────────────────┐
  │  JobRunner  异步作业 + SSE 进度                                │
  │                                                                │
  │  ── L1 生成管道 ──────────────────────────────────────────     │
  │   MaterialIngestor → ArtifactPlanner → SectionAgent(×N 并发)   │
  │                                          ├ search_materials    │
  │                                          ├ make_diagram        │
  │                                          ├ request_illustration│
  │                                          └ write_section(终止) │
  │        → AssetResolver → AssetFactory(按 hash 缓存去重)        │
  │        → ArtifactStore(校验 + 落库)                            │
  │                                                                │
  │  ── L2 编辑 Agent ────────────────────────────────────────     │
  │   EditAgent → 工具集 → 暂存 patch → 讲师确认 → apply → 新版本  │
  │                                                                │
  │  Exporter(pptx / docx / pdf)   VideoRenderer(Remotion)         │
  └────────────────────────────────────────────────────────────────┘
        │                      │                    │
   PostgreSQL(+pgvector)  RenderService        ImageProvider
   IR / 版本 / jobs / chunks  Mermaid→SVG/PNG  FLUX / Gemini(兜底)
```

### 4.2 组件清单

每个单元单一职责、接口干净。

| 组件 | 输入 → 输出 | 依赖 |
| --- | --- | --- |
| `MaterialIngestor` | 上传文件 → `Material` + 带页码锚点的 chunks | PyMuPDF、python-pptx/docx |
| `Retriever` | 查询 → 相关 chunks | pgvector、embedding 模型 |
| `IntentRouter` | 自然语言 → 目标产物类型 | LLM(便宜档) |
| `ArtifactPlanner` | 生成请求 + 材料 → 该产物的专属 IR | LLM |
| `RemediationPlanner` | 错题统计 + 题目 → `RemediationKit` | LLM |
| `GlossaryBuilder` | IR → 术语白话表 | LLM |
| `AltTextGenerator` | 资产 → `altText` | 多模态 LLM |
| `SectionAgent` | 单章节 + chunks → 该章节内容 | LLM + 工具集 |
| `AssetResolver` | 一处视觉需求 → 资产方案 | 规则 + LLM |
| `AssetFactory` | 资产方案 → 字节流 + URL | RenderService、AssetLibrary、ImageProvider |
| `PaperComposer` | 题目池 + 约束 → `ExamPaper` | 纯算法,无 AI |
| `ArtifactStore` | IR 读写 / patch / 版本 | PostgreSQL JSONB |
| `EditAgent` | 自然语言 + packageId → 待确认 patch | LLM + 工具集 |
| `Exporter` | IR → pptx / docx / pdf | python-pptx/docx、LibreOffice |
| `VideoRenderer` | `VideoScript` + 资产 → mp4 | Remotion、ffmpeg |
| `JobRunner` | 作业生命周期 + SSE 事件 | PostgreSQL、ARQ |
| `SlideDeck` / `LessonPlan` / `Quiz` 组件 | IR → React 渲染 | mermaid.js、KaTeX、Shiki |
| `AuditView` / `AdminPanel` 组件 | 生成记录 / 用户 / 课程数据 → React 渲染(只读为主) | — |

---

## 5. 数据模型

### 5.1 IR 结构

一个项目下有多个产物,每个产物是一份 IR。**所有产物共享一个项目级资产池。**

```jsonc
// ── 项目级共享 ────────────────────────────────────────────
Project {
  "id": "p1",
  "meta": {
    "title": "Git for group projects",
    "subject": "software-engineering",
    "audience": "non-CS beginner",
    "level": "intro",
    "durationMin": 45,
    "language": "zh-HK"
  },
  "learningObjectives": [
    { "id": "LO1", "text": "解释分支和主干的关系" },
    { "id": "LO2", "text": "说明一次 pull request 要包含什么" }
  ],
  "glossary": [                               // 项目级:术语白话解释(第 9.4 节)
    { "term": "rebase",
      "plain": "把分支的起点挪到另一条分支的最新提交上",
      "objectiveIds": ["LO1"] }
  ]
}
```

```jsonc
// ── 教案 ──────────────────────────────────────────────────
LessonPlan {
  "artifactId": "a-lesson-1",
  "type": "lessonPlan",
  "overview": "本节课让学生先理解为什么需要分支,再动手看一次合并。",
  "keyPoints": ["分支隔离改动", "主干保持可用"],
  "difficultPoints": ["为什么不能直接在主干上改"],
  "timeline": [
    {
      "id": "T1", "phase": "导入", "minutes": 5,
      "teacherAction": "抛出冲突场景:两个人同时改同一行",
      "studentAction": "说出自己遇到过的麻烦",
      "objectiveIds": ["LO1"],
      "slideIds": ["s1"],
      "checkUnderstanding": "能否说出分支解决的问题"
    }
  ],
  "questions": [
    { "text": "你现在的团队怎么处理代码冲突?",
      "intent": "引出当前流程",
      "expectedAnswer": "直说改主干 / 不知道" }
  ],
  "boardPlan": ["主干 ──●──●──●", "分支 ──●──● ⤴"],
  "homework": ["在自己的分支上改一行并提交"],
  "differentiation": {
    "beginner": "先只讲分支隔离,不引入 rebase",
    "advanced": "补充 rebase 与 merge 的取舍"
  },
  "sourceRefs": [{ "materialId": "m1", "page": 12 }]
}
```

```jsonc
// ── 课件 ──────────────────────────────────────────────────
SlideDeck {
  "artifactId": "a-slide-1",
  "type": "slideDeck",
  "slides": [
    {
      "id": "s3", "order": 3,
      "layout": "diagram",          // title | bullets | diagram | twoCol | code | quiz
      "title": "分支与合并",
      "bullets": ["主干始终保持可用", "分支隔离新功能"],
      "speakerNotes": "先问学生:如果两个人在同一份代码上改会怎样?",
      "visuals": [
        { "id": "v1", "kind": "diagram",
          "spec": { "engine": "mermaid", "code": "graph LR; A[主干]-->B[分支]" },
          "assetId": "as-7" }
      ],
      "objectiveIds": ["LO1"],
      "sourceRefs": [{ "materialId": "m1", "page": 14 }],
      "origin": "sourced"        // sourced | ai —— 无来源时必须显式标 ai(第 9.2 节)
    }
  ]
}
```

```jsonc
// ── 考题与模拟卷共用 ──────────────────────────────────────
Question {
  "id": "q1",
  "type": "mcq",                  // mcq | short | code | scenario
  "stem": "以下哪种做法最容易导致主干不可用?",
  "options": [
    { "id": "A", "text": "在分支上开发后合并" },
    { "id": "B", "text": "直接在主干上改并推送" }
  ],
  "answer": "B",
  "explanation": "主干是所有人共同的基础,直接改会立刻影响他人。",
  "difficulty": 2,                // 1–5
  "objectiveIds": ["LO1"],
  "points": 3,
  "visuals": [],                  // 考题同样可以配图
  "sourceRefs": []
}
```

```jsonc
// ── 模拟卷 = 组卷结果 ────────────────────────────────────
ExamPaper {
  "artifactId": "a-paper-1",
  "type": "examPaper",
  "constraints": { "totalPoints": 100, "durationMin": 90,
                   "coverage": ["LO1", "LO2"], "difficulty": { "easy": 0.3, "medium": 0.5, "hard": 0.2 } },
  "sections": [
    { "title": "一、选择题", "rule": "10 题 × 3 分",
      "questionIds": ["q1", "q4", "q9"] }
  ],
  "answerKey": true,
  "sourceRefs": []
}
```

```jsonc
// ── 视频 ──────────────────────────────────────────────────
VideoScript {
  "artifactId": "a-video-1",
  "type": "videoScript",
  "scenes": [
    { "id": "sc1",
      "slideRef": "s3",              // 引用课件页,不复制内容
      "narration": "分支让我们把改动隔离起来,不影响别人。",
      "durationSec": 12,
      "assetIds": ["as-7"] }
  ],
  "voice": { "provider": "edge", "voiceId": "zh-CN-XiaoxiaoNeural", "speed": 1.0 },
  "totalDurationSec": 0             // 由 TTS 真实音频回填
}
```

```jsonc
// ── 补救包(第 9.1 节)────────────────────────────────────
RemediationKit {
  "artifactId": "a-rem-1",
  "type": "remediationKit",
  "trigger": { "objectiveId": "LO2", "questionId": "q4", "wrongRate": 0.62 },
  "hypothesis": "学生可能把「分支」和「标签」混为一谈",
  "summary": "分支是一条独立的改动线;标签只是一个指向提交的指针。",
  "visuals": [ { "kind": "diagram", "spec": { "engine": "mermaid", "code": "..." },
                 "assetId": "as-9" } ],
  "checkQuestion": { "id": "q-rem-1", "type": "mcq", "stem": "...", "answer": "A" }
}
```

**交叉引用是保证一致性的机制**:`objectiveIds`、`slideIds`、`assetId`、`slideRef` 让教案、课件、考题、视频互相对齐,改一处全体同步。

### 5.2 资产池

```jsonc
Asset {
  "id": "as-7",
  "kind": "diagram",              // diagram | chart | icon | illustration | audio
  "status": "ready",              // pending | ready | failed
  "url": "/assets/as-7.svg",
  "hash": "sha256:...",           // 用于去重,同一张图全项目复用
  "provider": "kroki",            // kroki | mermaid-cli | lucide | undraw | flux | edge-tts
  "meta": { "format": "svg" },
  "spec": { "engine": "mermaid", "code": "graph LR; ..." },
  "altText": "主干与分支的示意图:分支从主干某点分出后又合并回去"
}
```

资产是**项目级**的:课件里的 Git 分支图,考题和视频可以直接复用,零成本。

### 5.3 数据库表

```text
projects(id, course_id, meta jsonb, objectives jsonb, created_by, created_at)

artifacts(id, project_id, type, status, doc jsonb, version, created_at, updated_at)
    -- status: draft | published | archived
    -- 每个产物独立版本化与发布(教案可以先发布,视频还在渲染)

artifact_versions(id, artifact_id, version, doc jsonb, diff jsonb, reason, created_at)
    -- L2 每次改动留 diff 和理由,可回滚;也是 AI Fluency 的证据

assets(id, project_id, hash, kind, provider, url, status, spec jsonb, meta jsonb)
    -- UNIQUE(project_id, hash) 实现去重

materials(id, project_id, filename, mime, status, page_count, storage_key)
material_chunks(id, material_id, page, text, embedding vector(1024))

generation_jobs(id, project_id, artifact_id, type, status, phase, progress, error, trace_id)
edit_sessions(id, artifact_id, messages jsonb, created_at)
patches(id, artifact_id, patch jsonb, diff jsonb, status, created_at)
    -- status: proposed | applied | rejected   ← 人在环的关键表
```

### 5.4 ERD

```text
profiles ──┬──< enrollments >──── courses ──┬──< materials ──< material_chunks
           │                                │
           ├──< activity_attempts >── activities
           │
           └──< generation_jobs >───────────┐
                                            ▼
courses ──< projects ──┬──< artifacts ──┬──< artifact_versions
                       │                ├──< patches        (status: proposed|applied|rejected)
                       │                └──< edit_sessions
                       └──< assets       (UNIQUE(project_id, hash))
```

| 关系 | 基数 | 要点 |
| --- | --- | --- |
| `projects → artifacts` | 1:N | 一个项目下多种产物,各自独立版本化与发布 |
| `artifacts → artifact_versions` | 1:N | 每次改动一条,含 `diff` 与 `reason` |
| `artifacts → patches` | 1:N | `proposed` 的改动;**只有 `apply` 才写回 `artifacts.doc`** |
| `projects → assets` | 1:N | **资产池是项目级**,跨产物复用,按 `hash` 去重 |
| `courses → materials` | 1:N | 上传的讲义 |
| `materials → material_chunks` | 1:N | 分块 + 向量,供检索与来源标注 |
| `profiles → generation_jobs` | 1:N | 审计入口:谁发起了哪次生成 |

**迁移:** Alembic 管理;`vector` 扩展与 `resource` 表(`material_chunks.embedding`)用一条初始迁移建立。`assets` 的唯一约束 `UNIQUE(project_id, hash)` 在首个迁移中建立。

### 5.5 权限矩阵

完整矩阵见 [../requirements.md](../requirements.md) 第 1 节。**实现层只有两条规则:**

1. **所有接口在服务端校验角色**,前端隐藏不作为安全边界(NFR-02)。
2. **未发布产物(`status=draft`)对学生接口一律不可见**(NFR-04),包括搜索、目录与直接按 ID 访问。

---

## 6. L1 生成流水线

### 6.1 阶段与进度

```
phase 1  摄取材料(解析 + 分块 + 向量化)      0–10%
phase 2  检索 + 规划大纲 + 解析意图           10–25%
phase 3  分节生成(并发 3)                    25–75%   ← SectionAgent
phase 4  视觉需求判定(AssetResolver)         75–85%
phase 5  资产生成(并发,命中缓存则跳过)      85–95%
phase 6  组装 + IR 校验                       95–100%
```

进度通过 SSE 推送(端点见 §13.4)。**进度界面本身就是很好的演示素材** ——
教师看得见 AI 在干什么,才愿意把备课交出去。

#### 6.1.1 进度事件契约

**进度事件是结构化数据,不是给人读的字符串。**

早期实现把说明文字压进一个 `detail` 字符串,例如
`"2/3 节:合并与冲突(工具调用 4 次,terminal)"`。前端若要按节分组、要数
「现在写到第几张」,就只能去正则拆这句话。措辞一改,前端静默失效 ——
**没有任何测试会变红**,因为没有契约可断言。

因此事件改为携带独立字段:

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `phase` | str | 六个阶段名之一 |
| `percent` | int | 0–100,**单调不减** |
| `kind` | enum | `phase` / `section` / `turn` / `tool` / `slide` |
| `detail` | str | 给人看的补充说明。**允许措辞变化,不得被程序解析** |
| `sectionIndex` | int \| null | 第几节(从 0 起) |
| `sectionTitle` | str \| null | 节标题,供 UI 直接显示,不必回查大纲 |
| `slideCount` | int | **累计**已写出的幻灯片张数 |
| `tool` | str \| null | 本次触发的工具名 |
| `status` | str | `section`:started / written / failed;`tool`:running / error |

两条硬约束:

1. **`percent` 单调不减。**前端据此画进度条,不必自己防回退。
2. **`detail` 不参与程序判断。**凡是要让 UI 分支的信息,都必须有自己的字段。

`kind` 是**传输层之内**的子类型。传输层自身的事件名(`progress` / `result` /
`error` / `done`)是另一个层级,见 §13.4 —— 两者不得混用,否则「一次失败的生成」
既可以表示成 `event: error` 又可以表示成 `kind="error"`,前端要写两套分支。

`sectionTitle` 冗余携带标题是有意的:大纲在阶段 2 才产生,而事件流是唯一
按时间顺序穿过全流程的东西。UI 应当**只依赖事件流**就能画出完整界面。

#### 6.1.2 动作流

进度界面上给教师看的过程,只有**一个**信息源:**每次工具调用**。

| | 动作流 |
| --- | --- |
| 来源 | 本地 —— 我们自己执行工具,顺手记一笔 |
| 依赖思考模式 | 否 |
| 无 API key 时可用 | 是(`ScriptedChatClient` 一样能驱动) |
| 成本 | 零 |
| 内容 | 「第 2 节 · 第 1 轮 · search_materials → 检索「分支合并」」 |

由 `run_agent` 的 `on_step` 回调产生,在三个时点触发:

    每轮开始              → 现在是第几轮
    每个工具执行前 / 后   → 在调什么、调完拿到什么
    循环终止              → terminal / no_tool_calls / max_turns / error

因为信息源全在本地,这一层**不依赖思考模式,也不依赖真模型**,
所以「看得见过程」这件事整体可以离线 TDD。

阶段 3 的进度插值也因此得以细化:原实现只在**某节整节跑完**时进一格,
一节内部二十秒毫无反馈。改为按「各节进度之和」插值 ——
不能简单写成「已完成节数 + 本节轮次占比」,那样三节并发时后报的会更小,
进度条会倒退(契约要求单调不减)。

`write_section` 落地时额外发一条 `kind="slide"` 事件,带上本节写出的页标题,
并更新 `slideCount` —— 这是「现在写到第几张 ppt」的数据来源。

**曾经还有第二条流:思考流。**把模型的思维链逐字显示在进度界面里。
后来整条撤掉了,原因见 §11.7 —— 界面不好读,而且默认路径上占掉约 35% 的帧
却没人看。设计文档留这段是为了记下**为什么不做**,免得下次有人又想加。

### 6.2 SectionAgent

每个章节一次调用,工具少而正交:

| 工具 | 作用 |
| --- | --- |
| `search_materials(query)` | 检索教师上传的讲义,返回带页码的片段 |
| `make_diagram(mermaid_code)` | 渲染 Mermaid,返回 `assetId` |
| `request_illustration(prompt)` | 请求一张插画(兜底路径) |
| `write_plan_entry(entry)` | 写入教案的时间线条目 |
| `write_section(slides)` | **写入本节幻灯片 —— 终止工具** |

**关键设计:`write_section` 是终止工具。** 调用它即结束循环。这比「让模型自己觉得写完了」可靠得多,是防止 agent 死循环的标准做法。

轮数上限 `max_turns = 6`,超限则强制调用终止工具,并把 trace 记录下来供事后检查。

### 6.3 Agent 的两种形态

| | 手写循环 | Pydantic AI |
| --- | --- | --- |
| 代码量 | ~50 行 | 声明式 |
| 结构化输出 | 自己解析 + 重试 | `result_type` 自动校验 |
| 可测试性 | 自己造 fixture | `FunctionModel` 脚本化模型回复 |
| 推荐 | **先写一遍,理解机制** | **再用它做正式实现** |

先手写一遍不是浪费时间 —— 是为了在答辩时能解释框架帮你做了什么。

### 6.4 IR 校验规则

生成完成后必须跑一遍**交叉引用完整性检查**,任一条不通过就不允许标记为可用:

| 规则 | 目的 |
| --- | --- |
| 每个 `LO` 至少被一页 slide 引用 | 教学目标不能没被覆盖 |
| `timeline` 里每个 `slideId` 必须存在 | 教案不能引用不存在的页 |
| `minutes` 总和 ≈ `durationMin`(±10%) | 课时不能超 |
| 每个 `assetId` 能解析到实际资产 | 不能有断链 |
| `ExamPaper` 覆盖 `constraints.coverage` 全部知识点 | 组卷不能漏考点 |
| `ExamPaper` 总分 == `constraints.totalPoints` | 分值不能算错 |
| `origin == "sourced"` 的内容必须有非空 `sourceRefs` | 不能声称有来源却拿不出来 |

校验失败 → **保存部分草稿** + 明确报错,**不是整包丢弃**。

---

## 7. L2 编辑 Agent

### 7.1 工具集

| 工具 | 作用 |
| --- | --- |
| `read_package()` / `read_slide(id)` | 读取当前 IR |
| `patch_slide(id, patch)` | 提出对某页的修改 |
| `patch_plan(section, patch)` | 提出对教案的修改 |
| `regenerate_slide(id, instruction)` | 重生成某一页 |
| `estimate_timing()` | 检查总时长是否超 |
| `check_coverage()` | 检查目标覆盖 |

### 7.2 关键安全设计:写操作只暂存,不落库

```
教师:"第 3 页太难了,给非 CS 背景的学生降一档"
  → agent 调 read_slide("s3")
  → agent 调 patch_slide("s3", {...})     ← 只写入 patches 表,status=proposed
  → 前端展示 diff,教师点「确认」
  → POST /api/patches/{id}/apply          ← 只有这一步才改 artifacts
```

**这条让 NFR-04 在每次编辑上都成立,而不只是在发布时成立。** 代价是前端必须实现 diff 预览组件,但这个组件本身就是很好的演示点。

`max_turns = 8`。超出则停止并返回已有进展。

### 7.3 版本与回滚

每次 `apply` 都写一条 `artifact_versions`(含 `diff` 和 `reason`)。教师可以回滚到任意版本。这份记录同时是报告里 AI Fluency「Discernment」的实拍证据。

---

## 8. 视觉资产策略

### 8.1 核心原则

**能用确定性资源解决的,就不要用生成模型。AI 生图是兜底,不是主力。**

### 8.2 AssetResolver 决策树

```
一处视觉需求
  ├─ 是流程 / 结构 / 关系?   → Mermaid 代码 → RenderService 渲染     成本 ≈ 0
  ├─ 是数据?                 → ECharts 配置 → 渲染                   成本 ≈ 0
  ├─ 是概念图标?             → 图标库(Lucide)                      成本 0
  ├─ 是通用场景插画?         → 插画库检索(unDraw / Storyset)        成本 0
  └─ 以上都匹配不上?         → 才调 ImageProvider(FLUX 等)          成本 低
```

### 8.3 为什么不优先用 AI 生图

| | 现成资产 | AI 生成 |
| --- | --- | --- |
| 成本 | 0 | 每张都花钱 |
| 速度 | 立即 | 2–10 秒/张 |
| **风格一致性** | ✅ 同一套库 = 统一视觉语言 | ❌ 20 页生成 20 种画风 |
| 版权 | 明确(需检查各库 license) | 有争议 |
| 可复现 | ✅ | ❌ |
| 乱码 / 畸形 | 不会有 | 经常有 |

「风格一致性」对教学材料尤其重要:一份课件里 20 张风格漂移的 AI 插画看起来像拼凑的,这是**可信度问题**,不只是美观问题。

**判断(非测量值):教案与课件中的绝大多数视觉需求属于「结构」「数据」「图标」三类,都能由确定性资源解决。**
因此在第一版不接生图模型是可行的。具体比例需要在实际生成若干节课后统计,**本文件不给出估算数字**。

### 8.4 为什么带文字的示意图不能用文生图

扩散模型画带中文标注的图**必然乱码**。而教案里的「讲解图片」绝大多数正是这类(分支图、架构图、流程图)。所以这些走 Mermaid,渲染出来清晰、可编辑、支持中文、零成本。

真正能画好图中文字的模型(Nano Banana / Ideogram)属于特例,不该进主流程。

### 8.5 质量闸门

渲染出的图可以**回喂给多模态模型**做自检:「这张图有没有文字乱码、箭头指错、标签重叠?」不合格就回喂错误让 agent 重画,两次失败则降级为纯文字版式。

### 8.6 缓存与去重

资产按 `hash` 去重并存在项目级资产池。`assets` 表加 `UNIQUE(project_id, hash)`。

---

## 9. 增值功能(差异化)

以下四项是在竞品能力矩阵中确认为**空白**、且与我们的差异化方向一致的功能。它们的共同点是:**绝大部分复用已有设计,不是新增子系统**。

| # | 功能 | 类型 | 关联假设 / 需求 |
| --- | --- | --- | --- |
| 1 | 错题驱动的补救内容生成 | 新增(轻量) | H-04 / FR-06 |
| 2 | 内容溯源 | 提升(`sourceRefs` 已有) | H-03 |
| 3 | 教学目标覆盖率检查 | 提升(校验已有) | H-01 / FR-05 |
| 4 | 术语白话化与无障碍 | 提升(多模态能力已有) | H-01 |

**竞品分析结论**:现有平台要么做内容生成,要么做学习分析,**没有一家把两者连成闭环**。第 1 项正是这个空白。

### 9.1 错题驱动的补救内容生成

**做什么**:教师在分析面板看到「第 4 题 62% 的学生答错」,点一个按钮,agent 生成一份 5 分钟补救材料 —— 一页小结 + 一张示意图 + 一道检查题。

**为什么**:这是 H-04(*instructors need actionable participation information, not a dashboard full of vanity metrics*)的直接答案。**竞品给图表,我们给动作。**

**触发源不同于主流程**:主流程由 prompt 触发,本功能由**分析数据**触发。这是复用整条生成管道的第二个入口。

**新增单元**:`RemediationPlanner`(错题统计 + 题目 → `RemediationKit`)。

**要求**:

- `hypothesis`(归因)必须与 `summary`(讲解)分开呈现。归因是**假设**,不是结论,教师必须知道这是推测。
- 统计数据来自 `question_stats` 聚合,不新建数据源。
- 与主流程一致:产出是 `draft`,需教师确认才发布。

### 9.2 内容溯源

**做什么**:每页课件、每道题旁边显示来源(如「来源:讲义 p.14」),点击跳到原文;没有来源的内容标为 **AI 补充**,提示教师重点审核。

**为什么**:直接打中 H-03。教师看到「这句话来自我第 14 页」和看到「这是 AI 编的」,信任度完全不同。竞品做的是**文档问答**,不是**逐条溯源**。

**IR 变化**:`sourceRefs` 已存在,新增一个显式标记 `origin`(`sourced` | `ai`)。

**要求**:

- `origin == "sourced"` 时 `sourceRefs` 不能为空 —— 由 6.4 的校验强制。
- UI 上 `origin: "ai"` 的内容必须有**可见标记**,不能只放在 tooltip 里。

### 9.3 教学目标覆盖率检查

**做什么**:生成后自动检查每个学习目标是否至少被一页课件和一道题覆盖;缺口在 UI 上标出,并提供「补生成」按钮。

**为什么**:竞品都在「生成内容」,没有一家验证**内容是否真的教到了该教的**。

**与 6.4 的关系**:校验规则已经存在,本项只是把它**从内部校验提升为教师可见的功能**。

**接口**:

```
GET  /api/artifacts/{id}/coverage        -> { covered: [...], gaps: [{ objectiveId, missing }] }
POST /api/artifacts/{id}/coverage/fill   { objectiveId } -> 生成缺失内容(走同一套生成作业)
```

**要求**:

- 覆盖率不足**不阻止发布**,只做提示。教师有权判断某个目标本节不覆盖。
- 「补生成」同样产出 patch,需教师确认后才落库(与 7.2 一致)。

### 9.4 术语白话化与无障碍

**做什么**:

1. 扫描产物中的技术术语,为每个生成一句话白话解释,学生悬停可见。
2. 为所有资产(`Asset`)生成 `altText`。

**为什么**:服务项目大纲里明确的 non-CS 受众。竞品矩阵中**没有任何一家提到无障碍**。且因为多模态模型能读图,`altText` 成本接近零。

**新增单元**:`GlossaryBuilder`(IR → `glossary`)、`AltTextGenerator`(资产 → `altText`)。

**要求**:

- 术语解释必须**一句话**,且不引入新的未解释术语。
- `altText` 描述**这张图在讲什么**,不是罗列图里有什么元素。

---

## 10. 管理员端

对应 FR-18 / FR-19 / FR-20。原需求文档里管理员只出现在角色卡,没有任何功能需求;本节补齐。

### 10.1 三个模块

| 模块 | 内容 | 数据来源 |
| --- | --- | --- |
| 用户管理 | 用户列表、角色分配、启用 / 禁用 | `profiles` |
| 课程管理 | 全部课程列表、发布状态、下架 / 归档 | `courses` / `artifacts` |
| **AI 生成审计** | 谁在何时生成什么、用哪个模型、审核与否、改了什么 | `generation_jobs` / `artifact_versions` / `patches` |

### 10.2 为什么生成审计值得做

`REQUIREMENTS_DESK_RESEARCH.md` 给管理员角色卡写的需求是 **"Roles, audit-friendly generation records, validation, human review, and safe error messages"**。而本项目的核心流程正是「AI 生成 → 人工审核 → 发布」——**审计记录是这条流程的副产物,不是额外要建的数据。**

| 审计页显示 | 来自 | 已有字段 |
| --- | --- | --- |
| 谁、何时、生成哪种产物 | `generation_jobs` | `project_id` / `type` / `created_at` |
| 用了哪个模型 | `generation_jobs` | `trace_id` → `ModelRouter` 逻辑标识 |
| 成功 / 失败 / 失败原因 | `generation_jobs` | `status` / `phase` / `error` |
| 每次改了什么、为何接受 | `artifact_versions` | `diff` / `reason` |
| 哪些改动被确认、哪些被驳回 | `patches` | `status` |

**结论:这一页几乎零额外数据成本**,但它把 AI Fluency 的 **Diligence(为发布内容负责)** 变成了看得见的东西。这是竞争对手矩阵里的空白项。

### 10.3 要求

- 审计页**只读**。管理员不能修改生成记录 —— 否则审计失去意义。
- **不显示任何密钥**。模型只显示逻辑标识(如 `verify_answer` / `section`),不显示 key、端点凭据或原始请求体。
- 下架课程是**软删除**(`status=archived`),不物理删除,以保留审计链。
- 管理员拥有全局分析视图,但**不能编辑他人课程内容** —— 内容责任归属作者。

---

## 11. 模型选型

### 11.1 原则

**不是选一个最火的模型,而是按任务配模型,并且全部可替换。** 所有模型调用必须经过 `ModelRouter`,禁止在业务代码里硬编码模型名。

### 11.2 按功能的能力清单

标记:**🧠 需要模型** / **🔧 纯工具**

| 功能 | 用什么 | 作用 |
| --- | --- | --- |
| 文件上传 | 🔧 S3 兼容对象存储 | 存原始材料 |
| PDF 抽文字 | 🔧 PyMuPDF | 文本 + 图片抽取,保留页码 |
| PDF 复杂版面 | 🔧 Marker / MinerU | 表格 / 双栏 / 公式还原成 Markdown |
| PPTX / DOCX 解析 | 🔧 python-pptx / python-docx | 读文字、备注、内嵌图 |
| 图片理解 / OCR | 🧠 **DeepSeek Flash** | 看懂讲义里的图、截图、图表,识别图中文字 |
| 分块 | 🔧 自写 chunker | 按语义 + 页码切分 |
| 向量化 | 🧠 BGE-M3 / Qwen3-Embedding | 文本 → 向量 |
| 向量检索 | 🔧 pgvector | 在 PostgreSQL 内做相似检索 |
| 重排序(可选) | 🧠 BGE-Reranker | 提升检索相关性 |
| 意图路由 | 🧠 DeepSeek(便宜档) | 判断教师要做哪种产物 |
| 大纲规划 | 🧠 DeepSeek | 章节骨架 + 目标 + 时长 |
| 教案生成 | 🧠 DeepSeek | 环节、时间线、提问、差异化 |
| 课件内容生成 | 🧠 DeepSeek(分节并发) | 每页标题 / 要点 / 讲稿 |
| 出题 | 🧠 DeepSeek | 题干、选项、解析 |
| **答案交叉验证** | 🧠 **换厂商模型**(Gemini Flash / Qwen) | 独立复核答案 |
| 组卷 | 🔧 自写 PaperComposer | 约束求解,无 AI |
| 对话式编辑 | 🧠 DeepSeek + function calling | 自然语言 → 工具调用 |
| 视觉需求决策 | 🔧 AssetResolver(规则 + 🧠 LLM) | 判断该用哪种图 |
| 示意图代码生成 | 🧠 DeepSeek | 生成 Mermaid 源码 |
| **示意图渲染** | 🔧 **Mermaid + Kroki / mermaid-cli** | 代码 → SVG/PNG,无模型 |
| 数据图表 | 🔧 ECharts / Recharts | 配置即出图 |
| 图标 | 🔧 Lucide / Iconify | 免费 SVG |
| 通用插画 | 🔧 unDraw / Storyset | 免费矢量 |
| 概念插画(兜底) | 🧠 FLUX.1-schnell / Nano Banana | 仅当现成库表达不出来 |
| 示意图质检 | 🧠 多模态模型 | 检查渲染结果 |
| 资产去重 | 🔧 SHA-256 + 资产池 | 全项目复用 |
| 图片处理 | 🔧 Pillow | 转换、压缩 |
| 网页渲染 | 🔧 React + Tailwind + mermaid.js + KaTeX + Shiki | 预览 |
| PPTX 导出 | 🔧 python-pptx | IR → .pptx |
| DOCX 导出 | 🔧 python-docx | IR → .docx |
| PDF 导出 | 🔧 LibreOffice / WeasyPrint | docx → pdf |
| 旁白合成 | 🧠 Edge-TTS(免费)/ MiniMax / 火山豆包 | 讲稿 → 语音 |
| 时长测量 | 🔧 ffprobe | 校准时间轴 |
| 视频渲染 | 🔧 Remotion + ffmpeg | 复用 React 组件渲 mp4 |
| 结构化校验 | 🔧 Pydantic | 强制输出符合 schema |
| 作业编排 | 🔧 ARQ(Redis) | 异步长任务 |
| 进度推送 | 🔧 SSE | 实时进度 |
| 重试降级 | 🔧 tenacity | 限流 / 超时重试 |
| 追踪 | 🔧 Langfuse | 每次运行的完整 trace |

### 11.3 为什么验证必须换厂商

如果生成和验证都用 DeepSeek,两者会**犯同一个错** —— 同一个模型的偏差是相关的,自己检查自己基本无效。出题这块尤其重要:模型出的题**答案会错**,而教师一眼就能看出来。

这是整个系统里少数几个**能明显提升质量**的杠杆之一。

### 11.4 ModelRouter 配置

```yaml
# config/models.yaml —— 换模型只改这里,不动业务代码
tasks:
  intent:        { provider: deepseek,    tier: cheap,   temperature: 0.0 }
  outline:       { provider: deepseek,    tier: default, temperature: 0.3 }
  section:       { provider: deepseek,    tier: default, temperature: 0.7 }
  question:      { provider: deepseek,    tier: default, temperature: 0.4 }
  verify_answer: { provider: gemini,      tier: cheap,   temperature: 0.0 }   # 故意换厂商
  mermaid:       { provider: deepseek,    tier: cheap,   temperature: 0.0 }
  vision:        { provider: deepseek,    tier: flash }                       # 多模态
  embed:         { provider: siliconflow, model: bge-m3 }
  image:         { provider: siliconflow, model: flux-1-schnell }             # 兜底,可选
  tts:           { provider: edge,        voice: zh-CN-XiaoxiaoNeural }
```

三个好处:①换模型不动业务代码 ②便宜任务自动降级省钱 ③**这张表本身就是报告里的架构图**。

### 11.5 说明

- DeepSeek Flash 是**多模态**的,支持图片输入(JPEG / PNG / GIF / WebP),可用于读讲义图、OCR、示意图质检。**但它不能生成图片** —— 「理解」和「生成」是两件事。
- DeepSeek 是否提供 embedding 端点**尚未确认**;落地前用 `GET https://api.deepseek.com/models` 核对。若无则用 BGE-M3。
- 具体模型名与价格会变,以各自官网为准。

### 11.6 思考模式:默认关闭

DeepSeek 服务端**默认开启**思考模式。这件事很隐蔽,踩过两次:

1. `demo_deepseek.py` 一直漏传开关,始终跑在思考模式下而无人察觉。
2. 思考模式下 `temperature` 被**静默忽略** —— `config/models.yaml` 里配的温度全部失效。

所以开关必须显式传,且由 `build_deepseek_client()` 统一构造,
不允许各入口自己拼 `extra_body`。

**默认关闭**(`settings.deepseek_thinking`),实测同一次 L1 生成:

| | 请求数 | 输入 token | 输出 token | 估算成本 |
| --- | --- | --- | --- | --- |
| 思考开启 | 19 | 58,953 | 18,964 | ≈ 0.135 元 |
| 思考关闭 | 22 | 51,790 | 6,857 | ≈ 0.079 元 |

输出 token 降到 36%,成本降 41%。备课是高频动作,默认必须是便宜的这条。

三种状态的语义必须保持区分(见 `OpenAICompatClient.__init__` 的文档字符串):

    None  → 不发这个参数,用服务端默认(即开启)
    False → 显式关闭,此时 temperature 才会生效
    True  → 显式开启,并按 reasoning_effort 控制强度

**一个容易致命的细节:带 `tools` 的请求,后续每一轮都必须完整回传
`reasoning_content`,即使那一轮没有调用工具。**漏了直接 HTTP 400。
不带 `tools` 时传了会被忽略,所以一律带上更安全。

注意这条与「默认关闭」不矛盾:**默认关闭不等于可以删掉回传逻辑**。
把 `deepseek_thinking` 打开只是改一行 YAML 的事,而那一刻
`agent.py` 里的回传就是唯一挡住 400 的东西。`test_agent.py` 里有两条测试盯着它。

---

### 11.7 为什么不做模型层流式

DeepSeek 支持 `stream=True`,逐块返回 `delta.reasoning_content`(思维链)
与 `delta.content`。用当前 key 实测过:一次 75 个 chunk 中 51 个是
`reasoning_content`,22 个是 `content`。

**本项目不用它。**曾经用过,后来整条删掉了。经过:

1. 一开始做「让教师看见 AI 在想什么」,顺理成章地接了模型层流式:
   `ChatClient.complete()` 加 `on_delta` 回调,真模型走 `stream=True`,
   假模型把整条回复回放成假分片(`replay_deltas`),好让这条路径离线也能验收。
2. 界面做出来之后发现那面滚动的思维链墙**不好读** —— 三节是并发的,
   三股独白交错着推过来。教师看的是「讲到第几页了」,不是模型的内心戏。
3. 撤掉界面 → `on_delta` 没有调用方了 → 模型层的流式分支、
   `ChatDelta`、`replay_deltas`、`kind="reasoning"` 全成了死代码,于是整条删除。

**进度上的实时感不来自模型层流式,而是来自 SSE 传输层:**
`StreamingResponse` 把 `run_agent` 的 `on_step` 事件边跑边推出去(§6.1.2、§13.4)。
首字节实测 **0.04 秒**,整次生成 43 帧、约 3 秒。

**为什么值得把这段写下来:**模型层流式看起来是「实时进度」的显然实现,
下一个想加进度的人很可能第一反应就是去开 `stream=True`。
它解决的是「模型一个字一个字往外吐」,而我们要的是
「**这件事做到哪一步了**」—— 前者是 token 级,后者是步骤级,两回事。

顺带一提:那条流式分支还带着 35% 的额外帧(实测 67 帧里 24 帧是思维链),
而且分片重组是实打实的复杂度(按 index 拼 `arguments`、
把分片累积回完整 `reasoning_content` 才能回传)。删掉它同时拿回了简洁和带宽。

---

---

## 12. 渲染与导出

### 12.1 网页渲染

```
<SlideDeck artifact={...} />   → 16:9 幻灯片,含 Mermaid / KaTeX / Shiki
<LessonPlan artifact={...} />  → 时间线表格
<Quiz artifact={...} />        → 题目与解析
```

### 12.2 导出

| 目标 | 方式 | 注意 |
| --- | --- | --- |
| pptx | python-pptx | **图必须用后端渲染的 PNG**,不能依赖前端 |
| docx | python-docx | 教案、考卷 |
| pdf | LibreOffice 转换 | — |
| mp4 | Remotion | 复用 `<SlideDeck>` 组件 |

**必须提前写进需求的预期**:导出是「内容等效」,不是「像素级还原」网页。这个预期不写清楚,后面会被当成 bug。

### 12.3 视频方案

```
SlideDeck IR
  → VideoScript(逐页把 speakerNotes 改写成旁白 + 估时长)
  → TTS 逐页合成音频(拿到真实时长,回填 durationSec)
  → Remotion 用 <SlideDeck> 组件 + 音轨 + 时间轴 → mp4
```

**为什么这是对的**:Remotion 能用 React 组件渲视频,所以同一套 `<SlideDeck>` 组件同时服务网页预览和视频渲染。改课件第 3 页,视频旁白跟着变。

**为什么不用文生视频模型**:贵、慢、画面会幻觉,而教学视频需要的是清晰的图表和文字,不是「看起来像在上课」的画面。这正是项目大纲里写的 *AI-narrated slides*。

### 12.4 导出模板

第一版只支持有限固定版式(`title` / `bullets` / `diagram` / `twoCol` / `code` / `quiz`),不追求任意排版。pptx 占位符 + 自适应文本框极易溢出。

---

## 13. API 契约

对应 `PROJECT_PLAN.md` §6 的 "Define API contracts and error responses"。所有接口**在服务端强制 RBAC**。

### 13.1 错误响应统一结构

```jsonc
{
  "error": {
    "code": "GENERATION_INVALID_OUTPUT",   // 稳定可判定,供前端分支
    "message": "AI 输出不符合结构,自动重试 1 次后仍失败",  // 面向用户,不泄露内部细节
    "retryable": true,                     // 决定前端是否显示重试按钮
    "detail": { "sectionId": "sec-3" }     // 可选,便于定位
  }
}
```

约定:`code` 永不复用;`message` 不含密钥、端点或堆栈;`retryable=false` 时前端只显示编辑入口。

### 13.2 端点

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/materials` | 教师 | 上传材料 → 解析 + 分块 + 向量化 |
| POST | `/api/generation/jobs` | 教师 | 创建生成作业 → `202 { job_id }` |
| GET | `/api/generation/jobs/{id}` | 教师 | 作业状态快照(用于轮询兜底) |
| GET | `/api/generation/jobs/{id}/events` | 教师 | **SSE**:阶段 + 进度 |
| POST | `/api/generation/jobs/{id}/cancel` | 教师 | 取消作业 |
| GET | `/api/artifacts/{id}` | 教师 / 管理员 | 读取 IR(含 `origin` 与 `sourceRefs`) |
| PATCH | `/api/artifacts/{id}` | 教师 | 人工直接编辑 |
| POST | `/api/artifacts/{id}/edit` | 教师 | **L2 对话式编辑** → 返回 `proposed` patches |
| POST | `/api/patches/{id}/apply` | 教师 | **确认应用 —— 唯一会修改 `artifacts.doc` 的写路径** |
| POST | `/api/patches/{id}/reject` | 教师 | 驳回 |
| GET | `/api/artifacts/{id}/versions` | 教师 | 版本列表 |
| POST | `/api/artifacts/{id}/rollback` | 教师 | 回滚到指定版本 |
| GET | `/api/artifacts/{id}/coverage` | 教师 | 覆盖率与缺口 |
| POST | `/api/artifacts/{id}/coverage/fill` | 教师 | 补生成缺失内容(走生成作业) |
| POST | `/api/artifacts/{id}/publish` | 教师 | 发布 |
| POST | `/api/artifacts/{id}/export` | 教师 | 导出 pptx / docx / pdf → 异步 → 下载链接 |
| GET | `/api/admin/users` | 管理员 | 用户列表 |
| PATCH | `/api/admin/users/{id}` | 管理员 | 改角色 / 启停 |
| GET | `/api/admin/courses` | 管理员 | 全部课程 |
| POST | `/api/admin/courses/{id}/archive` | 管理员 | 下架(软删除) |
| GET | `/api/admin/audit` | 管理员 | **AI 生成审计记录** |

### 13.3 三条接口层不变式

1. **只有 `/api/patches/{id}/apply` 会修改 `artifacts.doc`。** 其余任何写接口都不碰它。这条是 NFR-04 在接口层的落点,也是测试断言的对象。
2. **生成类接口一律返回 `202` + `job_id`**,绝不在请求内同步执行。
3. **导出与生成都是异步作业**,前端只持有 `job_id` 与最终下载链接。

### 13.4 进度流(SSE)

正式契约是两步:`POST /api/generation/jobs` → `202 { job_id }`,
再 `GET /api/generation/jobs/{id}/events` 订阅进度。

**演示实现有意偏离**,新增 `POST /api/demo/generate/stream`:
请求体与 `POST /api/demo/generate` 完全相同,响应为 `text/event-stream`。

| | 作业 + 订阅(正式) | 直接 POST 流(演示) |
| --- | --- | --- |
| 作业注册表 | 需要(job id、状态快照、TTL) | 不需要 |
| 后订阅者补发历史 | 需要缓冲已发事件 | 不需要(订阅者即发起者) |
| 断线重连 | 需要 `Last-Event-ID` | 不需要 |
| 取消 | 独立端点 | 断开连接即取消 |

单用户本地演示用不上前三项。等 ARQ + PostgreSQL 落地(§16.2)再补作业生命周期,
届时 `POST /api/demo/generate/stream` 整份删掉 —— demo 路由的文档字符串
本来就写着这个承诺。

**这里有一处与 AGENTS.md 硬规则的正面冲突,必须讲清楚。**硬规则写着
「生成是异步作业。用任务队列(ARQ),不要在请求处理函数里跑生成」。
`StreamingResponse` 本质上仍是**在请求处理函数里跑生成**,它只解决了这条规则的
一半理由:

| 规则想防的 | 流式端点是否解决 |
| --- | --- |
| 同步请求 30–120 秒后超时 | **是** —— 首字节立刻返回 |
| 长时间占用 API worker | **否** —— 协程仍挂在整个生成期间 |

所以这是一次**有意的、有记录的偏离**,而不是绕过:它只存在于 `/api/demo/*`
这套内存演示路由里(该路由的模块文档字符串第 11–17 行已经声明「正式 API 需要
认证、数据库、异步作业,这套是实现产品流程用的」)。正式路径仍是
`POST /api/generation/jobs` + ARQ worker。**若本偏离被带进 `/api/` 正式路由,
就是违反硬规则,PR 应当被驳回。**

事件名只有四种,子类型放在 `data.kind` 里(取值见 §6.1.1):

```
event: progress
data: {"phase":"分节生成","percent":47,"kind":"tool","detail":"命中 4 段讲义",
       "sectionIndex":1,"sectionTitle":"动手练习","slideCount":3,"tool":"search_materials"}

event: result
data: {…完整 CoursePackage…}

event: done
data: {"ok":true}
```

三条约束:

1. **`result` 事件至多一次,且必在 `done` 之前。**中途出错发 `event: error`
   (结构见 §13.1),这条不变。
2. **流式端点与同步端点对同一输入必须产出逐字段相同的 `package`。**
   这是「两种传输、一种行为」的守卫 —— 最容易悄悄跑偏的一类缺陷,必须由测试钉住。
3. **客户端断开即取消生成任务**,不留还在烧 token 的孤儿协程。

**为什么不用浏览器原生 `EventSource`**:它只支持 GET,带不了 JSON 请求体。
前端改用 `fetch` + `response.body.getReader()` 加一个小的 SSE 拆行器。

---

## 14. 错误处理与降级

**原则:任何单个资产或章节失败,都不能让整包失败。**

| 失败 | 行为 |
| --- | --- |
| 材料解析失败 | 跳过该文件,给 warning,继续 |
| LLM 返回非法 JSON | 带 schema 和错误重试 1 次;仍失败只丢这一节 |
| 章节超时 | 保存部分包,该节标「待生成」,可单独重试 |
| Mermaid 语法错 | 回喂错误重试 2 次 → 降级为纯文字版式 |
| 生图服务失败 | 该资产标 `failed`,版式降级,**不致命** |
| 答案验证不通过 | 标记该题待人工确认,不阻塞其余题目 |
| 导出失败 | 独立作业报错可重试,不影响预览 |
| Agent 超轮数 | 强制终止工具 + 记录 trace |
| 作业进程崩溃 | ARQ 持久化队列保证重跑 |

---

## 15. 测试策略

| 层 | 测什么 |
| --- | --- |
| 纯单元 | IR 校验、交叉引用完整性、`IR → pptx/docx` golden file 对比、`PaperComposer` 约束求解 |
| 契约 | 每个 agent 工具的输入输出 schema |
| **Agent** | **断言工具调用序列,不断言文本。** 例:给定「第 3 页太简单了」,trace 必须先有 `read_slide("s3")` 才允许出现 `patch_slide` |
| **安全** | **未确认的 patch 不得落库** —— 未调用 `apply` 时 `artifacts.doc` 必须不变 |
| 覆盖率 | 故意移除一道覆盖某目标的题 → `coverage` 接口必须报出该缺口 |
| 溯源 | 构造无来源内容 → `origin` 必须为 `ai`,不得默认为 `sourced` |
| 集成 | 全流程,LLM 与生图服务都 mock |
| **叙述层** | **断言 `on_step` 事件序列,不断言文本。** 例:一次分节生成必须先出现 `search_materials` 的 start 再出现它的 ok,且 `write_section` 之后不得再有该节的 tool 事件 |
| **进度流** | 消费 SSE,断言 `percent` 全程单调不减、`slideCount` 最终等于真实张数、`result` 至多一次且必在 `done` 之前 |
| **传输等价** | 同一输入、同一假模型,流式端点与同步端点产出的 `package` 必须逐字段相同 |
| 人工 | 用 rubric 评估生成教案的教学法质量(有无时间线 / 提问 / 差异化) |
| 接口契约 | 每个端点逐个角色验证:越权请求必须返回 403 |
| 审计 | 审计接口只读;响应体中不出现任何密钥或原始请求体 |

「断言工具调用序列」这一条是 AGENTS.md 的硬规则,叙述层与进度流两项是它在
实时推送上的延伸:**能看到的东西必须是可断言的,否则它只是看起来在工作。**

「未确认的 patch 不得落库」、「断言工具调用序列」、「传输等价」这三条
是能直接写进报告的质量证据。

---

## 16. 技术选型

### 16.1 Agent 框架

| 库 | 定位 | 评价 |
| --- | --- | --- |
| **手写循环** | 最小实现 | ⭐ **起点必做**,~50 行,理解机制 |
| **Pydantic AI** | 类型安全 agent 框架 | ⭐⭐ **推荐**:与 FastAPI/Pydantic 同源,有 `FunctionModel` 测试支持,OpenAI 兼容端点接 DeepSeek 无痛 |
| **Instructor** | 结构化输出 + 自动重试 | ⭐⭐ 管道里非 agent 的步骤用它 |
| LangGraph | 图状态机编排 | human-in-the-loop 中断 / 恢复最强;**审批流变复杂时再上** |
| LangChain | 全家桶 | ❌ 抽象过厚,调试困难,答辩难解释 |
| LlamaIndex | RAG 为主 | 仅当检索效果卡住时才考虑 |
| CrewAI / AutoGen | 多 agent 协作 | ❌ 本场景不需要多 agent,只会增加失败点 |

**分工**:

```
管道里非 agent 的步骤(大纲 / 课件 / 出题)  →  Instructor(structured output + 重试)
需要工具循环的步骤(检索 + 画图 + 自检)      →  Pydantic AI agent
```

### 16.2 基础设施

| 用途 | 选择 | 说明 |
| --- | --- | --- |
| 异步作业 | **ARQ**(Redis) | 与 asyncio 同源,轻 |
| ⚠️ 避免 | FastAPI `BackgroundTasks` | 进程重启任务丢失,长任务不可靠 |
| 追踪 | **Langfuse**(开源自建) | 完整 trace,答辩截图 |
| 工具协议 | MCP | 需要跨应用复用工具时再上 |

### 16.3 主技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Next.js + TypeScript + Tailwind |
| 后端 | FastAPI + Pydantic |
| 数据库 | PostgreSQL + pgvector |
| 迁移 | Alembic |
| 认证 | JWT + RBAC |
| 部署 | Vercel(前端)+ Render/Railway(后端) |

---

## 17. 风险

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 教学设计质量不稳定 | 模型写得"像"教学过程,但教学法水平飘 | 人工审核必须保留;**编辑体验的优先级高于生成质量** |
| 考题答案错误 | 教师一眼看出,直接失去信任 | 跨厂商交叉验证 + 标记待确认 |
| pptx 排版溢出 | 导出结果难看 | 只支持固定版式;明确「内容等效」预期 |
| 范围膨胀 | 五种产物 + 视频,工作量巨大 | 先把 `artifacts` 抽象做对(多产物、共享资产池),再按人力加类型 |
| 生成耗时长 | 30–120 秒,同步请求超时 | 强制异步作业 + SSE 进度 |
| Agent 成本失控 | 多轮循环烧 token | 轮数上限 + 便宜档模型 + Langfuse 监控 |

---

## 18. 未决问题

| # | 问题 | 当前倾向 |
| --- | --- | --- |
| Q1 | 交互以纯自然语言为主,还是模板 + 自然语言? | **混合**:默认给模板入口(教案/课件/考题/模拟卷/视频),也支持直接打字;agent 不确定时反问「你是要课件还是模拟卷?」 |
| Q2 | DeepSeek 是否提供 embedding 端点? | 落地前用 `GET /models` 核对 |
| Q3 | 第一版是否接生图模型? | **可不接**。图标库 + Mermaid + 图表库已能撑起一份像样的课件 |
| Q4 | 视频是否进第一版? | 优先级最低,吃课件成果,适合收尾 |
| Q5 | 仓库文档迁移 | 现有文档在 Desktop 工作区且未纳入版本控制,建议迁入本仓库 `docs/` |

---

## 19. 术语表

| 术语 | 含义 |
| --- | --- |
| **Artifact(产物)** | 一种可独立预览 / 编辑 / 发布 / 导出的教学材料 |
| **IR(中间表示)** | 描述产物内容的纯数据(JSON),不含样式 |
| **Renderer(渲染器)** | IR → 某形态的纯转换,不含 AI |
| **管道(Pipeline)** | 步骤顺序由代码写死的处理流程 |
| **Agent** | 由模型自行决定调用哪些工具、调用几次的循环 |
| **L1** | 生成阶段:管道为主,章节生成内部是一个 agent 循环 |
| **L2** | 编辑阶段:教师用自然语言下指令,agent 调工具改 IR |
| **Patch** | 一次待确认的修改,确认前不落库 |
| **Asset** | 项目级共享的视觉 / 音频资源,按 hash 去重 |
| **speakerNotes** | 课件每页的讲稿,同时用作视频旁白来源 |
| **RemediationKit(补救包)** | 由错题统计触发生成的轻量补救材料 |
| **origin** | 内容来源标记:`sourced`(有原始材料出处)或 `ai`(AI 补充) |
| **coverage(覆盖率)** | 学习目标被课件与题目覆盖的程度 |

---

## 附:相关文档

- 需求基线:`../requirements.md`
- 文档索引:`../README.md`
- 项目计划:`PROJECT_PLAN.md`
- 需求与假设:`REQUIREMENTS_DESK_RESEARCH.md`
- 竞品分析:`competitor_analysis/README.md`
- 项目大纲:`project_overivew.pdf`
