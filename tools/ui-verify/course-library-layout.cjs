const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.SMOKE_BASE || 'http://127.0.0.1:3000';
(async () => {
  const browser = await chromium.launch({channel:'chrome',headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const courses = ['Software engineering','Cyber security','Artificial intelligence','Big data computing'].map((title,i)=>({id:`fixture-${i}`,title,courseCode:`COMP${5241+i}`,subject:i%2?'Security':'Computing',audience:'Beginners',description:'A course with real learning objectives and teaching materials.',durationMin:45,chapterIds:['one','two'],status:i===1?'published':'draft'}));
    await page.route('**/api/**', route=> {
      const path = new URL(route.request().url()).pathname;
      if(path==='/api/auth/me')return route.fulfill({json:{user:{id:'fixture',name:'Teacher',email:'teacher@example.test',role:'instructor',status:'approved'},csrfToken:'test'}});
      if(path==='/api/auth/profile')return route.fulfill({json:{profile:{name:'Teacher',hasAvatar:false}}});
      if(path==='/api/demo/courses')return route.fulfill({json:{courses}});
      return route.fulfill({status:404,json:{detail:'Unexpected '+path}});
    });
    await page.goto(base+'/courses');
    await page.locator('.course-library-card').first().waitFor();
    assert.match(await page.locator('.course-library-page').evaluate(el=>getComputedStyle(el).fontFamily),/Manrope/i);
    const boxes = await page.locator('.course-library-card').evaluateAll(els=>els.map(el=>{const r=el.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width};}));
    assert.equal(boxes.length,4);
    assert.equal(boxes[0].y,boxes[1].y,'First two cards share a row');
    assert.ok(boxes[2].y>boxes[0].y,'Third card begins a second row');
    assert.equal(boxes[0].x,boxes[2].x,'Two aligned columns');
    assert.equal(await page.locator('h1').evaluate(el=>getComputedStyle(el).clip!=='auto'||el.classList.contains('sr-only')),true,'No title banner');
    await page.getByRole('combobox',{name:'Status',exact:true}).selectOption('published');
    assert.equal(await page.locator('.course-library-card').count(),1);
    await page.getByRole('button',{name:'Clear filters'}).click();
    await page.getByRole('textbox',{name:'Search courses',exact:true}).fill('nothing matches');
    await page.getByText('No courses match your filters',{exact:true}).waitFor();
    await page.getByRole('button',{name:'Clear filters'}).click();
    for(const width of [800,390,320]) {
      await page.setViewportSize({width,height:900});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`No overflow at ${width}`);
    }
    console.log('Course library two-column layout, filters, empty state and responsive widths passed.');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exit(1);});
