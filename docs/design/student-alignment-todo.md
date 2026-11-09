# 学生端对齐教师端 —— 待办清单（下一轮从这里开始）

分支：codex/team-final-integration   停止点提交：643a26c
状态：工作区已跟踪文件干净，全套测试绿（后端 479 / 门户 15 / 学生端 6 / 主题 9）

## 1) 目录工具条：去掉卡片容器（已验证可行）
`.portal .course-catalogue-toolbar`：border 0、background transparent、padding 0，
搜索框自己带边框落在页面底色上（和教师端一致）。

## 2) 下拉框去原生（已验证可行）
`.portal .course-catalogue-filter select`：
appearance: none; -webkit-appearance: none;
padding-right: 34px；background-image 用内联 SVG 画 chevron。
实测 computed appearance = none，截图正常。

## 3) tab 行合并「数量」（上次在这里翻车）
把 “My courses” 标题 + “2 courses” 计数并进 `.portal-tabs-row` 右侧，
删掉 `.portal-section-heading` 与 `.course-catalogue-results`。
⚠️ 必须同时改 tools/ui-verify/student-next-step.cjs：
   - block 1 / block 2 断言 `getByRole('heading', {name:'My courses'})`
   - block 6 依赖 `.course-catalogue-results p`
   改完立刻跑 6/6，再提交。

## 4) 课程页章节行 → 教师端单行结构（未做，上次写坏 CSS 已回滚）
`01` 徽章 · 标题 + 副标题 · 右侧「Completed 徽章 / 进度 + 箭头入口」。
改法：整块替换 `.portal-chapter-list > li` 的 JSX 与 CSS，不要内联插入。

## 5) 章节页底部空白（未定位）
先分别打印 .portal-player / .portal-side / .portal-reading / body 的 scrollHeight，
确定谁多出来再改一处。目标：滚动到底 = 内容底。

## 6) 其余待对齐
- 侧栏卡片（学习目标 / 邀请码）用教师端卡片规格
- 练习区折叠卡 → 教师端 Questions 面板
- 空状态 → .course-library-empty 规格

## 教训
- CSS 改动必须整块替换 + 改完立即 `tsc --noEmit` 与该页截图；上次内联插入导致样式表语法错误，整站掉样式。
- 动 UI 前先看 ui-verify 里哪些断言依赖它，改代码的同时改断言。
