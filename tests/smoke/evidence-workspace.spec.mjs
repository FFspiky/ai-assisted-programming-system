import {expect, test} from '@playwright/test';
import fs from 'node:fs';

const baseURL = process.env.SMOKE_BASE_URL || 'http://127.0.0.1:5005';
const original = 'n = int(input())\ntotal = 0\nfor i in range(1, n):\n    total += i\nprint(total)';
const candidate = original.replace('range(1, n)', 'range(1, n + 1)');

// All API traffic is intercepted: no accounts, submissions or model calls are real.
async function fixture(page) {
    fs.mkdirSync('tmp/workspace-ui', {recursive: true});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    let submission = {submission_id: 700, code: original, language: 'python', status: 'Wrong Answer',
        created_at: '2026-10-14T05:00:00', evidence: {executed: 1, total: 3, not_run: 2,
            cases: [{id: 'case-1', index: 1, is_public: true, status: 'Wrong Answer',
                input: '3', expected_output: '6', actual_output: '3'}]}};
    const proposal = {id: 900, help_id: 703, submission_id: 700, base_code: original,
        candidate_code: candidate, state: 'pending', revision: 0,
        diff: ['@@ -1,5 +1,5 @@', ' total = 0', '-for i in range(1, n):', '+for i in range(1, n + 1):', '     total += i']};
    const records = new Map();
    const events = [];
    const control = {errors, fail: false, insufficient: false};
    await page.route('**/api/**', async route => {
        const url = new URL(route.request().url()), path = url.pathname;
        const method = route.request().method();
        let json = {success: true, data: {}};
        if (path === '/api/current_user') json.user = {id: 99991, username: '界面检查', points: 0};
        else if (path === '/api/csrf-token') json.csrf_token = 'test-token';
        else if (path === '/api/help-settings') json.data = {mode: 'learning', revision: 0};
        else if (path === '/api/problems') json.problems = [{id: 'DEMO-01', title: '整数求和'}];
        else if (path === '/api/problems/DEMO-01') json.problem = {id: 'DEMO-01', title: '整数求和', difficulty: '简单',
            description: '<p>输入整数 n，输出从 1 到 n（包含 n）的整数之和。</p><pre>输入：3\n输出：6</pre>'};
        else if (path.endsWith('/latest-submission')) json.data = url.searchParams.get('language') === 'python' ? submission : null;
        else if (path.endsWith('/practice-history')) json.data = {submissions: url.searchParams.get('language') === 'python' ? [submission] : [],
            proposals: records.has(3) ? [proposal] : [], helps: [...records.values()], events,
            active_proposal_id: proposal.state === 'accepted' ? 900 : null, next_before: null};
        else if (/\/submissions\/\d+\/help$/.test(path)) {
            if (method === 'GET') json.data = {records: path.includes('/700/') ? [...records.values()] : []};
            else {
                if (control.fail) return route.fulfill({status: 503, json: {success: false, error: {message: '网络暂时不可用，请重试'}}});
                const level = route.request().postDataJSON().level;
                const record = {id: 700 + level, level, source: 'panel', mode: 'learning', state: 'ready',
                    submission_id: 700, created_at: '2026-10-14T05:01:00Z',
                    result: {status: control.insufficient ? 'insufficient_evidence' : 'supported',
                        summary: control.insufficient ? '当前公开证据不足以确定根因。' : level === 1 ? '回想循环右端点的含义。' : '核对循环范围与需要求和的整数。',
                        explanation: level === 1 ? '先观察循环实际包含了哪些值。' : '公开输入为 3，实际得到 3，预期为 6。请核对最后一个整数是否参与求和。',
                        code: level >= 3 ? candidate : '', lines: level === 1 || control.insufficient ? [] : [3],
                        evidence_ids: level === 1 || control.insufficient ? [] : ['case-1']},
                    ...(level === 3 ? {proposal} : {})};
                records.set(level, record); json.data = record;
            }
        } else if (path.endsWith('/review')) json.data = [...records.values()].find(r => path.includes('/' + r.id + '/'));
        else if (path.endsWith('/actions')) {
            const action = route.request().postDataJSON().action;
            proposal.state = {accept: 'accepted', reject: 'rejected', undo: 'undone'}[action];
            proposal.revision++;
            events.push({id: events.length + 1, kind: action, proposal_id: 900, submission_id: 700,
                created_at: '2026-10-14T05:02:00Z', data: {}});
            json.data = {proposal, editor_code: action === 'accept' ? candidate : original};
        } else if (path === '/api/check-solution') {
            submission = {...submission, submission_id: 701, code: route.request().postDataJSON().code, status: 'Accepted',
                evidence: {executed: 3, total: 3, not_run: 0, cases: [1, 2, 3].map(index => ({id: 'case-' + index,
                    index, is_public: true, status: 'Accepted', passed: true, input: '3', expected_output: '6', actual_output: '6'}))}};
            proposal.latest_test = {submission_id: 701, code: submission.code, status: 'Accepted', total: 3};
            json = {success: true, ...submission, data: submission};
        } else if (!path.endsWith('/shown') && path !== '/api/update_learning_time') {
            return route.fulfill({status: 404, json: {success: false}});
        }
        await route.fulfill({json});
    });
    await page.goto(baseURL + '/practice.html?problem=DEMO-01');
    await expect(page.locator('#helpMode')).toBeEnabled();
    await expect(page.locator('#submissionVerdict')).toHaveText('输出与预期不同');
    await page.locator('#codeInput').fill(original);
    return control;
}

test('证据定位、采纳撤销、复测和刷新恢复', async ({page}) => {
    await page.setViewportSize({width: 1440, height: 1080});
    const control = await fixture(page);
    await page.getByRole('button', {name: '定位与解释', exact: true}).click();
    await expect(page.locator('[data-help-level="2"]')).toHaveAttribute('aria-pressed', 'true');
    await page.locator('.evidence-link').click();
    await expect(page.locator('.case-card.is-selected')).toHaveCount(1);
    await expect(page.locator('.snapshot-line.is-selected')).toHaveCount(1);
    await page.getByRole('button', {name: '局部修改', exact: true}).click();
    const card = page.locator('#diagnosisContent [data-proposal-card]');
    await card.locator(':scope > summary').click();
    await expect(card.locator('.diff-add')).toContainText('range(1, n + 1)');
    await page.locator('#submissionResults').screenshot({path: 'tmp/workspace-ui/evidence-desktop.png'});
    const area = await page.locator('#submissionResults').boundingBox();
    await page.screenshot({path: 'tmp/workspace-ui/evidence-preview.png',
        clip: {...area, height: Math.min(area.height, 670)}});
    await card.locator('[data-proposal-action="accept"]').click();
    await expect(page.locator('#codeInput')).toHaveValue(candidate);
    await expect(card).toHaveAttribute('data-proposal-state', 'accepted');
    await card.locator('[data-proposal-action="undo"]').click();
    await expect(page.locator('#codeInput')).toHaveValue(original);
    await card.locator('[data-proposal-action="accept"]').click();
    await page.locator('#codeInput').fill(candidate + '\n# 自行修改');
    await expect(card.locator('[data-proposal-action="undo"]')).toBeDisabled();
    await expect(card.locator('[data-proposal-status]')).toContainText('尚未复测');
    await page.locator('#codeInput').fill(candidate);
    await page.locator('#submissionResults').scrollIntoViewIfNeeded();
    await page.reload();
    await expect(page.locator('#codeInput')).toHaveValue(candidate);
    await expect(page.locator('#diagnosisContent > details[open]')).toHaveCount(0);
    await expect(page.locator('#evidenceStale')).toBeVisible();
    await page.locator('#practiceReview > summary').click();
    await expect(page.locator('#practiceTimeline')).toContainText('撤销');
    await page.locator('#submitBtn').click();
    await expect(page.locator('#submissionVerdict')).toHaveText('当前用例通过');
    await expect(page.locator('#submissionComparison')).toContainText('上次提交 #700');
    await expect(page.locator('#evidenceStale')).toBeHidden();
    await expect(page.locator('#helpWorkspace')).toBeHidden();
    expect(control.errors).toEqual([]);
});

test('窄屏、失败重试、过期保护与语言切换', async ({page}) => {
    await page.setViewportSize({width: 390, height: 844});
    const control = await fixture(page);
    control.fail = true;
    await page.locator('[data-help-level="1"]').click();
    await expect(page.locator('#diagnosisStatus')).toContainText('网络暂时不可用');
    await expect(page.locator('#codeInput')).toHaveValue(original);
    await expect(page.locator('#evidenceCases')).toContainText('6');
    control.fail = false;
    await page.locator('[data-help-level="1"]').click();
    await expect(page.locator('[data-help-id="701"]')).toHaveAttribute('open', '');
    await expect(page.locator('#helpWorkspace')).toHaveAttribute('data-phase', 'ready');
    await page.locator('#codeInput').fill(original + '\n# 新改动');
    await expect(page.locator('[data-help-level="2"]')).toBeDisabled();
    await expect(page.locator('#helpSelection')).toHaveText('结果对应上次提交');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    await page.locator('#submissionResults').scrollIntoViewIfNeeded();
    await page.locator('#submissionResults').screenshot({path: 'tmp/workspace-ui/evidence-mobile.png'});
    await page.locator('#languageSelector').selectOption('cpp');
    await expect(page.locator('#submissionResults')).toBeHidden();
    await expect(page.locator('.snapshot-line.is-selected')).toHaveCount(0);
    expect(control.errors).toEqual([]);
});

test('证据不足保留真实失败状态，不显示定位引用', async ({page}) => {
    const control = await fixture(page);
    control.insufficient = true;
    await page.locator('[data-help-level="2"]').click();
    await expect(page.locator('[data-help-status="insufficient_evidence"]')).toContainText('公开证据不足');
    await expect(page.locator('.evidence-link')).toHaveCount(0);
    await expect(page.locator('#submissionVerdict')).toHaveText('输出与预期不同');
    expect(control.errors).toEqual([]);
});
