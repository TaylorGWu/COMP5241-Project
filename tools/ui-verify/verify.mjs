/** 教师端 v2 验证:三语切换、cookie 持久化、键盘审阅、滚动高亮、审阅栏内容。 */

import { writeFileSync } from "node:fs";

const URL_ = process.argv[2] ?? "http://localhost:3000";
const OUT = process.argv[3] ?? "/tmp/v3";
// 调试端口可配:9222 常被上一次没退干净的 Chrome 占着,
// 那时候脚本会连上一个空白页,然后所有断言都「通过」—— 因为它什么都测不到。
const PORT = Number(process.env.CDP_PORT ?? 9222);
const API = process.env.API_BASE ?? "http://127.0.0.1:8000";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ═══════════════════════════════════════════════════════════════
// ★ 先清空后端状态 —— 否则这个脚本会骗自己
// ═══════════════════════════════════════════════════════════════
// `/api/demo/*` 的状态是**进程级全局**的,活过了页面刷新。上一次验证跑完
// 留下的产物还在,于是新开的页面一加载就把它恢复出来 → 直接进工作台、
// 跳过 Setup → 生成控制台根本没被渲染过。
//
// 症状极具迷惑性:断言会「通过」,因为它测的是一个根本没出现的元素。
// (这个坑是加实时进度检查时才暴露出来的 —— 那次它报「0 次采样」。)
try {
  const r = await fetch(`${API}/api/demo/reset`, { method: "POST" });
  console.log(`后端状态已清空 (${r.status})`);
} catch (e) {
  console.log(`⚠️  清空后端状态失败:${e.message} —— 后面的断言可能不可信`);
}

const list = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json();
const target = list.find((t) => t.type === "page");
if (!target) throw new Error(`CDP:${PORT} 上没有页面 —— Chrome 起来了吗?`);
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((res, rej) => {
  ws.onopen = res;
  ws.onerror = rej;
});

let seq = 0;
const pending = new Map();
const errs = [];
ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) {
    pending.get(m.id)(m);
    pending.delete(m.id);
    return;
  }
  if (m.method === "Log.entryAdded" && m.params.entry.level === "error") {
    const t = m.params.entry.text;
    if (!t.includes("favicon") && !t.includes("ERR_INVALID_HTTP_RESPONSE")) errs.push(t);
  }
};
const send = (method, params = {}) => {
  const id = ++seq;
  ws.send(JSON.stringify({ id, method, params }));
  return new Promise((res) => pending.set(id, res));
};
const ev = async (expr) => {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return "EXC: " + r.result.exceptionDetails.text;
  return r.result?.result?.value;
};
const shoot = async (name) => {
  const r = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
  writeFileSync(`${OUT}-${name}.png`, Buffer.from(r.result.data, "base64"));
  console.log(`  shot -> ${OUT}-${name}.png`);
};
const clickText = async (label) => {
  const r = await ev(`(() => {
    const b = [...document.querySelectorAll('button')].find(x => x.textContent.trim() === ${JSON.stringify(label)});
    if (!b) return 'not found';
    if (b.disabled) return 'disabled';
    b.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
    return 'ok';
  })()`);
  return r;
};
const press = async (key, code, keyCode) => {
  await send("Input.dispatchKeyEvent", {
    type: "keyDown", key, code, windowsVirtualKeyCode: keyCode, nativeVirtualKeyCode: keyCode,
  });
  await send("Input.dispatchKeyEvent", {
    type: "keyUp", key, code, windowsVirtualKeyCode: keyCode, nativeVirtualKeyCode: keyCode,
  });
};
const headline = () => ev("document.querySelector('h1')?.innerText ?? '(none)'");
const marginText = () =>
  ev("([...document.querySelectorAll('aside')].at(-1)?.innerText ?? '').replace(/\\n{2,}/g,'\\n')");
const railActive = () => ev("document.querySelector('nav a[aria-current]')?.innerText ?? '(none)'");
const htmlLang = () => ev("document.documentElement.lang");

await send("Page.enable");
await send("Runtime.enable");
await send("Log.enable");
await send("Emulation.setDeviceMetricsOverride", {
  width: 1680, height: 1300, deviceScaleFactor: 2, mobile: false,
});

console.log("═══ 1. 默认语言 ═══");
await send("Page.navigate", { url: URL_ });
await sleep(4500);
console.log("  html lang:", await htmlLang());
console.log("  headline :", await headline());
await shoot("01-setup-en");

console.log("\n═══ 2. 切到繁體中文 ═══");
console.log("  click 繁 ->", await clickText("繁"));
await sleep(1200);
console.log("  html lang:", await htmlLang());
console.log("  headline :", await headline());
await shoot("02-setup-zhhk");

console.log("\n═══ 3. 刷新后是否记住(cookie 持久化)═══");
await send("Page.navigate", { url: URL_ });
await sleep(4000);
console.log("  html lang after reload:", await htmlLang());
console.log("  headline              :", await headline());

console.log("\n═══ 4. 切到简体中文 ═══");
console.log("  click 简 ->", await clickText("简"));
await sleep(1200);
console.log("  html lang:", await htmlLang());
console.log("  headline :", await headline());
await shoot("03-setup-zhcn");

console.log("\n═══ 5. 生成中:进度是不是真的在动(SSE)═══");
console.log("  click EN ->", await clickText("EN"));
await sleep(1000);

// 生成之前先把控制台盯上:每 150ms 采一次样。
// 用 data-* 属性读状态,而不是靠 class 名 —— 后者样式一改就静默失配,
// 脚本会「通过」,因为选择器根本没匹配上任何东西。
const readConsole = () =>
  ev(`(() => {
    const el = document.querySelector('[data-console="generation"]');
    if (!el) return null;
    return {
      percent: Number(el.dataset.percent),
      sections: Number(el.dataset.sections),
      slides: Number(el.dataset.slides),
      events: Number(el.dataset.events),
    };
  })()`);

console.log("  click Generate draft ->", await clickText("Generate draft"));

const samples = [];
for (let i = 0; i < 40; i++) {
  await sleep(150);
  const snap = await readConsole();
  if (snap) samples.push(snap);
  // 工作台出现就说明生成结束了
  const done = await ev("document.querySelectorAll('article[id^=\"slide-\"]').length");
  if (typeof done === "number" && done > 0) {
    console.log("  slides:", done);
    break;
  }
}

const percents = samples.map((s) => s.percent);
const distinct = [...new Set(percents)];
const monotonic = percents.every((p, i) => i === 0 || p >= percents[i - 1]);
const maxSections = Math.max(0, ...samples.map((s) => s.sections));
const maxSlides = Math.max(0, ...samples.map((s) => s.slides));

console.log("  采样次数            :", samples.length);
console.log("  不同的进度值        :", distinct.length, "→", distinct.slice(0, 12).join(", "));
console.log("  进度单调不减        :", monotonic ? "✅" : "❌ 倒退了!");
console.log("  同时出现的分节栏数  :", maxSections);
console.log("  「已写 N 张」最大值 :", maxSlides);

// 这几条是单元测试够不着的:它们考的是「浏览器里到底有没有在动」
const liveProblems = [];
if (samples.length < 3) liveProblems.push("控制台几乎没被采到样,进度可能是一次性刷出来的");
if (distinct.length < 4) liveProblems.push(`生成过程中只出现 ${distinct.length} 个不同进度值 —— 看起来不像在流式推进`);
if (!monotonic) liveProblems.push("进度条倒退了");
if (maxSections < 3) liveProblems.push(`同时只看到 ${maxSections} 条分节栏,应该有 3 条`);
if (maxSlides < 3) liveProblems.push(`「已写 N 张」最多只有 ${maxSlides},应该到 3`);
console.log("  →", liveProblems.length ? "❌ " + liveProblems.join("; ") : "✅ 实时进度正常");

console.log("\n═══ 6. 工作台与滚动高亮 ═══");
await sleep(1500);
console.log("  rail active (scroll-spy):", await railActive());
console.log("\n  --- 审阅栏内容 ---");
console.log(String(await marginText()).split("\n").map((l) => "  " + l).join("\n"));
await shoot("04-workspace");

console.log("\n═══ 7. 键盘 J / K 翻页 ═══");
console.log("  before:", await railActive());
await press("j", "KeyJ", 74);
await sleep(1400);
console.log("  after J:", await railActive());
await press("j", "KeyJ", 74);
await sleep(1400);
console.log("  after J:", await railActive());
await press("k", "KeyK", 75);
await sleep(1400);
console.log("  after K:", await railActive());

console.log("\n═══ 8. 提议(流式)→ 键盘 A 批准 → 历史 ═══");
// 输入框有默认文案,直接点 Send
await ev(`(() => {
  const b = [...document.querySelectorAll('button')].find(x => x.textContent.trim() === 'Send');
  b?.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
})()`);

// ★ L2 也要能看见 agent 在干什么。修好之前这里是转圈干等 ——
//   后端 /edit/stream 早就写好了,但前端从没调过它(两端都成了死代码)。
const stepCounts = [];
for (let i = 0; i < 40; i++) {
  await sleep(150);
  const n = await ev(
    "Number(document.querySelector('[data-agent-steps]')?.dataset.agentSteps ?? -1)"
  );
  if (typeof n === "number" && n >= 0) stepCounts.push(n);
  if (await ev("!!document.querySelector('aside pre')")) break;
}
const maxSteps = Math.max(-1, ...stepCounts);
console.log("  实时步骤采样      :", stepCounts.length, "次,最多", maxSteps, "步");

// ⚠️ 断言必须是**正好 2 步**,不能写成 `>= 2`。
// 假编辑模型固定调两次工具(read_slide、patch_slide)。曾经 start/end
// 配对失败,每条帧各占一行 → 显示成 4 行,而 `>= 2` 照样通过。
// 只写下界等于没测「配对有没有生效」。
if (maxSteps !== 2) {
  liveProblems.push(
    `L2 编辑期间显示 ${maxSteps} 步,应该是 2 步(read_slide、patch_slide)。` +
    `多了说明 start/end 没配对成一行,少了说明漏了步骤`
  );
}

for (let i = 0; i < 20; i++) {
  await sleep(1500);
  if (await ev("!!document.querySelector('aside pre')")) { console.log("  patch appeared"); break; }
}
await sleep(1000);
await shoot("05-proposed");
console.log("  press A (approve)");
await press("a", "KeyA", 65);
await sleep(3000);
console.log("\n  --- 批准后的审阅栏 ---");
console.log(String(await marginText()).split("\n").map((l) => "  " + l).join("\n"));
await shoot("06-recorded");

console.log("\n=== 汇总 ===");
if (liveProblems.length) {
  console.log("❌ 实时进度有问题:");
  for (const p of liveProblems) console.log("   · " + p);
} else {
  console.log("✅ 实时进度全部通过(L1 与 L2)");
}

console.log("\n=== 控制台错误 ===");
console.log(errs.length ? errs.slice(0, 6).join("\n") : "(none)");
ws.close();
process.exit(liveProblems.length ? 1 : 0);
