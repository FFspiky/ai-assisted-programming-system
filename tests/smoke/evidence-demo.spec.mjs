import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import crypto from 'node:crypto';

const baseURL = process.env.SMOKE_BASE_URL || 'http://127.0.0.1:5005';

test('分级帮助：真实证据、主动揭示、恢复、模式隔离与重新判题', async ({ page }) => {
    test.skip(process.env.EVIDENCE_LIVE_AI !== '1', 'Explicit opt-in required for real model calls');
    test.setTimeout(240000);
    const username = 'graded_' + crypto.randomBytes(4).toString('hex');
    const password = crypto.randomBytes(18).toString('hex');
    const registration = await page.request.post(`${baseURL}/api/register`, {data: {username, email: `${username}@example.test`, password}});
    expect(registration.status()).toBe(201);
    expect((await page.request.post(`${baseURL}/api/login`, {data:{username, password}})).ok()).toBeTruthy();
    const errors = [], records = [];
    let completions = 0;
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => { if (request.url().includes('/ai-inline-complete-stream')) completions += 1; });
    page.on('dialog', dialog => dialog.accept());
    await page.setViewportSize({width:1440,height:1080});
    await page.goto(`${baseURL}/practice.html?problem=DEMO-01`);
    await expect(page.locator('#helpMode')).toBeEnabled();
    await expect(page.locator('#helpMode')).toHaveValue('learning');
    await page.locator('#codeInput').fill('n = int(input())\ntotal = 0\nfor i in range(1, n):\n    total += i\nprint(total)\n');
    await page.locator('#submitBtn').click();
    await expect(page.locator('#evidenceSummary')).toContainText('Wrong Answer', {timeout:20000});
    await expect(page.locator('.help-history')).toHaveCount(0);
    expect(completions).toBe(0);
    for (const level of [1, 2, 3, 4]) {
        const pending = page.waitForResponse(response => /\/submissions\/\d+\/help$/.test(response.url()) && response.request().method() === 'POST', {timeout:80000});
        await page.locator(`[data-help-level="${level}"]`).click();
        const payload = await (await pending).json();
        expect(payload.success, JSON.stringify(payload.error)).toBeTruthy();
        const record = payload.data;
        records.push(record);
        expect(record.level).toBe(level);
        await expect(page.locator(`[data-help-id="${record.id}"]`)).toHaveAttribute('open', '');
        if (level < 3) expect(record.result.code).toBe('');
        if (level === 1) expect(record.result.lines).toEqual([]);
        if (level === 2) {
            await page.locator(`[data-help-id="${record.id}"] .evidence-link`).click();
            await expect(page.locator('.case-card.is-selected')).toHaveCount(1);
            await expect(page.locator('.snapshot-line.is-selected').first()).toBeVisible();
        }
    }
    fs.mkdirSync('tmp/f2-check', {recursive:true});
    fs.writeFileSync('tmp/f2-check/live-help.json', JSON.stringify(records, null, 2));
    await page.screenshot({path:'tmp/f2-check/graded-help.png',fullPage:true});
    await page.reload();
    await expect(page.locator('.help-history')).toHaveCount(4);
    await expect(page.locator('.help-history[open]')).toHaveCount(0);
    await expect(page.locator('#codeInput')).toHaveValue(/range\(1, n\)/);
    await page.locator('#helpMode').selectOption('free');
    await expect(page.locator('#completionStatus')).toContainText('已开启');
    await expect(page.locator('.help-history')).toHaveCount(0);
    await page.locator('#helpMode').selectOption('learning');
    await expect(page.locator('.help-history')).toHaveCount(4);
    await expect(page.locator('.help-history[open]')).toHaveCount(0);
    await expect(page.locator('#completionStatus')).toContainText('已关闭');

    // The existing optimization entry now honors the explicitly selected level.
    const optimized = page.waitForResponse(response => response.url().endsWith('/api/optimize-code'), {timeout:80000});
    await page.locator('#optimizeBtn').click();
    const optimization = await (await optimized).json();
    expect(optimization.success, JSON.stringify(optimization.error)).toBeTruthy();
    expect(optimization.learning_help.level).toBe(1);
    await expect(page.locator('#aiSuggestion .help-code')).toHaveCount(0);
    fs.writeFileSync('tmp/f2-check/live-optimization.json', JSON.stringify(optimization.learning_help, null, 2));

    // Check attachment and chosen-level UI without spending extra model calls.
    const chatRequests = [];
    await page.route('**/api/ai-chat-stream', route => {
        chatRequests.push(route.request().postDataJSON());
        return route.fulfill({contentType: 'text/event-stream', body: 'data: {"type":"content","text":"请检查边界条件。"}\n\ndata: {"type":"done"}\n\n'});
    });
    await page.locator('#aiToggleBtn').click();
    await page.locator('#messageInput').fill('一般如何调试');
    await page.locator('#sendMessage').click();
    await expect(page.locator('#sendMessage')).toBeEnabled();
    expect(chatRequests[0].include_context).toBe(false);
    expect(chatRequests[0].code).toBeUndefined();
    await page.locator('#attachPracticeContext').click();
    await page.locator('#codeHelpLevel').selectOption('2');
    await page.locator('#messageInput').fill('给我一些线索');
    await page.locator('#sendMessage').click();
    await expect(page.locator('#sendMessage')).toBeEnabled();
    expect(chatRequests[1].include_context).toBe(true);
    expect(chatRequests[1].help_level).toBeUndefined();
    expect(chatRequests[1].history).toHaveLength(2);
    await page.locator('#closeChatWindow').click();

    await page.locator('#codeInput').fill('n = int(input())\ntotal = 0\nfor i in range(1, n + 1):\n    total += i\nprint(total)\n');
    await expect(page.locator('#evidenceStale')).toBeVisible();
    await expect(page.locator('#diagnoseBtn')).toBeDisabled();
    await page.locator('#submitBtn').click();
    await expect(page.locator('#evidenceSummary')).toContainText('Accepted', {timeout:20000});
    await expect(page.locator('#evidenceSummary')).toContainText('3/3');
    await expect(page.locator('#helpActions')).toBeHidden();
    await expect(page.locator('.help-history')).toHaveCount(0);
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:'tmp/f2-check/mobile.png',fullPage:true});
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
    expect(errors).toEqual([]);
});
