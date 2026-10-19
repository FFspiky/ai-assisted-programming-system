import {expect, test} from '@playwright/test';

const base = process.env.SMOKE_BASE_URL || 'http://127.0.0.1:5005';
async function login(page) {
  const username = `contest-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  expect((await page.request.post(base + '/api/register', {data: {username, email: username+'@example.test', password:'test-password'}})).status()).toBe(201);
  expect((await page.request.post(base + '/api/login', {data: {username,password:'test-password'}})).ok()).toBeTruthy();
}

test('共创真实运行、解释保存、阶段切换及移动端布局', async ({page}) => {
  test.setTimeout(60000);
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await login(page);
  await page.goto(base+'/co-create.html?problem=CL-BASICS-01&language=python&mode=review');
  await page.locator('#topic-disclosure').evaluate(node=>node.open=true);
  await expect(page.locator('#language-select option')).toHaveCount(2);
  await expect(page.locator('#new-session')).toBeEnabled();
  await page.locator('#new-session').click();
  await expect(page.locator('#review-code')).toBeEnabled();
  await page.locator('#review-code').fill('t = int(input())\nprint(t // 3600, t // 60 % 60, t % 60)');
  await page.locator('#review-input').fill('3661');
  const running=page.waitForResponse(r=>r.url().endsWith('/review-run')&&r.request().method()==='POST');
  await page.locator('#run-review').click();
  expect((await running).status()).toBe(200);
  await expect(page.locator('#review-results')).toContainText('1 1 1');
  await page.locator('#verify-next').click();
  await page.locator('#reflection-reason').fill('分钟取余，避免重复计算已计入小时的部分。');
  const saving=page.waitForResponse(r=>r.url().endsWith('/learning/reflection')&&r.request().method()==='POST');
  await page.locator('#save-learning-reflection').click();
  expect((await saving).status()).toBe(200);
  await page.locator('#explain-next').click();
  await expect(page.locator('#stage-transfer')).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBeTruthy();
  expect(errors).toEqual([]);
});

test('任务室仅显示双语言并保存 C++ 草稿', async ({page})=>{
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await login(page);
  await page.goto(base+'/task-room.html');
  await page.locator('.mission-open').first().click();
  await expect(page.locator('#scenario-dialog')).toBeVisible();
  const language=page.locator('#scenario-dialog select');
  await expect(language.locator('option')).toHaveCount(2);
  await language.selectOption('cpp');
  const creating=page.waitForResponse(r=>r.url().endsWith('/projects')&&r.request().method()==='POST');
  await page.locator('#create-project').click();
  expect((await creating).status()).toBe(201);
  await expect(page.locator('#room-view')).toBeVisible();
  await expect(page.locator('#code-editor')).toHaveValue(/Json solve/);
  await page.reload();
  await expect(page.locator('#room-view')).toBeVisible();
  await expect(page.locator('#code-editor')).toHaveValue(/Json solve/);
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBeTruthy();
  expect(errors).toEqual([]);
});
