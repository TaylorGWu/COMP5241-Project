import type { Locale } from "./i18n-config";

const en = {
  headline: ["Your teaching.", "AI assisted.", "You decide."],
  body: "Turn your syllabus into lessons, slides and activities. Review every change before it reaches your students.",
  create: "Create a course", how: "How it works",
  assurance: "Nothing publishes without your approval.",
  overview: "From syllabus to a lesson you can stand behind.",
  steps: [
    { title: "Create your course", body: "Add your syllabus, define your learners and set a clear learning goal." },
    { title: "Build your chapter", body: "Draft slides, teaching notes and questions from one teaching brief." },
    { title: "Review and refine", body: "Inspect each AI suggestion. Apply only the changes you choose." },
  ],
  tagline: ["AI drafts the lesson.", "You make it yours."],
  detail: "Your materials set the direction. Your judgment shapes the result.",
  faqTitle: "Before your first course.",
  faq: [
    { question: "Can I edit what AI creates?", answer: "Yes. Edit slides directly or ask AI to propose a change. AI suggestions wait for your confirmation before they alter the content." },
    { question: "Does AI publish the course for me?", answer: "No. Generated content stays in draft. The teacher reviews the content and decides when to publish." },
    { question: "What do I need to start?", answer: "Create a teacher account, then submit your teaching qualification. Administrator approval is required before you can create courses." },
    { question: "Can I use my own syllabus?", answer: "Yes. Add your syllabus and teaching materials to give the draft a clear scope and learning objectives. You still need to check the accuracy of generated content." },
    { question: "Can I export the materials?", answer: "Export slides as PowerPoint and teaching notes or assembled papers as Word documents. Exports preserve the content, but may use a different layout from the web preview." },
    { question: "Can students register too?", answer: "Students can create an account without qualification review. The student learning portal is being developed separately; account registration does not mean every learning feature is available yet." },
  ],
  close: "Bring your next lesson into focus.",
  student: "Here to learn?", studentLink: "Create a student account",
};
type HomeCopy = typeof en;
const tc: HomeCopy = {
  headline: ["你的教學。", "AI 協助。", "由你決定。"],
  body: "把課程大綱變成教案、課件與練習。每項修改，都由你審核後再交給學生。",
  create: "建立課程", how: "教學流程", assurance: "未經你的確認，內容不會自動發佈。",
  overview: "從課程大綱，到你放心教的內容。",
  steps: [
    { title: "建立你的課程", body: "加入大綱，確定學習對象，寫下清楚的學習目標。" },
    { title: "建立教學章節", body: "從同一份教學需求，起草課件、講稿與題目。" },
    { title: "審核與調整", body: "逐項查看 AI 建議，只採用你認可的修改。" },
  ],
  tagline: ["AI 起草課程。", "你賦予它教學價值。"], detail: "以你的材料為起點，用你的判斷把內容講清楚。", faqTitle: "開始備課之前。",
  faq: [
    { question: "可以修改 AI 產生的內容嗎？", answer: "可以直接編輯課件，或要求 AI 提議修改。AI 建議必須經你確認，才會改動內容。" },
    { question: "AI 會自動發佈課程嗎？", answer: "不會。產生的內容保留為草稿，由教師檢查並決定何時發佈。" },
    { question: "開始之前需要準備甚麼？", answer: "先建立教師帳號，再提交教學資質。管理員審核通過後，便可建立課程。" },
    { question: "可以使用自己的課程大綱嗎？", answer: "可以加入課程大綱與教學材料，讓草稿有清楚的範圍和學習目標。教師仍需核實產生內容的準確性。" },
    { question: "可以匯出教學材料嗎？", answer: "課件可匯出為 PowerPoint；教案與已組成的試卷可匯出為 Word。匯出保留內容，但版面不一定與網頁預覽完全一致。" },
    { question: "學生也可以註冊嗎？", answer: "學生可直接建立帳號，無需資質審核。學生學習端正獨立開發，註冊不代表所有學習功能已經接通。" },
  ],
  close: "讓下一堂課，講得更清楚。", student: "想開始學習？", studentLink: "建立學生帳號",
};
const sc: HomeCopy = {
  headline: ["你的教学。", "AI 协助。", "由你决定。"],
  body: "把课程大纲变成教案、课件与练习。每项修改，都由你审核后再交给学生。",
  create: "创建课程", how: "教学流程", assurance: "未经你的确认，内容不会自动发布。",
  overview: "从课程大纲，到你放心教的内容。",
  steps: [
    { title: "创建你的课程", body: "加入大纲，确定学习对象，写下清楚的学习目标。" },
    { title: "创建教学章节", body: "从同一份教学需求，起草课件、讲稿与题目。" },
    { title: "审核与调整", body: "逐项查看 AI 建议，只采用你认可的修改。" },
  ],
  tagline: ["AI 起草课程。", "你赋予它教学价值。"], detail: "以你的材料为起点，用你的判断把内容讲清楚。", faqTitle: "开始备课之前。",
  faq: [
    { question: "可以修改 AI 生成的内容吗？", answer: "可以直接编辑课件，或要求 AI 提议修改。AI 建议必须经你确认，才会改动内容。" },
    { question: "AI 会自动发布课程吗？", answer: "不会。生成的内容保留为草稿，由教师检查并决定何时发布。" },
    { question: "开始之前需要准备什么？", answer: "先创建教师账号，再提交教学资质。管理员审核通过后，便可创建课程。" },
    { question: "可以使用自己的课程大纲吗？", answer: "可以加入课程大纲与教学材料，让草稿有清楚的范围和学习目标。教师仍需核实生成内容的准确性。" },
    { question: "可以导出教学材料吗？", answer: "课件可导出为 PowerPoint；教案与已组成的试卷可导出为 Word。导出保留内容，但版式不一定与网页预览完全一致。" },
    { question: "学生也可以注册吗？", answer: "学生可直接创建账号，无需资质审核。学生学习端正独立开发，注册不代表所有学习功能已经接通。" },
  ],
  close: "让下一堂课，讲得更清楚。", student: "想开始学习？", studentLink: "创建学生账号",
};
export function homepageCopy(locale: Locale): HomeCopy { return locale === "zh-HK" ? tc : locale === "zh-CN" ? sc : en; }
