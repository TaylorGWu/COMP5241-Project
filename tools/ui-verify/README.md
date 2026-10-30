# UI 验证脚本

用 Chrome DevTools Protocol 真的点一遍界面,而不是靠看代码猜。

## 新版账号与审核流程

`auth-smoke.cjs` 使用 Playwright 和隔离浏览器上下文，验证学生注册、教师资质
提交、待审核接口拦截、管理员下载／拒绝、补交、批准、退出及重新登录。它会创建
虚构测试账号，**只能连接独立临时数据库**，不能对现有演示课程库运行。

先用 `TEACHER_WORKSPACE_DB` 指向临时目录启动 8001 后端，在 `CORS_ORIGINS`
配置 `http://127.0.0.1:3001`，在该数据库用本机命令创建测试管理员。
然后以 `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8001` 构建前端并启动在 3001。
准备好 Playwright 和 Chrome 后运行：

```bash
# 密码由当前 shell 交互读取或通过安全环境注入，不把真实密码写进文档/脚本
export AUTH_SMOKE_DISPOSABLE=1
export AUTH_SMOKE_ADMIN_EMAIL=admin@example.test
node tools/ui-verify/auth-smoke.cjs
```

还需在进程环境中提供 `AUTH_SMOKE_ADMIN_PASSWORD`。如 Playwright 不在默认模块
路径，可用 `PLAYWRIGHT_MODULE` 指向其安装位置。`SMOKE_BASE` / `SMOKE_API`
可覆盖默认 3001 / 8001 地址。截图写入新建的系统临时目录，脚本最后输出位置。

`auth-session-boundary.cjs` 用合成 HTTP 响应驱动真实前端，验证跨账号重挂载、
过期登录恢复与迟到响应隔离；它不修改数据库，也不能代替后端权限测试。
`auth-capture.cjs` 批量截取登录/注册的桌面、手机、三语言和明暗模式，检查横向
溢出及登录按钮可见性；图片写入忽略的 `frontend/.impeccable/review/auth-v2/`。
三份脚本都支持 `PLAYWRIGHT_MODULE` 和 `SMOKE_BASE`。自动走查不是组外真人
可用性测试，不应在报告中这样表述。

`teacher-profile.cjs` 同样用合成 HTTP 边界驱动真实资料页，不改动真实数据库。
验证资料保存／重新加载、错误后保留输入、未保存离开确认、搜索多选科目、独立教师、
照片保存／删除且不覆盖文字、三语言手机布局、管理员展开资料、学生路由限制、
会话过期，以及待审／失败／驳回／通过的状态刷新。默认 `SMOKE_BASE` 为 3000，
截图写入系统临时目录；它不能替代 `backend/tests/test_teacher_profile.py` 的真实
存储、CSRF、图片解码与权限测试。

`public-refinement.cjs` 验证首页、教师资料和申请页的计算字体、图片加载、单排账号
导航、320px 至桌面布局、简繁中文及明暗主题；另测已审核教师手机工作台入口和
即时中英切换不丢失未保存资料。默认连接 3000，可用 `SMOKE_BASE` 改为生产预览。
浏览器请求由合成 HTTP 响应隔离，截图输出到系统临时目录，不改真实账号。

`home-example.cjs` 验证首页课程流程动画：创建课程 → 添加章节及草稿 → 查看
修改建议 → 教师确认。覆盖三语言与 1440/390/320px、键盘焦点、手动切换、
暂停/继续、重播、减少动态效果、完全移出视口后停止，以及自动播放最终停在
已确认的草稿。断言没有写 API 请求。使用 `SMOKE_BASE` 连接生产预览，截图
输出到系统临时目录；它只是合成浏览器走查，不是外部用户测试。

`account-menu.cjs` 验证登录后的首页、教师资料和审核页使用同一个圆形头像菜单。
覆盖三语言、桌面和 320/390px、私有照片与首字回退、照片更新/删除同步、Enter/
向下键/Tab/Esc、点击外部关闭、退出失败后保留提示及重试、游客入口不变，
以及已审核教师/学生/管理员各自的工作台入口。使用合成 API，不改真实账号。

`slide-actions.cjs` 以合成 API 驱动真实章节工作台，验证当前页前插／后插、选中并
编辑新页、保存与刷新、删除确认／取消、空标题、删除最后一页后重新新增、失败提示
及手机布局。默认连接 3000，支持 `SMOKE_BASE` 与 `PLAYWRIGHT_MODULE`，不改真实
课程；持久化、教案引用与操作记录由 `test_demo_workspace_sqlite.py` 测试临时数据库。

下文 `verify.mjs` 是旧版生成流程脚本：其匿名重置调用与全局状态描述早于账号
隔离改造，**不能再按原步骤直接运行**，需先迁移为认证会话与明确的课程路径。
保留旧说明作为历史问题记录，不作为新版认证系统的验收证据。

## 为什么需要它

`tsc`、`next build`、130 个后端测试全绿的时候,下面这些 bug 依然活着:

| 被发现的问题 | 为什么单元测试抓不到 |
| --- | --- |
| `cors_origins` 只写了 `localhost`,用 `127.0.0.1` 打开时**所有接口失败** | 后端测试走 ASGI transport,不经过浏览器,没有 Origin 头 |
| `normalizeLocale()` 放在 `"use client"` 模块里,服务端组件调用直接 **500** | 类型检查通过,构建也通过,只有真跑起来才炸 |
| 滚动高亮用 IntersectionObserver「取最靠上的可见项」,导致**永远停在第 1 页** | 这是布局与滚动行为,纯逻辑测试测不到 |
| 最后一页永远高亮不到(它到不了阅读线) | 同上 |
| 实时进度的**最后一批事件被 React 批处理吞掉**:`result` 和最后几帧落在同一个任务里 → 控制台在 100% 上闪一下就没,教师看不到「已写 3 张」 | `setEvents` / `setPkg` 各自的逻辑都对,单元测试逐帧断言也全绿。**只有把两次渲染放进同一个 tick 才会现形** |
| 后端 `STATE` 活过页面刷新,上一轮的产物被恢复 → 要测的界面根本没渲染,断言却「通过」 | 后端测试每个用例都自己清状态,不会遇到进程级污染 |

共同点:**假环境比真环境干净**。这和真模型跑出来的 7 个缺陷是同一类问题。

## 怎么跑

```bash
# 1. 起服务
cd backend && ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 &
cd frontend && npm run build && npm start &      # 注意:必须是生产构建

# 2. 起一个带调试端口的 Chrome
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --remote-debugging-port=9222 --no-sandbox \
  --user-data-dir=/tmp/chrome-verify about:blank &

# 3. 跑
node tools/ui-verify/verify.mjs http://localhost:3000 /tmp/shots
```

产出 `/tmp/shots-*.png`,并在终端打印每一步的实际状态
(`<html lang>`、页面标题、审阅栏全文、滚动位置、当前高亮项)。

## ⚠️ 必须用生产构建

Turbopack **开发模式**下,无头 Chrome 的 HMR WebSocket 握手会失败
(`ERR_INVALID_HTTP_RESPONSE`),页面因此**不会水合**,所有点击都没反应。
`/lab` 这个没改过的页面也一样 —— 所以这是环境问题,不是页面问题。
真实浏览器里开发模式正常。

## 覆盖的检查

1. 默认语言 = `en`,`<html lang>` 正确
2. 繁體中文 → 简体中文 → 英文,每一步的标题与 `lang` 都对
3. 刷新后语言仍记得(cookie 由服务端在首屏读出来,不闪)
4. **生成过程中实时进度**:采样 `[data-console]`,断言进度值单调不减、
   出现多个不同值、三条分节栏都在、「已写 N 张」最终等于课件张数
5. 生成 → 课件页数、目标覆盖度
6. 键盘 `J` / `K` 翻页,左栏高亮跟着走
7. 提议改动 → 键盘 `A` 批准 → 归档区出现记录
8. 全程收集 console / Log 错误,最后汇总打印

有问题的断言会让脚本**以退出码 1 结束**,可以直接接进 CI。

服务端渲染语言的验证不需要浏览器:

```bash
curl -s -H 'Cookie: pathpilot_locale=zh-HK' http://localhost:3000 | grep -o '<html lang="[^"]*"'
```

## 环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `CDP_PORT` | `9222` | Chrome 调试端口。**上一次没退干净的 Chrome 会占着 9222**,那时脚本会连上一个空白页,然后所有断言都「通过」—— 因为它什么都测不到 |
| `API_BASE` | `http://127.0.0.1:8000` | 后端地址,脚本启动时先 `POST /api/demo/reset` |

## ⚠️ 两个会让脚本骗自己的坑

**一、后端状态活过页面刷新。** `/api/demo/*` 的状态是**进程级全局**的。
上一轮跑完留下的产物还在,新开的页面一加载就把它恢复出来 → 直接进工作台、
跳过 Setup → 要测的元素根本没被渲染过。症状是断言「通过」。
所以脚本开头必须先 `POST /api/demo/reset`。

**二、断言不要绑在 class 名上。** 样式一改选择器就静默失配,脚本照样「通过」。
所以生成控制台暴露了一组 `data-*` 属性作为显式契约:

```html
<div data-console="generation"
     data-percent="58" data-sections="3"
     data-slides="0" data-events="21">
```

## Course library layout refinement

`course-library-layout.cjs` uses synthetic API fixtures to verify the approved
two-column desktop library, filters, empty state, computed Manrope and narrow
widths. Run with `SMOKE_BASE` and `PLAYWRIGHT_MODULE` like the other scripts.
`export-target.cjs` additionally guards separate slide toolbar, scope binding,
composer/proposal order, frozen plan targets and mobile content containment.
