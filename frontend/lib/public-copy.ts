import type { Locale } from "./i18n-config";

const en = {
  dashboard: "Dashboard",
  showShort: "Show", hideShort: "Hide", unsubmitted: "Qualification needed", unsubmittedTitle: "Your teacher account is ready.", unsubmittedBody: "Upload your teaching qualification when you're ready. You can create courses once an administrator approves it.",
  login: "Log in", start: "Get started", workspace: "Open workspace", logout: "Sign out", home: "Back to home",
  heroImageAlt: "Two educators preparing a lesson together.", heroImageNote: "AI-generated illustrative scene.",
  heroA: "Good teaching.", heroB: "Made tangible.", heroBody: "Build focused software engineering lessons from your materials. Let AI draft, then review every change.",
  teacherCta: "Start teaching", studentCta: "I'm here to learn", explore: "See how it works", example: "Interactive example · no AI request", exampleTitle: "Make an idea easier to understand.", exampleTopic: "Problem solving", exampleSlideLabel: "Lesson preview",
  brief: "The teaching brief", draft: "The lesson takes shape", review: "Your judgment, built in", exampleNote: "Illustrative content. Nothing here changes a real course.",
  briefText: "Introduce problem solving to beginners. Use a long registration queue to explain how to understand a problem, try a solution and check the result.", material: "lesson-brief.md", objective: "Apply a simple problem-solving process to an everyday situation.",
  slideTitle: "Start with the problem.", phaseUnderstand: "Understand", phaseTry: "Try a solution", phaseCheck: "Check the result", phaseCues: ["What's causing the wait?", "Change one thing", "Did waiting time fall?"], phaseUnderstandBody: "Observe the queue and ask people where they get stuck.", phaseTryBody: "Test a simpler sign-up form with a small group.", phaseCheckBody: "Compare the results, then decide what to adjust.",
  suggestion: "Connect the idea to everyday life", before: "Find a problem, choose a solution and evaluate it.", after: "Observe the queue, test a simpler sign-up form, then compare waiting times.", accept: "Accept change", accepted: "Change accepted", reason: "One familiar situation connects the explanation, activity and check for understanding.", replay: "Replay example", next: "Next step", demoLabel: "Explore the teaching workflow",
  teacherTitle: "Less time assembling.\nMore room to teach.", teacherBody: "Start with your materials and learning objectives. Refine slides, speaker notes and questions in one workspace, then review every proposed change before it reaches students.",
  studentTitle: "A clear place\nto begin.", studentBody: "Create your student account without an approval step. The learning portal is being developed separately; your account is ready to connect when it arrives.",
  source: "Grounded in your material", human: "Reviewed by a teacher", editable: "Built to be revised", finalTitle: "Bring your next lesson to life.", finalBody: "A focused workspace for the ideas worth understanding.", footer: "A COMP5241 project. Thoughtfully built, still evolving.",
  welcome: "Good to see you again.", loginBody: "One account. The right workspace for your role.", email: "Email address", password: "Password", name: "Full name", confirm: "Confirm password", show: "Show password", hide: "Hide password", noAccount: "New to Coursework?", hasAccount: "Already have an account?", create: "Create account", waiting: "Please wait…", passwordHint: "Use 15–128 characters. A memorable passphrase works well.", mismatch: "The passwords do not match.", connection: "Something went wrong. Please try again.",
  join: "Make room for\nbetter learning.", joinBody: "Choose the account that fits what you want to do.", student: "Student", instructor: "Teacher", studentBlurb: "Start with an account. No approval needed.", instructorBlurb: "Submit your teaching credentials for administrator review.",
  studentRegister: "Your next chapter starts here.", teacherRegister: "Your expertise belongs here.", teacherRegisterBody: "Create an account and upload your teaching credentials. An administrator will review your application before you can create courses.", studentRegisterBody: "Create your student account and get ready for the learning portal.", switchRole: "Choose a different role", qualification: "Teaching qualification", qualificationHint: "Upload a teaching certificate or an institutional credential. PDF, JPG or PNG, up to 5 MB. Only you and administrators can download it.", chooseFile: "Choose a document", fileSize: "This file is larger than 5 MB.", fileType: "Use a PDF, JPG or PNG file.", fileEmpty: "Choose a non-empty document.", fileRequired: "Please upload your teaching qualification.", submitApplication: "Submit application", localNote: "Local prototype · email addresses are not yet verified.",
  authSideTitle: "A lesson is more\nthan a slide.", authSideBody: "Make the idea clear. Give it an example. Leave the final judgment with the teacher.", authSideQuote: "AI starts the draft.\nYou make it worth teaching.",
  pendingTitle: "Your application is in review.", pendingBody: "Your teaching qualification has been submitted. An administrator needs to approve it before your teacher workspace becomes available.", rejectedTitle: "A little more information is needed.", rejectedBody: "Review the feedback below, then upload an updated document to submit your application again.", reasonLabel: "Administrator feedback", refresh: "Check status", submitted: "Submitted for review", download: "Download qualification", resubmit: "Resubmit application", approved: "Approved", pending: "Pending review", rejected: "Needs revision",
  studentWelcome: "You're in. Make yourself at home.", studentWelcomeBody: "Your student account is ready. The learning portal is being developed separately; courses and progress will appear here once that integration is available.", accountLabel: "Your account", studentReady: "Student account active", noCourses: "No learning activity yet", noCoursesBody: "We won't fill this space with pretend courses or progress. Your learning will start here when the portal is connected.",
  adminTitle: "A thoughtful start for every teacher.", adminBody: "Review teaching credentials before granting access to the course workspace.", applications: "Teacher applications", noApplications: "You're all caught up.", noApplicationsBody: "New teacher applications will appear here. There are no applications to review right now.", approve: "Approve teacher", reject: "Request revision", rejectHint: "Explain what needs to be corrected or supplied.", reviewRequired: "Add a reason before requesting a revision.", filterAll: "All applications", reviewSaved: "Review saved.", reviewDate: "Submitted", retry: "Try again", sessionCheck: "Checking your session…", roleNotice: "Administrator accounts are created locally. Public registration is for students and teachers only.",
};
export type PublicCopy = typeof en;

const zh: PublicCopy = {
  ...en,
  dashboard: "進入後台",
  login: "登入", start: "開始使用", workspace: "進入工作台", logout: "登出", home: "返回首頁",
  heroImageAlt: "兩位教育工作者一起備課。", heroImageNote: "AI 生成場景示意圖。",
  heroA: "好的教學，", heroB: "讓理解發生。", heroBody: "把你掌握的知識，變成他人能理解的課程。專注軟件工程短課，讓 AI 起草，由你決定。",
  teacherCta: "開始備課", studentCta: "我要學習", explore: "看看如何運作", example: "互動示例 · 不會呼叫 AI", exampleTitle: "讓抽象概念，變得好理解。", exampleTopic: "問題解決", exampleSlideLabel: "課件預覽",
  brief: "描述教學需求", draft: "讓課程成形", review: "由你作出判斷", exampleNote: "以下為示例內容，不會更改真實課程。",
  briefText: "為初學者設計一堂「解決問題」短課。以報名排隊太久為例，說明如何釐清問題、嘗試方案和檢查效果。", material: "教學需求.md", objective: "運用簡單步驟，處理生活中的實際問題。",
  slideTitle: "先理解問題，再尋找答案。", phaseUnderstand: "釐清問題", phaseTry: "嘗試方案", phaseCheck: "檢查效果", phaseCues: ["大家卡在哪裏？", "先改一件事", "等候時間有減少嗎？"], phaseUnderstandBody: "觀察排隊流程，詢問參加者遇到的困難。", phaseTryBody: "讓一小組人試用更簡單的報名表。", phaseCheckBody: "比較結果，再決定保留或調整方案。",
  suggestion: "把概念放進日常情境", before: "找出問題，提出方案，再評估成效。", after: "觀察排隊情況，試用簡化報名表，再比較等候時間。", accept: "確認採用", accepted: "已確認採用", reason: "以熟悉的情境串連講解、練習與檢查，讓學生知道如何運用。", replay: "重播示例", next: "下一步", demoLabel: "探索教學流程",
  teacherTitle: "少一點拼湊，\n多一點教學。", teacherBody: "從你的材料與學習目標出發，在同一個工作台調整課件、講稿和題目。每項 AI 修改都由你審核，才會成為課程的一部分。",
  studentTitle: "找到清晰的\n學習起點。", studentBody: "學生帳號無需審核即可註冊。學習端正獨立開發，接通後便可使用你的帳號開始學習。",
  source: "以你的材料為依據", human: "教師確認後才生效", editable: "隨時可以再修改", finalTitle: "讓下一堂課，真正講得明白。", finalBody: "為值得理解的知識，留一個專注的空間。", footer: "COMP5241 課程項目 · 認真打磨，持續完善。",
  welcome: "很高興再次見到你。", loginBody: "一個帳號，進入屬於你的工作空間。", email: "電郵地址", password: "密碼", name: "姓名", confirm: "確認密碼", show: "顯示密碼", hide: "隱藏密碼", noAccount: "第一次使用 Coursework？", hasAccount: "已有帳號？", create: "建立帳號", waiting: "請稍候…", passwordHint: "使用 15–128 個字元，建議選用容易記住的長密碼。", mismatch: "兩次輸入的密碼不一致。", connection: "暫時無法完成，請重試。",
  join: "為更好的學習，\n留一個位置。", joinBody: "選擇符合你使用目的的帳號。", student: "學生", instructor: "教師", studentBlurb: "直接建立帳號，無需審核。", instructorBlurb: "提交教學資質，由管理員審核。",
  studentRegister: "你的下一章，從這裏開始。", teacherRegister: "讓你的專長，成為一堂好課。", teacherRegisterBody: "建立帳號並上傳教學資質，管理員審核通過後即可建立課程。", studentRegisterBody: "建立學生帳號，為學習端接通做好準備。", switchRole: "選擇其他身份", qualification: "教學資質", qualificationHint: "請上傳教師證明或院校資質文件。支援 PDF、JPG、PNG，最多 5 MB，僅本人及管理員可下載。", chooseFile: "選擇文件", fileSize: "文件超過 5 MB。", fileType: "請使用 PDF、JPG 或 PNG 文件。", fileEmpty: "請選擇非空白文件。", fileRequired: "請上傳教學資質文件。", submitApplication: "提交申請", localNote: "本機原型 · 暫未驗證電郵地址。",
  authSideTitle: "一堂課，\n不只是一頁投影片。", authSideBody: "把概念講清楚，用例子幫助理解，讓教師保留最後的判斷。", authSideQuote: "AI 起草，\n你讓它值得教。",
  pendingTitle: "你的申請正在審核中。", pendingBody: "教學資質已提交。管理員審核通過後，你便可以進入教師工作台。", rejectedTitle: "還需要補充一點資料。", rejectedBody: "請查看以下回饋，上傳更新的資質文件後重新提交。", reasonLabel: "管理員回饋", refresh: "查詢狀態", submitted: "已提交審核", download: "下載資質文件", resubmit: "重新提交申請", approved: "已通過", pending: "待審核", rejected: "需要補充",
  studentWelcome: "帳號就緒，歡迎加入。", studentWelcomeBody: "你的學生帳號已建立。學習端正獨立開發，整合後便可在這裏查看課程和進度。", accountLabel: "你的帳號", studentReady: "學生帳號已啟用", noCourses: "暫時沒有學習活動", noCoursesBody: "這裏不會放虛構的課程或進度。學習端接通後，你的學習將從這裏開始。",
  adminTitle: "讓每位教師，都有可靠的起點。", adminBody: "在開放課程工作台前，先審核教師提交的教學資質。", applications: "教師申請", noApplications: "目前沒有待辦申請。", noApplicationsBody: "新的教師申請會顯示在這裏。現在沒有需要審核的項目。", approve: "通過申請", reject: "要求補交", rejectHint: "請說明需要更正或補充哪些資料。", reviewRequired: "要求補交前，請先填寫原因。", filterAll: "全部申請", reviewSaved: "審核結果已儲存。", reviewDate: "提交時間", retry: "重試", sessionCheck: "正在確認登入狀態…", roleNotice: "管理員帳號由本機管理命令建立，公開註冊僅適用於學生與教師。",
};

const cn: PublicCopy = {
  ...zh,
  dashboard: "进入后台",
  login: "登录", start: "开始使用", workspace: "进入工作台", logout: "退出登录", home: "返回首页",
  heroImageAlt: "两位教育工作者一起备课。", heroImageNote: "AI 生成场景示意图。",
  heroA: "好的教学，", heroB: "让理解发生。", heroBody: "把你掌握的知识，变成他人能理解的课程。专注软件工程短课，让 AI 起草，由你决定。",
  teacherCta: "开始备课", studentCta: "我要学习", explore: "看看如何运作", example: "互动示例 · 不会调用 AI", exampleTitle: "让抽象概念，变得好理解。", exampleTopic: "问题解决", exampleSlideLabel: "课件预览", brief: "描述教学需求", draft: "让课程成形", review: "由你作出判断", exampleNote: "以下为示例内容，不会更改真实课程。",
  briefText: "为初学者设计一堂「解决问题」短课。以报名排队太久为例，说明如何明确问题、尝试方案和检查效果。", material: "教学需求.md", objective: "运用简单步骤，处理生活中的实际问题。", slideTitle: "先理解问题，再寻找答案。", phaseUnderstand: "明确问题", phaseTry: "尝试方案", phaseCheck: "检查效果", phaseCues: ["大家卡在哪里？", "先改一件事", "等候时间减少了吗？"], phaseUnderstandBody: "观察排队流程，询问参加者遇到的困难。", phaseTryBody: "让一小组人试用更简单的报名表。", phaseCheckBody: "比较结果，再决定保留或调整方案。", suggestion: "把概念放进日常情境", before: "找出问题，提出方案，再评估效果。", after: "观察排队情况，试用简化报名表，再比较等候时间。", accept: "确认采用", accepted: "已确认采用", reason: "以熟悉的情境串联讲解、练习与检查，让学生知道如何运用。", replay: "重播示例", next: "下一步", demoLabel: "探索教学流程",
  teacherTitle: "少一点拼凑，\n多一点教学。", teacherBody: "从你的材料与学习目标出发，在同一个工作台调整课件、讲稿和题目。每项 AI 修改都由你审核，才会成为课程的一部分。", studentTitle: "找到清晰的\n学习起点。", studentBody: "学生账号无需审核即可注册。学习端正独立开发，接通后便可使用你的账号开始学习。", source: "以你的材料为依据", human: "教师确认后才生效", editable: "随时可以再修改", finalTitle: "让下一堂课，真正讲得明白。", finalBody: "为值得理解的知识，留一个专注的空间。", footer: "COMP5241 课程项目 · 认真打磨，持续完善。",
  welcome: "很高兴再次见到你。", loginBody: "一个账号，进入属于你的工作空间。", email: "电子邮箱", password: "密码", name: "姓名", confirm: "确认密码", show: "显示密码", hide: "隐藏密码", noAccount: "第一次使用 Coursework？", hasAccount: "已有账号？", create: "创建账号", waiting: "请稍候…", passwordHint: "使用 15–128 个字符，建议选用容易记住的长密码。", mismatch: "两次输入的密码不一致。", connection: "暂时无法完成，请重试。",
  join: "为更好的学习，\n留一个位置。", joinBody: "选择符合你使用目的的账号。", student: "学生", instructor: "教师", studentBlurb: "直接创建账号，无需审核。", instructorBlurb: "提交教学资质，由管理员审核。", studentRegister: "你的下一章，从这里开始。", teacherRegister: "让你的专长，成为一堂好课。", teacherRegisterBody: "创建账号并上传教学资质，管理员审核通过后即可创建课程。", studentRegisterBody: "创建学生账号，为学习端接通做好准备。", switchRole: "选择其他身份", qualification: "教学资质", qualificationHint: "请上传教师证明或院校资质文件。支持 PDF、JPG、PNG，最多 5 MB，仅本人及管理员可下载。", chooseFile: "选择文件", fileSize: "文件超过 5 MB。", fileType: "请使用 PDF、JPG 或 PNG 文件。", fileEmpty: "请选择非空白文件。", fileRequired: "请上传教学资质文件。", submitApplication: "提交申请", localNote: "本机原型 · 暂未验证邮箱地址。",
  authSideTitle: "一堂课，\n不只是一页幻灯片。", authSideBody: "把概念讲清楚，用例子帮助理解，让教师保留最后的判断。", authSideQuote: "AI 起草，\n你让它值得教。", pendingTitle: "你的申请正在审核中。", pendingBody: "教学资质已提交。管理员审核通过后，你便可以进入教师工作台。", rejectedTitle: "还需要补充一点资料。", rejectedBody: "请查看以下反馈，上传更新的资质文件后重新提交。", reasonLabel: "管理员反馈", refresh: "查询状态", submitted: "已提交审核", download: "下载资质文件", resubmit: "重新提交申请", approved: "已通过", pending: "待审核", rejected: "需要补充", studentWelcome: "账号就绪，欢迎加入。", studentWelcomeBody: "你的学生账号已创建。学习端正独立开发，整合后便可在这里查看课程和进度。", accountLabel: "你的账号", studentReady: "学生账号已启用", noCourses: "暂时没有学习活动", noCoursesBody: "这里不会放虚构的课程或进度。学习端接通后，你的学习将从这里开始。", adminTitle: "让每位教师，都有可靠的起点。", adminBody: "在开放课程工作台前，先审核教师提交的教学资质。", applications: "教师申请", noApplications: "目前没有待办申请。", noApplicationsBody: "新的教师申请会显示在这里。现在没有需要审核的项目。", approve: "通过申请", reject: "要求补交", rejectHint: "请说明需要更正或补充哪些资料。", reviewRequired: "要求补交前，请先填写原因。", filterAll: "全部申请", reviewSaved: "审核结果已保存。", reviewDate: "提交时间", retry: "重试", sessionCheck: "正在确认登录状态…", roleNotice: "管理员账号由本机管理命令创建，公开注册仅适用于学生与教师。",
};

const accountOverrides: Record<Locale, Partial<PublicCopy>> = {
  en: {
    welcome: "Log in to Coursework", loginBody: "Pick up where you left off.",
    join: "Create your account", studentRegister: "Create a student account", teacherRegister: "Create a teacher account",
    instructorBlurb: "Create an account, then submit your teaching qualification.",
    teacherRegisterBody: "Register first, then submit your qualification. Administrator approval enables course creation.",
    passwordHint: "15-128 characters. Use a memorable passphrase.",
  },
  "zh-HK": {
    welcome: "登入 Coursework", loginBody: "繼續你的教學與學習。", join: "建立你的帳號", studentRegister: "建立學生帳號", teacherRegister: "建立教師帳號",
    instructorBlurb: "先建立帳號，再提交教學資質。", teacherRegisterBody: "先完成註冊，之後再上傳資質。審核通過後即可建立課程。",
    showShort: "顯示", hideShort: "隱藏", unsubmitted: "尚未提交資質", unsubmittedTitle: "教師帳號已建立。", unsubmittedBody: "你可以稍後上傳教學資質。管理員審核通過後，即可建立課程。", passwordHint: "使用 15-128 個字元，建議選用容易記住的長密碼。",
  },
  "zh-CN": {
    welcome: "登录 Coursework", loginBody: "继续你的教学与学习。", join: "创建你的账号", studentRegister: "创建学生账号", teacherRegister: "创建教师账号",
    instructorBlurb: "先创建账号，再提交教学资质。", teacherRegisterBody: "先完成注册，之后再上传资质。审核通过后即可创建课程。",
    showShort: "显示", hideShort: "隐藏", unsubmitted: "尚未提交资质", unsubmittedTitle: "教师账号已创建。", unsubmittedBody: "你可以稍后上传教学资质。管理员审核通过后，即可创建课程。", passwordHint: "使用 15-128 个字符，建议选用容易记住的长密码。",
  },
};

export function publicCopy(locale: Locale): PublicCopy { return { ...(locale === "zh-HK" ? zh : locale === "zh-CN" ? cn : en), ...accountOverrides[locale] }; }
