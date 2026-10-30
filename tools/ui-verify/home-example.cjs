const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.SMOKE_BASE || 'http://127.0.0.1:3000';
const output = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'coursework-workflow-'));

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    for (const locale of ['en', 'zh-HK', 'zh-CN']) for (const width of [1440, 390, 320]) {
      const context = await browser.newContext({ viewport: { width, height: 950 }, reducedMotion: 'reduce', colorScheme: width === 390 ? 'dark' : 'light' });
      await context.addCookies([{ name: 'pathpilot_locale', value: locale, domain: new URL(base).hostname, path: '/' }]);
      const page = await context.newPage(); const errors = []; const writes = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/api/auth/me', route => route.fulfill({ status: 401, json: { detail: 'Not authenticated' } }));
      page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/api/') && request.method() !== 'GET') writes.push(request.url()); });
      await page.goto(base + '/');
      const demo = page.locator('.workflow-demo');
      await demo.waitFor(); await demo.scrollIntoViewIfNeeded();
      await page.evaluate(() => document.fonts.ready);
      const phase = async () => Number(await demo.getAttribute('data-phase'));
      assert.equal(await phase(), 0);
      await demo.locator('[data-demo-next]').focus(); await page.keyboard.press('Enter');
      assert.equal(await phase(), 1, 'create course produces its card');
      assert.equal(await demo.locator('.workflow-canvas').evaluate(element => element === document.activeElement), true, 'keyboard focus survives replacing a scene');
      await demo.locator('[data-demo-next]').click();
      assert.equal(await phase(), 2, 'add chapter opens the chapter brief');
      await demo.locator('[data-demo-next]').click();
      assert.equal(await phase(), 3, 'generation exposes the chapter preview');
      await demo.screenshot({ path: path.join(output, `${locale}-${width}-chapter.png`) });
      await demo.locator('[data-demo-next]').click();
      assert.equal(await phase(), 4, 'edit request exposes an unapplied proposal');
      const before = await demo.locator('[data-demo-preview]').innerText();
      await demo.locator('[data-demo-accept]').focus(); await page.keyboard.press('Enter');
      assert.equal(await phase(), 5);
      assert.notEqual(await demo.locator('[data-demo-preview]').innerText(), before, 'confirmation visibly updates the draft');
      assert.equal(await demo.locator('[data-demo-accept]').isDisabled(), true);
      await demo.screenshot({ path: path.join(output, `${locale}-${width}-confirmed.png`) });
      await page.locator('[data-demo-replay]').click();
      assert.equal(await phase(), 0);
      assert.equal(await demo.getAttribute('data-playing'), 'false', 'replay respects reduced motion');
      await demo.locator('[data-demo-step="2"]').click();
      assert.equal(await phase(), 4, 'manual navigation resets the proposal to pending');
      await demo.locator('[data-demo-step="0"]').click();
      assert.equal(await phase(), 0);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      await demo.screenshot({ path: path.join(output, `${locale}-${width}.png`) });
      assert.deepEqual(errors, []); assert.deepEqual(writes, []);
      console.log('PASS workflow, keyboard confirmation, replay, steps, no writes:', locale, width);
      await context.close();
    }
    const page = await browser.newPage({ viewport: { width: 1440, height: 950 }, reducedMotion: 'no-preference' });
    await page.route('**/api/auth/me', route => route.fulfill({ status: 401, json: { detail: 'Not authenticated' } }));
    await page.goto(base + '/');
    const demo = page.locator('.workflow-demo');
    await demo.waitFor(); await demo.scrollIntoViewIfNeeded();
    await page.waitForFunction(() => document.querySelector('.workflow-demo')?.dataset.phase === '1', null, { timeout: 10000 });
    await page.locator('[data-demo-play]').click();
    const paused = await demo.getAttribute('data-phase');
    await page.waitForTimeout(4500);
    assert.equal(await demo.getAttribute('data-phase'), paused, 'pause stops timed scene changes');
    await page.locator('[data-demo-play]').click();
    await page.waitForFunction(() => document.querySelector('.workflow-demo')?.dataset.running === 'true');
    // The walkthrough now lives inside the hero. Scroll below it to exercise
    // suspension; scrollY=0 intentionally keeps it visible in the first view.
    await page.setViewportSize({ width: 1440, height: 500 });
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await page.waitForFunction(() => document.querySelector('.workflow-demo').getBoundingClientRect().bottom <= 0);
    await page.waitForFunction(() => document.querySelector('.workflow-demo')?.dataset.running === 'false');
    const offscreen = await demo.getAttribute('data-phase');
    await page.waitForTimeout(4500);
    assert.equal(await demo.getAttribute('data-phase'), offscreen, 'offscreen demo does not advance');
    await demo.scrollIntoViewIfNeeded();
    try {
      await page.waitForFunction(previous => document.querySelector('.workflow-demo')?.dataset.phase !== previous, offscreen, { timeout: 10000 });
    } catch (error) {
      console.error('Resume diagnostics', await demo.evaluate(element => ({ ...element.dataset, top: element.getBoundingClientRect().top, height: element.getBoundingClientRect().height, viewport: innerHeight, hidden: document.hidden, scroll: scrollY })));
      throw error;
    }
    await page.waitForFunction(() => document.querySelector('.workflow-demo')?.dataset.phase === '5', null, { timeout: 25000 });
    assert.equal(await demo.getAttribute('data-running'), 'false', 'autoplay ends at the confirmed draft');
    assert.equal(await demo.locator('[data-demo-accept]').isDisabled(), true);
    await page.close();
    console.log('PASS autoplay, pause, resume and offscreen suspension');
    console.log('Screenshots:', output);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
