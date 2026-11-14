# AI Fluency 在项目开发中的应用

Anthropic 的 AI Fluency 4D 框架包括 Delegation（委托）、Description（描述）、Discernment（甄别）和 Diligence（尽责）。本项目主要将其用于团队与 AI 协作开发，而不是把四个概念当作产品功能。

**Delegation：**团队把代码草稿、重复性实现和问题定位交由 AI 辅助；需求取舍、架构决策、是否采纳修改以及最终验收仍由成员负责。AI 提供的是候选方案，而不是最终决定。

**Description：**我们不只在对话中临时交代要求，也把项目上下文和约束保存在仓库中。根目录 `AGENTS.md` 规定代理开始工作前应依次阅读生成设计、项目计划、需求研究、竞品分析和项目大纲；若必读文件缺失，应停止并询问，而不是自行猜测。前端的 `frontend/AGENTS.md` 还要求修改前查阅当前安装版本 Next.js 的对应文档。这样，设计规格、需求边界、技术约束和工作流程都能成为 AI 的持续上下文。此外，我们按任务使用专门的 agent skills：例如 `using-superpowers`（Superpowers）帮助选择适用流程，`test-driven-development` 约束修复先有失败测试再写实现；`frontend-design`、`design-taste-frontend` 和 `impeccable` 则辅助界面构思、避免模板化，并按现有设计规范检查和验证。仓库文件说明项目要什么、有哪些约束，Skills 说明具体任务怎么做。

**Discernment：**团队不会因为 AI 的解释听起来合理就直接接受结果。例如，一次接口校验修改导致 22 项测试失败，我们据此回退并重新评估；推荐功能则通过复现和回归测试，区分了预期规则与中文分词缺陷。AI 的方案需要由运行结果和项目要求检验。

**Diligence：**团队通过测试、浏览器验证和可追溯的修改记录检查 AI 辅助成果，并对最终交付负责。报告中也应如实区分 AI 辅助生成与成员主导的判断和审核，不把 AI 的输出直接等同于团队已验证的成果。

**参考：**Anthropic, [“AI Fluency: Framework and Foundations”](https://academy.claude.com/courses/ai-fluency-framework-foundations).
