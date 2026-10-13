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

async function assertWindowFits(page) {
    const dimensions = await page.locator('#aiFloatingWindow').evaluate(el => {
        const rect = el.getBoundingClientRect();
        const send = document.getElementById('sendMessage').getBoundingClientRect();
        const input = document.getElementById('messageInput').getBoundingClientRect();
        return {left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom,
            width: rect.width, sendRight: send.right, inputRight: input.right,
            inputBottom: input.bottom, inputWidth: input.width,
            viewportWidth: innerWidth, viewportHeight: innerHeight};
    });
    expect(dimensions.left).toBeGreaterThanOrEqual(11);
    expect(dimensions.top).toBeGreaterThanOrEqual(11);
    expect(dimensions.right).toBeLessThanOrEqual(dimensions.viewportWidth - 11);
    expect(dimensions.bottom).toBeLessThanOrEqual(dimensions.viewportHeight - 11);
    expect(dimensions.sendRight).toBeLessThan(dimensions.right);
    expect(dimensions.inputBottom).toBeLessThan(dimensions.bottom);
    expect(dimensions.inputWidth).toBeGreaterThan(100);
    expect(dimensions.inputRight).toBeLessThan(dimensions.sendRight);
}

test('聊天框拖动、缩放、位置保存、双方头像及窄屏输入完整', async ({page}) => {
    await mockSession(page);
    await mockChatStream(page);
    await page.setViewportSize({width: 1440, height: 900});
    await page.goto(baseURL + '/practice.html?problem=DEMO-01');
    await page.locator('#aiToggleBtn').click();
    const before = await page.locator('#aiFloatingWindow').boundingBox();
    const header = await page.locator('#aiDragHandle').boundingBox();
    await page.mouse.move(header.x + 90, header.y + 20);
    await page.mouse.down();
    await page.mouse.move(header.x - 410, header.y - 60, {steps: 12});
    await page.mouse.up();
    const moved = await page.locator('#aiFloatingWindow').boundingBox();
    expect(moved.x).toBeLessThan(before.x - 400);
    const handle = await page.locator('#chatResizeHandle').boundingBox();
    await page.mouse.move(handle.x + 10, handle.y + 10);
    await page.mouse.down();
    await page.mouse.move(handle.x - 90, handle.y - 140, {steps: 12});
    await page.mouse.up();
    const resized = await page.locator('#aiFloatingWindow').boundingBox();
    expect(resized.width).toBeLessThan(moved.width - 90);
    expect(resized.height).toBeLessThan(moved.height - 140);
    await assertWindowFits(page);
    await page.locator('#closeChatWindow').click();
    await page.locator('#aiToggleBtn').click();
    expect(await page.locator('#aiFloatingWindow').boundingBox()).toEqual(resized);
    await page.locator('#messageInput').fill('比较 list 和 tuple');
    await page.locator('#sendMessage').click();
    await expect(page.locator('.user-message .message-avatar img')).toBeVisible();
    await expect(page.locator('.ai-message .message-avatar img').last()).toBeVisible();
    await expect(page.locator('.user-message .message-header')).toHaveText('小林');
    await expect(page.locator('#stopChat')).toBeVisible();
    await assertWindowFits(page);
    await expect(page.locator('#stopChat')).toBeHidden();
    await page.locator('#resetChatWindow').click();
    expect((await page.locator('#aiFloatingWindow').boundingBox()).width).toBe(440);
    for (const size of [{width: 1024, height: 768}, {width: 390, height: 844}, {width: 320, height: 568}]) {
        await page.setViewportSize(size);
        await expect.poll(async () => page.locator('#aiFloatingWindow').evaluate(el => {
            const rect = el.getBoundingClientRect();
            return rect.right <= innerWidth - 11 && rect.bottom <= innerHeight - 11;
        })).toBe(true);
        await assertWindowFits(page);
    }
});

test('拖动桌宠不误开聊天，移动和缩放不会越出屏幕', async ({page}) => {
    await page.setViewportSize({width: 1024, height: 768});
    await page.goto(baseURL + '/practice.html?problem=DEMO-01');
    const pet = await page.locator('#aiToggleBtn').boundingBox();
    await page.mouse.move(pet.x + 40, pet.y + 40);
    await page.mouse.down();
    await page.mouse.move(900, 100, {steps: 12});
    await page.mouse.up();
    await expect(page.locator('#aiFloatingWindow')).toBeHidden();
    await page.locator('#aiToggleBtn').click();
    await page.locator('#aiDragHandle').focus();
    for (let i = 0; i < 30; i++) await page.keyboard.press('Shift+ArrowLeft');
    for (let i = 0; i < 30; i++) await page.keyboard.press('Shift+ArrowUp');
    await assertWindowFits(page);
    await page.locator('#chatResizeHandle').focus();
    for (let i = 0; i < 30; i++) await page.keyboard.press('Shift+ArrowRight');
    await assertWindowFits(page);
    await page.keyboard.press('Escape');
    await expect(page.locator('#aiFloatingWindow')).toBeHidden();
    await expect(page.locator('#aiToggleBtn')).toBeFocused();
});

test('八个方向缩放保持对边固定，最大化与拖动还原保留尺寸', async ({page}) => {
    await page.setViewportSize({width: 1440, height: 1000});
    await page.goto(baseURL + '/practice.html?problem=DEMO-01');
    await page.locator('#aiToggleBtn').click();
    const window = page.locator('#aiFloatingWindow');
    const header = await page.locator('#aiDragHandle').boundingBox();
    await page.mouse.move(header.x + 90, header.y + 25);
    await page.mouse.down();
    await page.mouse.move(header.x - 300, header.y - 150, {steps: 10});
    await page.mouse.up();
    for (const direction of ['n', 's', 'e', 'w', 'ne', 'nw', 'sw', 'se']) {
        const before = await window.boundingBox();
        const handle = await page.locator(`[data-direction="${direction}"]`).boundingBox();
        const dx = direction.includes('w') ? -20 : direction.includes('e') ? 20 : 0;
        const dy = direction.includes('n') ? -12 : direction.includes('s') ? 12 : 0;
        await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2);
        await page.mouse.down();
        await page.mouse.move(handle.x + handle.width / 2 + dx, handle.y + handle.height / 2 + dy, {steps: 5});
        await page.mouse.up();
        const after = await window.boundingBox();
        expect(after.width).toBeCloseTo(before.width + Math.abs(dx), 0);
        expect(after.height).toBeCloseTo(before.height + Math.abs(dy), 0);
        expect(direction.includes('w') ? after.x + after.width : after.x)
            .toBeCloseTo(direction.includes('w') ? before.x + before.width : before.x, 0);
        expect(direction.includes('n') ? after.y + after.height : after.y)
            .toBeCloseTo(direction.includes('n') ? before.y + before.height : before.y, 0);
    }
    const normal = await window.boundingBox();
    await page.locator('#maximizeChatWindow').click();
    await expect(window).toHaveClass(/is-maximized/);
    expect((await window.boundingBox()).width).toBe(1416);
    await page.locator('#maximizeChatWindow').click();
    expect(await window.boundingBox()).toEqual(normal);
    await page.locator('#aiChatTitle').dblclick();
    await expect(window).toHaveClass(/is-maximized/);
    await page.reload();
    await page.locator('#aiToggleBtn').click();
    await expect(window).toHaveClass(/is-maximized/);
    const maximizedHeader = await page.locator('#aiDragHandle').boundingBox();
    await page.mouse.move(maximizedHeader.x + 150, maximizedHeader.y + 25);
    await page.mouse.down();
    await page.mouse.move(450, 180, {steps: 10});
    await page.mouse.up();
    await expect(window).not.toHaveClass(/is-maximized/);
    expect((await window.boundingBox()).width).toBe(normal.width);
    await assertWindowFits(page);
});
