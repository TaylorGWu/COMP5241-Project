const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.SMOKE_BASE || 'http://127.0.0.1:3000';
(async () => {
  const browser = await chromium.launch({channel:'chrome',headless:true});
  try {
    const context = await browser.newContext({viewport:{width:1440,height:950}});
    await context.addCookies([{name:'pathpilot_locale',value:'en',domain:new URL(base).hostname,path:'/'}]);
    const page = await context.newPage();
    const slide = (id,title,order) => ({id,title,order,layout:'bullets',bullets:['A clear point'],speakerNotes:'Teaching notes',visuals:[],objectiveIds:[],sourceRefs:[],origin:'teacher'});
    let pkg = {project:{meta:{title:'Test chapter',audience:'Beginners',durationMin:30,language:'en'},learningObjectives:[],glossary:[]},assets:[],lessonPlan:{overview:'',timeline:[]},slideDeck:{slides:[slide('s1','First page',1),slide('s2','Last page',2)]}};
    let serial = 0; const writes = []; let fail = false;
    const root = '/api/demo/courses/fixture/chapters/chapter';
    const chapter = () => ({id:'chapter',courseId:'fixture',title:'Test chapter',summary:'',order:1,status:'draft',package:pkg});
    const patch = () => ({id:'p'+serial,kind:'deck',target_id:'deck',payload:{},reason:'Teacher change',diff:'',status:'applied',author:'teacher'});
    await page.route('**/api/**', async route => {
      const path = new URL(route.request().url()).pathname;
      if(path==='/api/auth/me') return route.fulfill({json:{user:{id:'test',name:'Teacher',email:'teacher@example.test',role:'instructor',status:'approved'},csrfToken:'test'}});
      if(path==='/api/demo/courses/fixture') return route.fulfill({json:{id:'fixture',title:'Test course',audience:'Beginners',durationMin:30,language:'en',learningObjectives:[],chapterIds:['chapter'],status:'draft'}});
      if(path===root) return route.fulfill({json:chapter()});
      if(path===root+'/activate') return route.fulfill({json:{...chapter(),patches:[]}});
      if(path===root+'/slides') {
        const body = route.request().postDataJSON(); writes.push(body);
        if(fail) return route.fulfill({status:503,json:{detail:'Please retry'}});
        const index = pkg.slideDeck.slides.findIndex(s=>s.id===body.anchor_id); let selected;
        if(body.action==='delete') {pkg.slideDeck.slides.splice(index,1);selected=pkg.slideDeck.slides[Math.min(index,pkg.slideDeck.slides.length-1)]?.id;}
        else {selected='new-'+(++serial);pkg.slideDeck.slides.splice(index+(body.action==='after'),0,slide(selected,body.title,1));}
        pkg.slideDeck.slides.forEach((s,i)=>s.order=i+1);
        return route.fulfill({json:{package:pkg,patch:patch(),selected_slide_id:selected}});
      }
      if(path===root+'/manual-edit') {
        const body=route.request().postDataJSON(); writes.push(body);
        Object.assign(pkg.slideDeck.slides.find(s=>s.id===body.target_id),body.payload);
        return route.fulfill({json:{package:pkg,patch:patch()}});
      }
      if(path==='/api/auth/profile') return route.fulfill({json:{profile:{name:'Teacher',hasAvatar:false}}});
      return route.fulfill({status:404,json:{detail:'Unexpected '+path}});
    });
    await page.goto(base+'/courses/fixture/chapters/chapter');
    await page.getByRole('button',{name:'Add slide',exact:true}).waitFor();
    await page.getByRole('button',{name:'Add slide',exact:true}).click();
    await page.getByRole('button',{name:'Before current slide',exact:true}).click();
    assert.equal(writes.at(-1).action,'before'); assert.equal(writes.at(-1).anchor_id,'s1');
    await page.getByLabel('Title',{exact:true}).fill('Inserted first');
    await page.getByRole('button',{name:'Save',exact:true}).click();
    await page.getByRole('button',{name:'Add slide',exact:true}).click();
    await page.getByRole('button',{name:'After current slide',exact:true}).click();
    assert.equal(writes.at(-1).action,'after'); assert.equal(writes.at(-1).anchor_id,'new-1');
    await page.getByRole('button',{name:'Cancel',exact:true}).click();
    await page.getByRole('button',{name:'Delete slide',exact:true}).click();
    const dialog = page.getByRole('dialog'); await dialog.waitFor();
    const count=writes.length; await dialog.getByRole('button',{name:'Cancel',exact:true}).click();
    assert.equal(writes.length,count,'Cancel must not delete');
    await page.getByRole('button',{name:'Delete slide',exact:true}).click();
    await page.getByRole('dialog').getByRole('button',{name:'Delete slide',exact:true}).click();
    assert.equal(writes.at(-1).action,'delete');assert.equal(writes.at(-1).anchor_id,'new-2');
    await page.reload(); await page.getByRole('button',{name:'Edit slide',exact:true}).click();
    assert.equal(await page.getByLabel('Title',{exact:true}).inputValue(),'Inserted first');
    await page.getByRole('button',{name:'Cancel',exact:true}).click();
    await page.getByRole('button',{name:'Edit slide',exact:true}).click();
    await page.getByLabel('Title',{exact:true}).fill('');
    await page.getByRole('button',{name:'Save',exact:true}).click();
    await page.getByLabel('Title',{exact:true}).waitFor({state:'hidden'});
    assert.equal(await page.getByRole('button',{name:'Edit slide',exact:true}).isEnabled(),true,'An empty title must remain editable');
    assert.equal(await page.getByRole('button',{name:'Delete slide',exact:true}).isEnabled(),true,'An empty title must remain deletable');
    fail=true;await page.getByRole('button',{name:'Add slide',exact:true}).click();await page.getByRole('button',{name:'After current slide',exact:true}).click();
    await page.getByText('Please retry',{exact:true}).waitFor();
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    fail=false;
    for(let remaining=3;remaining>0;remaining--) {
      await page.getByRole('button',{name:'Delete slide',exact:true}).click();
      await page.getByRole('dialog').getByRole('button',{name:'Delete slide',exact:true}).click();
      await page.getByRole('dialog').waitFor({state:'hidden'});
    }
    assert.equal(await page.getByRole('button',{name:'Edit slide',exact:true}).isEnabled(),false);
    await page.getByRole('button',{name:'Add slide',exact:true}).click();
    await page.getByLabel('Title',{exact:true}).waitFor();
    assert.equal(writes.at(-1).anchor_id,null,'Empty deck can start again without a stale anchor');
    console.log('Slide actions: before/after payload, selected new editor, save, cancel/confirm delete, reload, failure, narrow layout passed');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
