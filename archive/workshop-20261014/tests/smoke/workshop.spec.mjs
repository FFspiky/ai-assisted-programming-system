import {expect,test} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const baseURL=process.env.SMOKE_BASE_URL||'http://127.0.0.1:5006';
fs.mkdirSync('tmp/workshop-check',{recursive:true});

async function login(page){
  const result=await page.request.post(baseURL+'/api/login',{data:{username:'workshop_browser',password:'workshop-browser-only'}});
  expect(result.status()).toBe(200);
  await page.goto(baseURL+'/workshop.html');
  await expect(page.locator('#creationCode')).not.toHaveValue('');
}
async function run(page){
  await page.locator('#runCreation').click();
  await expect(page.locator('#workshopStatus')).toContainText('运行完成',{timeout:20000});
  await expect(page.locator('#saveCreation')).toBeEnabled();
}

test('访客示例、主题切换、回放和窄屏布局',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setViewportSize({width:1440,height:1050});
  await page.goto(baseURL+'/workshop.html');
  await expect(page.locator('.scene-card')).toHaveCount(3);
  await expect(page.locator('#canvasHost canvas')).toBeVisible();
  await expect(page.locator('#traceSource')).toContainText('示例回放');
  await page.locator('#timeline').fill('20');
  await expect(page.locator('#framePosition')).toHaveText('21 / 72');
  await expect(page.locator('#playPause')).toHaveText('播放');
  await page.locator('#runCreation').click();
  await expect(page.locator('#loginToCreate')).toBeVisible();
  await page.locator('[data-scene=sorting]').click();
  await expect(page.locator('#studioHeading')).toContainText('排序编舞');
  await expect(page.locator('#traceDescription')).toContainText('个数字');
  await page.locator('[data-scene=route]').click();
  await expect(page.locator('#traceDescription')).toContainText('航线');
  await page.locator('[data-scene=ocean]').click();
  await page.locator('#timeline').fill('48');
  await page.screenshot({path:'tmp/workshop-check/desktop-preview.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:'tmp/workshop-check/mobile.png',fullPage:true});
  expect(errors).toEqual([]);
});

test('真实运行三个主题，保存版本、刷新恢复、离线导出',async({page,context})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setViewportSize({width:1440,height:1050});await login(page);
  await page.locator('#creationTitle').fill('浏览器验证 · 向光而游');await run(page);
  await page.locator('#timeline').fill('48');
  await page.locator('#saveCreation').click();
  await expect(page.locator('#workshopStatus')).toContainText('版本 1 已保存');
  await expect(page.locator('#versionSelect option')).toHaveCount(1);
  const projectURL=page.url();
  await page.locator('#param-speed').fill('4');
  await expect(page.locator('#traceSource')).toContainText('旧回放');
  await expect(page.locator('#saveCreation')).toBeDisabled();
  await run(page);await page.locator('#saveCreation').click();
  await expect(page.locator('#workshopStatus')).toContainText('版本 2 已保存');
  await expect(page.locator('#versionSelect option')).toHaveCount(2);
  await page.reload();await expect(page.locator('#versionSelect option')).toHaveCount(2);
  await expect(page.locator('#param-speed')).toHaveValue('4');
  await page.locator('#versionSelect').selectOption({label:'版本 1'});
  await expect(page.locator('#param-speed')).toHaveValue('2.5');
  await expect(page.locator('#traceSource')).toContainText('你的运行');
  await page.locator('#palette').selectOption('sunrise');
  const downloadPromise=page.waitForEvent('download');
  await page.locator('#exportWork').click();
  const download=await downloadPromise,exportPath=path.resolve('tmp/workshop-check/export.html');await download.saveAs(exportPath);
  expect(fs.statSync(exportPath).size).toBeGreaterThan(1000000);
  const offline=await context.newPage();const requests=[];offline.on('request',r=>requests.push(r.url()));
  await offline.goto(pathToFileURL(exportPath).href);
  await expect(offline.locator('canvas')).toBeVisible();
  await offline.locator('#seek').fill('10');await expect(offline.locator('#pos')).toHaveText('11 / 72');
  expect(requests.filter(url=>url.startsWith('http'))).toEqual([]);await offline.close();
  for(const scene of ['sorting','route']){await page.goto(baseURL+'/workshop.html?scene='+scene);await expect(page.locator('#creationCode')).not.toHaveValue('');await run(page);await expect(page.locator('#traceSource')).toContainText('Docker');}
  await page.goto(projectURL);await expect(page.locator('#versionSelect option')).toHaveCount(2);await page.locator('#timeline').fill('48');
  await page.screenshot({path:'tmp/workshop-check/desktop-real.png',fullPage:true});
  expect(errors).toEqual([]);
});

test('AI 候选失败重试、过期保护、应用撤销与运行失败',async({page})=>{
  await login(page);const original=await page.locator('#creationCode').inputValue();
  let responseMode='stale',release;
  const gate=new Promise(resolve=>release=resolve);
  await page.route('**/api/workshop/suggest',async route=>{
    if(responseMode==='stale')await gate;
    if(responseMode==='error'){await route.fulfill({status:502,json:{success:false,error:{message:'模拟 AI 暂时不可用'}}});return;}
    const request=route.request().postDataJSON();
    await route.fulfill({status:201,json:{success:true,data:{suggestion:{id:999,title:'候选 · 慢潮',summary:'模拟候选：降低速度，代码增加一行注释。',params:{...request.params,speed:1},code:request.code+'\n# candidate',generation:{requested_model:'mock'}}}}});
  });
  await page.locator('#suggestCreation').click();
  await page.locator('#creationCode').fill(original+'\n# my new edit');release();
  await expect(page.locator('#candidateStale')).toBeVisible();await expect(page.locator('#applyCandidate')).toBeDisabled();
  await page.locator('#discardCandidate').click();
  responseMode='error';await page.locator('#suggestCreation').click();await expect(page.locator('#workshopStatus')).toContainText('模拟 AI 暂时不可用');
  responseMode='fresh';await page.locator('#suggestCreation').click();await expect(page.locator('#applyCandidate')).toBeEnabled();
  const before=await page.locator('#creationCode').inputValue();
  await page.locator('#applyCandidate').click();await expect(page.locator('#creationCode')).toHaveValue(before+'\n# candidate');
  await expect(page.locator('#saveCreation')).toBeDisabled();await page.locator('#undoCandidate').click();await expect(page.locator('#creationCode')).toHaveValue(before);
  await run(page);
  await page.locator('#creationCode').fill("raise RuntimeError('workshop-test-error')");await page.locator('#runCreation').click();
  await expect(page.locator('#workshopStatus')).toContainText('workshop-test-error',{timeout:20000});await expect(page.locator('#saveCreation')).toBeDisabled();
  await page.locator('#creationCode').fill(original);await run(page);
});

test('主题加载失败可以重试，旧排行榜入口继续可用',async({page})=>{
  let fail=true;await page.route('**/api/workshop/catalog',route=>fail?route.fulfill({status:503,json:{success:false,error:{message:'模拟目录网络失败'}}}):route.continue());
  await page.goto(baseURL+'/workshop.html');await expect(page.locator('#catalogError')).toContainText('模拟目录网络失败');
  fail=false;await page.locator('#retryCatalog').click();await expect(page.locator('.scene-card')).toHaveCount(3);
  await page.goto(baseURL+'/learn-analytics.html#leaderboard');await expect(page).toHaveURL(/learning-records.html#leaderboard/);
});

test('访客登录后恢复自己的创作草稿',async({page})=>{
  await page.goto(baseURL+'/workshop.html');await expect(page.locator('#creationCode')).not.toHaveValue('');
  const code=(await page.locator('#creationCode').inputValue())+'\n# my guest draft';
  await page.locator('#creationCode').fill(code);await page.locator('#creationTitle').fill('登录前的灵感');
  await page.locator('#param-speed').fill('3.5');await page.locator('#runCreation').click();
  await page.locator('#loginToCreate').click();await expect(page).toHaveURL(/login.html/);
  await page.locator('#username').fill('workshop_browser');await page.locator('#password').fill('workshop-browser-only');await page.locator('#submitBtn').click();
  await expect(page).toHaveURL(/workshop.html/);await expect(page.locator('#workshopStatus')).toContainText('已恢复你登录前');
  await expect(page.locator('#creationCode')).toHaveValue(code);await expect(page.locator('#creationTitle')).toHaveValue('登录前的灵感');await expect(page.locator('#param-speed')).toHaveValue('3.5');
  expect(await page.evaluate(()=>sessionStorage.getItem('codelab.workshop.login-draft'))).toBeNull();
});
