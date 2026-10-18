import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const baseURL = process.env.SMOKE_BASE_URL || 'http://127.0.0.1:5007';
const artifacts = 'tmp/task-room-check';
const referencesPath = path.join(artifacts, 'references.json');
const endpoint = '/api/task-room/projects';

function stable(value) {
  return JSON.stringify(Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b))));
}

function reference(project) {
  const records = JSON.parse(fs.readFileSync(referencesPath, 'utf8'));
  const match = records.find(record => record.scenario_id === project.scenario_id && stable(record.rules) === stable(project.contract.rules));
  expect(match, 'Fixture must provide an independently verified reference for this confirmed contract').toBeTruthy();
  return match.code;
}

async function login(page) {
  const response = await page.request.post(baseURL + '/api/login', {
    data: { username: 'task-browser', password: 'test-password' },
  });
  expect(response.status()).toBe(200);
}

function responseFor(page, suffix, method = 'POST') {
  return page.waitForResponse(response => response.request().method() === method && new URL(response.url()).pathname.endsWith(suffix));
}

async function create(page, scenario = 'signup_roster') {
  await page.locator(`.mission-open[data-scenario="${scenario}"]`).click();
  await expect(page.locator('#scenario-dialog')).toBeVisible();
  const pending = responseFor(page, endpoint);
  await page.locator('#create-project').click();
  const response = await pending;
  expect(response.status()).toBe(201);
  const project = (await response.json()).data.project;
  await expect(page.locator('#room-view')).toBeVisible();
  return project;
}

async function freeze(page) {
  const pending = responseFor(page, '/freeze');
  await page.locator('#freeze-contract').click();
  const response = await pending;
  expect(response.status()).toBe(200);
  await expect(page.locator('#code-editor')).toBeEnabled();
  return (await response.json()).data.project;
}

async function run(page, code) {
  await page.locator('#code-editor').fill(code);
  const pending = responseFor(page, '/run');
  await page.locator('#run-acceptance').click();
  const response = await pending;
  expect(response.status()).toBe(200);
  return (await response.json()).data;
}

async function deliver(page) {
  await expect(page.locator('#deliver-project')).toBeEnabled();
  const pending = responseFor(page, '/deliver');
  await page.locator('#deliver-project').click();
  const response = await pending;
  expect(response.status()).toBe(200);
  return (await response.json()).data.project;
}

test.beforeEach(async ({ page }) => {
  // Browser verification never calls the paid model service.
  await page.route('**/api/task-room/projects/*/messages', route => route.fulfill({
    status: 503,
    json: { success: false, data: {}, error: { code: 'AI_UNAVAILABLE', message: '测试中的 AI 服务暂不可用，请重试。' } },
  }));
  page.on('dialog', dialog => dialog.accept());
  fs.mkdirSync(artifacts, { recursive: true });
});

test('任务完整闭环：需求、Docker验收、交付、变更、恢复与导出', async ({ page }) => {
  test.setTimeout(120000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.setViewportSize({ width: 1536, height: 1050 });
  await login(page);
  await page.goto(baseURL + '/task-room.html');
  await expect(page.locator('.mission-open')).toHaveCount(9);
  let project = await create(page);
  project = await freeze(page);
  const firstContract = project.contract.id;

  const failed = await run(page, 'def solve(data):\n    return {}\n');
  expect(failed.run.status).toBe('failed');
  expect(failed.run.execution.execution_backend).toBe('docker');
  await expect(page.locator('#deliver-project')).toBeDisabled();
  const passed = await run(page, reference(project));
  expect(passed.run.status).toBe('passed');
  expect(passed.run.passed).toBe(passed.run.total);
  project = await deliver(page);
  expect(project.state).toBe('delivered');

  const change = project.scenario.changes.find(item => Object.entries(item.patch).some(([key, value]) => project.contract.rules[key] !== value));
  expect(change).toBeTruthy();
  const changing = responseFor(page, '/changes');
  await page.locator(`#change-list button[data-change="${change.id}"]`).click();
  const changedResponse = await changing;
  expect(changedResponse.status()).toBe(200);
  project = (await changedResponse.json()).data.project;
  expect(project.contract.version).toBe(2);
  expect(project.contract.id).not.toBe(firstContract);
  expect(project.delivery).toBeNull();
  await expect(page.locator('#deliver-project')).toBeDisabled();

  const oldCode = await page.locator('#code-editor').inputValue();
  const obsolete = await run(page, oldCode);
  expect(obsolete.run.status).toBe('failed');
  const newCode = reference(project);
  const acceptedV2 = await run(page, newCode);
  expect(acceptedV2.run.status).toBe('passed');
  project = await deliver(page);
  expect(project.delivery.contract_id).toBe(project.contract.id);
  const id = project.id;

  await page.reload();
  await expect(page.locator('#room-view')).toBeVisible();
  await expect(page.locator('#code-editor')).toHaveValue(newCode);
  await expect(page.locator('#contract-number')).toContainText('2');
  await expect(page.locator('#contract-history')).toContainText('1');
  const downloadPending = page.waitForEvent('download');
  await page.locator('#export-project').click();
  const download = await downloadPending;
  expect(download.suggestedFilename()).toMatch(/^task-room-.*\.zip$/);
  await download.saveAs(path.join(artifacts, 'browser-delivery.zip'));
  expect(fs.statSync(path.join(artifacts, 'browser-delivery.zip')).size).toBeGreaterThan(300);
  await page.screenshot({ path: path.join(artifacts, 'desktop-delivery.png'), fullPage: true });

  // Editing a delivered snapshot reopens work and removes the previous badge.
  const revised = newCode + '\n# Edited after delivery; run acceptance again.\n';
  await page.locator('#code-editor').fill(revised);
  const reopened = responseFor(page, endpoint + '/' + id, 'PATCH');
  await page.locator('#save-code').click();
  expect((await reopened).status()).toBe(200);
  await expect(page.locator('#room-state')).toHaveText('开发与验收');
  await expect(page.locator('#deliver-project')).toBeDisabled();
  await page.reload();
  await expect(page.locator('#code-editor')).toHaveValue(revised);
  await expect(page.locator('#room-state')).toHaveText('开发与验收');

  const archiving = responseFor(page, endpoint + '/' + id, 'PATCH');
  await page.locator('#archive-project').click();
  const archived = await archiving;
  expect(archived.status()).toBe(200);
  await expect(page.locator('#catalog-view')).toBeVisible();
  await expect(page.locator(`#project-list button[data-project="${id}"]`)).toHaveCount(0);
  await page.locator('#show-archived').check();
  await page.locator(`#project-list button[data-project="${id}"]`).click();
  await expect(page.locator('#room-view')).toBeVisible();
  const restoring = responseFor(page, endpoint + '/' + id, 'PATCH');
  await page.locator('#archive-project').click();
  expect((await restoring).status()).toBe(200);
  expect(errors).toEqual([]);
});

test('AI失败清楚可重试，任务资料和当前代码仍可使用', async ({ page }) => {
  const errors = [];
  const operations = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {
    if (request.method() === 'POST' && new URL(request.url()).pathname.endsWith('/messages'))
      operations.push(request.postDataJSON().operation_id);
  });
  await login(page);
  await page.goto(baseURL + '/task-room.html');
  await create(page, 'event_waitlist');
  await page.locator('#chat-input').fill('取消报名后可以释放名额吗？');
  const failed = responseFor(page, '/messages');
  await page.locator('#send-message').click();
  expect((await failed).status()).toBe(503);
  await expect(page.locator('#notice')).toContainText('AI 服务暂不可用');
  await expect(page.locator('#send-message')).toBeEnabled();
  await expect(page.locator('#chat-input')).toHaveValue('取消报名后可以释放名额吗？');
  const retried = responseFor(page, '/messages');
  await page.locator('#send-message').click();
  expect((await retried).status()).toBe(503);
  expect(operations).toHaveLength(2);
  expect(operations[1]).not.toBe(operations[0]);
  await expect(page.locator('#chat-input')).toHaveValue('取消报名后可以释放名额吗？');
  await expect(page.locator('#client-brief')).not.toBeEmpty();
  const project = await freeze(page);
  expect(project.contract.cases.length).toBeGreaterThan(0);
  await page.locator('#code-editor').fill('def solve(data):\n    return {}\n');
  const saving = responseFor(page, endpoint + '/' + project.id, 'PATCH');
  await page.locator('#save-code').click();
  expect((await saving).status()).toBe(200);
  await page.reload();
  await expect(page.locator('#code-editor')).toHaveValue('def solve(data):\n    return {}\n');
  expect(errors).toEqual([]);
});

test('移动端任务大厅和工作台无横向溢出，访客能查看任务介绍', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(baseURL + '/task-room.html');
  await expect(page.locator('.mission-open')).toHaveCount(9);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.locator('.mission-open').first().click();
  await expect(page.locator('#scenario-dialog')).toBeVisible();
  await expect(page.locator('#scenario-preview')).not.toBeEmpty();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.locator('#scenario-dialog .dialog-close').click();
  await page.screenshot({ path: path.join(artifacts, 'mobile-catalog.png'), fullPage: true });
  await login(page);
  await page.reload();
  await create(page, 'stock_orders');
  await freeze(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: path.join(artifacts, 'mobile-room.png'), fullPage: true });
  expect(errors).toEqual([]);
});
