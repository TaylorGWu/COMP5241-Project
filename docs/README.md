# 文档索引

本目录是 COMP5241 项目的文档中心。**每份文档都标了状态 —— 先看状态,再看内容。**

## 文档

| 文档 | 语言 | 状态 | 说明 |
| --- | --- | --- | --- |
| [requirements.md](requirements.md) | 🇨🇳 | 🟡 待验证 | **需求基线 v1.0** —— 已规范化,含验收标准与追溯矩阵;因未经真人访谈,全部需求标为「假设」 |
| [design/course-generation-design.md](design/course-generation-design.md) | 🇨🇳 | 🟡 待评审 | 设计规格(19 章 / 998 行):IR 数据模型、L1/L2 agent、资产生成、模型选型、API 契约、管理员端 |
| [PROJECT_PLAN.md](PROJECT_PLAN.md) · [中文译本](PROJECT_PLAN.zh.md) | 🇬🇧 / 🇨🇳 | 🟡 草案 | 项目计划。**含 54 项未勾选待办**;MoSCoW 与分工表原文标注为 "proposal",尚未团队确认 |
| [REQUIREMENTS_DESK_RESEARCH.md](REQUIREMENTS_DESK_RESEARCH.md) · [中文译本](REQUIREMENTS_DESK_RESEARCH.zh.md) | 🇬🇧 / 🇨🇳 | 🟡 证据来源 | 桌面研究 + 内部角色工作坊。**不是用户访谈证据** |
| [competitor_analysis/README.md](competitor_analysis/README.md) · [中文译本](competitor_analysis/README.zh.md) | 🇬🇧 / 🇨🇳 | 🟢 完成 | 4 家竞品分析,含证据边界与 limitations 声明 |
| [project_overivew.pdf](project_overivew.pdf) | 🇬🇧 | ⚪ 外部 | 课程官方大纲,非本组产出 |
| [prototypes/](prototypes/) | — | 🟡 草案 | 学生端 HTML 方向稿；教师端可运行原型位于 `frontend/` 与 `backend/`，不在本目录 |
| [prototypes/explorations/](prototypes/explorations/) | — | ⚪ 归档 | 5 个被否决的学生端探索版本,保留作过程证据 |
| [../AGENTS.md](../AGENTS.md) | 🇨🇳 | 🟡 待确认 | Agent 工作规则,尚未经团队会议确认 |

**语言约定:** 同时有中英两份的,**以英文原版为准**,两份需保持同步;只有中文的,中文即权威版本。
`project_overivew.pdf` 是课程官方文件,不翻译。

## 代码结构

```
backend/     FastAPI 后端(见 backend/README.md)
  app/schemas/ir.py    IR 数据模型 —— AI 的唯一输出契约
  app/llm/router.py    ModelRouter —— 模型调用的唯一入口
  app/api/deps.py      角色鉴权(后端强制)
  config/models.yaml   模型配置
  env.yaml.example     本地配置模板(复制为 env.yaml,已忽略)
  tests/               IR、agent、审核、持久化、接口与导出回归测试
frontend/    Next.js 教师端原型
  app/                 路由与页面
.venv/       本地 Python 3.12 环境(git 已忽略)
```

- 仓库工作规则:[../AGENTS.md](../AGENTS.md)
