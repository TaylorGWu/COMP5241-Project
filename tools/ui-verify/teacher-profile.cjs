const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const base = process.env.SMOKE_BASE || 'http://127.0.0.1:3000';
const output = fs.mkdtempSync(path.join(os.tmpdir(), 'teacher-profile-ui-'));
// Synthetic HTTP boundaries exercise mounted controls without mutating real accounts.
const user = { id: 'profile-test', name: 'Preview Teacher', email: 'preview@example.test', role: 'instructor', status: 'pending', reviewReason: null, qualificationSubmitted: true };
let profile = { name: user.name, bio: '', institution: '', independent: false, position: '', university: '', degree: '', experience: '', subjects: [], otherSubject: '', hasAvatar: false, avatarVersion: null };
let failSave = false, failStatus = false, expireProfile = false;
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1kAAAAASUVORK5CYII=', 'base64');
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1050 }, reducedMotion: 'reduce' });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await context.addCookies([{ name: 'pathpilot_locale', value: 'en', domain: new URL(base).hostname, path: '/' }]);
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url()).pathname;
    const method = route.request().method();
    const reply = (data, status=200) => route.fulfill({ status, json: data });
    if (url === '/api/auth/me') {
      await new Promise(resolve => setTimeout(resolve, 250));
      return failStatus ? reply({ detail: 'Status service unavailable. Try again.' }, 503) : reply({ user, csrfToken: 'test-csrf' });
    }
    if (url === '/api/auth/csrf') return reply({ csrfToken: 'test-csrf' });
    if (url === '/api/admin/applications') return reply({ applications: [{ ...user, role: 'instructor', status: 'pending', qualificationFilename: 'test-proof.pdf', submittedAt: 1792684800 }] });
    if (url.endsWith('/profile') && url.startsWith('/api/admin/applications/')) return reply({ profile });
    if (url.endsWith('/avatar') && url.startsWith('/api/admin/applications/')) return route.fulfill({ contentType: 'image/png', body: png });
    if (url === '/api/auth/profile') {
      if (expireProfile) return reply({ detail: 'Sign in to continue' }, 401);
      if (method === 'PUT') {
        await new Promise(resolve => setTimeout(resolve, 300));
        if (failSave) return reply({ detail: 'Profile could not be saved. Try again.' }, 503);
        profile = { ...profile, ...route.request().postDataJSON() };
        user.name = profile.name;
      }
      return reply({ profile });
    }
    if (url === '/api/auth/avatar') {
      if (method === 'GET') return route.fulfill({ contentType: 'image/png', body: png });
      profile.hasAvatar = method !== 'DELETE';
      profile.avatarVersion = profile.hasAvatar ? String(Date.now()) : null;
      return reply({ profile });
    }
    if (url === '/api/demo/courses') return reply({ courses: [] });
    throw new Error(`Unexpected request: ${method} ${url}`);
  });
  try {
    await page.goto(base + '/profile');
    await page.getByRole('heading', { name: 'Teacher profile', exact: true }).waitFor();
    await page.locator('#teacher-name').fill('Updated Teacher');
    await page.getByLabel('University / college', { exact: true }).fill('Example University');
    await page.getByLabel('Highest qualification', { exact: true }).selectOption('master');
    await page.getByLabel('Teaching experience', { exact: true }).selectOption('3-5');
    await page.getByRole('button', { name: 'Choose subjects', exact: true }).click();
    await page.getByLabel('Search subjects', { exact: true }).fill('data');
    await page.getByRole('checkbox', { name: 'Databases', exact: true }).check();
    await page.getByRole('button', { name: 'Done', exact: true }).click();
    await page.getByLabel('Current institution', { exact: true }).fill('Example College');
    await page.getByRole('button', { name: 'Save changes', exact: true }).click();
    await page.getByRole('button', { name: 'Saving…', exact: true }).waitFor();
    await page.getByRole('status').filter({ hasText: 'Profile saved' }).waitFor();
    await page.reload();
    assert.equal(await page.getByLabel('University / college', { exact: true }).inputValue(), 'Example University');
    await page.getByLabel('Personal introduction', { exact: true }).fill('Unsaved introduction');
    page.once('dialog', dialog => dialog.dismiss());
    await page.getByRole('link', { name: 'View qualification status', exact: true }).click();
    assert.equal(new URL(page.url()).pathname, '/profile', 'dismissed discard must retain page');
    assert.equal(await page.getByLabel('Personal introduction', { exact: true }).inputValue(), 'Unsaved introduction');
    failSave = true;
    await page.getByRole('button', { name: 'Save changes', exact: true }).click();
    await page.getByRole('alert').filter({ hasText: 'could not be saved' }).waitFor();
    assert.equal(await page.getByLabel('Personal introduction', { exact: true }).inputValue(), 'Unsaved introduction');
    failSave = false;
    await page.getByRole('button', { name: 'Save changes', exact: true }).click();
    await page.getByRole('status').filter({ hasText: 'Profile saved' }).waitFor();
    await page.getByLabel('Job title / role', { exact: true }).fill('Unsaved lecturer');
    await page.locator('#teacher-photo').setInputFiles({ name: 'portrait.png', mimeType: 'image/png', buffer: png });
    await page.getByRole('button', { name: 'Save photo', exact: true }).click();
    await page.getByRole('status').filter({ hasText: 'Photo saved' }).waitFor();
    assert.equal(await page.getByLabel('Job title / role', { exact: true }).inputValue(), 'Unsaved lecturer');
    await page.screenshot({ path: path.join(output, 'profile-desktop.png'), fullPage: true });
    await page.getByRole('button', { name: 'Remove photo', exact: true }).click();
    await page.getByRole('status').filter({ hasText: 'Photo removed' }).waitFor();
    await page.getByLabel('Independent teacher', { exact: true }).check();
    assert.equal(await page.getByLabel('Current institution', { exact: true }).count(), 0);
    await page.getByRole('button', { name: 'Save changes', exact: true }).click();
    await page.getByRole('status').filter({ hasText: 'Profile saved' }).waitFor();
    assert.equal(profile.institution, '');
    for (const locale of ['en', 'zh-HK', 'zh-CN']) {
      await context.addCookies([{ name: 'pathpilot_locale', value: locale, domain: new URL(base).hostname, path: '/' }]);
      await page.setViewportSize({ width: 390, height: 900 });
      await page.emulateMedia({ colorScheme: locale === 'en' ? 'light' : 'dark' });
      await page.reload();
      await page.locator('#teacher-name').waitFor();
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      await page.screenshot({ path: path.join(output, `profile-mobile-${locale}.png`), fullPage: true });
    }
    await context.addCookies([{ name: 'pathpilot_locale', value: 'en', domain: new URL(base).hostname, path: '/' }]);
    await page.goto(base + '/application');
    await page.getByRole('button', { name: 'Refresh status', exact: true }).click();
    await page.getByRole('button', { name: 'Checking…', exact: true }).waitFor();
    await page.getByRole('status').filter({ hasText: 'Still in review' }).waitFor();
    failStatus = true;
    await page.getByRole('button', { name: 'Refresh status', exact: true }).click();
    await page.getByRole('alert').filter({ hasText: 'Status service unavailable' }).waitFor();
    await page.getByRole('heading', { name: 'Your application is in review.' }).waitFor();
    failStatus = false;
    user.status = 'rejected'; user.reviewReason = 'Please upload a clearer credential.';
    await page.getByRole('button', { name: 'Refresh status', exact: true }).click();
    await page.getByRole('heading', { name: 'A little more information is needed.' }).waitFor();
    await page.getByText(user.reviewReason).waitFor();
    user.status = 'pending'; user.reviewReason = null;
    await page.reload();
    await page.getByRole('heading', { name: 'Your application is in review.' }).waitFor();
    user.status = 'approved';
    await page.getByRole('button', { name: 'Refresh status', exact: true }).click();
    await page.waitForURL('**/courses');
    user.role = 'admin'; user.status = 'active';
    await page.goto(base + '/admin');
    await page.getByRole('button', { name: 'View teacher profile', exact: true }).click();
    await page.getByText('Example University', { exact: true }).waitFor();
    await page.getByText("Master's degree", { exact: true }).waitFor();
    await page.screenshot({ path: path.join(output, 'admin-profile-mobile.png'), fullPage: true });
    user.role = 'student';
    await page.goto(base + '/profile');
    await page.waitForURL('**/student');
    user.role = 'instructor'; user.status = 'pending'; expireProfile = true;
    await page.goto(base + '/profile');
    await page.waitForURL('**/login?next=%2Fprofile');
    assert.deepEqual(errors, []);
    console.log('PASS profile edit/save/reload/error retention, navigation guard, subjects, photo save/remove without overwriting edits, independent status, 3 mobile locales, admin disclosure, student guard, expiry, refresh pending/error/rejection/approval');
    console.log('Screenshots:', output);
  } catch (error) { await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true }); console.log('Failure screenshot:', output); throw error; } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
