import type { Locale } from "./i18n-config";

export type TeacherProfile = {
  name: string; bio: string; institution: string; independent: boolean; position: string;
  university: string; degree: string; experience: string; subjects: string[]; otherSubject: string;
  hasAvatar: boolean; avatarVersion: string | null;
};
export function profilePayload(p: TeacherProfile) {
  return { name: p.name, bio: p.bio, institution: p.independent ? "" : p.institution,
    independent: p.independent, position: p.position, university: p.university,
    degree: p.degree, experience: p.experience, subjects: p.subjects,
    otherSubject: p.subjects.includes("other") ? p.otherSubject : "" };
}

const en = {
  loading: "Loading profile…", leave: "Leave this page and discard your unsaved changes?",
  title: "Teacher profile", intro: "Introduce yourself, your education and what you teach.",
  optional: "Only your name is required. These details are visible to you and administrators, not published to students.",
  personal: "Personal information", education: "Education", teaching: "Teaching background", photo: "Profile photo",
  photoHint: "JPG or PNG, up to 5 MB. We resize your photo and remove embedded metadata.",
  choosePhoto: "Choose photo", savePhoto: "Save photo", removePhoto: "Remove photo", cancelPhoto: "Cancel selection",
  photoSaved: "Photo saved.", photoRemoved: "Photo removed.", photoError: "Choose a non-empty JPG or PNG photo up to 5 MB.",
  name: "Full name", bio: "Personal introduction", university: "University / college", degree: "Highest qualification",
  institution: "Current institution", independent: "Independent teacher", position: "Job title / role", experience: "Teaching experience",
  subjects: "Subjects you teach", chooseSubjects: "Choose subjects", search: "Search subjects", done: "Done", noMatch: "No matching subjects. Choose Other to add your own.",
  other: "Other subject", select: "Not specified", save: "Save changes", saving: "Saving…", discard: "Discard changes",
  saved: "Profile saved.", unsaved: "You have unsaved changes.", unchanged: "No unsaved changes.",
  loadError: "Your profile could not be loaded. Try again.", retry: "Try again", error: "Could not save. Your changes are still here. Try again.",
  qualification: "Qualification review", qualificationHint: "Your profile does not replace qualification review. Course creation requires administrator approval.",
  teacherAccount: "Teacher account",
  viewStatus: "View qualification status", privatePhoto: "Your photo is private to you and administrators.",
  viewProfile: "View teacher profile", hideProfile: "Hide teacher profile", empty: "Not provided",
  refresh: "Refresh status", checking: "Checking…", stillPending: "Still in review. Checked just now.",
  refreshedRejected: "Review updated. See the feedback below.",
  degrees: { secondary: "Secondary education", diploma: "Diploma / associate degree", bachelor: "Bachelor's degree", master: "Master's degree", doctorate: "Doctorate", other: "Other" },
  years: { "0-2": "0-2 years", "3-5": "3-5 years", "6-10": "6-10 years", "11+": "11+ years" },
  subjectNames: { "software-engineering": "Software engineering", programming: "Programming", "web-development": "Web development", databases: "Databases", testing: "Software testing", systems: "Systems and networks", security: "Cybersecurity", "data-science": "Data science", other: "Other" },
};
type Copy = { [K in keyof typeof en]: typeof en[K] extends string ? string : { [P in keyof typeof en[K]]: string } };
const zh: Copy = {
  loading: "正在載入資料…", leave: "離開此頁並放棄尚未儲存的修改？",
  title: "教師資料", intro: "介紹你的背景、教育經歷與教學專長。", optional: "僅姓名為必填。資料只供你與管理員查看，不會公開給學生。",
  personal: "關於你", education: "教育背景", teaching: "任教與專長", photo: "個人照片", photoHint: "支援 JPG、PNG，最多 5 MB。照片會縮小並移除內嵌元資料。",
  choosePhoto: "選擇照片", savePhoto: "儲存照片", removePhoto: "移除照片", cancelPhoto: "取消選擇", photoSaved: "照片已儲存。", photoRemoved: "照片已移除。", photoError: "請選擇非空白的 JPG 或 PNG 照片，最多 5 MB。",
  name: "姓名", bio: "個人簡介", university: "畢業院校", degree: "最高學歷", institution: "目前任教院校／機構", independent: "獨立教師", position: "職稱／崗位", experience: "教學年資",
  subjects: "擅長科目", chooseSubjects: "選擇科目", search: "搜尋科目", done: "完成選擇", noMatch: "沒有相符的科目。可選擇「其他」自行補充。", other: "其他科目", select: "暫不填寫",
  save: "儲存修改", saving: "正在儲存…", discard: "放棄修改", saved: "資料已儲存。", unsaved: "有尚未儲存的修改。", unchanged: "所有修改均已儲存。", loadError: "暫時無法載入資料，請重試。", retry: "重試", error: "未能儲存，修改仍保留在此頁，請重試。",
  qualification: "資質審核", qualificationHint: "個人資料不能代替資質審核。管理員審核通過後，才可建立課程。", viewStatus: "查看資質狀態", privatePhoto: "照片只供你與管理員查看。",
  teacherAccount: "教師帳號",
  viewProfile: "查看教師資料", hideProfile: "收起教師資料", empty: "未填寫", refresh: "重新查詢", checking: "正在查詢…", stillPending: "仍在審核中，剛剛已查詢。", refreshedRejected: "審核狀態已更新，請查看以下回饋。",
  degrees: { secondary: "中學", diploma: "文憑／副學士", bachelor: "學士", master: "碩士", doctorate: "博士", other: "其他" },
  years: { "0-2": "0–2 年", "3-5": "3–5 年", "6-10": "6–10 年", "11+": "11 年或以上" },
  subjectNames: { "software-engineering": "軟件工程", programming: "程式設計", "web-development": "網頁開發", databases: "資料庫", testing: "軟件測試", systems: "系統與網絡", security: "網絡安全", "data-science": "數據科學", other: "其他" },
};
const cn: Copy = {
  ...zh, loading: "正在加载资料…", leave: "离开此页并放弃尚未保存的修改？",
  title: "教师资料", intro: "介绍你的背景、教育经历与教学专长。", optional: "仅姓名为必填。资料只供你与管理员查看，不会公开给学生。",
  personal: "关于你", education: "教育背景", teaching: "任教与专长", photo: "个人照片", photoHint: "支持 JPG、PNG，最多 5 MB。照片会缩小并移除内嵌元数据。",
  choosePhoto: "选择照片", savePhoto: "保存照片", removePhoto: "移除照片", cancelPhoto: "取消选择", photoSaved: "照片已保存。", photoRemoved: "照片已移除。", photoError: "请选择非空白的 JPG 或 PNG 照片，最多 5 MB。",
  name: "姓名", bio: "个人简介", university: "毕业院校", degree: "最高学历", institution: "目前任教院校／机构", independent: "独立教师", position: "职称／岗位", experience: "教学年限",
  subjects: "擅长科目", chooseSubjects: "选择科目", search: "搜索科目", done: "完成选择", noMatch: "没有匹配的科目。可选择“其他”自行补充。", other: "其他科目", select: "暂不填写",
  save: "保存修改", saving: "正在保存…", discard: "放弃修改", saved: "资料已保存。", unsaved: "有尚未保存的修改。", unchanged: "所有修改均已保存。", loadError: "暂时无法加载资料，请重试。", retry: "重试", error: "未能保存，修改仍保留在此页，请重试。",
  qualification: "资质审核", qualificationHint: "个人资料不能代替资质审核。管理员审核通过后，才可创建课程。", viewStatus: "查看资质状态", privatePhoto: "照片只供你与管理员查看。",
  teacherAccount: "教师账号",
  viewProfile: "查看教师资料", hideProfile: "收起教师资料", empty: "未填写", refresh: "刷新状态", checking: "正在查询…", stillPending: "仍在审核中，刚刚已查询。", refreshedRejected: "审核状态已更新，请查看以下反馈。",
  degrees: { secondary: "中学", diploma: "文凭／副学士", bachelor: "学士", master: "硕士", doctorate: "博士", other: "其他" },
  years: { "0-2": "0-2 年", "3-5": "3-5 年", "6-10": "6-10 年", "11+": "11 年或以上" },
  subjectNames: { "software-engineering": "软件工程", programming: "程序设计", "web-development": "网页开发", databases: "数据库", testing: "软件测试", systems: "系统与网络", security: "网络安全", "data-science": "数据科学", other: "其他" },
};
export function teacherProfileCopy(locale: Locale): Copy { return locale === "zh-HK" ? zh : locale === "zh-CN" ? cn : en; }
