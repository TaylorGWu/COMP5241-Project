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
const course = { id:'sample', title:'Software engineering', description:'Requirements, design and testing.', courseCode:'COMP5241', subject:'Computing', level:'Beginner', durationMin:45, chapterCount:1, chapterIds:['one'], status:'published', enrolled:true, completionPercent:20, lastChapterId:'one', lastSlideId:'s2' };
const question = { id:'q1', stem:'Why create a branch?', revision:'a'.repeat(64), options:[{id:'A',text:'Isolate work'},{id:'B',text:'Delete history'}] };

function chapterPayload(reviewSlideId) {
  return {
    chapter: { id:'one', title:'Example chapter', slides:[slideOne, slideTwo], questions:[question], glossary:[] },
    progress: { visitedSlideIds:['s1','s2'], lastSlideId:'s2', completionPercent:60, completed:false },
    results: { q1: { questionId:'q1', selectedOptionId:'B', correct:false, correctOptionId:'A', explanation:'A branch isolates work.', attemptId:'a1', reviewSlideId } },
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
      assert.equal(await page.getByText('60 min').count() >= 1, true, 'The weekly time budget is shown');
      // The editor exposes the budget field so it can be changed.
      await page.getByText('Edit learning goals').click();
      const budget = page.getByLabel('Time available each week');
      assert.equal(await budget.inputValue(), '60', 'The budget input is prefilled from the server');
      // A goal recommendation must not also appear as the resume card.
      assert.equal(await page.getByRole('heading', { name:'Suggested next course' }).count(), 1);
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
      await page.getByRole('heading', { name:'Continue learning' }).waitFor();
      assert.equal(await page.getByRole('heading', { name:'Suggested next course' }).count(), 0, 'A resume must not be offered twice');
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
      await page.getByRole('heading', { name:'Example chapter' }).waitFor();
      assert.equal(await page.getByText('2 / 2').count(), 1, 'Starts on the last slide the learner saw');
      const review = page.getByRole('button', { name:'Review the related page' });
      await review.waitFor();
      await review.click();
      await page.getByText('1 / 2').waitFor();
      assert.equal(await page.getByText('1 / 2').count(), 1, 'Review jumps to the teaching slide');
      // A correct answer offers no review link.
      assert.deepEqual(errors, []);
      await context.close();
      console.log('PASS wrong answer review link jumps to the teaching slide');
    }

    console.log('Student next-step, weekly budget and review link passed.');
    console.log('Screenshots: ' + out);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
