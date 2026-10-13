import {expect, test} from '@playwright/test';

const baseURL = process.env.SMOKE_BASE_URL || 'http://127.0.0.1:5005';
const code = 'n=int(input())\ntotal=0\nfor i in range(1,n):\n total+=i\nprint(total)';
const submission = {submission_id:700, code, language:'python', status:'Wrong Answer', diagnosis:null,
    evidence:{executed:1,total:3,not_run:2,cases:[{id:'case-1',index:1,is_public:true,status:'Wrong Answer',input:'3',expected_output:'6',actual_output:'3'}]}};
const record = level => ({id:700+level,level,mode:'learning',result:{status:'supported',summary:'检查循环范围',explanation:'自行核对取值范围',code:'',lines:level===1?[]:[3],evidence_ids:level===1?[]:['case-1']}});

test('改变帮助层级、编辑和切换语言时不沿用过期定位或建议', async ({page}) => {
    await page.route('**/api/current_user', route => route.fulfill({json:{success:true,user:{id:99997,username:'提示检查',points:0}}}));
    await page.route('**/api/csrf-token', route => route.fulfill({json:{csrf_token:'test-token'}}));
    await page.route('**/api/help-settings', route => route.fulfill({json:{success:true,data:{mode:'learning',revision:0}}}));
    await page.route('**/latest-submission?*', route => route.fulfill({json:{success:true,data:route.request().url().includes('python')?submission:null}}));
    await page.route('**/api/submissions/700/help', route => route.fulfill({json:{success:true,data:route.request().method()==='GET'?{records:[]}:record(route.request().postDataJSON().level)}}));
    await page.route('**/api/help/*/shown', route => route.fulfill({json:{success:true}}));
    await page.route('**/api/optimize-code', route => route.fulfill({json:{success:true,learning_help:record(1)}}));
    await page.goto(baseURL+'/practice.html?problem=DEMO-01');
    await expect(page.locator('#helpMode')).toBeEnabled();
    await page.locator('#codeInput').fill(code);
    await page.locator('[data-help-level="2"]').click();
    await page.locator('.evidence-link').click();
    await expect(page.locator('.snapshot-line.is-selected')).toHaveCount(1);
    await page.locator('[data-help-level="1"]').click();
    await expect(page.locator('[data-help-id="701"]')).toHaveAttribute('open','');
    await expect(page.locator('.snapshot-line.is-selected')).toHaveCount(0);
    await expect(page.locator('#submissionCodePanel')).not.toHaveAttribute('open');
    await page.locator('#optimizeBtn').click();
    await expect(page.locator('#aiSuggestion .help-result')).toBeVisible();
    await page.locator('#codeInput').fill(code+'\n# changed');
    await expect(page.locator('#optimizationStale')).toBeVisible();
    await page.locator('#languageSelector').selectOption('cpp');
    await expect(page.locator('#optimizationResult')).toBeHidden();
    await page.locator('#codeInput').fill('int main() {}');
    let release;
    await page.route('**/api/optimize-code', async route => {
        await new Promise(resolve => { release=resolve; });
        await route.fulfill({json:{success:true,learning_help:record(1)}}).catch(()=>{});
    });
    await page.locator('#optimizeBtn').click();
    await expect.poll(()=>!!release).toBeTruthy();
    await page.locator('#languageSelector').selectOption('python');
    release();
    await expect(page.locator('#optimizeBtn')).toBeEnabled();
    await expect(page.locator('#optimizationResult')).toBeHidden();
});
