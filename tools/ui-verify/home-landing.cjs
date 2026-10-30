const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.SMOKE_BASE || 'http://127.0.0.1:3000';
const out = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'coursework-landing-'));
(async()=>{
  const browser=await chromium.launch({channel:'chrome',headless:true});
  try {
    for(const locale of ['en','zh-HK','zh-CN'])for(const width of [1440,768,390,320]){
      const context=await browser.newContext({viewport:{width,height:1100},reducedMotion:'reduce',colorScheme:width===390?'dark':'light'});
      await context.addCookies([{name:'pathpilot_locale',value:locale,domain:new URL(base).hostname,path:'/'}]);
      const page=await context.newPage(); const errors=[]; const writes=[];
      page.on('pageerror',e=>errors.push(e.message));
      page.on('request',r=>{if(new URL(r.url()).pathname.startsWith('/api/')&&r.method()!=='GET')writes.push(r.url());});
      await page.route('**/api/auth/me',r=>r.fulfill({status:401,json:{detail:'Not authenticated'}}));
      await page.goto(base+'/');
      if(locale==='en')await page.getByRole('heading',{level:1,name:'Your teaching. AI assisted. You decide.',exact:true}).waitFor();
      await page.locator('.public-hero .workflow-demo').waitFor();
      await page.evaluate(()=>document.fonts.ready);
      const header=page.locator('.public-header');
      assert.equal(await header.locator('a[href="/register/instructor"]').count(),1,'One primary course action');
      assert.equal(await page.locator('.public-hero .public-hero-visual').count(),0,'The product walkthrough replaces the decorative photo');
      const font=await page.locator('h1').evaluate(e=>getComputedStyle(e).fontFamily);
      assert.equal(await page.locator('.public-hero-copy > p').evaluate(e=>getComputedStyle(e).fontFamily),font,'One homepage typeface');
      if(width===1440){
        const copy=await page.locator('.public-hero-copy').boundingBox();const demo=await page.locator('.public-hero .workflow-section').boundingBox();
        assert.ok(demo.x>copy.x+copy.width,'Desktop walkthrough sits beside headline');
      }
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'No horizontal overflow');
      await page.locator('[data-demo-step="2"]').click();
      await page.locator('[data-demo-accept]').waitFor();
      await page.locator('[data-demo-accept]').click();
      assert.equal(await page.locator('.workflow-demo').getAttribute('data-phase'),'5');
      await page.locator('[data-demo-replay]').click();
      assert.equal(await page.locator('.workflow-demo').getAttribute('data-playing'),'false','Reduced motion stays manual');
      const faq=page.locator('.home-faq details');assert.equal(await faq.count(),6);
      await faq.first().locator('summary').click();assert.equal(await faq.first().getAttribute('open'),'');
      assert.equal(await page.locator('a[href="/register/student"]').count(),1,'Student entry remains available');
      await page.screenshot({path:path.join(out,`${locale}-${width}.png`),fullPage:true});
      assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
      await context.close();console.log('PASS landing composition, scope, locale, reduced motion:',locale,width);
    }
    console.log('Screenshots:',out);
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
