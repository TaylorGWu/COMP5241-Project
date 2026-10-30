/** Labels describe the visible order, never infer a page number from its ID. */
export const workspaceCopy = {
  en: { slide: (n: number) => `Slide ${n}`, count: (n: number, total: number) => `Slide ${n} of ${total}`, target: "New request target", hint: "New requests use this selection. Existing plans keep their original target.", proposals: "Proposed changes", empty: "No slide selected", questions: "Questions", paper: "Assessment" },
  "zh-HK": { slide: (n: number) => `第 ${n} 頁`, count: (n: number, total: number) => `第 ${n} / ${total} 頁`, target: "新要求的修改對象", hint: "新要求使用目前選取的內容，已有計劃保留原本的修改對象。", proposals: "待確認改動", empty: "尚未選取幻燈片", questions: "題目", paper: "評估" },
  "zh-CN": { slide: (n: number) => `第 ${n} 页`, count: (n: number, total: number) => `第 ${n} / ${total} 页`, target: "新请求的修改对象", hint: "新请求使用当前选中的内容，已有计划保留原本的修改对象。", proposals: "待确认改动", empty: "尚未选中幻灯片", questions: "题目", paper: "评估" },
};
