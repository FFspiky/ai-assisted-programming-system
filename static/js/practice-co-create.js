(() => {
    'use strict';
    const button = document.getElementById('coCreateBtn');
    const editor = document.getElementById('codeInput');
    const language = document.getElementById('languageSelector');
    let user = null, latest = null, busy = false;
    const status = document.createElement('p');
    status.className = 'panel-note'; status.setAttribute('role', 'status'); button.closest('.editor-header')?.after(status);
    window.addEventListener('practice:user', event => { user = event.detail; });
    window.addEventListener('practice:submission', event => {
        latest = event.detail;
        button.textContent = latest?.status === 'Accepted' ? '共创另一种解法' : '用当前代码找反例';
    });
    language.addEventListener('change', () => { latest = null; button.textContent = '用这题共创'; });
    button.addEventListener('click', async () => {
        if (busy) return;
        const problem = getCurrentProblemId();
        if (!problem) { status.textContent = '请先选择一道题目。'; return; }
        if (!user) {
            status.textContent = '登录后可保存题目共创，当前草稿已保留。';
            location.href = '/login.html?next=' + encodeURIComponent(location.pathname + location.search);
            return;
        }
        let submissionId = latest?.submission_id;
        try { submissionId = window.PracticeReview?.submissionContext().parent_submission_id || submissionId; }
        catch (_) { /* A draft can enter co-creation before its first submission. */ }
        const snapshot = {mode: latest && latest.status !== 'Accepted' ? 'review' : 'examples', reuse:true,
            problem_id: problem, language: language.value, code: editor.value,
            input_text: document.getElementById('customInput').value,
            ...(submissionId ? {submission_id: submissionId} : {})};
        const returnURL = new URL(location.href);
        returnURL.searchParams.delete('co_create_proposal');
        returnURL.searchParams.set('language', snapshot.language);
        busy = true; button.disabled = true;
        const readonly = editor.readOnly, disabled = language.disabled;
        editor.readOnly = true; language.disabled = true;
        status.textContent = '正在带入题目、语言和这份代码…';
        try {
            const response = await UserSession.csrfFetch('/api/co-create/sessions', {method:'POST',
                headers:{'Content-Type':'application/json'},body:JSON.stringify(snapshot)});
            const result = await response.json();
            if (!response.ok || !result.success) throw new Error(UserSession.apiErrorMessage(result));
            location.href = '/co-create.html?' + new URLSearchParams({session:result.data.session.id,mode:snapshot.mode,
                problem,language:snapshot.language,return_to:returnURL.pathname+returnURL.search});
        } catch (error) { status.textContent = '共创尚未打开：' + error.message + '。原草稿仍保留，可重新尝试。'; }
        finally { busy = false; button.disabled = false; editor.readOnly = readonly; language.disabled = disabled; }
    });
})();
