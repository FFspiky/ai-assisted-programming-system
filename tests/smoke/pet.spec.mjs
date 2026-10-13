import {expect, test} from '@playwright/test';

const baseURL = process.env.SMOKE_BASE_URL || 'http://127.0.0.1:5005';
async function setup(page) {
    await page.setViewportSize({width: 1280, height: 900});
    await page.goto(baseURL + '/practice.html?problem=DEMO-01');
    await expect(page.locator('#aiToggleBtn')).toHaveAttribute('data-ready', 'true');
}

test('拖起、悬空、松手落地使用不同原画且不误开聊天', async ({page}) => {
    await setup(page);
    const pet = page.locator('#aiToggleBtn');
    const initial = await pet.getAttribute('data-frame');
    const rect = await pet.boundingBox();
    await page.mouse.move(rect.x + 60, rect.y + 60);
    await page.mouse.down();
    await page.mouse.move(430, 250, {steps: 12});
    await expect(pet).toHaveAttribute('data-state', 'drag');
    await expect(pet).not.toHaveAttribute('data-frame', initial);
    await expect(pet).toHaveClass(/is-dragging/);
    await expect(page.locator('#aiFloatingWindow')).toBeHidden();
    await page.screenshot({path: 'tmp/assistant-check/pet-dragging.png'});
    await page.mouse.up();
    await expect(pet).toHaveAttribute('data-state', /fall|land/);
    await expect(pet).toHaveAttribute('data-state', 'idle');
    const landed = await pet.boundingBox();
    expect(landed.y).toBeGreaterThan(190);
    expect(landed.y).toBeLessThanOrEqual(222);
    await expect(page.locator('#aiFloatingWindow')).toBeHidden();
    await page.reload();
    await expect(pet).toHaveAttribute('data-ready', 'true');
    expect((await pet.boundingBox()).x).toBeCloseTo(landed.x, 0);
    expect((await pet.boundingBox()).y).toBeCloseTo(landed.y, 0);
});

test('动作菜单播放多帧、睡眠保持、醒来恢复且菜单在屏幕内', async ({page}) => {
    await setup(page);
    const pet = page.locator('#aiToggleBtn');
    const menu = page.locator('#petActionMenu');
    for (const action of ['wave', 'jump', 'dance', 'eat']) {
        await pet.click({button: 'right'});
        await expect(menu).toBeVisible();
        await menu.locator(`[data-pet-action="${action}"]`).click();
        await expect(pet).toHaveAttribute('data-state', action);
        const frame = await pet.getAttribute('data-frame');
        await expect(pet).not.toHaveAttribute('data-frame', frame);
        await expect(pet).toHaveAttribute('data-state', 'idle');
    }
    await pet.click({button: 'right'});
    await menu.locator('[data-pet-action="sleep"]').click();
    await expect(pet).toHaveAttribute('data-state', 'sleep');
    await page.waitForTimeout(3300);
    await expect(pet).toHaveAttribute('data-state', 'sleep');
    await page.screenshot({path: 'tmp/assistant-check/pet-sleeping.png'});
    await pet.click({button: 'right'});
    await menu.locator('[data-pet-action="wake"]').click();
    await expect(pet).toHaveAttribute('data-state', 'wake');
    await expect(pet).toHaveAttribute('data-state', 'idle');
    await page.setViewportSize({width: 320, height: 568});
    await pet.click({button: 'right'});
    const rect = await menu.boundingBox();
    expect(rect.x).toBeGreaterThanOrEqual(0);
    expect(rect.y).toBeGreaterThanOrEqual(0);
    expect(rect.x + rect.width).toBeLessThanOrEqual(320);
    expect(rect.y + rect.height).toBeLessThanOrEqual(568);
});

test('减少动态效果仍显示拖起状态，取消拖动可恢复', async ({page}) => {
    await page.emulateMedia({reducedMotion: 'reduce'});
    await setup(page);
    const pet = page.locator('#aiToggleBtn');
    const rect = await pet.boundingBox();
    await page.mouse.move(rect.x + 50, rect.y + 50);
    await page.mouse.down();
    await page.mouse.move(360, 260, {steps: 5});
    await expect(pet).toHaveAttribute('data-state', 'drag');
    expect(await page.locator('.pet-sprite').evaluate(el => getComputedStyle(el).transform)).toBe('none');
    await page.mouse.up();
    await expect(pet).toHaveAttribute('data-state', 'idle');
    await expect(page.locator('#aiFloatingWindow')).toBeHidden();
});

test('聊天思考和回答切换动作，拖动结束恢复当前聊天状态', async ({page}) => {
    await page.route('**/api/current_user', route => route.fulfill({json: {
        success: true, user: {id: 99997, username: '动作测试', points: 0}
    }}));
    await page.route('**/api/csrf-token', route => route.fulfill({json: {csrf_token: 'test-token'}}));
    await page.addInitScript(() => {
        const originalFetch = window.fetch;
        window.fetch = async (url, options) => {
            if (url !== '/api/ai-chat-stream') return originalFetch(url, options);
            return new Response(new ReadableStream({start(controller) {
                window.emitPetResponse = event => {
                    controller.enqueue(new TextEncoder().encode('data: ' + JSON.stringify(event) + '\n\n'));
                    if (event.type === 'done') controller.close();
                };
            }}), {headers: {'Content-Type': 'text/event-stream'}});
        };
    });
    await setup(page);
    const pet = page.locator('#aiToggleBtn');
    await pet.click();
    await page.locator('#messageInput').fill('帮我看看');
    await page.locator('#sendMessage').click();
    await expect(pet).toHaveAttribute('data-state', 'think');
    const rect = await pet.boundingBox();
    await page.mouse.move(rect.x + 50, rect.y + 50);
    await page.mouse.down();
    await page.mouse.move(350, 400, {steps: 5});
    await expect(pet).toHaveAttribute('data-state', 'drag');
    await page.mouse.up();
    await expect(pet).toHaveAttribute('data-state', 'think');
    await page.evaluate(() => window.emitPetResponse({type: 'content', text: '可以，我们一起看。'}));
    await expect(pet).toHaveAttribute('data-state', 'talk');
    await page.evaluate(() => window.emitPetResponse({type: 'done'}));
    await expect(pet).toHaveAttribute('data-state', 'wave');
    await expect(pet).toHaveAttribute('data-state', 'idle');
});
