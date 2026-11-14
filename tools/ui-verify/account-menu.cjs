const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.SMOKE_BASE || 'http://127.0.0.1:3001';
const output = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'coursework-account-menu-'));
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1kAAAAASUVORK5CYII=', 'base64');
const teacher = { id: 'menu-teacher', name: 'Preview Teacher', email: 'teacher@example.test', role: 'instructor', status: 'pending', qualificationSubmitted: true, reviewReason: null };
const profile = { name: teacher.name, bio: '', university: '', institution: '', independent: false, degree: '', position: '', experience: '', subjects: [], otherSubject: '', hasAvatar: true, avatarVersion: 'photo-1' };
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    for (const [locale, width] of [['en',1440], ['zh-HK',390], ['zh-CN',320]]) {
      const context = await browser.newContext({ viewport: { width, height: 950 }, reducedMotion: 'reduce' });
      await context.addCookies([{name:'pathpilot_locale',value:locale,domain:new URL(base).hostname,path:'/'}]);
      const page = await context.newPage(); const errors = [];
      let current = { ...teacher }; let photo = true; let failLogout = false;
      const writes = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/api/**', route => {
        const api = new URL(route.request().url()).pathname;
        const method = route.request().method();
        if (method !== 'GET') writes.push(api);
        if (api === '/api/auth/me') return current ? route.fulfill({json:{user:current,csrfToken:'menu-csrf'}}) : route.fulfill({status:401,json:{detail:'Not authenticated'}});
        if (api === '/api/auth/profile') return route.fulfill({json:{profile:{...profile,hasAvatar:photo,avatarVersion:photo?'photo-1':null}}});
        if (api === '/api/auth/avatar') return route.fulfill({contentType:'image/png',body:png});
        if (api === '/api/auth/logout') {
          if (failLogout) return route.fulfill({status:503,json:{detail:'Try signing out again.'}});
          current = null; return route.fulfill({json:{ok:true}});
        }
        if (api === '/api/demo/courses') return route.fulfill({json:{courses:[]}});
        throw new Error('Unexpected account-menu API '+api);
      });
      for (const route of ['/', '/profile', '/application']) {
        await page.goto(base+route);
        const trigger = page.locator('[data-account-menu-trigger]');
        await trigger.waitFor();
        assert.equal(await page.locator('.public-header a[href="/#how-it-works"]').count(),0,'remove the redundant explainer nav link');
        if(route==='/') assert.equal(await page.locator('[data-workspace-entry]').getAttribute('href'),'/application','pending teachers enter qualification review');
        await page.locator('[data-account-menu-trigger] img').waitFor();
        await trigger.locator('img').evaluate(image=>image.decode());
        assert.equal(await page.locator('[data-account-menu-panel]').count(),0);
        assert.equal(await page.locator('.public-header .account-name').count(),0);
        await trigger.focus(); await page.keyboard.press('Enter');
        const panel = page.locator('[data-account-menu-panel]');
        await panel.waitFor();
        assert.equal(await panel.locator('.account-menu-name').innerText(), teacher.name);
        assert.equal(await panel.locator('a[href="/profile"]').count(),1);
        assert.equal(await panel.locator('a[href="/application"]').count(),1);
        await page.keyboard.press('Escape');
        assert.equal(await panel.count(),0);
        assert.equal(await trigger.evaluate(element=>element===document.activeElement),true);
        await page.keyboard.press('ArrowDown');
        await page.waitForFunction(()=>document.querySelector('.account-menu-links a')===document.activeElement);
        await panel.locator('[data-account-logout]').focus();
        await page.keyboard.press('Tab');
        assert.equal(await panel.count(),0,'tabbing outside closes the disclosure');
        await trigger.click();
        const outsideBounds = await panel.boundingBox();
        // On narrow screens the disclosure intentionally overlays the heading;
        // use the visible page gutter, not a covered element, as the outside hit.
        await page.mouse.click(4, outsideBounds.y + 10);
        assert.equal(await panel.count(),0,'outside click closes account disclosure');
        await trigger.click();
        const bounds = await panel.boundingBox();
        assert.ok(bounds.x>=0 && bounds.x+bounds.width<=width,'dropdown fits narrow viewport');
        await page.screenshot({path:path.join(output,`${route==='/'?'home':route.slice(1)}-${locale}-${width}.png`)});
        await page.keyboard.press('Escape');
      }
      assert.deepEqual(writes,[],'opening account controls never mutates data');
      await page.goto(base+'/');
      photo = false; await page.reload();
      await page.locator('[data-account-menu-trigger] .teacher-photo--initial').waitFor();
      photo = true;
      await page.evaluate(()=>window.dispatchEvent(new Event('coursework-profile-photo-changed')));
      await page.locator('[data-account-menu-trigger] img').waitFor();
      photo = false;
      await page.evaluate(()=>window.dispatchEvent(new Event('coursework-profile-photo-changed')));
      await page.locator('[data-account-menu-trigger] .teacher-photo--initial').waitFor();
      await page.locator('[data-account-menu-trigger]').click();
      failLogout=true;
      await page.locator('[data-account-logout]').click();
      try { await page.getByRole('alert').filter({hasText:'Try signing out again.'}).waitFor({timeout:3000}); }
      catch (error) {
        console.error('Logout disclosure diagnostics',await page.evaluate(()=>({open:document.querySelector('[data-account-menu-trigger]')?.getAttribute('aria-expanded'),panel:!!document.querySelector('[data-account-menu-panel]'),focused:document.activeElement?.tagName})));
        throw error;
      }
      assert.equal(await page.locator('[data-account-menu-trigger]').count(),1);
      failLogout=false;
      await page.locator('[data-account-logout]').click();
      await page.waitForURL('**/login');
      assert.equal(await page.locator('[data-account-menu-trigger]').count(),0);
      await page.goto(base+'/');
      await page.locator('.public-header a[href="/login"]').waitFor();
      assert.equal(await page.locator('[data-workspace-entry]').count(),0,'guest navigation has no duplicated dashboard/login entry');
      assert.equal(await page.locator('.public-header a[href="/register/instructor"]').isVisible(),true,'guest home retains login and teacher registration');
      await context.close();
      assert.deepEqual(errors,[]);
      console.log('PASS shared photo menu, keyboard, outside close, layout, fallback and logout:',locale,width);
    }
    for (const [role,status,destination] of [['instructor','approved','/courses'],['student','active','/student'],['admin','active','/admin']]) {
      const context = await browser.newContext();
      const page = await context.newPage(); let profileReads=0;
      await page.route('**/api/**',route=>{
        const api=new URL(route.request().url()).pathname;
        if(api==='/api/auth/me') return route.fulfill({json:{user:{...teacher,role,status},csrfToken:'role-test'}});
        if(api==='/api/auth/profile'){profileReads++;return route.fulfill({json:{profile:{...profile,hasAvatar:false,avatarVersion:null}}});}
        throw new Error('Unexpected role request '+api);
      });
      await page.goto(base+'/');
      await page.locator('[data-workspace-entry]').waitFor();
      assert.equal(await page.locator('[data-workspace-entry]').getAttribute('href'),destination,'dashboard entry respects role and approval');
      await page.locator('[data-account-menu-trigger]').click();
      assert.equal(await page.locator(`[data-account-menu-panel] a[href="${destination}"]`).count(),1);
      assert.equal(await page.locator('[data-account-menu-panel] a[href="/profile"]').count(),role==='instructor'?1:0);
      if(role!=='instructor') assert.equal(profileReads,0,'non-teachers do not request private teacher profiles');
      await context.close();
      console.log('PASS role-specific account destination:',role,status);
    }
    console.log('Screenshots:',output);
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
