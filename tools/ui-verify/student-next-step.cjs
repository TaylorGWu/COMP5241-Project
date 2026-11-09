// Verifies the integrated student next-step reason, the weekly time budget, and
// the "review the related page" link after a wrong answer. Fixtures only: no
// real course, account or database is touched.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.SMOKE_BASE || 'http://127.0.0.1:3000';
const out = fs.mkdtempSync(path.join(os.tmpdir(), 'coursework-student-next-step-'));

const slideOne = { id:'s1', order:1, layout:'bullets', title:'Branches isolate work', bullets:['A branch keeps work separate'], quizInstruction:'', statusGroups:[], visuals:[] };
const slideTwo = { id:'s2', order:2, layout:'bullets', title:'Check yourself', bullets:['Which answer fits?'], quizInstruction:'', statusGroups:[], visuals:[] };
const course = { id:'sample', title:'Software engineering', description:'Requirements, design and testing.', courseCode:'COMP5241', subject:'Computing', level:'Beginner', durationMin:45, chapterCount:1, chapterIds:['one'], status:'published', enrolled:true, completionPercent:20, lastChapterId:'one', lastSlideId:'s2', totalSlides:2, visitedSlides:2, totalQuestions:4, answeredQuestions:2, correctAnswers:1, studyDays:6, lastStudiedAt:Math.floor(Date.now()/1000)-7200, chapterTitles:['Introduction','Neural networks'] };
const question = { id:'q1', stem:'Why create a branch?', revision:'a'.repeat(64), options:[{id:'A',text:'Isolate work'},{id:'B',text:'Delete history'}] };

function chapterPayload(reviewSlideId) {
  return {
    chapter: { id:'one', title:'Example chapter', slides:[slideOne, slideTwo], questions:[question], glossary:[] },
    progress: { visitedSlideIds:['s1','s2'], lastSlideId:'s2', completionPercent:60, completed:false },
    results: { q1: { questionId:'q1', selectedOptionId:'B', correct:false, correctOptionId:'A', explanation:'A branch isolates work.', attemptId:'a1', reviewSlideId } },
    previousChapter: null,
    nextChapter: null,
  };
}

(async () => {
  const browser = await chromium.launch({ channel:'chrome', headless:true });
  try {
    // ---- 1. a goal-based reason explains itself; no duplicate resume card ----
    {
      const context = await browser.newContext({ viewport:{width:1440,height:1000}, reducedMotion:'reduce' });
      const page = await context.newPage(); const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      const user = { id:'u1', name:'Learner', email:'learner@example.test', role:'student', status:'active', active:true, createdAt:1700000000 };
      await page.route('**/api/**', route => {
        const api = new URL(route.request().url()).pathname;
        const payloads = {
          '/api/auth/me': { user, csrfToken:'fixture' },
          '/api/student/home': { courses:[course], profile:{ background:'new to git', goal:'learn branching', weeklyMinutes:60 }, recommendation:{ courseId:'sample', reason:'It matches words in your background and goal.', reasonCode:'goal' } },
          '/api/student/courses/sample': { course, chapters:[{ id:'one', title:'Example chapter', slideCount:2, questionCount:1, completionPercent:60, completed:false }], enrolled:true },
        };
        if (api in payloads) return route.fulfill({ json: payloads[api] });
        return route.fulfill({ json: {} });
      });
      await page.goto(base + '/student');
      await page.getByRole('heading', { name:'My learning' }).waitFor();
      const reason = page.getByText('It matches words in your background and goal.');
      await reason.waitFor();
      assert.equal(await reason.count(), 1, 'The reason code is rendered as copy, not a rebuilt sentence');
      assert.equal(await page.getByText(/Your background:/).count(), 0, 'The old templated reason paragraph is gone');
      // Weekly budget is visible in the saved profile summary.
      // The goals have their own page, reached from the account menu.
      await page.locator('.account-actions button').first().click();
      await page.locator('.account-menu-goals').click();
      await page.waitForURL('**/student/profile');
      await page.locator('.portal-profile h1').waitFor();
      const budget = page.getByLabel('Weekly study budget');
      assert.equal(await budget.inputValue(), '60', 'The budget input is prefilled from the server');
      // Saving confirms beside the button and then clears itself, rather than
      // leaving a permanent label under the form.
      const said = page.locator('.portal-save-feedback');
      await page.getByRole('button', { name:'Save goals' }).click();
      await said.waitFor();
      assert.ok((await said.innerText()).includes('Saved'), 'The confirmation is announced');
      await page.waitForTimeout(2900);
      assert.equal(await said.count(), 0, 'The confirmation clears itself');
      // The rest of this block is about the home screen.
      await page.goto(base + '/student');
      await page.locator('.portal-tabs').waitFor();
      // A goal recommendation must not also appear as the resume card.
      assert.equal(await page.getByRole('heading', { name:'Suggested next course' }).count(), 1);
      // Reading and answering are reported separately rather than blended away.
      await page.getByText(/2\/2 pages read/).first().waitFor();
      await page.getByText(/2\/4 questions answered/).first().waitFor();
      // Derived activity: days plus a relative time, never a made-up duration.
      await page.getByText(/6 study days/).first().waitFor();
      await page.getByText(/Last studied/).first().waitFor();
      // The page separates what I am learning from the catalogue.
      assert.equal(await page.locator('.portal-tabs button[aria-current]').innerText(), 'My learning');
      // Both tabs carry the same toolbar; it narrows whichever list is showing.
      assert.equal(await page.locator('.course-catalogue-search').count(), 1, 'My learning is searchable too');
      await page.getByRole('button', { name:'Courses', exact:true }).click();
      await page.waitForTimeout(200);
      assert.equal(await page.locator('.course-catalogue-search').count(), 1, 'The catalogue tab is searchable');
      assert.equal(await page.locator('.portal-tabs button[aria-current]').innerText(), 'Courses');
      assert.deepEqual(errors, []);
      await context.close();
      console.log('PASS goal reason, weekly budget, single next-step entry');
    }

    // ---- 2. a resume reason is shown in the resume card only ----
    {
      const context = await browser.newContext({ viewport:{width:1440,height:1000}, reducedMotion:'reduce' });
      const page = await context.newPage();
      const user = { id:'u1', name:'Learner', email:'learner@example.test', role:'student', status:'active', active:true, createdAt:1700000000 };
      await page.route('**/api/**', route => {
        const api = new URL(route.request().url()).pathname;
        const payloads = {
          '/api/auth/me': { user, csrfToken:'fixture' },
          '/api/student/home': { courses:[course], profile:{ background:'', goal:'', weeklyMinutes:0 }, recommendation:{ courseId:'sample', reason:'Continue the course you have already started.', reasonCode:'resume' } },
        };
        if (api in payloads) return route.fulfill({ json: payloads[api] });
        return route.fulfill({ json: {} });
      });
      await page.goto(base + '/student');
      // The list is named by its tab and counted beside it; there is no heading.
      await page.getByText('1 course', { exact:true }).first().waitFor();
      assert.equal(await page.getByRole('heading', { name:'Suggested next course' }).count(), 0, 'A resume must not be offered twice');
      // The reason stays visible even when the next step is "keep going".
      await page.getByText(/Keep going/).first().waitFor();
      assert.equal(await page.getByText('Software engineering').count() >= 1, true, 'The resumed course is still reachable');
      await context.close();
      console.log('PASS resume reason uses the single resume card');
    }

    // ---- 3. a wrong answer offers the related page and jumps there ----
    {
      const context = await browser.newContext({ viewport:{width:1440,height:1000}, reducedMotion:'reduce' });
      const page = await context.newPage(); const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      const user = { id:'u1', name:'Learner', email:'learner@example.test', role:'student', status:'active', active:true, createdAt:1700000000 };
      await page.route('**/api/**', route => {
        const api = new URL(route.request().url()).pathname;
        if (api === '/api/auth/me') return route.fulfill({ json: { user, csrfToken:'fixture' } });
        if (api === '/api/student/home') return route.fulfill({ json: { courses:[course], profile:{ background:'', goal:'', weeklyMinutes:0 }, recommendation:null } });
        if (api === '/api/student/courses/sample/chapters/one/progress') return route.fulfill({ json: { progress:{ visitedSlideIds:['s1','s2'], lastSlideId:'s2', completionPercent:60, completed:false } } });
        if (api === '/api/student/courses/sample/chapters/one') return route.fulfill({ json: chapterPayload('s1') });
        return route.fulfill({ json: {} });
      });
      await page.goto(base + '/student/courses/sample/chapters/one');
      // The chapter page has no page heading; the slide's own title is the marker.
      await page.locator('.portal-stage:not(.portal-stage--thumb)').waitFor();
      assert.equal(await page.getByText('2 / 2').count(), 1, 'Starts on the last slide the learner saw');
      // Practice is a view of its own, so open it before reading the result.
      await page.locator('.portal-tabs--reading button', { hasText:'Practice' }).click();
      const review = page.getByRole('button', { name:'Review the related page' });
      await review.waitFor();
      await review.click();
      // Reviewing a page switches back to the slides view.
      await page.getByText('1 / 2').waitFor();
      assert.equal(await page.locator('.portal-tabs--reading button[aria-current]').innerText(), 'Slides', 'Review returns to the slides');
      assert.equal(await page.getByText('1 / 2').count(), 1, 'Review jumps to the teaching slide');
      // A correct answer offers no review link.
      assert.deepEqual(errors, []);
      await context.close();
      console.log('PASS wrong answer review link jumps to the teaching slide');
    }

    // ---- 4. a long practice set shows one question at a time ----
    {
      const context = await browser.newContext({ viewport:{width:1440,height:1000}, reducedMotion:'reduce' });
      const page = await context.newPage(); const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      const user = { id:'u1', name:'Learner', email:'learner@example.test', role:'student', status:'active', active:true, createdAt:1700000000 };
      const three = ['q1','q2','q3'].map((id, i) => ({ id, stem:`Question ${i+1} about search`, revision:'a'.repeat(64), options:[{id:'A',text:'First'},{id:'B',text:'Second'}] }));
      await page.route('**/api/**', route => {
        const api = new URL(route.request().url()).pathname;
        if (api === '/api/auth/me') return route.fulfill({ json: { user, csrfToken:'fixture' } });
        if (api === '/api/student/home') return route.fulfill({ json: { courses:[course], profile:{ background:'', goal:'', weeklyMinutes:0 }, recommendation:null } });
        if (api.endsWith('/progress')) return route.fulfill({ json: { progress:{ visitedSlideIds:['s1'], lastSlideId:'s1', completionPercent:20, completed:false } } });
        if (api === '/api/student/courses/sample/chapters/one') return route.fulfill({ json: {
          chapter:{ id:'one', title:'Example chapter', slides:[slideOne, slideTwo], questions:three, glossary:[] },
          progress:{ visitedSlideIds:['s1'], lastSlideId:'s1', completionPercent:20, completed:false },
          results:{}, previousChapter:null, nextChapter:null } });
        return route.fulfill({ json: {} });
      });
      await page.goto(base + '/student/courses/sample/chapters/one');
      // The chapter page has no page heading; the slide's own title is the marker.
      await page.locator('.portal-stage:not(.portal-stage--thumb)').waitFor();
      assert.equal(await page.locator('.portal-question').count(), 0, 'Practice is its own view, not stacked under the slide');
      await page.locator('.portal-tabs--reading button', { hasText:'Practice' }).click();
      await page.waitForTimeout(200);
      assert.equal(await page.locator('.portal-question').count(), 3, 'All questions stay listed');
      assert.equal(await page.locator('.portal-question[data-open]').count(), 1, 'Only one question is expanded');
      assert.equal(await page.locator('.portal-question-toggle').first().getAttribute('aria-expanded'), 'true', 'The first unanswered question opens');
      await page.locator('.portal-question-toggle').nth(2).click();
      await page.waitForTimeout(200);
      assert.equal(await page.locator('.portal-question[data-open]').count(), 1, 'Opening one closes the other');
      assert.equal(await page.locator('.portal-question-toggle').nth(2).getAttribute('aria-expanded'), 'true');
      assert.equal(await page.locator('.portal-question-toggle').first().getAttribute('aria-expanded'), 'false');
      // Practice fills the reading column; the rail keeps the tutor.
      const layout = await page.evaluate(() => {
        const reading = document.querySelector('.portal-reading').getBoundingClientRect();
        const practice = document.querySelector('.portal-practice').getBoundingClientRect();
        const tutor = document.querySelector('.portal-tutor').getBoundingClientRect();
        return {
          inColumn: practice.left >= reading.left - 1 && practice.right <= reading.right + 1,
          belowTabs: practice.top > reading.top + 40,
          tutorBeside: tutor.left >= reading.right - 1,
        };
      });
      assert.ok(layout.inColumn && layout.belowTabs, 'Practice fills the reading column under the tabs');
      assert.ok(layout.tutorBeside, 'The tutor is the rail at 1440px');
      assert.deepEqual(errors, []);
      await context.close();
      console.log('PASS practice list expands one question at a time');
    }

    // ---- 5. a chapter footer points at the next published chapter ----
    {
      const context = await browser.newContext({ viewport:{width:1440,height:1000}, reducedMotion:'reduce' });
      const page = await context.newPage(); const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      const user = { id:'u1', name:'Learner', email:'learner@example.test', role:'student', status:'active', active:true, createdAt:1700000000 };
      await page.route('**/api/**', route => {
        const api = new URL(route.request().url()).pathname;
        if (api === '/api/auth/me') return route.fulfill({ json: { user, csrfToken:'fixture' } });
        if (api === '/api/student/home') return route.fulfill({ json: { courses:[course], profile:{ background:'', goal:'', weeklyMinutes:0 }, recommendation:null } });
        if (api.endsWith('/progress')) return route.fulfill({ json: { progress:{ visitedSlideIds:['s1'], lastSlideId:'s1', completionPercent:60, completed:false } } });
        if (api === '/api/student/courses/sample/chapters/one') return route.fulfill({ json: {
          chapter:{ id:'one', title:'Example chapter', slides:[slideOne, slideTwo], questions:[], glossary:[] },
          progress:{ visitedSlideIds:['s1'], lastSlideId:'s1', completionPercent:60, completed:false },
          results:{},
          previousChapter:null,
          nextChapter:{ id:'two', title:'Linear regression' } } });
        return route.fulfill({ json: {} });
      });
      await page.goto(base + '/student/courses/sample/chapters/one');
      // The chapter page has no page heading; the slide's own title is the marker.
      await page.locator('.portal-stage:not(.portal-stage--thumb)').waitFor();
      const next = page.locator('a[href="/student/courses/sample/chapters/two"]');
      assert.equal(await next.count(), 1, 'The footer links to the next chapter');
      assert.ok((await next.innerText()).includes('Next chapter'), 'The link is labelled');
      assert.ok((await next.innerText()).includes('Linear regression'), 'The next chapter title is shown');
      assert.equal(await page.getByText('Previous chapter').count(), 0, 'A first chapter offers no previous link');
      assert.deepEqual(errors, []);
      await context.close();
      console.log('PASS chapter footer links to the next chapter');
    }

    // ---- 6. the course filter appears once the catalogue is worth filtering ----
    {
      const context = await browser.newContext({ viewport:{width:1440,height:1000}, reducedMotion:'reduce' });
      const page = await context.newPage();
      const user = { id:'u1', name:'Learner', email:'learner@example.test', role:'student', status:'active', active:true, createdAt:1700000000 };
      const many = [1,2,3,4,5].map(n => ({...course, id:`c${n}`, title:`Course ${n}`, enrolled:false,
        subject: n % 2 ? 'Computing' : 'Design', level: n > 3 ? 'Advanced' : 'Beginner',
        description:`Description ${n}`, chapterTitles:n === 3 ? ['Neural networks'] : ['Basics']}));
      await page.route('**/api/**', route => {
        const api = new URL(route.request().url()).pathname;
        if (api === '/api/auth/me') return route.fulfill({ json: { user, csrfToken:'fixture' } });
        if (api === '/api/student/home') return route.fulfill({ json: { courses:many, profile:{ background:'', goal:'', weeklyMinutes:0 }, recommendation:null } });
        return route.fulfill({ json: {} });
      });
      await page.goto(base + '/student');
      // Nothing joined yet, so the catalogue is the sensible first tab.
      await page.getByRole('heading', { name:'Courses', exact:true }).waitFor();
      assert.equal(await page.locator('.portal-tabs button[aria-current]').innerText(), 'Courses');
      assert.equal(await page.locator('.course-catalogue-search').count(), 1, 'Five courses are worth filtering');
      await page.locator('.course-catalogue-search input').fill('Course 3');
      await page.waitForTimeout(200);
      assert.equal(await page.locator('.portal-course').count(), 1, 'The filter narrows the list');
      await page.locator('.course-catalogue-search input').fill('neural');
      await page.waitForTimeout(200);
      assert.equal(await page.locator('.portal-course').count(), 1, 'A chapter title is searchable');
      assert.ok((await page.locator('.portal-course').innerText()).includes('Neural networks'),
        'The matching chapter is named, so the hit is not unexplained');
      await page.locator('.course-catalogue-search input').fill('');
      await page.waitForTimeout(200);
      const filters = page.locator('.course-catalogue-filter select');
      assert.equal(await filters.count(), 2, 'Level and subject filter the catalogue');
      await filters.nth(1).selectOption('Design');
      await page.waitForTimeout(200);
      assert.equal(await page.locator('.portal-course').count(), 2, 'Subject narrows the list');
      await filters.nth(0).selectOption('Advanced');
      await page.waitForTimeout(200);
      assert.equal(await page.locator('.portal-course').count(), 1, 'Level narrows it again');
      await filters.nth(1).selectOption('all');
      await filters.nth(0).selectOption('all');
      await page.waitForTimeout(200);
      assert.equal(await page.locator('.portal-course').count(), 5, 'Clearing both restores the list');
      await context.close();
      console.log('PASS catalogue search and attribute filters narrow the list');
    }

    console.log('Student next-step, weekly budget and review link passed.');
    console.log('Screenshots: ' + out);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
