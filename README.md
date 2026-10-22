# Coursework · COMP5241

AI 辅助的软件工程迷你课程平台。本分支重点实现教师端：从教学目标和材料起草课程，在网页中编辑、审核 AI 建议，再由教师决定是否发布。

## 当前原型

- 课程与章节管理：课程卡片、章节大纲、教学对象、时长与教材语言设置。
- 结构化生成：教案、逐页课件、讲稿、题目与模拟卷，以 JSON IR 作为共同内容来源。
- 人工审核：AI 修改先成为待确认 patch；查看前后差异与原因，逐项接受或驳回。
- 教学视觉：确定性示意图、网页概念动画预览；支持课件 PPTX、教案与试卷 DOCX 导出。
- 本机持久化：教师课程、章节和审核状态保存在 SQLite，无需另装数据库服务。

这是开发原型，不代表所有设计规格均已完成。网页概念动画不等于完整的 TTS/MP4 视频流水线；生产鉴权、ARQ 队列和部署仍需按设计推进。生成内容须由教师检查，自动测试不等同于教学效果验证。

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

打开 [教师课程列表](http://127.0.0.1:3000/courses)。后端提供 [健康检查](http://127.0.0.1:8000/api/health) 和 [接口文档](http://127.0.0.1:8000/docs)。前端默认连接 `http://127.0.0.1:8000`，可设置 `NEXT_PUBLIC_API_BASE` 后重启。

## 数据与安全

首次启动自动创建 `backend/.local/teacher-workspace.db`。每位成员的数据独立，不需要提交数据库或配置共享数据库。可用后端环境变量 `TEACHER_WORKSPACE_DB` 指定其他路径。

`backend/env.yaml`、`.venv/`、`node_modules/`、`.next/` 和 `backend/.local/` 均不应提交。SQLite 不包含生成媒体文件，数据库备份不等于完整媒体备份。需要干净演示时指定新的数据库路径，不要直接删除已有资料库。

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

## 项目资料与协作

| 路径 | 内容 |
| --- | --- |
| `frontend/` | Next.js / React 教师界面 |
| `backend/` | FastAPI、ModelRouter、IR、SQLite 与导出器 |
| `docs/` | 需求、研究、设计、计划与原型证据 |
| `tools/` | 本机界面验证辅助工具 |

入口见 [文档索引](docs/README.md)、[工作规则](AGENTS.md)、[生成设计](docs/design/course-generation-design.md) 和 [教学内容质量说明](docs/design/teaching-content-quality.md)。桌面研究与内部评审不能作为真人访谈或组外测试证据。

协作使用功能分支与 PR，不直接向 `main` 推送。提交前检查 `git status`，确保终端位于实际开发的 checkout/worktree；不同 worktree 的未提交修改不会互相显示。
