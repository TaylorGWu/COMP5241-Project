const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.SMOKE_BASE || 'http://127.0.0.1:3001';
const output = path.resolve('frontend/.impeccable/review/auth-v2');
const cases = [
  ['login','en',1440,'light'], ['login','en',1440,'dark'],
  ['login','en',390,'light'], ['login','en',390,'dark'],
  ['login','zh-HK',390,'light'], ['login','zh-HK',390,'dark'],
  ['login','zh-CN',1440,'light'], ['login','zh-CN',1440,'dark'],
  ['register/instructor','en',1440,'light'], ['register/instructor','en',390,'light'],
  ['register','en',1440,'light'], ['register','en',390,'light'],
  ['','en',390,'light'], ['','zh-HK',390,'dark'],
];
(async()=>{
  fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({channel:'chrome',headless:true});
  const errors=[];
  try {
    for(const [route,locale,width,theme] of cases) {
      const context=await browser.newContext({viewport:{width,height:950},colorScheme:theme,reducedMotion:'reduce'});
      await context.addCookies([{name:'pathpilot_locale',value:locale,domain:new URL(base).hostname,path:'/'}]);
      const page=await context.newPage();
      page.on('pageerror',error=>errors.push(error.message));
      await page.goto(`${base}/${route}`);
      await page.locator('h1').waitFor();
      await page.evaluate(()=>document.fonts.ready);
      await page.waitForFunction(()=>[...document.images].every(image=>image.getClientRects().length===0||(image.complete&&image.naturalWidth>0)));
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      if(route==='login') {
        const button=page.getByRole('button',{name:locale==='en'?'Log in':locale==='zh-HK'?'登入':'登录',exact:true});
        const box=await button.boundingBox();
        assert.ok(box.y+box.height<950,'login action is visible without scrolling');
      }
      const file=`${route.replaceAll('/','-')||'home'}-${locale}-${width}-${theme}.png`;
      await page.screenshot({path:path.join(output,file),fullPage:true});
      console.log(file);
      await context.close();
    }
    assert.deepEqual(errors,[]);
    console.log('PASS all captures: no page errors, no horizontal overflow, login actions in viewport');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
