/**
 * 教师端后几步的浏览器验证 —— 出题 / 组卷 / 白话化 / 导出。
 *
 * ═══════════════════════════════════════════════════════════════
 * 为什么要有这个脚本(单元测试和接口测试都不够)
 * ═══════════════════════════════════════════════════════════════
 * 后端 317 条测试全绿,但一条都证明不了「按钮点下去有没有反应」:
 *
 *   · 处理函数有没有接上 (`onQuestions` 传没传)
 *   · 点了之后 pkg 有没有更新(状态没接的话界面不动)
 *   · 组卷之后那两个试卷下载链接有没有**从禁用变成可用**
 *   · 导出链接点下去浏览器会不会真的下载
 *
 * 这些只有真浏览器能证明。
 *
 * ═══════════════════════════════════════════════════════════════
 * 断言读 data-*,不读文字
 * ═══════════════════════════════════════════════════════════════
 * 断言 innerText 的脚本会在改文案或加语言之后**静默通过** ——
 * 选择器没匹配上,断言就变成了空转。所以状态一律从
 * `data-teacher-tools` / `data-questions` / `data-paper` / `data-export` 读。
 *
 * 用法:
 *   node verify-teacher-tools.mjs [页面地址] [截图前缀]
 *   CDP_PORT=9223 API_BASE=http://127.0.0.1:8000 node verify-teacher-tools.mjs
 */

import { writeFileSync } from "node:fs";

const URL_ = process.argv[2] ?? "http://localhost:3000";
const OUT = process.argv[3] ?? "/tmp/teacher-tools";
const PORT = Number(process.env.CDP_PORT ?? 9222);
const API = process.env.API_BASE ?? "http://127.0.0.1:8000";
const DOWNLOAD_DIR = process.env.DOWNLOAD_DIR ?? "/tmp/teacher-tools-downloads";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// 状态是进程级全局的,活过页面刷新。不清的话新页面一加载就恢复出上次的产物,
// 于是「还没生成的初始状态」根本测不到。
try {
  const r = await fetch(`${API}/api/demo/reset`, { method: "POST" });
  console.log(`后端状态已清空 (${r.status})`);
} catch (e) {
  console.log(`⚠️  清空后端状态失败:${e.message} —— 后面的断言不可信`);
}

const problems = [];
const fail = (msg) => {
  problems.push(msg);
  console.log(`  ❌ ${msg}`);
};
const pass = (msg) => console.log(`  ✅ ${msg}`);

// ── 拿一个**页面** target ────────────────────────────────────────
// 不能只从 `/json` 里挑 `type === "page"`:Chrome 155 用 `about:blank` 起
// headless 时,那个 target 报的是 `type: "other"`,而 `/json` 里根本没有
// 一个 `page`。这时候脚本会连上 browser_ui 之类的 target,
// 然后卡在第一个 `Page.enable` 上 —— 表现为「unsettled top-level await」,
// 看不出真正的原因。
//
// 所以显式建一个页面。PUT 是较新 Chrome 的要求(GET 会 405)。
let target = null;
for (const [method, url] of [
  ["PUT", `http://127.0.0.1:${PORT}/json/new?about:blank`],
  ["GET", `http://127.0.0.1:${PORT}/json/new?about:blank`],
]) {
  try {
    const r = await fetch(url, { method });
    if (r.ok) {
      target = await r.json();
      break;
    }
  } catch {
    /* 换下一个方法 */
  }
}
if (!target) {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json();
  target = list.find((t) => t.type === "page");
}
if (!target?.webSocketDebuggerUrl) {
  throw new Error(`CDP:${PORT} 上拿不到页面 target —— Chrome 起来了吗?`);
}
console.log(`  CDP target: ${target.type ?? "?"} ${target.url ?? ""}`);
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
  const r = await send("Runtime.evaluate", {
    expression: expr,
    returnByValue: true,
    awaitPromise: true,
  });
  if (r.result?.exceptionDetails) return "EXC: " + r.result.exceptionDetails.text;
  return r.result?.result?.value;
};
const shoot = async (name) => {
  const r = await send("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: true,
  });
  writeFileSync(`${OUT}-${name}.png`, Buffer.from(r.result.data, "base64"));
  console.log(`  shot -> ${OUT}-${name}.png`);
};
const clickText = async (label) =>
  ev(`(() => {
    const b = [...document.querySelectorAll('button')].find(x => x.textContent.trim() === ${JSON.stringify(label)});
    if (!b) return 'not found';
    if (b.disabled) return 'disabled';
    b.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
    return 'ok';
  })()`);

/** 从 data-* 读工具栏状态。 */
const toolsState = () =>
  ev(`(() => {
    const el = document.querySelector('[data-teacher-tools="1"]');
    if (!el) return null;
    return {
      questions: Number(el.dataset.questions),
      glossary: Number(el.dataset.glossary),
      paper: el.dataset.paper,
      paperPoints: Number(el.dataset.paperPoints),
      paperTarget: Number(el.dataset.paperTarget),
      exports: [...el.querySelectorAll('[data-export]')].map(x => ({
        kind: x.dataset.export,
        ready: x.dataset.exportReady,
        href: x.getAttribute('href'),
      })),
    };
  })()`);

await send("Page.enable");
await send("Runtime.enable");
await send("Log.enable");
await send("Browser.setDownloadBehavior", {
  behavior: "allow",
  downloadPath: DOWNLOAD_DIR,
});
await send("Emulation.setDeviceMetricsOverride", {
  width: 1680,
  height: 1500,
  deviceScaleFactor: 2,
  mobile: false,
});

// ═══════════════════════════════════════════════════════════════
console.log("\n═══ 1. 生成课件,进工作台 ═══");
// ═══════════════════════════════════════════════════════════════
await send("Page.navigate", { url: URL_ });
await sleep(4500);
console.log("  click Generate draft ->", await clickText("Generate draft"));

let entered = false;
for (let i = 0; i < 50; i++) {
  await sleep(300);
  const n = await ev("document.querySelectorAll('article[id^=\"slide-\"]').length");
  if (typeof n === "number" && n > 0) {
    console.log(`  工作台出现,${n} 页`);
    entered = true;
    break;
  }
}
if (!entered) {
  fail("没进到工作台 —— 后面的断言都没意义");
} else {
  pass("进了工作台");
}
await sleep(1200);

// ═══════════════════════════════════════════════════════════════
console.log("\n═══ 2. 工具栏渲染出来了,且是「还没生成」的初始状态 ═══");
// ═══════════════════════════════════════════════════════════════
const initial = await toolsState();
console.log("  ", JSON.stringify(initial));
if (!initial) {
  fail("页面上找不到 [data-teacher-tools] —— 组件没渲染");
} else {
  if (initial.questions !== 0) fail(`初始应有 0 道题,实际 ${initial.questions}`);
  if (initial.glossary !== 0) fail(`初始应有 0 条词条,实际 ${initial.glossary}`);
  if (initial.paper !== "none") fail(`初始试卷状态应是 none,实际 ${initial.paper}`);
  const kinds = initial.exports.map((e) => e.kind).join(",");
  const want = "deck,plan,exam-teacher,exam-student";
  if (kinds !== want) fail(`导出链接应是 ${want},实际 ${kinds}`);
  const exams = initial.exports.filter((e) => e.kind.startsWith("exam"));
  if (exams.some((e) => e.ready !== "false")) {
    fail("还没组卷,试卷下载不该是可用的");
  } else {
    pass("初始状态正确(试卷下载已禁用)");
  }
}
await shoot("01-initial");

// ═══════════════════════════════════════════════════════════════
console.log("\n═══ 3. 出题 ═══");
// ═══════════════════════════════════════════════════════════════
console.log("  click Generate questions ->", await clickText("Generate questions"));
let afterQuestions = null;
for (let i = 0; i < 30; i++) {
  await sleep(300);
  const s = await toolsState();
  if (s && s.questions > 0) {
    afterQuestions = s;
    break;
  }
}
if (!afterQuestions) {
  fail("点了出题之后题数还是 0 —— 按钮没接上,或者接口失败");
} else {
  pass(`出了 ${afterQuestions.questions} 道题`);
}
await shoot("02-questions");

// ═══════════════════════════════════════════════════════════════
console.log("\n═══ 4. 组卷(改成 20 分再点)═══");
// ═══════════════════════════════════════════════════════════════
const setTotal = await ev(`(() => {
  const el = document.querySelector('[data-field="total"]');
  if (!el) return 'not found';
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(el, '20');
  el.dispatchEvent(new Event('input', { bubbles: true }));
  return el.value;
})()`);
console.log("  总分设为:", setTotal);
await sleep(300);
console.log("  click Build paper ->", await clickText("Build paper"));

let afterPaper = null;
for (let i = 0; i < 30; i++) {
  await sleep(300);
  const s = await toolsState();
  if (s && s.paper !== "none") {
    afterPaper = s;
    break;
  }
}
if (!afterPaper) {
  fail("点了组卷之后试卷状态还是 none");
} else {
  console.log(
    `  试卷: ${afterPaper.paper}  实际 ${afterPaper.paperPoints} 分 / 目标 ${afterPaper.paperTarget} 分`,
  );
  if (afterPaper.paper !== "exact") {
    fail(`组卷没凑出精确总分(状态 ${afterPaper.paper})`);
  } else if (afterPaper.paperPoints !== 20) {
    fail(`总分应是 20,实际 ${afterPaper.paperPoints}`);
  } else {
    pass("卷子总分精确等于 20");
  }
  const exams = afterPaper.exports.filter((e) => e.kind.startsWith("exam"));
  const hrefs = exams.map((e) => e.href).filter(Boolean);
  if (exams.some((e) => e.ready !== "true")) {
    fail("组完卷了,试卷下载还是禁用的");
  } else if (!hrefs.every((h) => h.includes("export/exam-paper.docx"))) {
    fail(`试卷下载地址不对: ${hrefs.join(" | ")}`);
  } else {
    pass("试卷下载已启用,地址正确");
  }
}
await shoot("03-paper");

// ═══════════════════════════════════════════════════════════════
console.log("\n═══ 5. 术语白话化 ═══");
// ═══════════════════════════════════════════════════════════════
console.log("  click Plain-language glossary ->", await clickText("Plain-language glossary"));
let afterGlossary = null;
for (let i = 0; i < 30; i++) {
  await sleep(300);
  const s = await toolsState();
  if (s && s.glossary > 0) {
    afterGlossary = s;
    break;
  }
}
if (!afterGlossary) {
  fail("点了白话化之后词条数还是 0");
} else {
  pass(`${afterGlossary.glossary} 条词条`);
}
await shoot("04-glossary");

// ═══════════════════════════════════════════════════════════════
console.log("\n═══ 6. 下载真的会发生吗 ═══");
// ═══════════════════════════════════════════════════════════════
// 光看到 <a href> 不算数 —— 后端返回 409 的话链接照样「可点」。
const downloadProbe = await ev(`(async () => {
  const results = [];
  for (const kind of ['deck.pptx', 'lesson-plan.docx', 'exam-paper.docx']) {
    const r = await fetch('${API}/api/demo/export/' + kind, { method: 'GET' });
    const buf = await r.arrayBuffer();
    results.push({ kind, status: r.status, bytes: buf.byteLength,
                   isZip: new Uint8Array(buf, 0, 4).join(',') === '80,75,3,4' });
  }
  return results;
})()`);
for (const r of downloadProbe ?? []) {
  const ok = r.status === 200 && r.isZip;
  console.log(`  ${ok ? "✅" : "❌"} ${r.kind}  HTTP ${r.status}  ${r.bytes} 字节  ${r.isZip ? "合法 zip" : "不是 zip"}`);
  if (!ok) fail(`${r.kind} 下载失败或不是合法 Office 文件`);
}

// ═══════════════════════════════════════════════════════════════
console.log("\n═══ 7. 控制台有没有报错 ═══");
// ═══════════════════════════════════════════════════════════════
if (errs.length) {
  fail(`控制台有 ${errs.length} 条错误`);
  for (const e of errs.slice(0, 6)) console.log("     ", e.slice(0, 160));
} else {
  pass("零控制台错误");
}

// ═══════════════════════════════════════════════════════════════
console.log("\n" + "═".repeat(60));
if (problems.length) {
  console.log(`❌ ${problems.length} 个问题:`);
  for (const p of problems) console.log("   · " + p);
  process.exit(1);
} else {
  console.log("✅ 教师端后几步:全部通过");
  process.exit(0);
}
