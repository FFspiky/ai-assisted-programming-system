import { expect, test } from '@playwright/test';

const baseURL = process.env.SMOKE_BASE_URL || 'http://127.0.0.1:5005';

async function mockSession(page) {
    await page.route('**/api/current_user', route => route.fulfill({json: {
        success: true, user: {id: 99999, username: '小林', display_name: '小林', points: 0}
    }}));
    await page.route('**/api/csrf-token', route => route.fulfill({json: {csrf_token: 'test-token'}}));
    await page.route('**/api/update_learning_time', route => route.fulfill({json: {success: true}}));
}

async function mockChatStream(page, {stop = false} = {}) {
    await page.addInitScript(({stop}) => {
        const originalFetch = window.fetch;
        window.chatRequests = [];
        window.fetch = async (url, options) => {
            if (url !== '/api/ai-chat-stream') return originalFetch(url, options);
            window.chatRequests.push(JSON.parse(options.body));
            const encoder = new TextEncoder();
            let cancelled = false;
            const stream = new ReadableStream({start(controller) {
                options.signal.addEventListener('abort', () => {
                    cancelled = true;
                    controller.error(new DOMException('Stopped', 'AbortError'));
                });
                const send = event => {
                    if (cancelled) return;
                    const bytes = encoder.encode('data: ' + JSON.stringify(event) + '\n\n');
                    // Split UTF-8 characters and SSE frames across network chunks.
                    for (let i = 0; i < bytes.length; i += 7) controller.enqueue(bytes.slice(i, i + 7));
                };
                setTimeout(() => send({type: 'reasoning', text: '先比较数据是否可变。<img src=x onerror=alert(1)>'}), 50);
                if (stop) return;
                setTimeout(() => send({type: 'content', text: '**list 可变**，tuple 不可变。'}), 1200);
                setTimeout(() => { if (!cancelled) {send({type: 'done'}); controller.close();} }, 1600);
            }});
            return new Response(stream, {headers: {'Content-Type': 'text/event-stream'}});
        };
    }, {stop});
}

test('思考实时显示、回答后折叠、历史只发送回答', async ({page}) => {
    await mockSession(page);
    await mockChatStream(page);
    await page.goto(baseURL + '/practice.html?problem=DEMO-01');
    await page.locator('#aiToggleBtn').click();
    await page.locator('#messageInput').fill('list 和 tuple 有何区别？');
    await page.locator('#sendMessage').click();
    const thought = page.locator('.reasoning-panel').last();
    await expect(thought).toBeVisible();
    await expect(thought.locator('.reasoning-text')).toBeVisible();
    await expect(thought.locator('.reasoning-text')).toContainText('先比较数据是否可变');
    await expect(page.locator('.message-content').last()).not.toContainText('tuple 不可变');
    await expect(page.locator('.message-content').last()).toContainText('tuple 不可变');
    await expect(thought).not.toHaveAttribute('open');
    await expect(page.locator('#stopChat')).toBeHidden();
    await thought.locator('summary').click();
    await expect(thought.locator('.reasoning-text')).toBeVisible();
    await expect(thought.locator('img')).toHaveCount(0);
    await page.locator('#messageInput').fill('继续');
    await page.locator('#sendMessage').click();
    const requests = await page.evaluate(() => window.chatRequests);
    expect(requests[1].history[1].content).toBe('**list 可变**，tuple 不可变。');
    expect(JSON.stringify(requests[1].history)).not.toContain('onerror');
});

test('停止思考保留内容且可再次发送', async ({page}) => {
    await mockSession(page);
    await mockChatStream(page, {stop: true});
    await page.goto(baseURL + '/practice.html?problem=DEMO-01');
    await page.locator('#aiToggleBtn').click();
    await page.locator('#messageInput').fill('分析一下');
    await page.locator('#sendMessage').click();
    await expect(page.locator('.reasoning-text')).toContainText('先比较数据');
    await page.locator('#stopChat').click();
    await expect(page.locator('.chat-stream-status')).toContainText('已停止');
    await expect(page.locator('.reasoning-text')).toContainText('先比较数据');
    await expect(page.locator('#sendMessage')).toBeEnabled();
});
