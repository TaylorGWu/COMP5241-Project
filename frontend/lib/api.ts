/**
 * demo 接口的客户端封装。
 *
 * ⚠️ 这里连的是 `/api/demo/*` —— **仅供本地测试的内存版接口**。
 * 正式的 `/api/artifacts/*` 需要认证和数据库,还没做(见设计规格 §13)。
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

async function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload?.detail ?? `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload?.detail ?? `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { signal });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload?.detail ?? `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

// ── SSE 客户端(设计规格 §13.4)──────────────────────────────
//
// 为什么不用浏览器原生的 `EventSource`:
// **它只支持 GET,带不了 JSON 请求体。**而我们的生成接口需要收主题、
// 受众、教材语言等一整套参数。所以只能用 `fetch` + 手动拆帧。
//
// 拆帧规则(SSE 规范里我们用到的那一小部分):
//   · 帧之间用空行分隔 —— 即 `\n\n`
//   · `event: <名字>` 一行,`data: <JSON>` 一行
//   · 后端用 `json.dumps` 生成 data,所以 JSON 里**不会有裸换行**
//     (会被转义成 `\n` 两个字符),因此按 `\n\n` 切是安全的

export type SseFrame = { event: string; data: unknown };

/** 把一个 Response 的 body 按 SSE 帧流式解析出来。 */
async function readSse(
  res: Response,
  onFrame: (frame: SseFrame) => void,
): Promise<void> {
  if (!res.body) throw new Error("响应没有 body,无法流式读取");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const flush = (block: string) => {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      // 以 `:` 开头的是注释(心跳),忽略
    }
    if (!dataLines.length) return;
    try {
      onFrame({ event, data: JSON.parse(dataLines.join("\n")) });
    } catch {
      // 单帧 JSON 坏了不该让整次生成失败 —— 进度是辅助信息
    }
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let at: number;
    while ((at = buffer.indexOf("\n\n")) >= 0) {
      flush(buffer.slice(0, at));
      buffer = buffer.slice(at + 2);
    }
  }
  if (buffer.trim()) flush(buffer);
}

export type StreamStatus = "idle" | "streaming" | "done" | "error";

/** 一个流式端点的通用驱动:负责拆帧,并按事件名分派。 */
async function streamRequest(
  path: string,
  body: unknown,
  handlers: {
    onProgress?: (data: Record<string, unknown>) => void;
    onResult: (data: Record<string, unknown>) => void;
    signal?: AbortSignal;
  },
): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: handlers.signal,
  });

  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload?.detail ?? `HTTP ${res.status}`);
  }

  let gotResult = false;
  await readSse(res, ({ event, data }) => {
    const payload = (data ?? {}) as Record<string, unknown>;
    if (event === "progress") {
      handlers.onProgress?.(payload);
    } else if (event === "result") {
      gotResult = true;
      handlers.onResult(payload);
    } else if (event === "error") {
      // 结构见设计规格 §13.1
      const err = (payload.error ?? {}) as Record<string, unknown>;
      throw new Error(String(err.message ?? "生成失败"));
    }
    // `done` 不用处理:result 已经到过了
  });

  if (!gotResult) throw new Error("生成提前结束,没有拿到结果");
}

// ── 与后端 IR 对应的最小类型(字段用 camelCase,和 §5.1 一致)──

/**
 * 进度事件的子类型(§6.1.1)。
 *
 * 刻意**没有 `reasoning`** —— 思考流那条路径已经从后端整条删掉了(§11.7)。
 * 类型里留着它就是在骗人:调用方会以为自己需要处理一种永远不会来的事件。
 */
export type ProgressKind = "phase" | "section" | "turn" | "tool" | "slide";

/**
 * 一条进度事件。
 *
 * ⚠️ `detail` **只给人看**,措辞随时会变,不要拿它做程序判断 ——
 * 要分支就用 `kind` / `sectionIndex` / `slideCount` / `tool`。
 */
export type ProgressEvent = {
  phase: string;
  percent: number;
  detail: string;
  kind: ProgressKind;
  /** 第几节(从 0 起)。用于按节分栏。 */
  sectionIndex: number | null;
  sectionTitle: string | null;
  /** 累计已写出的幻灯片张数 —— 「现在写到第几张」。 */
  slideCount: number;
  tool: string | null;
  /**
   * 细分状态。
   *   kind=section → `started` | `written` | `failed`
   *   kind=tool    → `running` | `error`
   *
   * 有它才能区分「这一节写完了」和「这一节失败了」,而不必去猜 `detail` 的措辞。
   */
  status: string;
};

/** L2 编辑流的进度帧(见后端 `/api/demo/edit/stream`)。 */
export type EditProgressEvent = {
  kind: "turn" | "tool" | "stop";
  tool: string | null;
  status: string;
  detail: string;
  turn: number;
};

export type MaterialReport = {
  filename: string;
  detected_form: string;
  status: "ok" | "degraded" | "failed";
  message: string;
  pages: number;
  extracted_chars: number;
  ocr_used: boolean;
};

export type Outline = {
  objectives: string[];
  sections: { title: string; minutes: number; objectiveIds: string[] }[];
  rationale: string;
  usedFallback: boolean;
};

export type Slide = {
  id: string;
  order: number;
  layout: string;
  title: string;
  bullets: string[];
  speakerNotes: string;
  // spec 里放的是「这张图该怎么画」(目前是 mermaid 源码)。
  // 资产还没渲染成图之前,画布上就把这段源码显示出来,而不是留一个空框。
  visuals: {
    id: string;
    kind: string;
    assetId?: string;
    spec?: { engine?: string; code?: string };
  }[];
  objectiveIds: string[];
  sourceRefs: { materialId: string; page?: number }[];
  origin: "sourced" | "ai";
};

export type TimelineEntry = {
  id: string;
  phase: string;
  minutes: number;
  teacherAction: string;
  studentAction: string;
  slideIds: string[];
  checkUnderstanding: string;
};

export type CoursePackage = {
  project: {
    // language 是**教材**语言,由生成时的选择决定,和界面语言无关。
    meta: { title: string; audience: string; durationMin: number; language?: string };
    learningObjectives: { id: string; text: string }[];
    /** 术语白话解释(§9.4)。没生成过就是空数组。 */
    glossary?: GlossaryEntry[];
  };
  assets: { id: string; kind: string; url?: string; altText?: string }[];
  lessonPlan?: { timeline: TimelineEntry[]; overview: string };
  slideDeck?: { slides: Slide[] };
  questionSet?: QuestionSet | null;
  examPaper?: ExamPaper | null;
};

/** 课程拥有章节；课件、题库与试卷都属于某一个章节草稿。 */
export type TeacherCourse = {
  id: string;
  title: string;
  description: string;
  audience: string;
  language: string;
  durationMin: number;
  status: "draft" | "published";
  chapterIds: string[];
};

export type TeacherChapter = {
  id: string;
  courseId: string;
  title: string;
  summary: string;
  order: number;
  status: "empty" | "generating" | "draft" | "ready" | "failed";
  package?: CoursePackage | null;
};

// ── 教师端四个增量:出题 / 组卷 / 白话化 / 导出 ──────────────

export type Question = {
  id: string;
  type: "mcq" | "short" | "code" | "scenario";
  stem: string;
  options: { id: string; text: string }[];
  answer: string;
  explanation: string;
  difficulty: number;
  objectiveIds: string[];
  points: number;
};

export type QuestionSet = {
  artifactId: string;
  questions: Question[];
};

export type PaperSection = { title: string; rule: string; questionIds: string[] };

export type ExamPaper = {
  artifactId: string;
  constraints: {
    totalPoints: number;
    durationMin: number;
    coverage: string[];
    difficulty: { easy: number; medium: number; hard: number };
  };
  sections: PaperSection[];
  answerKey: boolean;
};

export type GlossaryEntry = { term: string; plain: string; objectiveIds: string[] };

export type QuestionsResponse = {
  model_mode: string;
  question_set: QuestionSet;
  /** true 表示一道题都没出出来 —— 界面上要说清楚,别显示成「0 道题」。 */
  used_fallback: boolean;
  reason: string;
  package: CoursePackage;
};

export type PaperResponse = {
  ok: boolean;
  /** 三条约束里哪条没满足。空字符串才是正常。 */
  reason: string;
  actual_points: number;
  missing: string[];
  actual_difficulty: { easy: number; medium: number; hard: number };
  paper: ExamPaper;
  package: CoursePackage;
};

export type GlossaryResponse = {
  model_mode: string;
  glossary: GlossaryEntry[];
  alt_texts: Record<string, string>;
  used_fallback: boolean;
  reason: string;
  package: CoursePackage;
};

/** `/state` 的返回。刷新页面后前端用它把产物接回来。 */
export type StateResponse = {
  has_package: boolean;
  model_mode?: string;
  package?: CoursePackage;
  integrity_issues?: string[];
  patches?: Patch[];
};

export type PaperConstraints = {
  total_points: number;
  duration_min: number;
  coverage: string[];
  easy: number;
  medium: number;
  hard: number;
};

export type Patch = {
  id: string;
  kind: string;
  target_id: string;
  payload: Record<string, unknown>;
  reason: string;
  diff: string;
  status: "proposed" | "applied" | "rejected";
  /** 谁提的。AI 提议要你确认;教师改的保存即生效。 */
  author: "ai" | "teacher";
};

export type GenerateResponse = {
  model_mode: string;
  events: ProgressEvent[];
  materials: MaterialReport[];
  outline: Outline | null;
  package: CoursePackage;
  integrity_issues: string[];
  agents: { call_names: string[]; turns: number; stopped_by: string; errors: string[] }[];
};

export type EditResponse = {
  model_mode: string;
  reply: string;
  call_names: string[];
  patches: Patch[];
  package: CoursePackage;
};

export type GenerateInput = {
  topic: string;
  audience: string;
  duration_min: number;
  objectives: string[];
  material_text: string;
  use_real_model: boolean;
  /**
   * 教材用什么语言写。**与界面语言无关** —— 中文界面完全可以出英文教材。
   * 后端会把它同时喂给规划阶段和分节撰写阶段。
   */
  language: string;
};

/**
 * 导出下载地址。
 *
 * 这几个是**普通链接**,不走 fetch —— 浏览器拿到 `Content-Disposition`
 * 就会直接下载,不用把二进制读进内存再造 Blob。
 */
export const exportUrls = {
  deck: () => `${API_BASE}/api/demo/export/deck.pptx`,
  lessonPlan: () => `${API_BASE}/api/demo/export/lesson-plan.docx`,
  /** `answers=false` 是学生版(不含答案与解析)。 */
  examPaper: (answers: boolean) =>
    `${API_BASE}/api/demo/export/exam-paper.docx?answers=${answers}`,
};

export const api = {
  outline: (b: GenerateInput) => post<{ model_mode: string; outline: Outline }>("/api/demo/outline", b),
  generate: (b: GenerateInput) => post<GenerateResponse>("/api/demo/generate", b),
  edit: (message: string, useReal: boolean) =>
    post<EditResponse>("/api/demo/edit", { message, use_real_model: useReal }),

  /**
   * 流式生成 —— **边跑边收进度**(设计规格 §13.4)。
   *
   * 和 `generate()` 的区别只有一个:进度不再等生成完才一起给,
   * 而是每发生一件事就推一帧。所以教师能看见「第 2 节 · 正在检索讲义」。
   *
   * 两条路产出的包是一样的 —— 后端就是同一个实现(见 demo.py 的
   * `_run_generation`),这是 §13.4 约束 2。
   */
  generateStream: (
    b: GenerateInput,
    handlers: {
      onProgress?: (e: ProgressEvent) => void;
      onResult: (r: GenerateResponse) => void;
      signal?: AbortSignal;
    },
  ) =>
    streamRequest("/api/demo/generate/stream", b, {
      onProgress: (d) => handlers.onProgress?.(d as unknown as ProgressEvent),
      onResult: (d) => handlers.onResult(d as unknown as GenerateResponse),
      signal: handlers.signal,
    }),

  /**
   * 流式编辑。L2 比 L1 更值得看过程:能看见 agent 先读了哪一页、为什么这么改。
   */
  editStream: (
    message: string,
    useReal: boolean,
    handlers: {
      onProgress?: (e: EditProgressEvent) => void;
      onResult: (r: EditResponse) => void;
      signal?: AbortSignal;
    },
  ) =>
    streamRequest(
      "/api/demo/edit/stream",
      { message, use_real_model: useReal },
      {
        onProgress: (d) => handlers.onProgress?.(d as unknown as EditProgressEvent),
        onResult: (d) => handlers.onResult(d as unknown as EditResponse),
        signal: handlers.signal,
      },
    ),

  /**
   * 取当前状态。
   *
   * **刷新页面之后必须调它** —— 否则生成结果只活在 React state 里,
   * 页面一刷新就回到 Setup,而后端手里那份产物还在。
   */
  state: () => get<StateResponse>("/api/demo/state"),

  createCourse: (input: {
    title: string;
    description: string;
    audience: string;
    durationMin: number;
    language: string;
  }) => post<TeacherCourse>("/api/demo/courses", input),

  courses: () => get<{ courses: TeacherCourse[] }>("/api/demo/courses"),

  course: (courseId: string) => get<TeacherCourse>(`/api/demo/courses/${courseId}`),

  publishCourse: (courseId: string) => post<TeacherCourse>(`/api/demo/courses/${courseId}/publish`, {}),
  unpublishCourse: (courseId: string) => post<TeacherCourse>(`/api/demo/courses/${courseId}/unpublish`, {}),

  chapter: (courseId: string, chapterId: string) =>
    get<TeacherChapter>(`/api/demo/courses/${courseId}/chapters/${chapterId}`),

  createChapter: (courseId: string, input: { title: string; summary?: string }) =>
    post<TeacherChapter>(`/api/demo/courses/${courseId}/chapters`, input),

  deleteChapter: (courseId: string, chapterId: string) =>
    fetch(`${API_BASE}/api/demo/courses/${courseId}/chapters/${chapterId}`, { method: "DELETE" }),

  activateChapter: (courseId: string, chapterId: string) =>
    post<TeacherChapter>(`/api/demo/courses/${courseId}/chapters/${chapterId}/activate`, {}),

  updateChapter: (
    courseId: string,
    chapterId: string,
    changes: Partial<Pick<TeacherChapter, "title" | "summary" | "status" | "package">>,
  ) => patch<TeacherChapter>(`/api/demo/courses/${courseId}/chapters/${chapterId}`, changes),

  generateChapter: (courseId: string, chapterId: string, input: GenerateInput) =>
    post<GenerateResponse & { chapter: TeacherChapter }>(
      `/api/demo/courses/${courseId}/chapters/${chapterId}/generate`,
      input,
    ),

  /** 出题。学习目标取自产物的大纲,不用前端再传一遍。 */
  questions: (countPerObjective: number, useReal: boolean, language: string) =>
    post<QuestionsResponse>("/api/demo/questions", {
      count_per_objective: countPerObjective,
      use_real_model: useReal,
      language,
    }),

  /** 组卷。**纯算法,不调用模型** —— 所以它不慢,也不需要「用真模型」开关。 */
  paper: (constraints: PaperConstraints) =>
    post<PaperResponse>("/api/demo/paper", constraints),

  /** 术语白话化 + 图片替代文本。 */
  glossary: (useReal: boolean, language: string) =>
    post<GlossaryResponse>("/api/demo/glossary", {
      use_real_model: useReal,
      language,
    }),

  apply: (patchId: string) =>
    post<{ package: CoursePackage }>("/api/demo/apply", { patch_id: patchId }),
  reject: (patchId: string) =>
    post<{ package: CoursePackage }>("/api/demo/reject", { patch_id: patchId }),
  reset: () => post<{ status: string }>("/api/demo/reset", {}),

  /**
   * 教师直接改内容 —— 不走 AI。
   *
   * ⚠️ 注意后端仍然是「生成 patch 并立刻 apply」,不是直接写产物。
   * 所以每次手动改都会留下一条 author="teacher" 的记录(可审计、可回退)。
   */
  manualEdit: (
    kind: "slide" | "timeline",
    targetId: string,
    payload: Record<string, unknown>,
    note = "教师手动修改",
  ) =>
    post<{ patch: Patch; package: CoursePackage }>("/api/demo/manual-edit", {
      kind,
      target_id: targetId,
      payload,
      note,
    }),
};
