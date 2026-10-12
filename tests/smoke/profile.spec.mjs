import { test, expect } from '@playwright/test';
import crypto from 'node:crypto';
import fs from 'node:fs';

const baseURL = process.env.SMOKE_BASE_URL || 'http://127.0.0.1:5005';
async function register(page) {
    const username = 'profile_' + crypto.randomBytes(4).toString('hex');
    const password = crypto.randomBytes(18).toString('hex');
    const response = await page.request.post(baseURL+'/api/register', {data:{username,password,email:username+'@example.test'}});
    expect(response.status()).toBe(201);
    return {username,password};
}

test('访客提交提示登录，返回原题且保留代码', async ({ page }) => {
    const account = await register(page);
    await page.goto(baseURL+'/practice.html?problem=DEMO-01');
    await expect(page.locator('.problem-title')).toContainText('整数求和');
    await expect(page.locator('.evidence-intro, .evidence-panel, #loadDemoBtn, .demo-entry')).toHaveCount(0);
    await expect(page.locator('.problem-content')).not.toContainText('AI 辅助编写');
    const code = 'print("guest draft")';
    await page.locator('#codeInput').fill(code);
    await page.locator('#submitBtn').click();
    await expect(page.locator('#outputContent')).toContainText('请先登录后再提交代码');
    await expect(page.locator('#outputContent')).not.toContainText('CSRF');
    await page.locator('#outputContent a').click();
    await page.locator('#username').fill(account.username);
    await page.locator('#password').fill(account.password);
    await page.locator('#submitBtn').click();
    await expect(page).toHaveURL(/practice.html\?problem=DEMO-01/);
    await expect(page.locator('#codeInput')).toHaveValue(code);
});

test('个人页资料、头像、统计、改名草稿和修改密码', async ({ page }) => {
    test.setTimeout(60000);
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    const account = await register(page);
    const login = await (await page.request.post(baseURL+'/api/login',{data:account})).json();
    const headers = {'X-CSRF-Token':login.csrf_token};
    for (const code of ['print(0)','n=int(input())\nprint(n*(n+1)//2)']) {
        const response = await page.request.post(baseURL+'/api/check-solution',{headers,data:{problem_id:'DEMO-01',language:'python',code}});
        expect(response.ok()).toBeTruthy();
    }
    await page.request.post(baseURL+'/api/update_learning_time',{headers,data:{duration:120}});
    await page.setViewportSize({width:1440,height:1000});
    await page.goto(baseURL+'/practice.html?problem=DEMO-01');
    await expect(page.locator('#evidenceSummary')).toContainText('Accepted');
    await expect(page.locator('#submissionResults')).toBeVisible();
    expect(await page.locator('#submissionResults').evaluate(el=>!!el.closest('.output-area'))).toBeTruthy();
    const draft = 'print("keep after rename")';
    await page.locator('#codeInput').fill(draft);
    await page.getByRole('link',{name:'个人主页',exact:true}).click();
    await expect(page.locator('#profileName')).toHaveText(account.username);
    await expect(page.locator('.profile-stat').nth(0)).toContainText('1');
    await expect(page.locator('.profile-stat').nth(1)).toContainText('1');
    await expect(page.locator('.profile-stat').nth(2)).toContainText('2');
    await expect(page.locator('.profile-stat').nth(3)).toContainText('50%');
    await expect(page.locator('.profile-stat').nth(4)).toContainText('2 分钟');
    await expect(page.locator('.profile-table tbody tr')).toHaveCount(2);
    await page.getByRole('button',{name:'编辑个人资料',exact:true}).click();
    await page.locator('#displayName').fill('小林');
    await page.locator('#profileUsername').fill(account.username+'_new');
    await page.locator('#profileBioInput').fill('正在练习 Python 和 C++。');
    await page.locator('#profileLocation').fill('上海');
    await page.getByRole('button',{name:'保存资料',exact:true}).click();
    await expect(page.locator('#profileFormMessage')).toContainText('资料已保存');
    // A small local fixture exercises the real upload endpoint.
    const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jK1sAAAAASUVORK5CYII=','base64');
    await page.locator('#avatarFile').setInputFiles({name:'avatar.png',mimeType:'image/png',buffer:png});
    await expect(page.locator('#avatarMessage')).toContainText('头像已更新');
    await page.reload();
    await expect(page.locator('#profileName')).toHaveText('小林');
    await expect(page.locator('#profileAvatar')).toHaveAttribute('src',/\/api\/profile\/avatar\?v=/);
    await expect(page.locator('.user-avatar img')).toHaveAttribute('src',/\/api\/profile\/avatar\?v=/);
    fs.mkdirSync('tmp/profile-check',{recursive:true});
    await page.screenshot({path:'tmp/profile-check/profile-desktop.png',fullPage:true});
    await page.setViewportSize({width:390,height:844});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth+2)).toBeTruthy();
    await page.screenshot({path:'tmp/profile-check/profile-mobile.png',fullPage:true});
    await page.setViewportSize({width:1440,height:1000});
    await page.goto(baseURL+'/practice.html?problem=DEMO-01');
    await expect(page.locator('#codeInput')).toHaveValue(draft);
    await page.screenshot({path:'tmp/profile-check/practice.png',fullPage:true});
    await page.getByRole('link',{name:'个人主页',exact:true}).click();
    await page.getByRole('tab',{name:'账号安全'}).click();
    await page.locator('#currentPassword').fill(account.password);
    const nextPassword = account.password+'x';
    await page.locator('#newPassword').fill(nextPassword);
    await page.locator('#confirmPassword').fill(nextPassword);
    await page.getByRole('button',{name:'修改密码',exact:true}).click();
    await expect(page).toHaveURL(/login.html\?password=updated/);
    await expect(page.locator('#formMessage')).toContainText('密码已修改');
    await page.locator('#username').fill(account.username+'_new');
    await page.locator('#password').fill(nextPassword);
    await page.locator('#submitBtn').click();
    await expect(page).toHaveURL(/profile.html$/);
    await expect(page.locator('#profileName')).toHaveText('小林');
    expect(errors).toEqual([]);
});
