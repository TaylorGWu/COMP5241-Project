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

**包管理器统一用 npm**(本机 pnpm 未在 PATH 中)。

## 阅读顺序(新成员)

| # | 读什么 | 耗时 | 得到什么 |
| --- | --- | --- | --- |
| 1 | [project_overivew.pdf](project_overivew.pdf) | 20 min | 课程要求与评分标准 |
| 2 | [PROJECT_PLAN.md](PROJECT_PLAN.md) | 15 min | 我们打算怎么做 |
| 3 | [requirements.md](requirements.md) | 20 min | 要做什么、优先级、验收标准 |
| 4 | [design/course-generation-design.md](design/course-generation-design.md) | 60 min | 怎么做 |
| 5 | [competitor_analysis/README.md](competitor_analysis/README.md) | 15 min | 为什么这么做 |

## 状态图例

| 标记 | 含义 |
| --- | --- |
| 🟢 完成 | 内容完整,可用作论证依据 |
| 🟡 草案 / 待验证 / 待评审 | **不得当作已确认的结论引用** |
| ⚪ 外部 / 归档 | 非本组产出,或已废弃的版本 |

## ⚠️ 已知的文档不一致(待团队确认)

| # | 不一致 | 现状与处理 |
| --- | --- | --- |
| 1 | **组员人数** | 课程大纲写 "group of **4** members";本组实为 **5 人**,`PROJECT_PLAN.md` 与 `REQUIREMENTS_DESK_RESEARCH.md` 均按 5 人撰写。进度会或答辩如被问,需能说明 |
| 2 | **数据模型** | `PROJECT_PLAN.md` 的 Core data model 早于设计规格,未含 `projects` / `artifacts` / `assets` / `patches` 等表。**以 [design](design/course-generation-design.md) §5 为准** |
| 3 | **技术栈** | `PROJECT_PLAN.md` 未含 pgvector、Redis + ARQ worker、对象存储、Remotion。**以 [design](design/course-generation-design.md) §16 为准** |
| 4 | **视频的优先级** | 设计规格把视频列为 Could(成本最高、不对应评分顶档要求),`PROJECT_PLAN.md` 未单列 |
| 5 | **管理员是否 Must** | 设计规格把管理员三模块列为 Must(交付物要求 Admin 用户手册),但 `PROJECT_PLAN.md` 的 MoSCoW **Must 里没有管理员** |

## 证据边界(重要)

- 本项目**尚未进行真人访谈**,也没有组外可用性测试。
- 因此 [requirements.md](requirements.md) 中所有需求标为「假设」,**不得描述为已验证的用户需求**。
- 竞品分析覆盖 4 家平台的**公开资料**,不代表其真实产品行为 —— 未建立账号、未实际使用。
- 内部角色工作坊是**团队内部的假设生成**,不是用户研究。

## 相关

- 仓库工作规则:[../AGENTS.md](../AGENTS.md)
