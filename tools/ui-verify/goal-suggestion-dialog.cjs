// The goal save must announce a changed recommendation in a dialog, and stay
// quiet when saving does not move the suggestion. Uses the disposable preview
// account on the local backend; it restores the goal it started from.
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
    };
    const openDialog = () => page.locator('dialog.portal-suggestion-dialog[open]');
    const suggestedTitle = () => openDialog().locator('.portal-suggestion-dialog__course a').textContent();
    const dismissIfOpen = async () => {
      if (await openDialog().count()) {
        await page.getByRole('button', { name: 'Keep browsing' }).click();
        await openDialog().waitFor({ state: 'detached', timeout: 5000 });
      }
    };

    // 1. Establish the baseline recommendation for 'cyber security'.
    await save('cyber security');
    await dismissIfOpen();

    // 2. Saving the same goal again must not nag: no dialog this time.
    await save('cyber security');
    await page.waitForTimeout(1200);
    assert.equal(await openDialog().count(), 0, 'unchanged goal must not open the dialog');

    // 3. A different goal opens the dialog with the other course.
    await save('big data pipelines');
    await openDialog().waitFor({ state: 'visible', timeout: 10000 });
    assert.equal(await suggestedTitle(), 'Big Data Computing');
    assert.ok((await openDialog().textContent()).includes('It fits the time you have each week.') || (await openDialog().textContent()).includes('It matches words in your background and goal.'));
    await page.getByRole('button', { name: 'Keep browsing' }).click();
    await openDialog().waitFor({ state: 'detached', timeout: 5000 });

    // 4. Moving the goal back re-opens the dialog on the first course.
    await save('cyber security');
    await openDialog().waitFor({ state: 'visible', timeout: 10000 });
    assert.equal(await suggestedTitle(), 'Cyber and Internet Security');
    await page.getByRole('button', { name: 'Keep browsing' }).click();

    // 5. Restore the goal the account started with.
    await save(startGoal);
    await dismissIfOpen();

    console.log('PASS goal-suggestion-dialog: changed goal opens the dialog, unchanged stays quiet');
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
