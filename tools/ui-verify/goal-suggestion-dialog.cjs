// The goal save must NOT interrupt with a dialog: it refreshes the My learning
// bell, which carries the suggestion as a notification pill and rings until
// the learner opens it - and rings again when the recommendation changes.
// Uses the disposable preview account on the local backend; it restores the
// goal it started from.
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.SMOKE_BASE || 'http://localhost:3000';
const email = 'student@preview.example.test';
const password = 'a long example password';
const goalField = 'What would you like to learn?';

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const failures = [];
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 950 }, reducedMotion: 'reduce' });
    await context.addCookies([{ name: 'pathpilot_locale', value: 'en', domain: new URL(base).hostname, path: '/' }]);
    const page = await context.newPage();
    page.on('pageerror', (error) => failures.push(error.message));

    await page.goto(base + '/login');
    await page.getByLabel('Email address', { exact: true }).fill(email);
    await page.getByLabel('Password', { exact: true }).fill(password);
    await page.getByRole('button', { name: 'Log in', exact: true }).click();
    await page.waitForURL(base + '/student');

    // The account may already sit on any goal, so the script builds its own
    // baseline instead of assuming one.
    await page.goto(base + '/student/profile');
    const startGoal = await page.getByLabel(goalField, { exact: true }).inputValue();

    const save = async (goal) => {
      await page.getByLabel(goalField, { exact: true }).fill(goal);
      await page.getByRole('button', { name: 'Save goals', exact: true }).click();
      await page.getByText('Saved', { exact: true }).waitFor({ timeout: 10000 });
      await page.waitForTimeout(600);
      assert.equal(await page.locator('dialog.portal-suggestion-dialog[open]').count(), 0, 'Saving stays on the form; the bell carries the news');
    };
    const bell = () => page.locator('.portal-tabs-notification');
    const openDialog = () => page.locator('dialog.portal-suggestion-dialog[open]');
    const suggestedTitle = () => openDialog().locator('.portal-course h3 a').textContent();
    const closeDialog = async () => {
      await page.getByRole('button', { name: 'Keep browsing' }).click();
      await openDialog().waitFor({ state: 'detached', timeout: 5000 });
    };

    // 1. A save that changes the recommendation rings the bell; the dialog
    //    opens only from the bell.
    await save('cyber security');
    await page.goto(base + '/student');
    await bell().waitFor();
    assert.ok(await bell().locator('.portal-tabs-notification__dot').count(), 'A standing suggestion marks the bell with a dot');
    assert.ok((await bell().textContent()).includes('Suggested next course'), 'The notification names itself');
    assert.ok(await bell().getAttribute('data-attention') !== null, 'An unopened suggestion rings the bell');
    await bell().click();
    await openDialog().waitFor({ state: 'visible', timeout: 10000 });
    assert.equal(await suggestedTitle(), 'Cyber and Internet Security');
    await closeDialog();
    assert.equal(await bell().getAttribute('data-attention'), null, 'Opening the suggestion stops the ring');

    // 2. Saving the same goal again leaves the bell quiet.
    await page.goto(base + '/student/profile');
    await save('cyber security');
    await page.goto(base + '/student');
    await bell().waitFor();
    assert.equal(await bell().getAttribute('data-attention'), null, 'An unchanged recommendation does not ring again');
    assert.ok(await bell().locator('.portal-tabs-notification__dot').count(), 'The suggestion stays on the bell');

    // 3. A different goal rings the bell again, with the other course.
    await page.goto(base + '/student/profile');
    await save('big data pipelines');
    await page.goto(base + '/student');
    await bell().waitFor();
    assert.ok(await bell().getAttribute('data-attention') !== null, 'A changed recommendation rings again');
    await bell().click();
    await openDialog().waitFor({ state: 'visible', timeout: 10000 });
    assert.equal(await suggestedTitle(), 'Big Data Computing');
    await closeDialog();

    // 4. Restore the goal the account started with.
    await page.goto(base + '/student/profile');
    await save(startGoal);

    console.log('PASS goal-suggestion-dialog: save rings the bell, only the bell opens the dialog');
  } catch (error) {
    failures.push(error instanceof Error ? error.message : String(error));
  } finally {
    await browser.close();
  }
  if (failures.length) {
    console.error('FAIL goal-suggestion-dialog:\n' + failures.join('\n'));
    process.exit(1);
  }
})();
