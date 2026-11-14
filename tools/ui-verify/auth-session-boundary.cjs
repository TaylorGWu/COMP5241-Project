const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.SMOKE_BASE || 'http://127.0.0.1:3001';

// Synthetic HTTP responses exercise the real mounted UI without changing users or courses.
const account = id => ({ id, name: `Instructor ${id}`, email: `${id}@example.test`, role: 'instructor', status: 'approved', reviewReason: null });
const course = id => ({ id: `course-${id}`, title: `${id} private course`, courseCode: id, subject: 'Git', audience: 'Beginner', status: 'draft', description: '', chapterIds: [], durationMin: 30 });
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; };
const settle = page => page.evaluate(() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done))));
const visible = page => page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const failures = [];
  async function scenario(name, run, config = {}) {
    const context = await browser.newContext();
    await context.addCookies([{ name: 'pathpilot_locale', value: 'en', domain: new URL(base).hostname, path: '/' }]);
    const page = await context.newPage();
    page.setDefaultTimeout(5000);
    page.setDefaultNavigationTimeout(5000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const state = { id: 'A', role: config.role || 'instructor', status: config.status || 'approved', courseReads: [], pending: null, csrfReads: 0, loginTokens: [] };
    const identity = id => ({ ...account(id), role: state.role, status: state.status, reviewReason: `${id} review reason` });
    await page.route('**/api/**', async route => {
      const path = new URL(route.request().url()).pathname;
      const json = (body, status = 200) => route.fulfill({ status, json: body });
      if (path === '/api/auth/me') {
        const pending = state.pending;
        if (pending) {
          state.pending = null;
          pending.started.resolve();
          await pending.release.promise;
          await json(pending.status === 401 ? { detail: 'Sign in to continue' } : { user: account(pending.id), csrfToken: `${pending.id}-token` }, pending.status || 200).catch(() => {});
          pending.finished.resolve();
          return;
        }
        return state.id ? json({ user: identity(state.id), csrfToken: `${state.id}-token` }) : json({ detail: 'Sign in to continue' }, 401);
      }
      if (path === '/api/admin/applications') {
        const pending = state.queuePending;
        const id = state.id;
        if (pending) { state.queuePending = null; pending.started.resolve(); await pending.release.promise; }
        await json({ applications: [{ ...account(`app-${id}`), name: `${id} applicant`, status: 'pending', qualificationFilename: 'qualification.pdf', submittedAt: 1700000000 }] });
        pending?.finished.resolve();
        return;
      }
      if (path === '/api/demo/courses') { state.courseReads.push(state.id); return json({ courses: [course(state.id)] }); }
      if (path === '/api/auth/csrf') { state.csrfReads++; return json({ csrfToken: 'fresh-challenge' }); }
      if (path === '/api/auth/login') {
        const token = route.request().headers()['x-csrf-token'];
        state.loginTokens.push(token);
        if (token !== 'fresh-challenge') return json({ detail: 'The form expired. Reload and try again.' }, 403);
        state.id = 'B'; return json({ user: account('B'), csrfToken: 'B-token' });
      }
      if (path === '/api/auth/logout') { state.id = null; return json({ ok: true }); }
      return json({ detail: `Unexpected test request: ${path}` }, 404);
    });
    const hold = (id, status) => { const pending = { id, status, started: deferred(), release: deferred(), finished: deferred() }; state.pending = pending; return pending; };
    const signIn = async () => {
      await page.getByLabel('Email address', { exact: true }).fill('B@example.test');
      await page.getByLabel('Password', { exact: true }).fill('disposable-password');
      await page.getByRole('button', { name: 'Log in', exact: true }).click();
      await page.waitForURL('**/courses');
      await page.getByRole('heading', { name: 'B private course', exact: true }).waitFor();
    };
    try {
      await page.goto(base + (config.path || '/courses'));
      await page.getByText(config.initial || 'A private course', { exact: true }).waitFor();
      await run({ page, state, hold, signIn });
      assert.deepEqual(errors, []);
      console.log('PASS ' + name);
    } catch (error) { failures.push(name); console.error('FAIL ' + name + ': ' + error.message); }
    finally { await context.close(); }
  }
  try {
    await scenario('switching approved accounts remounts private course state', async ({ page, state }) => {
      state.id = 'B';
      await visible(page);
      await page.getByRole('button', { name: 'Your account · Instructor B', exact: true }).waitFor();
      await page.getByRole('heading', { name: 'B private course', exact: true }).waitFor({ timeout: 3000 });
      assert.equal(await page.getByRole('heading', { name: 'A private course', exact: true }).count(), 0);
      assert.deepEqual(state.courseReads, ['A', 'B']);
    });
    await scenario('a late identity response cannot undo a newer account refresh', async ({ page, state, hold }) => {
      const pending = hold('A');
      await visible(page); await pending.started.promise;
      state.id = 'B'; await visible(page);
      await page.getByRole('button', { name: 'Your account · Instructor B', exact: true }).waitFor();
      pending.release.resolve(); await pending.finished.promise; await settle(page);
      assert.equal(await page.getByRole('button', { name: 'Your account · Instructor B', exact: true }).count(), 1);
      assert.equal(await page.getByRole('button', { name: 'Your account · Instructor A', exact: true }).count(), 0);
    });
    await scenario('visibility expiry obtains a fresh challenge before login', async ({ page, state, signIn }) => {
      state.id = null; await visible(page);
      await page.waitForURL('**/login?next=*');
      await signIn();
      assert.equal(state.csrfReads, 1);
      assert.deepEqual(state.loginTokens, ['fresh-challenge']);
    });
    for (const status of [200, 401]) await scenario(`a refresh started before logout cannot undo a newly accepted account (${status})`, async ({ page, state, hold, signIn }) => {
      const pending = hold('A', status);
      await visible(page); await pending.started.promise;
      await page.locator('[data-account-menu-trigger]').click();
      await page.getByRole('button', { name: 'Sign out', exact: true }).click();
      await page.waitForURL(url => url.pathname === '/login');
      await signIn();
      pending.release.resolve(); await pending.finished.promise; await settle(page);
      assert.equal(new URL(page.url()).pathname, '/courses');
      assert.equal(await page.getByRole('button', { name: 'Your account · Instructor B', exact: true }).count(), 1);
      assert.equal(await page.getByRole('heading', { name: 'B private course', exact: true }).count(), 1);
      assert.equal(state.csrfReads, 1);
    });
    await scenario('a former administrator queue response cannot replace the new account queue', async ({ page, state }) => {
      const pending = { started: deferred(), release: deferred(), finished: deferred() };
      state.queuePending = pending;
      await page.getByRole('button', { name: 'Check status', exact: true }).click();
      await pending.started.promise;
      state.id = 'B'; await visible(page);
      await page.getByText('B applicant', { exact: true }).waitFor();
      pending.release.resolve(); await pending.finished.promise; await settle(page);
      assert.equal(await page.getByText('B applicant', { exact: true }).count(), 1);
      assert.equal(await page.getByText('A applicant', { exact: true }).count(), 0);
    }, { role: 'admin', status: 'active', path: '/admin', initial: 'A applicant' });
    await scenario('changing applicants discards the previous qualification file', async ({ page, state }) => {
      await page.locator('input[type=file]').setInputFiles({ name: 'A-private-credential.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\n%%EOF') });
      state.id = 'B'; await visible(page);
      await page.getByText('B@example.test', { exact: true }).waitFor();
      assert.equal(await page.locator('input[type=file]').evaluate(input => input.files.length), 0);
      assert.equal(await page.getByText('A-private-credential.pdf', { exact: true }).count(), 0);
    }, { status: 'rejected', path: '/application', initial: 'A@example.test' });
  } finally { await browser.close(); }
  if (failures.length) throw new Error(`${failures.length} session boundary regression(s) failed: ${failures.join('; ')}`);
})().catch(error => { console.error(error); process.exitCode = 1; });
