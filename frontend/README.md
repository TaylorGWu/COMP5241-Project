# 教师端前端

Next.js App Router + React + TypeScript。项目安装、后端配置与功能边界见 [根目录 README](../README.md)。

## 本机开发

```bash
npm ci
npm run dev -- --hostname 127.0.0.1 --port 3000
```

打开 <http://127.0.0.1:3000/>。默认后端地址为 `http://127.0.0.1:8000`；可设置 `NEXT_PUBLIC_API_BASE` 后重启（生产构建需重新构建）。密钥仅放后端，不得用前端环境变量传递。

公共首页为 `/`，统一登录 `/login`；学生、教师注册分别为 `/register/student`、
`/register/instructor`。教师先注册账号，再到 `/application` 单独上传资质，须由 `/admin` 的
管理员审核后才能打开教师工作台。学生 `/student` 暂为账号入口，不是完整学习端。
管理员仅通过后端本机命令创建，具体操作见根 README。

JSON、SSE、上传及删除共用携带 Cookie/CSRF 的请求层；下载链接也要求有效会话。
前端跳转用于改善体验，实际角色、审核状态和课程归属由后端检查。请保持前后端
同为 `127.0.0.1` 或同为 `localhost`，避免跨站 Cookie 问题。

## 主要入口

- `app/profile/page.tsx`、`components/TeacherProfile.tsx`：独立教师资料页、照片预览／保存／删除、教育与任教资料、科目搜索多选；未保存离开提示。
- `lib/teacher-profile.ts`、`app/profile.css`：三语言资料文案、可编辑字段白名单和沿用现有品牌的表单布局。
- `app/courses/page.tsx`：课程卡片、搜索与筛选。
- `app/courses/[courseId]/page.tsx`：课程大纲、章节管理与设置。
- `app/courses/[courseId]/chapters/[chapterId]/page.tsx`：章节生成、预览与审核。
- `components/ReviewMargin.tsx`：待确认修改与差异审核。
- `lib/api.ts`：后端请求与生成事件流。

课程内容由后端 SQLite 持久化；浏览器不是唯一存储。AI 建议必须由教师确认，不能自动接受或发布。

教师可从账号区进入 `/profile`，无论资质尚未提交、待审、驳回或已通过。学生和管理员不能进入教师自编辑页。管理员在申请列表按需展开已提交申请者的资料。头像通过携带 Cookie 的私密请求取为 blob，不使用公开静态路径；照片单独保存，不覆盖表单中尚未保存的文字。资料页不会开放课程权限。

`/application` 的刷新状态提供检查中、仍待审核、失败重试反馈；暂时断网保留当前页面，审核通过进入工作台，驳回展示补充原因。

## 验证与构建

```bash
node --experimental-strip-types --test tests/*.test.mjs
npx tsc --noEmit --incremental false
npm run build
```

测试命令使用支持 TypeScript type stripping 的 Node.js（本机验证使用 22.14）。构建后可运行 `npm run start`，后端仍需单独启动。自动测试不能替代响应式布局、键盘操作与真实模型内容的人工检查。
