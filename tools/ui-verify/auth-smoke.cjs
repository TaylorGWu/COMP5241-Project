const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.SMOKE_BASE || 'http://127.0.0.1:3001';
const apiBase = process.env.SMOKE_API || 'http://127.0.0.1:8001';
if (process.env.AUTH_SMOKE_DISPOSABLE !== '1' || !process.env.AUTH_SMOKE_ADMIN_PASSWORD) throw new Error('Use a disposable backend and set AUTH_SMOKE_DISPOSABLE=1 plus AUTH_SMOKE_ADMIN_PASSWORD');
const fs = require('node:fs');
const path = require('node:path');
const output = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'coursework-auth-smoke-'));
const shot = name => path.join(output, name+'.png');
const password = require('node:crypto').randomBytes(24).toString('base64url');
const run = process.env.SMOKE_RUN || String(Date.now());
const studentEmail = `student-${run}@example.test`;
const teacherEmail = `teacher-${run}@example.test`;
const qualification = { name: 'sample-qualification.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\n% Disposable test qualification, not a real credential.\n%%EOF\n') };

async function fillCredentials(page, email, registration, secret = password) {
  if (registration) await page.getByLabel('Full name', {exact:true}).fill(registration);
  await page.getByLabel('Email address', {exact:true}).fill(email);
  await page.getByLabel('Password', {exact:true}).fill(secret);
  if (registration) await page.getByLabel('Confirm password', {exact:true}).fill(password);
}
async function login(page, email, secret = password) {
  await page.goto(base+'/login');
  await fillCredentials(page,email,undefined,secret);
  await page.getByRole('button',{name:'Log in',exact:true}).click();
}

(async()=>{
  const browser = await chromium.launch({channel:'chrome',headless:true});
  const failures=[];
  const contexts=[];
  const make=async(width=1440)=>{
    const context=await browser.newContext({viewport:{width,height:950},reducedMotion:'reduce'});
    await context.addCookies([{name:'pathpilot_locale',value:'en',domain:new URL(base).hostname,path:'/'}]);
    contexts.push(context);
    const page=await context.newPage();
    page.on('pageerror',e=>failures.push(e.message));
    return page;
  };
  try {
    const student=await make(390);
    await student.goto(base+'/register/student');
    await fillCredentials(student,studentEmail,'Preview student');
    await student.getByLabel('Confirm password',{exact:true}).fill('a-different-long-password');
    await student.getByRole('button',{name:'Create account',exact:true}).click();
    await student.getByRole('alert').filter({hasText:'The passwords do not match.'}).waitFor();
    await student.getByLabel('Confirm password',{exact:true}).fill(password);
    await student.getByRole('button',{name:'Show password',exact:true}).click();
    assert.equal(await student.getByLabel('Password',{exact:true}).getAttribute('type'),'text');
    await student.getByRole('button',{name:'Create account',exact:true}).click();
    await student.waitForURL('**/student');
    await student.getByRole('heading',{name:"You're in. Make yourself at home."}).waitFor();
    await student.screenshot({path:shot('student-account'),fullPage:true});
    await student.goto(base+'/courses');
    await student.waitForURL('**/student');
    console.log('PASS student registration, activation, password visibility and role guard');

    const teacher=await make();
    await teacher.goto(base+'/register/instructor');
    await fillCredentials(teacher,teacherEmail,'Preview teacher');
    await teacher.locator('input[type=file]').setInputFiles(qualification);
    await teacher.getByRole('button',{name:'Submit application',exact:true}).click();
    await teacher.waitForURL('**/application');
    await teacher.getByRole('heading',{name:'Your application is in review.'}).waitFor();
    await teacher.screenshot({path:shot('application-pending'),fullPage:true});
    const denied = await teacher.evaluate(async(api)=> (await fetch(api+'/api/demo/courses',{credentials:'include'})).status,apiBase);
    assert.equal(denied,403,'pending instructor must not reach teacher API');
    console.log('PASS teacher qualification submitted; pending account blocked server-side');

    const admin=await make();
    await login(admin,process.env.AUTH_SMOKE_ADMIN_EMAIL || 'admin@example.test',process.env.AUTH_SMOKE_ADMIN_PASSWORD);
    await admin.waitForURL('**/admin');
    const entry=admin.locator('.application-entry').filter({hasText:teacherEmail});
    await entry.waitFor();
    await admin.screenshot({path:shot('admin-queue'),fullPage:true});
    const [download] = await Promise.all([admin.waitForEvent('download'),entry.getByRole('link').click()]);
    assert.equal(download.suggestedFilename(),'sample-qualification.pdf');
    await entry.getByRole('button',{name:'Request revision',exact:true}).click();
    await entry.getByPlaceholder('Explain what needs to be corrected or supplied.').fill('Please supply a clearer institution credential.');
    await entry.getByRole('button',{name:'Request revision',exact:true}).click();
    await entry.waitFor({state:'detached'});
    await teacher.getByRole('button',{name:'Check status',exact:true}).click();
    await teacher.getByRole('heading',{name:'A little more information is needed.'}).waitFor();
    await teacher.screenshot({path:shot('application-rejected'),fullPage:true});
    await teacher.locator('input[type=file]').setInputFiles(qualification);
    await teacher.getByRole('button',{name:'Resubmit application',exact:true}).click();
    await teacher.getByRole('heading',{name:'Your application is in review.'}).waitFor();
    await admin.getByRole('button',{name:'Check status',exact:true}).click();
    await entry.waitFor();
    await entry.getByRole('button',{name:'Approve teacher',exact:true}).click();
    await entry.waitFor({state:'detached'});
    await teacher.getByRole('button',{name:'Check status',exact:true}).click();
    await teacher.waitForURL('**/courses');
    await teacher.getByRole('heading',{name:'Your courses',exact:true}).waitFor();
    await teacher.screenshot({path:shot('approved-workspace'),fullPage:true});
    console.log('PASS administrator attachment download, rejection, resubmission and approval');
    await teacher.getByRole('button',{name:'Sign out',exact:true}).click();
    await teacher.waitForURL(url => url.pathname === '/login');
    await login(teacher,teacherEmail);
    await teacher.waitForURL('**/courses');
    console.log('PASS sign out and persistent approved-account sign in');
    await teacher.goto(base+'/courses/new');
    await teacher.getByPlaceholder('e.g. Git collaboration').fill('Disposable browser-test course');
    await teacher.getByRole('button',{name:'Create course',exact:true}).click();
    await teacher.waitForURL(/\/courses\/course-\d+$/);
    await teacher.getByRole('heading',{name:'Disposable browser-test course',exact:true}).waitFor();
    console.log('PASS authenticated teacher course creation through existing UI');
    for(const context of contexts) for(const page of context.pages()) assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    assert.deepEqual(failures,[]);
    console.log('PASS no page errors or horizontal overflow');
    console.log('Screenshots:',output);
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exit(1);});
