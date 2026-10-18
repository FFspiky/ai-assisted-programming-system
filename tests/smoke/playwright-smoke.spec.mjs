import { expect, test } from '@playwright/test';

const baseURL = process.env.SMOKE_BASE_URL || 'http://127.0.0.1:5005';

const pages = [
  {
    path: '/index.html',
    text: '智练 CodeLab',
    controls: [{ role: 'link', name: '登录' }, { role: 'link', name: '注册' }]
  },
  {
    path: '/login.html',
    text: '登录',
    controls: [{ role: 'button', name: '登录' }]
  },
  {
    path: '/register.html',
    text: '注册',
    controls: [{ role: 'button', name: '注册' }]
  },
  {
    path: '/problem_selector.html',
    text: '选择题目',
    controls: [{ role: 'link', name: '登录' }, { role: 'link', name: '注册' }]
  },
  {
    path: '/practice.html?problem=P001',
    text: '代码编辑器',
    controls: [
      { role: 'link', name: /选择题目/ },
      { role: 'button', name: /运行代码/ },
      { role: 'button', name: /提交解答/ }
    ]
  },
  {
    path: '/learn-analytics.html',
    text: '学习分析',
    controls: [{ role: 'link', name: '登录' }, { role: 'link', name: '注册' }]
  }
];

for (const pageCase of pages) {
  test(`${pageCase.path} renders without client errors`, async ({ page }) => {
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));

    const response = await page.goto(`${baseURL}${pageCase.path}`, {
      waitUntil: 'domcontentloaded'
    });
    await page.waitForTimeout(300);

    expect(response?.status(), `${pageCase.path} should return 200`).toBe(200);
    await expect(page.getByText(pageCase.text, { exact: false }).first()).toBeVisible();
    for (const control of pageCase.controls) {
      // Target the interactive control, not matching copy in a hidden panel.
      await expect(page.getByRole(control.role, { name: control.name, exact: true })).toBeVisible();
    }
    expect(errors, `${pageCase.path} should not raise runtime errors`).toEqual([]);
  });
}

const mobilePages = [
  {
    path: '/index.html',
    text: '智练 CodeLab'
  },
  {
    path: '/practice.html?problem=P001',
    text: '代码编辑器'
  },
  {
    path: '/learn-analytics.html',
    text: '学习分析'
  }
];

for (const pageCase of mobilePages) {
  test(`${pageCase.path} mobile viewport has no overflow`, async ({ page }) => {
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.setViewportSize({ width: 390, height: 844 });

    const response = await page.goto(`${baseURL}${pageCase.path}`, {
      waitUntil: 'domcontentloaded'
    });
    await page.waitForTimeout(300);

    const hasHorizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2
    );

    expect(response?.status(), `${pageCase.path} should return 200`).toBe(200);
    await expect(page.getByText(pageCase.text, { exact: false }).filter({visible:true}).first()).toBeVisible();
    expect(hasHorizontalOverflow, `${pageCase.path} should not overflow horizontally`).toBe(false);
    expect(errors, `${pageCase.path} should not raise runtime errors on mobile`).toEqual([]);
  });
}
