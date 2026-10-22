# 教师端前端

Next.js App Router + React + TypeScript。项目安装、后端配置与功能边界见 [根目录 README](../README.md)。

## 本机开发

```bash
npm ci
npm run dev -- --hostname 127.0.0.1 --port 3000
```

打开 <http://127.0.0.1:3000/courses>。默认后端地址为 `http://127.0.0.1:8000`；可设置 `NEXT_PUBLIC_API_BASE` 后重启。密钥仅放后端，不得用前端环境变量传递。

## 主要入口

- `app/courses/page.tsx`：课程卡片、搜索与筛选。
- `app/courses/[courseId]/page.tsx`：课程大纲、章节管理与设置。
- `app/courses/[courseId]/chapters/[chapterId]/page.tsx`：章节生成、预览与审核。
- `components/ReviewMargin.tsx`：待确认修改与差异审核。
- `lib/api.ts`：后端请求与生成事件流。

课程内容由后端 SQLite 持久化；浏览器不是唯一存储。AI 建议必须由教师确认，不能自动接受或发布。

## 验证与构建

```bash
node --experimental-strip-types --test tests/*.test.mjs
npx tsc --noEmit --incremental false
npm run build
```

测试命令使用支持 TypeScript type stripping 的 Node.js（本机验证使用 22.14）。构建后可运行 `npm run start`，后端仍需单独启动。自动测试不能替代响应式布局、键盘操作与真实模型内容的人工检查。
