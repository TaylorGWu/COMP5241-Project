const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.SMOKE_BASE || 'http://127.0.0.1:3000';
const out = fs.mkdtempSync(path.join(os.tmpdir(), 'coursework-workspace-theme-'));
const course = { id:'sample', title:'Software engineering', description:'Requirements, design and testing.', courseCode:'COMP5241', subject:'Computing', level:'Beginner', audience:'Beginners', durationMin:45, chapterCount:2, chapterIds:['one','two'], status:'published', enrolled:true, completionPercent:25, lastChapterId:'one', lastSlideId:'s1' };
const adminCourse = { id:'sample', title:course.title, courseCode:course.courseCode, ownerName:'Teacher', status:'published', archived:false, moderationReason:null, chapterCount:2, enrollmentCount:1 };
(async()=>{
  const browser = await chromium.launch({channel:'chrome',headless:true});
  try {
    for (const role of ['instructor','student','admin']) for (const width of [1440,390,320]) {
      const context=await browser.newContext({viewport:{width,height:1000},reducedMotion:'reduce',colorScheme:width===390?'dark':'light'});
      await context.addCookies([{name:'pathpilot_locale',value:'en',domain:new URL(base).hostname,path:'/'}]);
      const page=await context.newPage(); const errors=[]; const writes=[];
      page.on('pageerror',e=>errors.push(e.message));
      const user={id:role,name:'Preview account',email:'preview@example.test',role,status:role==='instructor'?'approved':'active',active:true,createdAt:1700000000};
      await page.route('**/api/**',route=>{
        const api=new URL(route.request().url()).pathname;
        if(route.request().method()!=='GET' && !api.endsWith('/activate')) writes.push(api);
        const sampleSlide={id:'s1',order:1,title:'A teaching example',layout:'bullets',bullets:['A clear explanation'],speakerNotes:'Teacher notes',visuals:[],objectiveIds:[],sourceRefs:[],origin:'teacher'};
        const samplePackage={project:{meta:{title:'Example chapter',audience:'Beginners',durationMin:30,language:'en'},learningObjectives:[],glossary:[]},assets:[],lessonPlan:{overview:'',timeline:[]},slideDeck:{slides:[sampleSlide]}};
        const sampleChapter={id:'one',courseId:'sample',title:'Example chapter',summary:'',order:1,status:'draft',package:samplePackage};
        const payloads={
          '/api/auth/me':{user,csrfToken:'preview'},
          '/api/auth/profile':{profile:{name:user.name,bio:'Practical teaching examples.',institution:'',independent:false,position:'',university:'',degree:'',experience:'',subjects:[],otherSubject:'',hasAvatar:false,avatarVersion:null}},
          '/api/demo/courses':{courses:[course,{...course,id:'second',title:'AI concepts',status:'draft'}]},
          '/api/demo/courses/sample':{...course,chapterIds:[],learningObjectives:[]},
          '/api/demo/courses/sample/coverage':{outcomes:[]},
          '/api/demo/courses/sample/analytics':{averageScore:0,enrolledCount:0,mostMissed:[]},
          '/api/demo/courses/sample/chapters/one':sampleChapter,
          '/api/demo/courses/sample/chapters/one/activate':{...sampleChapter,patches:[]},
          '/api/student/home':{courses:[course],profile:{background:'Computer science student',goal:'Understand software design',weeklyMinutes:60},recommendation:{courseId:'sample',reason:'Matches your learning goal.',reasonCode:'goal'}},
          '/api/admin/overview':{users:3,courses:1,publishedCourses:1,pendingApplications:0,enrollments:1,userRoles:[{role:'student',count:1},{role:'instructor',count:1},{role:'admin',count:1}],courseStates:[{state:'published',count:1},{state:'unpublished',count:0},{state:'suspended',count:0}],courseEnrollments:[{courseId:'sample',title:course.title,courseCode:course.courseCode,count:1}]},
          '/api/admin/users':{users:[user]},
          '/api/admin/courses':{courses:[adminCourse]},
          '/api/admin/applications':{applications:[]},
          '/api/admin/audit':{events:[]},
        };
        return api in payloads ? route.fulfill({json:payloads[api]}) : route.fulfill({status:404,json:{detail:'Unexpected preview route '+api}});
      });
      await page.goto(base+(role==='instructor'?'/courses':'/'+role));
      const root=page.locator(role==='instructor'?'.course-library-page':'.portal');
      await root.waitFor();
      await page.evaluate(()=>document.fonts.ready);
      const selection=width===390?'rgb(52, 63, 43)':'rgb(230, 233, 223)';
      if(role==='instructor') {
        const navigation=page.locator('.teacher-nav__link[aria-current="page"]');
        assert.equal(await navigation.evaluate(el=>getComputedStyle(el).backgroundColor),selection,'Teacher top navigation must use the shared selected colour after the CSS cascade');
        await navigation.hover();
        assert.equal(await navigation.evaluate(el=>getComputedStyle(el).backgroundColor),selection,'Hover must not restore the old blue navigation');
      }
      await page.locator('[data-account-menu-trigger]').click();
      const accountSelection=page.locator('.account-menu-links a[aria-current="page"]');
      await accountSelection.waitFor();
      assert.equal(await accountSelection.evaluate(el=>getComputedStyle(el).backgroundColor),selection,'Account disclosure uses the same selection tokens');
      await page.keyboard.press('Escape');
      if(role==='instructor') {
        await page.locator('.course-library-card').first().waitFor();
        await page.getByRole('textbox',{name:'Search courses',exact:true}).fill('no match');
        await page.getByText('No courses match your filters',{exact:true}).waitFor();
        await page.getByRole('button',{name:'Clear filters'}).click();
        assert.equal(await page.locator('.course-library-card').count(),2);
      } else if(role==='student') {
        await page.locator('.portal-resume-course').waitFor();
        assert.ok(await page.locator('a[href="/student/courses/sample"]').count()>0);
      } else {
        await page.locator('.portal-metric').first().waitFor();
        assert.equal(await page.locator('.portal-chart-panel').count(),3);
      }
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${role} fits ${width}px`);
      await page.screenshot({path:path.join(out,`${role}-${width}.png`),fullPage:true});
      if(role==='instructor') {
        await page.goto(base+'/courses/sample');
        await page.locator('.course-menu__item').first().waitFor();
        await page.getByRole('button',{name:'Insights',exact:true}).click();
        const selected=page.locator('.course-menu__item[aria-current="page"]');
        assert.equal(await selected.innerText(),'Insights');
        assert.equal(await selected.evaluate(el=>getComputedStyle(el).backgroundColor),width===390?'rgb(52, 63, 43)':'rgb(230, 233, 223)','Course sidebar uses the shared sage selection in both themes');
        await page.screenshot({path:path.join(out,`course-detail-${width}.png`),fullPage:true});
        await page.goto(base+'/courses/new');
        const createNavigation=page.locator('.teacher-nav__link[aria-current="page"]');
        await createNavigation.waitFor();
        assert.equal(await createNavigation.evaluate(el=>getComputedStyle(el).backgroundColor),selection,'Create course navigation matches the catalogue');
        await page.goto(base+'/profile');
        await page.locator('#teacher-name').waitFor();
        await page.locator('.teacher-profile-aside nav a').nth(1).click();
        const profileNavigation=page.locator('.teacher-profile-aside nav a[aria-current="location"]');
        assert.equal(await profileNavigation.evaluate(el=>getComputedStyle(el).backgroundColor),selection,'Profile section links use the global selection style');
        await page.locator('.global-system-settings__trigger').click();
        const preferences=page.locator('.global-system-settings__panel [role="group"] > button[aria-pressed="true"]');
        assert.equal(await preferences.count(),2);
        for(const control of await preferences.all()) assert.equal(await control.evaluate(el=>getComputedStyle(el).backgroundColor),selection,'Settings segmented controls use the global selection style');
        await page.locator('.global-system-settings__head button').click();
        await page.goto(base+'/courses/sample/chapters/one');
        await page.locator('[data-workspace-tab="slides"]').waitFor();
        const editor=page.locator('.chapter-workspace-page');
        assert.equal(await editor.evaluate(el=>getComputedStyle(el).backgroundColor),width===390?'rgb(24, 24, 24)':'rgb(247, 246, 242)','Editor canvas matches the application shell');
        assert.equal(await page.locator('.slide-actions__add').evaluate(el=>getComputedStyle(el).backgroundColor),width===390?'rgb(242, 242, 242)':'rgb(36, 36, 36)','Add slide follows the shared primary-action style');
        assert.equal(await page.locator('.studio-topbar__inner > span:first-child > span:first-child').evaluate(el=>getComputedStyle(el).color),width===390?'rgb(36, 36, 36)':'rgb(255, 255, 255)','Editor brand mark stays legible in both themes');
        assert.equal(await page.locator('.slide-body').last().evaluate(el=>getComputedStyle(el).getPropertyValue('--color-ink').trim()),width===390?'#eef3fa':'#172033','Teaching slide ink stays unchanged by the shell theme');
        const editorTab=page.locator('[data-workspace-tab][aria-current="page"]');
        assert.equal(await editorTab.evaluate(el=>getComputedStyle(el).backgroundColor),selection,'Editor navigation uses shared selection without recolouring lesson content');
        await page.screenshot({path:path.join(out,`chapter-editor-${width}.png`),fullPage:true});
      }
      if(role==='admin') {
        await page.locator('.portal-metric').first().click();
        await page.locator('.portal-user-row').waitFor();
        assert.equal(await page.locator('.portal-section-nav button[aria-current]').count(),1);
      }
      assert.deepEqual(errors,[]); assert.deepEqual(writes,[],'Navigation and styling never modify saved content');
      await context.close(); console.log('PASS workspace skin, layout and interactions:',role,width);
    }
    console.log('Screenshots:',out);
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
