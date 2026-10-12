# UI 验证脚本

用 Chrome DevTools Protocol 真的点一遍界面,而不是靠看代码猜。

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
