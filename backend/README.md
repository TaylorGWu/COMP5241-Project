# backend — FastAPI 后端

结构与设计规格 `docs/design/course-generation-design.md` 对应。

## 运行

```bash
cd backend
cp env.yaml.example env.yaml   # 填入密钥(env.yaml 已被 git 忽略)
../.venv/bin/pip install -r requirements.txt
../.venv/bin/uvicorn app.main:app --reload
```

章节课件中的带文字示意图由 Mermaid CLI 渲染为 PNG，同一张图用于网页预览和 PPTX 导出。
此功能需要 Node.js 和 Chrome/Chromium。首次运行在 `backend/` 执行
`PUPPETEER_SKIP_DOWNLOAD=1 npm ci`；如果浏览器不在常见安装位置，设置
`PUPPETEER_EXECUTABLE_PATH`。渲染失败时单张图会显示明确占位，其余页面仍可导出。

健康检查:`GET http://127.0.0.1:8000/api/health`

### 可选 AI 教学插画（Cloudflare Workers AI）

在实际启动后端的目录中编辑已忽略的 `env.yaml`，加入
`cloudflare_account_id` 和 `cloudflare_api_token`（或设置同名大写环境变量）。
Token 仅需所选账户的 Workers AI Read / Edit 权限，不要提交或截图真实值。
模型由 `config/models.yaml` 的 `image` 任务经 ModelRouter 选择。

真实模型生成中，SectionAgent 可为具体教学情境调用 `request_illustration`。
它不是每页必备装饰，也不替代 Mermaid：含文字标注的结构、流程和技术图仍用确定性渲染。
当前没有自动接入图标／插画库检索；资源优先级由工具提示约束，不声称已有完整 AssetResolver。
每次章节生成最多尝试两张，固定 4 steps；不自动重试，避免重复消耗额度。
图片验证并重新编码为 PNG，存入 `var/uploads/illustrations/`，IR 保留 prompt、实际发送的
resolvedPrompt、provider、model 和状态。仅引用它的已授权章节可读取图片，PPTX 导出只读取已存文件，绝不再次生图。
失败保留正文、标记 `failed` / `retryable`，教师可以重新生成重试；仍须人工审核发布。
离线假模型演示不会调用 Cloudflare。本接入沿用已记录的 `/api/demo/*` 原型 SSE 路径，
不等同于已完成正式 ARQ 作业迁移。更改配置后需重启后端。

### 账号、教师审核和权限

当前 `/api/demo/*` 路由虽保留原型名称，但已经要求真实登录且为已审核教师。
学生直接注册；教师须提交最多 5 MiB 的 PDF／JPEG／PNG 资质，管理员审核通过
后才能使用教师接口。详情见 [根 README](../README.md#注册审核与旧课程)。
会话使用 HttpOnly Cookie；写请求还需精确匹配的 Origin 和 `X-CSRF-Token`。
前端通过 `/api/auth/csrf` 或 `/api/auth/me` 获取令牌，不能仅靠前端隐藏按钮。
资质仅本人和管理员可下载，不能在公开静态目录提供。

可选教师资料由 `services/teacher_profile.py` 管理，新增 `teacher_profiles` 表与认证 schema v2，不覆盖原有账号、资质或课程。`GET/PUT /api/auth/profile` 仅处理当前教师的可编辑资料，严格拒绝额外字段、无效选择项和超长输入；`GET/PUT/DELETE /api/auth/avatar` 管理本人私密头像。写请求继续要求 Origin/CSRF。管理员只可通过 `/api/admin/applications/{id}/profile` 和 `/avatar` 查看已提交资质的申请者。头像限 5 MiB JPG/PNG、2000 万像素，缩至最长边 512 像素并重新编码，清除元数据；所有读取均 `no-store`。这些接口允许未审核教师完善资料，但绝不改变审核状态。

```bash
# 在 backend/ 运行；密码交互输入，不出现在命令行
../.venv/bin/python -m app.auth_cli create-admin --name "Administrator" --email admin@example.com
# 旧课程只在核对课程 ID 和目标教师后显式认领，不自动迁给首个用户
../.venv/bin/python -m app.auth_cli claim-unowned --instructor-email teacher@example.com course-1
```

只运行一个应用 worker。请求级上下文及章级锁隔离不同教师和章节，流中断会释放
锁；旧版未带章节路径的工具使用当前会话明确激活的章节，带章节路径的请求不会
更改其他标签页的旧版选择。临时会话选择与锁映射仍驻留进程内直到重启，尚不适合
长时间多用户生产部署。课程 IR、patch 和归属存于 SQLite。

### 教师端本机工作区

教师端的课程、章节 IR、审核 patch、版本记录、学生名单和作答分析默认保存在
`backend/.local/teacher-workspace.db`。这是自动创建、已被 Git 忽略的 SQLite
文件，因此每位成员直接启动后端即可拥有独立工作区，不需要安装或配置数据库服务。

如需为测试或另一份本机演示使用不同资料库，可在启动前指定路径：

```bash
TEACHER_WORKSPACE_DB=/tmp/coursework-teacher.db ../.venv/bin/uvicorn app.main:app --reload
```

旧版临时 JSON 工作区只会在 SQLite 为空时被一次性迁入。删除该 SQLite 文件会重置
本机教师端资料；它不包含 API key、模型客户端或生成的媒体文件。

## 跑起来看看(不需要 API key)

```bash
cd backend
../.venv/bin/python -m app.demo_pipeline
```

这是一条完整跑通的 L1 流水线:六段进度 → 三个 SectionAgent 并发工作 →
产出 IR → 跑交叉引用校验。**阶段 1 会真读一份讲义,并用它的 chunk 做检索。**

单独看材料摄取:

```bash
cd backend
../.venv/bin/python -m app.demo_ingest      # 现场造 7 种材料并逐个摄取
```

它用**规则版假模型**替换了真模型,用**内存假实现**替换了检索和渲染。
换成真实现时,`agent.py` 和 `pipeline.py` 一行都不用改 —— 这就是依赖注入的意义。

## 测试

```bash
cd backend
../.venv/bin/pytest
```

测试断言的是**工具调用序列**,不是模型输出的文本 ——
文本每次都不同,断言它等于没断言。

## 目录

| 路径 | 对应规格章节 |
| --- | --- |
| `app/schemas/ir.py` | §5.1 IR 结构 + §6.4 校验规则(27 个模型) |
| `app/services/agent.py` | §6.2 / §7 **agent 循环**(终止工具、轮数上限、工具序列留痕) |
| `app/services/tools.py` | §6.2 SectionAgent 工具集 · §7.1 编辑 Agent 工具集 |
| `app/services/pipeline.py` | §6.1 **六阶段流水线**(进度、并发、失败隔离) |
| `app/services/ingest.py` | §6.1 **阶段 1 材料摄取**(magic bytes 探测 · 扫描件转 OCR · 分块保页码) |
| `app/demo_ingest.py` | 可运行演示:7 种材料 + 摄取报告 |
| `app/llm/client.py` | 模型客户端(含离线假模型) |
| `app/llm/router.py` | §11.4 ModelRouter |
| `app/api/deps.py` | §5.5 权限矩阵(后端强制) |
| `app/demo_pipeline.py` | 可运行演示(假模型) |
| `app/workers/` | 异步作业 + SSE(待实现) |
| `config/models.yaml` | §11.4 模型配置 |

## 三条必须遵守的硬规则(见 AGENTS.md)

1. AI 只产出 IR,不产出 HTML / pptx —— 渲染与导出是纯转换
2. 模型调用一律经 `ModelRouter`,禁止硬编码模型名
3. 只有 `POST /api/patches/{id}/apply` 会修改 `artifacts` 内容


---

## 材料摄取支持什么

**不靠扩展名判断,靠文件头 + 内容探测。** 因为同一个 `.pdf` 可能是两种完全不同的东西。

| 上传的东西 | 探测结果 | 怎么处理 |
| --- | --- | --- |
| 有文字层的 PDF | `text_pdf` | PyMuPDF 直接抽文字 + 页码 |
| **扫描版 PDF** | `scanned_pdf` | 渲染成图 → **转 OCR** |
| PPTX / DOCX | `pptx` / `docx` | 抽文字 + 表格 + 备注 |
| Markdown / TXT | `text` | 直接读 |
| 图片(拍的书页、截图) | `image` | **走 OCR** |
| 其它 | `unsupported` | 拒绝,并说明支持哪些格式 |

**每份材料都报告抽到多少字**,而不是笼统的「解析成功」:

```
✅ 讲义.pdf        text_pdf · 2 页 · 112 字
⚠️  扫描版讲义.pdf  scanned_pdf · 1 页 · 58 字 · 已 OCR   ← 建议抽查识别准确性
❌ 报表.xlsx       unsupported · 0 字                     ← 不支持的格式
```

抽到 0 字一定标为失败 —— 静默成功会让教师以为是模型不行,而实际是文件没读到。

**OCR 是可替换的:** `IngestDeps(ocr_image=...)`。demo 用假实现,
生产接 DeepSeek Flash(demo 不需要 API key 就是因为这个)。
