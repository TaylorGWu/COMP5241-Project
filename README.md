# Coursework · COMP5241

AI 辅助的软件工程迷你课程平台。本分支重点实现教师端：从教学目标和材料起草课程，在网页中编辑、审核 AI 建议，再由教师决定是否发布。

## 当前原型

- 公共首页与账号入口：交互式教学示例、统一登录、学生／教师独立注册页面。
- 教师资质审核：先注册教师账号，再单独上传 PDF／JPG／PNG 资质，管理员通过后才能创建课程；学生注册无需审核。
- 教师资料：在 `/profile` 保存个人简介、毕业院校、学历、任教机构／独立教师、岗位、教学年限和多选科目；支持私密头像上传、更换与删除。资料完善不等于资质审核通过。
- 账号权限：SQLite 账号、Argon2id 密码哈希、Cookie 会话、退出登录、后端角色及课程归属检查。
- 课程与章节管理：课程卡片、章节大纲、教学对象、时长与教材语言设置。
- 结构化生成：教案、逐页课件、讲稿、题目与模拟卷，以 JSON IR 作为共同内容来源。
- 人工审核：AI 修改先成为待确认 patch；查看前后差异与原因，逐项接受或驳回。
- 教学视觉：确定性示意图、网页概念动画预览；支持课件 PPTX、教案与试卷 DOCX 导出。
- 本机持久化：教师课程、章节和审核状态保存在 SQLite，无需另装数据库服务。

这是开发原型，不代表所有设计规格均已完成。网页概念动画不等于完整的 TTS/MP4 视频流水线；生产环境安全加固、ARQ 队列和部署仍需按设计推进。学生页目前是账号入口，尚未整合另一分支的完整学习端；管理员页目前实现教师申请审核，不等于完整管理后台。生成内容须由教师检查，自动测试不等同于教学效果验证。

## 本机启动

需要 Python 3.12、Node.js 22.14+、npm。以下命令从当前分支的仓库根目录开始；Git worktree 需要自己的依赖目录。

### 后端

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend
cp env.yaml.example env.yaml
PUPPETEER_SKIP_DOWNLOAD=1 npm ci
../.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

已有 `env.yaml` 时不要重复复制覆盖。真实模型密钥仅填入该文件或后端环境变量，模型路由配置在 `backend/config/models.yaml`。无需密钥的离线流水线演示：在 `backend/` 运行 `../.venv/bin/python -m app.demo_pipeline`。

Mermaid 示意图需要本机 Chrome/Chromium。浏览器不在常见位置时设置 `PUPPETEER_EXECUTABLE_PATH`；单张图失败不会阻止其余页面导出。

### 前端（另开终端）

```bash
cd frontend
npm ci
npm run dev -- --hostname 127.0.0.1 --port 3000
```

打开 [首页](http://127.0.0.1:3000/)，通过 [注册](http://127.0.0.1:3000/register) 或 [登录](http://127.0.0.1:3000/login) 进入对应角色页面。后端提供 [健康检查](http://127.0.0.1:8000/api/health) 和 [接口文档](http://127.0.0.1:8000/docs)。前端默认连接 `http://127.0.0.1:8000`，可设置 `NEXT_PUBLIC_API_BASE` 后重启（生产构建需重新构建）。

前后端请使用一致的主机写法，例如都用 `127.0.0.1`，不要将它与 `localhost` 混用。自定义前端端口时，把确切来源加进后端 `cors_origins`；携带 Cookie 的请求不允许使用通配来源。生产部署必须使用 HTTPS 和 Secure Cookie；开发 HTTP 仅支持本机回环地址。

## 注册、审核与旧课程

学生注册后即可登录 `/student`。教师注册只需账号资料，不必同时上传文件；注册后进入 `/application`，可以再上传最多 5 MiB 的 PDF、JPEG 或 PNG 教学资质。尚未提交、审核中或被要求补交时，均不能创建课程；审核通过后才可访问 `/courses`。管理员可下载资质、通过或填写原因要求补交；教师补交后重新进入待审核。资质保存在私有 SQLite 中，不是公开图片链接。演示建议使用明确标注的脱敏测试文件，不上传敏感证件。

管理员不开放注册，也没有默认密码。在 `backend/` 运行以下命令，由本机操作者设置密码（交互隐藏输入，15–128 个字元）：

```bash
../.venv/bin/python -m app.auth_cli create-admin --name "Administrator" --email admin@example.com
```

随后从登录页进入 `/admin` 审核教师申请。旧课程不会被删除，也不会自动交给第一个注册用户；认领前不会出现在新教师列表中。确认目标教师账号后，显式指定要分配的课程：

```bash
# 只读列出尚未分配的课程 ID（系统需有 sqlite3 命令）
sqlite3 .local/teacher-workspace.db "SELECT id FROM courses WHERE id NOT IN (SELECT course_id FROM course_owners);"
# 替换为实际教师邮箱与已核对的课程 ID；已归属课程不可覆盖分配
../.venv/bin/python -m app.auth_cli claim-unowned --instructor-email teacher@example.com course-1
```

目前不提供邮件验证、密码找回或第三方登录。教师自注册不等于已验证教师身份，必须经过管理员审核。**生成服务暂时只运行一个应用 worker**：章节内容与审核记录已持久化，编辑锁和旧版会话选择仍是进程内状态，重启会清除它们；不要用多个 uvicorn worker 扩容。

## 数据与安全

教师资料与头像只供本人及管理员查看，不会自动发布给学生。头像限 JPG／PNG、最多 5 MiB；后端验证并解码图片，缩至最长边 512 像素，重新编码为 JPEG，移除 EXIF 等元数据。头像和资质文件分开保存，不能互相代替。编辑资料不改变审核结果或课程权限。

首次启动自动创建 `backend/.local/teacher-workspace.db`。每位成员的数据独立，不需要提交数据库或配置共享数据库。可用后端环境变量 `TEACHER_WORKSPACE_DB` 指定其他路径。

`backend/env.yaml`、`.venv/`、`node_modules/`、`.next/` 和 `backend/.local/` 均不应提交。SQLite 现在包含账号哈希、会话摘要和私有资质文件，应限制访问并谨慎保管备份；首次升级认证表会通过 SQLite backup API 保留旧数据库备份。它不包含生成媒体文件，数据库备份不等于完整媒体备份。需要干净演示时指定新的数据库路径，不要直接删除已有资料库。

## 验证

```bash
# 仓库根目录
cd backend
../.venv/bin/pytest

# 另一终端，从仓库根目录开始
cd frontend
node --experimental-strip-types --test tests/*.test.mjs
npx tsc --noEmit --incremental false
npm run build
```

后端覆盖 IR、工具调用、patch 审核、SQLite、生成接口、动画契约与导出；前端包含路由、生成流和界面契约回归。仍需人工走查界面及审查真实模型内容。

## AI 辅助开发约定：AGENTS.md

[AGENTS.md](AGENTS.md) 是本仓库的 AI 编程助手工作规则，不是产品运行时的 agent 实现，也不是功能完成清单。成员使用 AI 辅助开发前，应先阅读该文件及其指定的设计、项目计划、需求研究、竞品分析和课程大纲，避免脱离项目范围生成代码。

核心约束包括：

- 内容以结构化 JSON IR 为唯一真相源，渲染与导出不调用模型；模型调用统一经 `ModelRouter`。
- AI 编辑只提出待确认 patch，教师确认后才应用；生成结果不自动发布。
- 带文字示意图使用确定性渲染；单个资源失败不能中断整包。
- 密钥仅保存在后端本机配置或环境变量，不进入源码、日志或前端。
- 保留设计取舍、AI 使用、测试结果与可归属提交；团队成员须能解释所提交的代码。

这些是开发约束与目标，不表示所有目标已实现；当前原型边界见上文。真人访谈和组外测试仍须提供真实证据，不能用 AI 模拟反馈替代。

## 项目资料与协作

| 路径 | 内容 |
| --- | --- |
| `frontend/` | Next.js / React 教师界面 |
| `backend/` | FastAPI、ModelRouter、IR、SQLite 与导出器 |
| `docs/` | 需求、研究、设计、计划与原型证据 |
| `tools/` | 本机界面验证辅助工具 |
| `AGENTS.md` | AI 辅助开发的项目上下文、架构约束与过程证据规则 |

入口见 [文档索引](docs/README.md)、[工作规则](AGENTS.md)、[生成设计](docs/design/course-generation-design.md) 和 [教学内容质量说明](docs/design/teaching-content-quality.md)。桌面研究与内部评审不能作为真人访谈或组外测试证据。

协作使用功能分支与 PR，不直接向 `main` 推送。提交前检查 `git status`，确保终端位于实际开发的 checkout/worktree；不同 worktree 的未提交修改不会互相显示。
