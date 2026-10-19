/**
 * 刷新页面会不会丢产物。
 *
 * ═══════════════════════════════════════════════════════════════
 * 修之前是什么样(实测,不是推测)
 * ═══════════════════════════════════════════════════════════════
 *   后端 `/state` 明明返回 3 页,但**前端从来不调用它** ——
 *   生成结果只活在 React state 里,按一下 F5 就回到 Setup。
 *   对教师来说就是「白做了」,而后端手里那份产物其实还在。
 *
 * 修法是在挂载时拉一次 `/state`(见 app/page.tsx 里那段注释)。
 *
 * ═══════════════════════════════════════════════════════════════
 * 为什么四步都要走,少一步都能被假实现骗过去
 * ═══════════════════════════════════════════════════════════════
 *   ① 清空后打开        → Setup    证明它不会凭空冒出产物
 *   ② 生成之后          → 工作台
 *   ③ 刷新 / 重开       → 工作台   ← 修的就是这个
 *   ④ 清空后再打开      → Setup    ← 关键
 *
 * 只测 ③ 的话,一个「永远显示工作台」的假实现照样能通过。
 * ④ 是唯一能戳穿它的那一步。
 *
 * 另外补一段最贴近实际使用的:出题 + 组卷之后再刷新 ——
 * 要恢复的不只是课件,还有题库和卷子。而界面上「总分对不对」是**算出来的**,
 * 恢复得不全会从「Exactly 20 points」变成「20 分里凑到 0 分」。
 *
 * 用法:
 *   node verify-state-restore.mjs [页面地址]
 *   CDP_PORT=9229 API_BASE=http://127.0.0.1:8000 node verify-state-restore.mjs
 */

const PORT = Number(process.env.CDP_PORT ?? 9229);
const URL_ = process.env.PAGE_URL ?? "http://localhost:3000";
const API = process.env.API_BASE ?? "http://127.0.0.1:8000";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const t = await (
  await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: "PUT" })
).json();
if (!t?.webSocketDebuggerUrl) {
  throw new Error(`CDP:${PORT} 上拿不到页面 target —— Chrome 起来了吗?`);
}
const ws = new WebSocket(t.webSocketDebuggerUrl);
await new Promise((res, rej) => {
  ws.onopen = res;
  ws.onerror = rej;
});

let seq = 0;
const pend = new Map();
const errs = [];
ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pend.has(m.id)) {
    pend.get(m.id)(m);
    pend.delete(m.id);
    return;
  }
  if (m.method === "Log.entryAdded" && m.params.entry.level === "error") {
    const x = m.params.entry.text;
    if (!x.includes("favicon") && !x.includes("ERR_INVALID_HTTP_RESPONSE")) errs.push(x);
  }
};
const send = (method, params = {}) => {
  const id = ++seq;
  ws.send(JSON.stringify({ id, method, params }));
  return new Promise((r) => pend.set(id, r));
};
const ev = async (expr) => {
  const r = await send("Runtime.evaluate", {
    expression: expr,
    returnByValue: true,
    awaitPromise: true,
  });
  if (r.result?.exceptionDetails) return "EXC: " + r.result.exceptionDetails.text;
  return r.result?.result?.value;
};
const click = (label) =>
  ev(`(() => {
    const b = [...document.querySelectorAll('button')].find(x => x.textContent.trim() === ${JSON.stringify(label)});
    if (!b) return 'not found';
    if (b.disabled) return 'disabled';
    b.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
    return 'ok';
  })()`);

// 状态一律从 data-* 读 —— 断言文字的话,改一次文案或加一种语言就会静默空转
const PROBE = `(() => {
  const el = document.querySelector('[data-teacher-tools="1"]');
  return {
    slides: document.querySelectorAll('article[id^="slide-"]').length,
    tools: !!el,
    questions: el ? Number(el.dataset.questions) : 0,
    glossary: el ? Number(el.dataset.glossary) : 0,
    paper: el ? el.dataset.paper : "none",
    points: el ? Number(el.dataset.paperPoints) : 0,
    examReady: el ? [...el.querySelectorAll('[data-export^="exam"]')].map(x => x.dataset.exportReady) : [],
  };
})()`;

const problems = [];
const reset = () => fetch(`${API}/api/demo/reset`, { method: "POST" });

const probe = async (label, expectWorkspace) => {
  const s = await ev(PROBE);
  const where = s.slides > 0 ? `工作台(${s.slides} 页)` : "Setup";
  const ok = expectWorkspace ? s.slides > 0 : s.slides === 0;
  console.log(`  ${ok ? "✅" : "❌"} ${label.padEnd(22)} ${where}`);
  if (!ok) problems.push(`${label}:期望${expectWorkspace ? "工作台" : "Setup"},实际 ${where}`);
  return s;
};

const waitFor = async (expr, label) => {
  for (let i = 0; i < 45; i++) {
    await sleep(300);
    if (await ev(expr)) return true;
  }
  problems.push(`${label}:等超时`);
  return false;
};

const open = async () => {
  await send("Page.navigate", { url: URL_ });
  await sleep(4500);
};

await send("Page.enable");
await send("Runtime.enable");
await send("Log.enable");

// ═══════════════════════════════════════════════════════════════
console.log("═══ ① 清空之后打开(不该凭空冒出产物)═══");
// ═══════════════════════════════════════════════════════════════
await reset();
await open();
await probe("清空后首次打开", false);

// ═══════════════════════════════════════════════════════════════
console.log("\n═══ ② 生成 ═══");
// ═══════════════════════════════════════════════════════════════
console.log("  Generate draft ->", await click("Generate draft"));
await waitFor(`document.querySelectorAll('article[id^="slide-"]').length > 0`, "工作台出现");
await sleep(1200);
await probe("生成之后", true);

// ═══════════════════════════════════════════════════════════════
console.log("\n═══ ③ 刷新 / 重开 —— 修的就是这个 ═══");
// ═══════════════════════════════════════════════════════════════
await send("Page.reload");
await sleep(4500);
const reloaded = await probe("刷新之后", true);
if (reloaded.slides > 0 && !reloaded.tools) {
  problems.push("产物回来了但教师工具栏没回来 —— 状态接得不全");
}
await open();
await probe("重开页面之后", true);

// ═══════════════════════════════════════════════════════════════
console.log("\n═══ ④ 出题 + 组卷,再刷新(最贴近实际使用)═══");
// ═══════════════════════════════════════════════════════════════
console.log("  Generate questions ->", await click("Generate questions"));
await waitFor(
  `Number(document.querySelector('[data-teacher-tools="1"]')?.dataset.questions) > 0`,
  "题数 > 0",
);

// 先把总分改成题库凑得出的数。默认是 100,而假模型这 4 道题加起来只有 30 分 ——
// 那样组卷会如实报「凑不出」(ok=false),这段就测不到精确恢复了。
await ev(`(() => {
  const el = document.querySelector('[data-field="total"]');
  if (!el) return 'no field';
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(el, '20');
  el.dispatchEvent(new Event('input', { bubbles: true }));
  return el.value;
})()`);
await sleep(400);
console.log("  Build paper ->", await click("Build paper"));
await waitFor(
  `document.querySelector('[data-teacher-tools="1"]')?.dataset.paper === 'exact'`,
  "组卷完成",
);

const before = await ev(PROBE);
console.log(`  刷新之前: 题数=${before.questions} 卷子=${before.paper} ${before.points} 分`);

await send("Page.reload");
await sleep(5000);
const after = await ev(PROBE);
console.log(`  刷新之后: 题数=${after.questions} 卷子=${after.paper} ${after.points} 分`);

for (const [key, label] of [
  ["questions", "题数"],
  ["glossary", "词条数"],
  ["paper", "卷子状态"],
  ["points", "卷子实际分"],
]) {
  const ok = before[key] === after[key];
  console.log(`  ${ok ? "✅" : "❌"} ${label.padEnd(8)} ${before[key]} → ${after[key]}`);
  if (!ok) problems.push(`${label}刷新后变了:${before[key]} → ${after[key]}`);
}
const ready = after.examReady.length > 0 && after.examReady.every((x) => x === "true");
console.log(`  ${ready ? "✅" : "❌"} 试卷下载刷新后仍可用`);
if (!ready) problems.push("刷新后试卷下载又变回禁用");

// ═══════════════════════════════════════════════════════════════
console.log("\n═══ ⑤ 清空之后再打开(戳穿「永远显示工作台」的假实现)═══");
// ═══════════════════════════════════════════════════════════════
await reset();
await open();
await probe("清空后再次打开", false);

// ═══════════════════════════════════════════════════════════════
console.log("\n═══ 控制台 ═══");
// ═══════════════════════════════════════════════════════════════
if (errs.length) {
  console.log(`  ❌ ${errs.length} 条错误`);
  problems.push(`${errs.length} 条控制台错误`);
  for (const e of errs.slice(0, 5)) console.log("     ", e.slice(0, 150));
} else {
  console.log("  ✅ 零控制台错误");
}

console.log("\n" + "═".repeat(58));
if (problems.length) {
  console.log(`❌ ${problems.length} 个问题:`);
  for (const p of problems) console.log("   · " + p);
  process.exit(1);
}
console.log("✅ 刷新/重开都不丢产物,清空之后也能正确回到 Setup");
process.exit(0);
