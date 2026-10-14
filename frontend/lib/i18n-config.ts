/**
 * 界面多语言的**数据层** —— 这个文件没有 "use client"。
 *
 * ═══════════════════════════════════════════════════════════════
 * 为什么要和 i18n.tsx 分开
 * ═══════════════════════════════════════════════════════════════
 * 语言存在 cookie 里,由 `app/layout.tsx`(服务端组件)读出来,
 * 这样首屏就是正确语言、不会闪。
 *
 * 但 `"use client"` 模块被服务端 import 时,导出的是**客户端引用**,
 * 不是真实函数 —— 在服务端调用它直接 500:
 *
 *     Attempted to call normalizeLocale() from the server
 *     but normalizeLocale is on the client.
 *
 * 所以词典、语言表、normalizeLocale 这些**纯数据与纯函数**必须放在
 * 一个普通的模块里,服务端和客户端都能直接用;只有 Provider 和 hook
 * 才需要待在 "use client" 那边。
 *
 * ═══════════════════════════════════════════════════════════════
 * 类型安全
 * ═══════════════════════════════════════════════════════════════
 * 用 `Messages = Widen<typeof en>` 推导类型,再让另外两份标注成 Messages。
 * 漏翻一个键 `tsc` 直接报错 —— 比运行时回退成 key 字符串强得多。
 *
 * ═══════════════════════════════════════════════════════════════
 * 语言是两条轴,不要混
 * ═══════════════════════════════════════════════════════════════
 *   界面语言  —— 这里管,决定按钮和标签用哪种语言
 *   内容语言  —— 由教师在工作台上单独选,决定**生成的教材**用什么语言
 *
 * 港校场景下这两者经常不同(中文界面 + 英文教材),所以是独立开关。
 */

// ═══════════════════════════════════════════════════════════════
// 英文版 —— 其余语言的类型基准
// ═══════════════════════════════════════════════════════════════

const en = {
  app: {
    startOver: "Start over",
    liveModel: "Live model",
    sampleModel: "Sample model",
  },
  setup: {
    eyebrow: "New course",
    headline: "What are you teaching?",
    lede: "Describe the course, and paste your own materials if you have them. You will get a slide deck and a lesson plan that share one set of learning objectives — and nothing reaches students until you approve it.",
    brief: "The brief",
    topic: "Course topic",
    audience: "Who is it for",
    length: "Length",
    minutes: "minutes",
    objectives: "Learning objectives",
    onePerLine: "one per line",
    materials: "Your materials",
    materialsLede:
      "Paste lecture notes, or leave this empty and the draft will be written from the brief alone. Anything you paste here is cited page by page; anything the model adds is marked as AI-added.",
    contentLanguage: "Course language",
    contentLanguageHint: "What the generated material is written in. Independent of this interface.",
    useReal: "Use the live DeepSeek model",
    useRealHint: "Off = a scripted sample model, so the flow can be demonstrated without a key.",
    generate: "Generate draft",
    working: "Working…",
    outlineOnly: "Outline only",
    outlineOnlyHint: "Outline only skips writing the slides and is much faster.",
    chars: (n: number) => `${n} chars`,
    pages: (n: number) => `${n} pages`,
    ocr: "OCR",
  },
  progress: {
    title: "Generating",
    phaseLog: "Phase log",
    materials: "Read materials",
    outline: "Plan outline",
    sections: "Write sections",
    visuals: "Decide visuals",
    assets: "Build assets",
    assembly: "Assemble & check",

    // ── 实时过程(设计规格 §6.1.2)──
    live: "Live",
    waiting: "Waiting",
    writing: "Writing",
    written: "Done",
    queued: "Queued",
    slidesWritten: (n: number) => `${n} slide${n === 1 ? "" : "s"} written`,
    latestPages: "Latest pages",
    elapsed: (s: number) => `${s}s`,
    turnLabel: (n: number) => `round ${n}`,
    cancel: "Stop",
    cancelled: "Stopped",
  },
  coverage: {
    label: "Objective coverage",
    count: (n: number) => `${n} slide${n === 1 ? "" : "s"}`,
    notCovered: "not covered",
    issues: (n: number) => `${n} cross-reference issue${n === 1 ? "" : "s"}`,
    passed: "Cross-reference checks passed",
    gapsTitle: "Not covered yet",
    gapHint: "No slide references this objective.",
    allCovered: "Every objective is covered by at least one slide.",
  },
  rail: {
    slides: (n: number) => `Slides (${n})`,
    plan: (n: number) => `Plan (${n})`,
    meta: (o: { duration: number; slides: number; assets: number }) =>
      `${o.duration} min · ${o.slides} slides · ${o.assets} assets`,
    forAudience: (a: string) => `For ${a}`,
    sources: "Sources",
    runDetails: "Run details",
    turns: (n: number) => `${n} turns`,
    empty: "Nothing here yet.",
  },
  slide: {
    layoutTitle: "Title",
    layoutBullets: "Bullets",
    layoutDiagram: "Diagram",
    layoutTwoCol: "Two column",
    layoutCode: "Code",
    layoutQuiz: "Quiz",
    edit: "Edit",
    sourced: "Sourced",
    aiAdded: "AI-added",
    proposed: (n: number) => `${n} proposed change${n === 1 ? "" : "s"}`,
    fieldTitle: "Title",
    fieldLayout: "Layout",
    fieldBullets: "Bullets",
    fieldNotes: "Speaker notes",
    save: "Save",
    cancel: "Cancel",
    saveNote: "Saving still records a version you can roll back.",
    noSlides: "This course has no slides yet.",
    notGenerated: "not generated yet",
    noSource: "No source recorded yet.",
  },
  plan: {
    teacher: "Teacher",
    students: "Students",
    check: "Check",
    slides: "Slides",
    empty: "This course has no lesson plan yet.",
    fieldPhase: "Phase",
    fieldMinutes: "Minutes",
    fieldTeacher: "What the teacher does",
    fieldStudents: "What students do",
    fieldCheck: "How you check they followed",
    saveNote: "Total minutes are checked against the course length on save.",
  },
  margin: {
    waiting: "Waiting on you",
    nothingWaiting: "Nothing is waiting. The material matches what you approved.",
    askChange: "Ask for a change",
    placeholder: "e.g. Slide 2 is too dense for a non-CS audience",
    send: "Send",
    integrityOk: "Checked here, not just reported: nothing changed while this was waiting for you.",
    integrityBad: "This changed before you approved it — the review step was bypassed.",
    agentDid: (n: number) => `What the agent did (${n} tool calls)`,
    agentWorking: "Working on it",
    agentRound: (n: number) => `round ${n}`,
    agentWaiting: "Waiting for the model to respond…",
    recorded: "Recorded",
    historyEmpty: "No changes recorded yet.",
    coverGap: (id: string, text: string) =>
      `Please add material covering ${id} — ${text}. No slide references it yet.`,
    approve: "Approve",
    reject: "Reject",
    applied: "Applied",
    rejected: "Rejected",
    authorYou: "You",
    authorAi: "AI",
  },
  tools: {
    title: "After the plan",
    questions: "Generate questions",
    questionsAgain: "Regenerate questions",
    questionsNote: (n: number) => `${n} question${n === 1 ? "" : "s"}`,
    difficultySpread: (lo: number, hi: number) => `difficulty ${lo}–${hi}`,
    paper: "Build paper",
    paperTotal: "Total points",
    paperDuration: "Minutes",
    paperExact: (n: number) => `Exactly ${n} points`,
    paperShort: (got: number, want: number) => `${got} of ${want} points`,
    glossary: "Plain-language glossary",
    glossaryNote: (n: number) => `${n} term${n === 1 ? "" : "s"}`,
    notYet: "Not generated yet",
    export: "Export",
    exportDeck: "Slides .pptx",
    exportPlan: "Lesson plan .docx",
    exportExamTeacher: "Paper (with answers)",
    exportExamStudent: "Paper (student copy)",
    exportNote: "Export is content-equivalent, not pixel-identical to the preview.",
  },
  keys: {
    toggle: "Slides / lesson plan",
    label: "Keyboard shortcuts",
    approve: "Approve change",
    reject: "Reject change",
    next: "Next page",
    prev: "Previous page",
  },
} as const;

type Widen<T> = T extends string
  ? string
  : T extends (...args: infer A) => string
    ? (...args: A) => string
    : { [K in keyof T]: Widen<T[K]> };

export type Messages = Widen<typeof en>;

// ═══════════════════════════════════════════════════════════════
// 繁體中文(香港)
// ═══════════════════════════════════════════════════════════════

const zhHK: Messages = {
  app: {
    startOver: "重新開始",
    liveModel: "真實模型",
    sampleModel: "範例模型",
  },
  setup: {
    eyebrow: "新課程",
    headline: "你這次要教什麼?",
    lede: "描述這門課,有的話把你的教材貼進來。你會拿到一份課件和一份教案,兩者共用同一組學習目標 —— 而且在你逐頁確認之前,不會有任何內容到學生手上。",
    brief: "課程設定",
    topic: "課程主題",
    audience: "對象是誰",
    length: "課時",
    minutes: "分鐘",
    objectives: "學習目標",
    onePerLine: "一行一個",
    materials: "你的教材",
    materialsLede:
      "貼上講義內容;留空也可以,系統只依據上面的設定來寫。貼進來的內容會逐頁標出來源,模型自己補的會標成 AI 補充。",
    contentLanguage: "教材語言",
    contentLanguageHint: "生成內容用哪種語言寫。與這個介面的語言無關。",
    useReal: "使用真實 DeepSeek 模型",
    useRealHint: "不勾 = 用內建的範例模型,沒有 API key 也能完整走一遍流程。",
    generate: "生成草稿",
    working: "處理中…",
    outlineOnly: "只看大綱",
    outlineOnlyHint: "只看大綱會跳過撰寫課件,快很多。",
    chars: (n: number) => `${n} 字`,
    pages: (n: number) => `${n} 頁`,
    ocr: "已 OCR",
  },
  progress: {
    title: "生成中",
    phaseLog: "階段記錄",
    materials: "讀取教材",
    outline: "規劃大綱",
    sections: "分節撰寫",
    visuals: "判定視覺需求",
    assets: "生成資產",
    assembly: "組裝與校驗",

    live: "即時",
    waiting: "等待中",
    writing: "撰寫中",
    written: "完成",
    queued: "排隊中",
    slidesWritten: (n: number) => `已寫 ${n} 張`,
    latestPages: "最新幾頁",
    elapsed: (s: number) => `${s} 秒`,
    turnLabel: (n: number) => `第 ${n} 輪`,
    cancel: "停止",
    cancelled: "已停止",
  },
  coverage: {
    label: "學習目標覆蓋",
    count: (n: number) => `${n} 頁`,
    notCovered: "未覆蓋",
    issues: (n: number) => `${n} 項交叉引用問題`,
    passed: "交叉引用校驗通過",
    gapsTitle: "尚未覆蓋",
    gapHint: "目前沒有任何一頁引用這個學習目標。",
    allCovered: "每個學習目標都至少被一頁課件覆蓋。",
  },
  rail: {
    slides: (n: number) => `課件 (${n})`,
    plan: (n: number) => `教案 (${n})`,
    meta: (o: { duration: number; slides: number; assets: number }) =>
      `${o.duration} 分鐘 · ${o.slides} 頁 · ${o.assets} 個資產`,
    forAudience: (a: string) => `對象:${a}`,
    sources: "來源材料",
    runDetails: "執行細節",
    turns: (n: number) => `${n} 輪`,
    empty: "暫時沒有內容。",
  },
  slide: {
    layoutTitle: "標題頁",
    layoutBullets: "條列",
    layoutDiagram: "示意圖",
    layoutTwoCol: "雙欄",
    layoutCode: "程式碼",
    layoutQuiz: "測驗",
    edit: "編輯",
    sourced: "有來源",
    aiAdded: "AI 補充",
    proposed: (n: number) => `${n} 項待確認`,
    fieldTitle: "標題",
    fieldLayout: "版面",
    fieldBullets: "要點",
    fieldNotes: "講稿",
    save: "儲存",
    cancel: "取消",
    saveNote: "儲存後仍會留下一筆版本記錄,可以回退。",
    noSlides: "這門課還沒有課件。",
    notGenerated: "尚未生成",
    noSource: "尚未記錄繪圖來源。",
  },
  plan: {
    teacher: "教師",
    students: "學生",
    check: "確認理解",
    slides: "對應頁面",
    empty: "這門課還沒有教案。",
    fieldPhase: "環節名稱",
    fieldMinutes: "時長(分鐘)",
    fieldTeacher: "教師做什麼",
    fieldStudents: "學生做什麼",
    fieldCheck: "怎麼確認學生聽懂了",
    saveNote: "儲存時會核對總時長與課程長度是否相符。",
  },
  margin: {
    waiting: "待你確認",
    nothingWaiting: "沒有待確認的改動,目前內容就是你核准的版本。",
    askChange: "要求修改",
    placeholder: "例如:第 2 頁對非本科學生來說太密了",
    send: "送出",
    integrityOk: "這裡自己再比對過,不是只聽後端說:待確認期間內容一字未變。",
    integrityBad: "這份內容在你核准之前就被改動了 —— 審閱這一步被繞過了。",
    agentDid: (n: number) => `Agent 做了什麼(${n} 次工具呼叫)`,
    agentWorking: "正在處理",
    agentRound: (n: number) => `第 ${n} 輪`,
    agentWaiting: "等待模型回應…",
    recorded: "已歸檔",
    historyEmpty: "還沒有任何改動記錄。",
    coverGap: (id: string, text: string) =>
      `請補上 ${id} 的內容 —— ${text}。目前沒有任何一頁覆蓋它。`,
    approve: "確認套用",
    reject: "駁回",
    applied: "已套用",
    rejected: "已駁回",
    authorYou: "教師",
    authorAi: "AI",
  },
  tools: {
    title: "教案之後",
    questions: "出題",
    questionsAgain: "重新出題",
    questionsNote: (n: number) => `${n} 道題`,
    difficultySpread: (lo: number, hi: number) => `難度 ${lo}–${hi}`,
    paper: "組卷",
    paperTotal: "總分",
    paperDuration: "時長(分鐘)",
    paperExact: (n: number) => `正好 ${n} 分`,
    paperShort: (got: number, want: number) => `${want} 分裡湊到 ${got} 分`,
    glossary: "術語白話化",
    glossaryNote: (n: number) => `${n} 條詞條`,
    notYet: "還沒生成",
    export: "匯出",
    exportDeck: "課件 .pptx",
    exportPlan: "教案 .docx",
    exportExamTeacher: "試卷(教師版)",
    exportExamStudent: "試卷(學生版)",
    exportNote: "匯出是內容等效,不是跟預覽逐像素一致。",
  },
  keys: {
    toggle: "課件 / 教案",
    label: "鍵盤快速鍵",
    approve: "確認套用",
    reject: "駁回變更",
    next: "下一頁",
    prev: "上一頁",
  },
};

// ═══════════════════════════════════════════════════════════════
// 简体中文
// ═══════════════════════════════════════════════════════════════

const zhCN: Messages = {
  app: {
    startOver: "重新开始",
    liveModel: "真实模型",
    sampleModel: "示例模型",
  },
  setup: {
    eyebrow: "新课程",
    headline: "你这次要教什么?",
    lede: "描述这门课,有的话把你的教材贴进来。你会拿到一份课件和一份教案,两者共用同一组学习目标 —— 而且在你逐页确认之前,不会有任何内容到学生手上。",
    brief: "课程设置",
    topic: "课程主题",
    audience: "面向谁",
    length: "课时",
    minutes: "分钟",
    objectives: "学习目标",
    onePerLine: "一行一个",
    materials: "你的教材",
    materialsLede:
      "把讲义粘进来;留空也可以,系统只依据上面的设置来写。粘贴的内容会逐页标出来源,模型自己补的会标成 AI 补充。",
    contentLanguage: "教材语言",
    contentLanguageHint: "生成内容用什么语言写。与这个界面的语言无关。",
    useReal: "使用真实 DeepSeek 模型",
    useRealHint: "不勾 = 用内置的示例模型,没有 API key 也能完整走一遍流程。",
    generate: "生成草稿",
    working: "处理中…",
    outlineOnly: "只看大纲",
    outlineOnlyHint: "只看大纲会跳过撰写课件,快很多。",
    chars: (n: number) => `${n} 字`,
    pages: (n: number) => `${n} 页`,
    ocr: "已 OCR",
  },
  progress: {
    title: "生成中",
    phaseLog: "阶段日志",
    materials: "读取教材",
    outline: "规划大纲",
    sections: "分节撰写",
    visuals: "判定视觉需求",
    assets: "生成资产",
    assembly: "组装与校验",

    live: "实时",
    waiting: "等待中",
    writing: "撰写中",
    written: "完成",
    queued: "排队中",
    slidesWritten: (n: number) => `已写 ${n} 张`,
    latestPages: "最新几页",
    elapsed: (s: number) => `${s} 秒`,
    turnLabel: (n: number) => `第 ${n} 轮`,
    cancel: "停止",
    cancelled: "已停止",
  },
  coverage: {
    label: "学习目标覆盖",
    count: (n: number) => `${n} 页`,
    notCovered: "未覆盖",
    issues: (n: number) => `${n} 项交叉引用问题`,
    passed: "交叉引用校验通过",
    gapsTitle: "尚未覆盖",
    gapHint: "目前没有任何一页引用这个学习目标。",
    allCovered: "每个学习目标都至少被一页课件覆盖。",
  },
  rail: {
    slides: (n: number) => `课件 (${n})`,
    plan: (n: number) => `教案 (${n})`,
    meta: (o: { duration: number; slides: number; assets: number }) =>
      `${o.duration} 分钟 · ${o.slides} 页 · ${o.assets} 个资产`,
    forAudience: (a: string) => `面向:${a}`,
    sources: "来源材料",
    runDetails: "运行细节",
    turns: (n: number) => `${n} 轮`,
    empty: "暂时没有内容。",
  },
  slide: {
    layoutTitle: "标题页",
    layoutBullets: "要点",
    layoutDiagram: "示意图",
    layoutTwoCol: "双栏",
    layoutCode: "代码",
    layoutQuiz: "测验",
    edit: "编辑",
    sourced: "有来源",
    aiAdded: "AI 补充",
    proposed: (n: number) => `${n} 项待确认`,
    fieldTitle: "标题",
    fieldLayout: "版面",
    fieldBullets: "要点",
    fieldNotes: "讲稿",
    save: "保存",
    cancel: "取消",
    saveNote: "保存后仍会留下一条版本记录,可以回退。",
    noSlides: "这门课还没有课件。",
    notGenerated: "尚未生成",
    noSource: "尚未记录绘图来源。",
  },
  plan: {
    teacher: "教师",
    students: "学生",
    check: "确认理解",
    slides: "对应页面",
    empty: "这门课还没有教案。",
    fieldPhase: "环节名称",
    fieldMinutes: "时长(分钟)",
    fieldTeacher: "教师做什么",
    fieldStudents: "学生做什么",
    fieldCheck: "怎么确认学生听懂了",
    saveNote: "保存时会核对总时长与课程长度是否相符。",
  },
  margin: {
    waiting: "待你确认",
    nothingWaiting: "没有待确认的改动,当前内容就是你批准的版本。",
    askChange: "要求修改",
    placeholder: "例如:第 2 页对非本专业学生来说太密了",
    send: "发送",
    integrityOk: "这里自己又比对过一次,不是只听后端说:待确认期间内容一字未变。",
    integrityBad: "这份内容在你批准之前就被改动了 —— 审阅这一步被绕过了。",
    agentDid: (n: number) => `Agent 做了什么(${n} 次工具调用)`,
    agentWorking: "正在处理",
    agentRound: (n: number) => `第 ${n} 轮`,
    agentWaiting: "等待模型响应…",
    recorded: "已归档",
    historyEmpty: "还没有任何改动记录。",
    coverGap: (id: string, text: string) =>
      `请补上 ${id} 的内容 —— ${text}。目前没有任何一页覆盖它。`,
    approve: "确认应用",
    reject: "驳回",
    applied: "已应用",
    rejected: "已驳回",
    authorYou: "教师",
    authorAi: "AI",
  },
  tools: {
    title: "教案之后",
    questions: "出题",
    questionsAgain: "重新出题",
    questionsNote: (n: number) => `${n} 道题`,
    difficultySpread: (lo: number, hi: number) => `难度 ${lo}–${hi}`,
    paper: "组卷",
    paperTotal: "总分",
    paperDuration: "时长(分钟)",
    paperExact: (n: number) => `正好 ${n} 分`,
    paperShort: (got: number, want: number) => `${want} 分里凑到 ${got} 分`,
    glossary: "术语白话化",
    glossaryNote: (n: number) => `${n} 条词条`,
    notYet: "还没生成",
    export: "导出",
    exportDeck: "课件 .pptx",
    exportPlan: "教案 .docx",
    exportExamTeacher: "试卷(教师版)",
    exportExamStudent: "试卷(学生版)",
    exportNote: "导出是内容等效,不是跟预览逐像素一致。",
  },
  keys: {
    toggle: "课件 / 教案",
    label: "键盘快捷键",
    approve: "确认应用",
    reject: "驳回更改",
    next: "下一页",
    prev: "上一页",
  },
};

// ═══════════════════════════════════════════════════════════════
// 语言表
// ═══════════════════════════════════════════════════════════════

export const LOCALES = ["en", "zh-HK", "zh-CN"] as const;
export type Locale = (typeof LOCALES)[number];

/** 给语言切换器用。native 用该语言自己的写法。 */
export const LOCALE_LABELS: Record<Locale, { native: string; short: string }> = {
  en: { native: "English", short: "EN" },
  "zh-HK": { native: "繁體中文", short: "繁" },
  "zh-CN": { native: "简体中文", short: "简" },
};

export const CATALOG: Record<Locale, Messages> = {
  en,
  "zh-HK": zhHK,
  "zh-CN": zhCN,
};

export const LOCALE_COOKIE = "pathpilot_locale";

export function normalizeLocale(value: string | undefined | null): Locale {
  return (LOCALES as readonly string[]).includes(value ?? "") ? (value as Locale) : "en";
}
