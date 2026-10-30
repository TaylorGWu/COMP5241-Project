const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const base = process.env.SMOKE_BASE || 'http://127.0.0.1:3000';
const output = fs.mkdtempSync(path.join(os.tmpdir(), 'coursework-public-refinement-'));
const user = { id: 'visual-test', name: 'Preview Teacher', email: 'preview@example.test', role: 'instructor', status: 'pending', reviewReason: null, qualificationSubmitted: true };
const profile = { name: user.name, bio: 'I help beginners learn software engineering through practical examples.', institution: 'Example College', independent: false, position: 'Lecturer', university: 'Example University', degree: 'master', experience: '3-5', subjects: ['programming', 'testing'], otherSubject: '', hasAvatar: false, avatarVersion: null };
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const errors = [];
  try {
    for (const [locale, width, theme, status = 'pending'] of [['en',1440,'light'], ['en',390,'light'], ['en',320,'light'], ['zh-HK',1440,'light'], ['zh-CN',390,'dark'], ['en',1024,'dark'], ['en',390,'light','approved']]) {
      user.status = status;
      const context = await browser.newContext({ viewport: { width, height: 1000 }, colorScheme: theme, reducedMotion: 'reduce' });
      await context.addCookies([{ name: 'pathpilot_locale', value: locale, domain: new URL(base).hostname, path: '/' }]);
      const page = await context.newPage();
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/api/**', route => {
        const api = new URL(route.request().url()).pathname;
        if (route.request().method() !== 'GET') throw new Error('Visual checks must not mutate data');
        if (api === '/api/auth/me') return route.fulfill({ json: { user, csrfToken: 'visual-test' } });
        if (api === '/api/auth/profile') return route.fulfill({ json: { profile } });
        throw new Error('Unexpected API request ' + api);
      });
      for (const route of status === 'approved' ? ['/profile'] : ['/', '/profile', '/application']) {
        await page.goto(base + route);
        await page.locator('main h1').waitFor();
        if (route === '/profile') await page.locator('#teacher-name').waitFor();
        await page.evaluate(() => document.fonts.ready);
        const metrics = await page.evaluate(() => {
          const main = document.querySelector('main'); const h1 = main.querySelector('h1');
          const header = main.querySelector('.public-header');
          return { overflow: document.documentElement.scrollWidth > innerWidth, titleFont: getComputedStyle(h1).fontFamily,
            bodyFont: getComputedStyle(main).fontFamily, headerHeight: header.getBoundingClientRect().height,
            heroTopPadding: main.querySelector('.public-hero') ? parseFloat(getComputedStyle(main.querySelector('.public-hero')).paddingTop) : null,
            duplicateAccountRows: document.querySelectorAll('main .account-actions').length,
            wrongWorkspace: !!header.querySelector('a[href="/application"].public-button'),
            images: [...document.querySelectorAll('main img')].map(image => ({ loaded: image.complete && image.naturalWidth > 0, width: image.width, height: image.height })) };
        });
        assert.equal(metrics.overflow, false, `${route} ${locale} ${width}: no horizontal overflow`);
        assert.match(metrics.titleFont, /Manrope|Noto Sans|Noto_Sans/);
        assert.match(metrics.bodyFont, route === '/' || route === '/profile' ? /Manrope|Noto Sans|Noto_Sans/ : /Source Sans|Source_Sans|Noto Sans|Noto_Sans/);
        if (width >= 1024) assert.ok(metrics.headerHeight <= 80, 'desktop navigation stays compact');
        if (route === '/') {
          assert.ok(metrics.headerHeight <= 65, `home navigation is a compact bar rather than a banner: ${metrics.headerHeight}px`);
          assert.ok(metrics.heroTopPadding <= 48, 'home content begins close to the navigation');
        }
        if (route !== '/') assert.equal(metrics.duplicateAccountRows, 1, 'one account navigation only');
        if (status === 'approved') {
          await page.locator('[data-account-menu-trigger]').click();
          assert.equal(await page.locator('.account-menu-links a[href="/courses"]').isVisible(), true, 'approved mobile teachers retain a workspace exit in the account menu');
          await page.keyboard.press('Escape');
        }
        if (route === '/application') assert.equal(metrics.wrongWorkspace, false, 'pending review must not point a primary workspace button at itself');
        if (route === '/application') {
          assert.equal(await page.locator('.public-header .account-name').count(), 0, 'application identity is not duplicated in navigation');
          assert.equal(await page.locator('.application-identity strong').innerText(), user.name);
          assert.equal(await page.locator('.application-identity .teacher-photo').count(), 1, 'identity stays with its avatar in the application card');
        }
        if (route === '/') assert.equal(await page.locator('.public-hero .workflow-demo').isVisible(), true, 'homepage leads with the working product walkthrough');
        await page.screenshot({ path: path.join(output, `${route === '/' ? 'home' : route.slice(1)}-${locale}-${width}-${theme}${status === 'approved' ? '-approved' : ''}.png`), fullPage: true });
        console.log('PASS', route, locale, width, theme, metrics.titleFont);
        if (status === 'approved') {
          await page.locator('#teacher-bio').fill('Keep this unsaved introduction during language changes.');
          await page.locator('.global-system-settings__trigger').click();
          await page.getByTitle('简体中文', { exact: true }).click();
          await page.waitForFunction(() => document.documentElement.lang === 'zh-CN' && getComputedStyle(document.querySelector('main')).fontFamily.includes('Noto Sans SC'));
          assert.equal(await page.locator('#teacher-bio').inputValue(), 'Keep this unsaved introduction during language changes.');
          await page.getByTitle('繁體中文', { exact: true }).click();
          await page.waitForFunction(() => document.documentElement.lang === 'zh-HK' && getComputedStyle(document.querySelector('main')).fontFamily.includes('Noto Sans TC'));
          assert.equal(await page.locator('#teacher-bio').inputValue(), 'Keep this unsaved introduction during language changes.');
          console.log('PASS live EN/SC/TC font switching preserves dirty profile input');
        }
      }
      await context.close();
    }
    user.status = 'pending';
    for (const mode of ['photo', 'missing', 'failed']) {
      const context = await browser.newContext({ viewport: { width: 390, height: 950 } });
      const page = await context.newPage();
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/api/**', route => {
        const api = new URL(route.request().url()).pathname;
        assert.equal(route.request().method(), 'GET', 'identity rendering never writes account data');
        if (api === '/api/auth/me') return route.fulfill({ json: { user, csrfToken: 'visual-test' } });
        if (api === '/api/auth/profile') return mode === 'failed' ? route.fulfill({ status: 503, json: { detail: 'Unavailable' } }) : route.fulfill({ json: { profile: { ...profile, hasAvatar: mode === 'photo', avatarVersion: mode === 'photo' ? 'test-photo' : null } } });
        if (api === '/api/auth/avatar') return route.fulfill({ contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1kAAAAASUVORK5CYII=', 'base64') });
        throw new Error('Unexpected identity request ' + api);
      });
      await page.goto(base + '/application');
      await page.locator('.application-identity strong').waitFor();
      if (mode === 'photo') {
        await page.locator('.application-identity img').waitFor();
        await page.locator('.application-identity img').evaluate(image => image.decode());
      } else assert.equal(await page.locator('.application-identity .teacher-photo--initial').count(), 1);
      assert.equal(await page.locator('.public-header .account-name').count(), 0);
      assert.equal(await page.locator('.application-identity strong').innerText(), user.name);
      assert.equal(await page.locator('.application-identity a').isVisible(), true);
      await page.locator('.application-status-refresh button').click();
      await page.waitForFunction(() => document.querySelector('.application-status-refresh [role="status"]')?.textContent.trim().length > 0 && document.querySelector('.application-status-refresh button')?.getAttribute('aria-busy') === 'false');
      assert.equal(await page.locator('.application-panel').isVisible(), true, 'photo/profile failure does not block status refresh');
      console.log('PASS application identity', mode);
      await context.close();
    }
    assert.deepEqual(errors, []);
    console.log('Screenshots:', output);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
