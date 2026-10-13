import {expect, test} from '@playwright/test';

const baseURL = process.env.SMOKE_BASE_URL || 'http://127.0.0.1:5005';

async function setup(page) {
    await page.route('**/api/current_user', route => route.fulfill({json: {
        success: true, user: {id: 99998, username: '补全测试', points: 0}
    }}));
    await page.route('**/api/csrf-token', route => route.fulfill({json: {csrf_token: 'test-token'}}));
    await page.route('**/api/update_learning_time', route => route.fulfill({json: {success: true}}));
    await page.addInitScript(() => {
        const fetchOriginal = window.fetch;
        window.completionRequests = [];
        window.finishCompletions = [];
        window.fetch = async (url, options) => {
            if (url !== '/api/ai-inline-complete-stream') return fetchOriginal(url, options);
            const request = JSON.parse(options.body);
            window.completionRequests.push(request);
            const encoder = new TextEncoder();
            let cancelled = false;
            const stream = new ReadableStream({start(controller) {
                options.signal.addEventListener('abort', () => {
                    cancelled = true;
                    controller.error(new DOMException('Stopped', 'AbortError'));
                });
                setTimeout(() => { if (!cancelled) controller.enqueue(encoder.encode('42')); }, 200);
                window.finishCompletions.push(() => { if (!cancelled) {controller.enqueue(encoder.encode(')')); controller.close();} });
            }});
            return new Response(stream, {headers: {'Content-Type': 'text/plain'}});
        };
    });
    await page.goto(baseURL + '/practice.html?problem=DEMO-01');
    await expect(page.locator('.username')).toHaveText('补全测试');
}

test('自动补全无需开关、流式显示、Tab 接受且重复上下文命中缓存', async ({page}) => {
    await setup(page);
    await expect(page.locator('#completionEnabled')).toHaveCount(0);
    await page.locator('#codeInput').fill('print(');
    await expect(page.locator('#ghostLayer .ghost')).toHaveText('42');
    await page.evaluate(() => window.finishCompletions[0]());
    await expect(page.locator('#ghostLayer .ghost')).toHaveText('42)');
    await page.locator('#codeInput').press('Tab');
    await expect(page.locator('#codeInput')).toHaveValue('print(42)');
    // Cancel the follow-on request and return to the original cursor context.
    await page.locator('#codeInput').press('Escape');
    await page.locator('#codeInput').fill('print(');
    await expect(page.locator('#ghostLayer .ghost')).toHaveText('42)');
    expect(await page.evaluate(() => window.completionRequests.length)).toBe(1);
});

test('Esc、输入和光标移动取消旧流，过期文本不会重新出现', async ({page}) => {
    await setup(page);
    const input = page.locator('#codeInput');
    await input.fill('print(');
    await expect(page.locator('#ghostLayer .ghost')).toHaveText('42');
    await input.press('Escape');
    await page.evaluate(() => window.finishCompletions.forEach(finish => finish()));
    await page.waitForTimeout(250);
    await expect(page.locator('#ghostLayer .ghost')).toHaveText('');
    await input.fill('sum([');
    await expect.poll(() => page.evaluate(() => window.completionRequests.length)).toBe(2);
    await input.press('ArrowLeft');
    await page.evaluate(() => window.finishCompletions.forEach(finish => finish()));
    await page.waitForTimeout(250);
    await expect(page.locator('#ghostLayer .ghost')).toHaveText('');
    await input.fill('max([');
    await expect(page.locator('#ghostLayer .ghost')).toHaveText('42');
    await input.fill('x');
    await page.evaluate(() => window.finishCompletions.forEach(finish => finish()));
    await page.waitForTimeout(250);
    await expect(page.locator('#ghostLayer .ghost')).toHaveText('');
    await expect(input).toHaveValue('x');
});

test('输入法组词和访客不会自动发起补全请求', async ({page}) => {
    await setup(page);
    const input = page.locator('#codeInput');
    await input.focus();
    await input.dispatchEvent('compositionstart');
    await input.fill('# 正在输入');
    await page.waitForTimeout(300);
    expect(await page.evaluate(() => window.completionRequests.length)).toBe(0);
    await input.dispatchEvent('compositionend');
    await expect.poll(() => page.evaluate(() => window.completionRequests.length)).toBe(1);
    await page.evaluate(() => window.dispatchEvent(new Event('auth:required')));
    await input.fill('print(');
    await page.waitForTimeout(300);
    expect(await page.evaluate(() => window.completionRequests.length)).toBe(1);
    await expect(page.locator('#ghostLayer .ghost')).toHaveText('');
});
