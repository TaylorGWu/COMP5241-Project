const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.SMOKE_BASE||'http://127.0.0.1:3000';
const out=fs.mkdtempSync(path.join(require('node:os').tmpdir(),'coursework-profile-layout-'));
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
  for(const locale of ['en','zh-HK','zh-CN'])for(const width of [1440,800,801,768,390,320]){
    const ctx=await browser.newContext({viewport:{width,height:1050},reducedMotion:'reduce',colorScheme:width===390?'dark':'light'});
    await ctx.addCookies([{name:'pathpilot_locale',value:locale,domain:new URL(base).hostname,path:'/'}]);
    const page=await ctx.newPage();const errors=[];const writes=[];
    page.on('pageerror',e=>errors.push(e.message));
    let user={id:'profile-fixture',name:'Preview Teacher',email:'preview@example.test',role:'instructor',status:'pending',qualificationSubmitted:false};
    const profile={name:user.name,bio:'Teaching through practical examples.',institution:'',independent:false,position:'',university:'',degree:'',experience:'',subjects:['programming'],otherSubject:'',hasAvatar:false,avatarVersion:null};
    await page.route('**/api/**',r=>{const url=new URL(r.request().url()).pathname;
      if(r.request().method()!=='GET')writes.push(url);
      if(url==='/api/auth/me')return r.fulfill({json:{user,csrfToken:'test'}});
      if(url==='/api/auth/profile')return r.fulfill({json:{profile}});
      return r.fulfill({status:404,json:{detail:'Unexpected '+url}});
    });
    await page.goto(base+'/profile');await page.locator('#teacher-name').waitFor();
    assert.equal(await page.locator('.profile-identity strong').innerText(),user.name,'Identity belongs in the left rail');
    assert.equal(await page.locator('.profile-identity .teacher-photo').count(),0,'Sidebar identity must not repeat the photo editor/avatar');
    assert.equal(await page.locator('.profile-photo-editor .teacher-photo').count(),1,'Photo upload preview is preserved');
    assert.equal(await page.locator('.profile-review-status').getAttribute('data-review-state'),'unsubmitted');
    assert.equal(await page.locator('.profile-photo-controls .profile-identity-email').count(),0,'No repeated identity in photo editor');
    const aside=await page.locator('.teacher-profile-aside').boundingBox();const form=await page.locator('.teacher-profile-form').boundingBox();
    assert.ok(aside,'Sidebar must have a coherent layout box, including at the old 800px breakpoint');
    assert.ok(width<=800 ? form.y>=aside.y+aside.height-1 : form.x>=aside.x+aside.width-1,'Sidebar/form reflow must agree with the breakpoint');
    assert.equal(await page.locator('.profile-review-note a').getAttribute('href'),'/application');
    await page.locator('#teacher-bio').fill('Changed but not yet saved.');
    const save=page.locator('.profile-save-bar button[type=submit]');assert.equal(await save.isEnabled(),true);
    await save.scrollIntoViewIfNeeded();
    await page.locator('.profile-save-bar button[type=button]').click();
    assert.equal(await page.locator('#teacher-bio').inputValue(),profile.bio);
    const nav=page.locator('.teacher-profile-aside nav a');await nav.nth(1).click();
    assert.equal(await nav.nth(1).getAttribute('aria-current'),'location');
    await page.locator('#teacher-position').fill('Lecturer');await page.keyboard.press('Tab');
    assert.equal(await page.locator('#teacher-experience').evaluate(e=>e===document.activeElement),true);
    await page.evaluate(()=>window.scrollTo(0,0));
    const last=await page.locator('#profile-teaching').boundingBox();const bar=await page.locator('.profile-save-bar').boundingBox();
    assert.ok(bar.y >= last.y+last.height-1,'Save bar must not cover teaching fields');
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    await page.screenshot({path:path.join(out,`${locale}-${width}.png`),fullPage:true});
    await page.locator('.profile-save-bar button[type=button]').click();
    for(const [status,submitted,want]of [['pending',true,'pending'],['rejected',true,'rejected'],['approved',true,'approved']]){
      user={...user,status,qualificationSubmitted:submitted};
      await page.reload();await page.locator('#teacher-name').waitFor();
      assert.equal(await page.locator('.profile-review-status').getAttribute('data-review-state'),want);
    }
    assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
    await ctx.close();console.log('PASS identity, review states, discard, anchors, focus, overflow:',locale,width);
  }
  console.log('Screenshots:',out);
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1);});
