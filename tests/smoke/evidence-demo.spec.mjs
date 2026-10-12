import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import crypto from 'node:crypto';

const baseURL = process.env.SMOKE_BASE_URL || 'http://127.0.0.1:5005';

test('真实证据诊断：提交、引用定位、刷新恢复、修正通过', async ({ page }) => {
    test.skip(process.env.EVIDENCE_LIVE_AI !== '1', 'Explicit opt-in required for a real model call');
    test.setTimeout(120000);
    const username = 'evidence_' + crypto.randomBytes(4).toString('hex');
    const password = crypto.randomBytes(18).toString('hex');
    const registration = await page.request.post(`${baseURL}/api/register`, {data: {username, email: `${username}@example.test`, password}});
    expect(registration.status()).toBe(201);
    expect((await page.request.post(`${baseURL}/api/login`, {data:{username, password}})).ok()).toBeTruthy();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('dialog', dialog => dialog.accept());
    await page.setViewportSize({width:1440,height:1080});
    await page.goto(`${baseURL}/practice.html?problem=DEMO-01`);
    await expect(page.locator('.problem-title')).toContainText('整数求和');
    await page.locator('#codeInput').fill('n = int(input())\ntotal = 0\nfor i in range(1, n):\n    total += i\nprint(total)\n');
    await page.locator('#submitBtn').click();
    await expect(page.locator('#evidenceSummary')).toContainText('Wrong Answer', {timeout:20000});
    await expect(page.locator('.case-card')).toContainText('预期输出');
    const diagnosisResponse = page.waitForResponse(response => response.url().endsWith('/diagnosis') && response.request().method() === 'POST', {timeout:80000});
    await page.locator('#diagnoseBtn').click();
    const response = await diagnosisResponse;
    const payload = await response.json();
    expect(payload.success, JSON.stringify(payload.error)).toBeTruthy();
    await expect(page.locator('.finding-card').first()).toBeVisible();
    await page.locator('.evidence-link').first().click();
    await expect(page.locator('.case-card.is-selected').first()).toBeVisible();
    await expect(page.locator('.snapshot-line.is-selected').first()).toBeVisible();
    fs.mkdirSync('tmp/evidence-demo', {recursive:true});
    fs.writeFileSync('tmp/evidence-demo/live-diagnosis.json', JSON.stringify(payload.data,null,2));
    await page.screenshot({path:'tmp/evidence-demo/diagnosis.png',fullPage:true});
    await page.reload();
    await expect(page.locator('.finding-card').first()).toBeVisible();
    await expect(page.locator('#codeInput')).toHaveValue(/range\(1, n\)/);
    await page.locator('#codeInput').fill('n = int(input())\ntotal = 0\nfor i in range(1, n + 1):\n    total += i\nprint(total)\n');
    await expect(page.locator('#evidenceStale')).toBeVisible();
    await page.locator('#submitBtn').click();
    await expect(page.locator('#evidenceSummary')).toContainText('Accepted', {timeout:20000});
    await expect(page.locator('#evidenceSummary')).toContainText('3/3');
    await expect(page.locator('#diagnoseBtn')).toBeHidden();
    await page.screenshot({path:'tmp/evidence-demo/accepted.png',fullPage:true});
    // Necessary rendering regression: untrusted AI text cannot create active elements.
    const safe = await page.evaluate(() => {
        const holder = document.createElement('div');
        holder.innerHTML = window.SafeContent.markdown('<img src=x onerror="window.injected=true"><script>window.injected=true</script>');
        document.body.append(holder);
        const result = holder.querySelector('img,script') === null && !window.injected;
        holder.remove();
        return result;
    });
    expect(safe).toBeTruthy();
    expect(errors).toEqual([]);
});
