const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.SMOKE_BASE || 'http://127.0.0.1:3000';
(async () => {
  const browser = await chromium.launch({channel:'chrome',headless:true});
  try {
    const context = await browser.newContext({viewport:{width:1440,height:950}});
    await context.addCookies([{name:'pathpilot_locale',value:'en',domain:new URL(base).hostname,path:'/'}]);
    const page = await context.newPage();
    page.setDefaultTimeout(15000);
    const slide = (id,order) => ({id,order,title:id,layout:'bullets',bullets:['Identify the learning goal before planning an activity.','Compare possible approaches using a familiar example.','Check understanding and revise the explanation.'],speakerNotes:'',visuals:[],objectiveIds:[],sourceRefs:[],origin:'teacher'});
    const pkg={project:{meta:{title:'Test chapter',audience:'Beginners',durationMin:30,language:'en'},learningObjectives:[],glossary:[]},assets:[],lessonPlan:{timeline:[]},slideDeck:{slides:[slide('s1',1),slide('s2',2),slide('s-inserted-uuid',3),slide('s3',4)]}};
    const root='/api/demo/courses/fixture/chapters/chapter'; const requests=[];
    const chapter={id:'chapter',courseId:'fixture',title:'Test chapter',summary:'',order:1,status:'draft',package:pkg};
    await page.route('**/api/**', async route=>{
      const path=new URL(route.request().url()).pathname;
      if(path==='/api/auth/me')return route.fulfill({json:{user:{id:'test',name:'Teacher',email:'teacher@example.test',role:'instructor',status:'approved'},csrfToken:'test'}});
      if(path==='/api/auth/profile')return route.fulfill({json:{profile:{name:'Teacher',hasAvatar:false}}});
      if(path==='/api/demo/courses/fixture')return route.fulfill({json:{id:'fixture',title:'Test',audience:'Beginners',durationMin:30,language:'en',learningObjectives:[],chapterIds:['chapter'],status:'draft'}});
      if(path===root)return route.fulfill({json:chapter});
      if(path===root+'/activate')return route.fulfill({json:{...chapter,patches:[{id:'proposal',kind:'slide',target_id:'s2',status:'proposed',author:'agent',reason:'Clarify this explanation.',diff:'- title: Old title\n+ title: Clearer title',payload:{title:'Clearer title'}}]}});
      if(path===root+'/export/deck.pptx')return route.fulfill({headers:{'Content-Disposition':'attachment; filename="test.pptx"'},contentType:'application/vnd.openxmlformats-officedocument.presentationml.presentation',body:Buffer.from('PK fixture')});
      if(path===root+'/edit/plan'){
        requests.push(route.request().postDataJSON());
        return route.fulfill({json:{request:'Improve this page',summary:'Selected page',slide_id:'s-inserted-uuid',target:'slides',findings:[],actions:[{id:'one',title:'Improve selected page',detail:'',prompt:'Read s-inserted-uuid only',target_id:'s-inserted-uuid',selected:true}]}});
      }
      if(path===root+'/edit/stream'){
        requests.push(route.request().postDataJSON());
        return route.fulfill({contentType:'text/event-stream',body:`event: result\ndata: ${JSON.stringify({reply:'Done',call_names:[],patches:[],package:pkg})}\n\n`});
      }
      return route.fulfill({status:404,json:{detail:'Unexpected '+path}});
    });
    await page.goto(base+'/courses/fixture/chapters/chapter');
    console.log('Editor fixture loaded.');
    await page.locator('[data-slide-toolbar]').waitFor();
    assert.match(await page.locator('.chapter-workspace-page').evaluate(el=>getComputedStyle(el).fontFamily),/Manrope/i);
    assert.equal(await page.locator('[data-workspace-tabs] [data-slide-actions]').count(),0,'Slide actions have a separate toolbar');
    assert.equal(await page.locator('[data-review-dock]').evaluate(el=>el.firstElementChild.hasAttribute('data-revision-composer')),true,'Composer precedes pending proposals');
    await page.getByText('Export',{exact:true}).click();
    const exportLink=page.locator('[data-export="deck"]');
    assert.equal(await exportLink.evaluate(el=>{const r=el.getBoundingClientRect();return el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));}),true,'Export link must not be clipped by the tab scroller');
    const download=page.waitForEvent('download');await exportLink.click();assert.equal((await download).suggestedFilename(),'test.pptx');
    console.log('Export download verified.');
    await page.getByText('Export',{exact:true}).click();
    await page.getByRole('button',{name:'03 s-inserted-uuid',exact:false}).click();
    assert.equal(await page.locator('[data-revision-scope]').count(),0,'Selected slide does not need a redundant target card');
    await page.getByRole('textbox',{name:'AI revision'}).fill('Improve this page');
    await page.getByRole('button',{name:'Plan',exact:true}).click();
    await page.getByText('Selected page',{exact:true}).waitFor();
    assert.equal(requests.at(-1).slide_id,'s-inserted-uuid','Planning must carry stable selected ID');
    await page.getByRole('button',{name:'01 s1',exact:false}).click();
    await page.getByRole('button',{name:'Questions',exact:true}).click();
    await page.getByRole('button',{name:/Run 1 selected action/}).click();
    await page.getByText('Done',{exact:true}).first().waitFor({state:'attached'});
    assert.equal(requests.at(-1).slide_id,'s-inserted-uuid','Executing a plan must keep its original target after navigation');
    assert.equal(requests.at(-1).target,'slides','Material navigation must not retarget an approved plan');
    console.log('Frozen plan target verified.');
    await page.setViewportSize({width:390,height:844});
    await page.getByText('Export',{exact:true}).click();
    assert.equal(await exportLink.evaluate(el=>{const r=el.getBoundingClientRect();return el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));}),true);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.getByText('Export',{exact:true}).click();
    await page.locator('[data-workspace-tab="slides"]').click();
    for(const width of [390,320]) {
      await page.setViewportSize({width,height:844});
      assert.equal(await page.locator('[data-slide-stage] .slide-body').evaluate(el=>{
        const frame=el.getBoundingClientRect();return [...el.querySelectorAll('h3,li')].every(child=>child.getBoundingClientRect().bottom<=frame.bottom+1);
      }),true,`Multi-bullet slide content must fit at ${width}px`);
    }
    console.log('Export hit testing/download and stable plan/execution target passed (desktop/mobile).');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
