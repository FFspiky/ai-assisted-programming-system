(() => {
    const byId = id => document.getElementById(id);
    const editor = byId('codeInput');
    const language = byId('languageSelector');
    const cases = byId('evidenceCases');
    const diagnosisContent = byId('diagnosisContent');
    const diagnose = byId('diagnoseBtn');
    let submission = null, user = null, userReady = false, problem = null;
    let controller = null, sequence = 0, restoreSequence = 0, edited = false;
    let activeLanguage = language.value;

    function node(tag, text, className = '') {
        const element = document.createElement(tag);
        if (text !== undefined) element.textContent = text;
        element.className = className;
        return element;
    }
    function draftKey(lang = activeLanguage) {
        return `codelab:draft:v2:${user?.id || 'guest'}:${getCurrentProblemId()}:${lang}`;
    }
    function saveDraft() {
        if (!userReady) return;
        try {
            localStorage.setItem(draftKey(), JSON.stringify({code: editor.value, input: byId('customInput').value}));
            byId('draftStatus').textContent = '草稿已保存';
        } catch (_) { byId('draftStatus').textContent = '浏览器无法保存草稿，请手动复制代码'; }
    }
    function restoreDraft() {
        try {
            const pending = JSON.parse(sessionStorage.getItem('codelab:login-draft') || 'null');
            if (user && pending && pending.problem === getCurrentProblemId() && pending.language === activeLanguage
                && (!pending.user_id || pending.user_id === user.id)) {
                localStorage.setItem(draftKey(), JSON.stringify({code:pending.code,input:pending.input}));
                sessionStorage.removeItem('codelab:login-draft');
            }
            const saved = JSON.parse(localStorage.getItem(draftKey()) || 'null');
            if (saved && typeof saved.code === 'string') {
                editor.value = saved.code;
                byId('customInput').value = saved.input || '';
                renderGhostLayer();
                byId('draftStatus').textContent = '已恢复本题草稿';
                return true;
            }
        } catch (_) { /* A broken draft must not prevent editing. */ }
        return false;
    }
    function markStale() {
        byId('evidenceStale').hidden = !submission || (editor.value === submission.code && language.value === submission.language);
    }
    function cancelPending() {
        sequence += 1;
        controller?.abort();
        controller = null;
        byId('cancelDiagnosisBtn').hidden = true;
    }
    function focusEvidence(ids, lines) {
        cases.querySelectorAll('.case-card').forEach(card => card.classList.toggle('is-selected', ids.includes(card.dataset.caseId)));
        byId('submissionCodePanel').open = true;
        byId('submissionCode').querySelectorAll('.snapshot-line').forEach(line => line.classList.toggle('is-selected', lines.includes(Number(line.dataset.line))));
        const target = byId('submissionCode').querySelector('.is-selected');
        target?.scrollIntoView({behavior: 'smooth', block: 'nearest'});
        if (editor.value === submission.code && lines.length) {
            const chunks = editor.value.split('\n');
            const first = Math.min(...lines) - 1;
            const start = chunks.slice(0, first).reduce((sum, text) => sum + text.length + 1, 0);
            editor.focus({preventScroll: true});
            editor.setSelectionRange(start, start + chunks[first].length);
        }
    }
    function showDiagnosis(result) {
        diagnosisContent.replaceChildren();
        if (!result) return;
        diagnosisContent.append(node('p', result.summary, 'diagnosis-summary'));
        if (result.status === 'insufficient_evidence') {
            diagnosisContent.prepend(node('p', '公开证据不足', 'hypothesis-tag'));
            return;
        }
        result.findings.forEach(finding => {
            const card = node('article', undefined, 'finding-card');
            card.append(node('span', '可能原因', 'hypothesis-tag'), node('h3', finding.title), node('p', finding.explanation));
            const action = node('button', `查看依据 · ${finding.lines.length ? '第 ' + finding.lines.join('、') + ' 行' : '执行用例'}`, 'evidence-button evidence-link');
            action.type = 'button';
            action.addEventListener('click', () => focusEvidence(finding.evidence_ids, finding.lines));
            card.append(action, node('p', '建议：' + finding.next_check, 'next-check'));
            diagnosisContent.append(card);
        });
    }
    function showSubmission(data) {
        cancelPending();
        submission = data?.submission_id ? data : null;
        byId('submissionResults').hidden = !submission;
        cases.replaceChildren();
        diagnosisContent.replaceChildren();
        byId('submissionCode').replaceChildren();
        byId('submissionCodePanel').hidden = !submission;
        if (!submission) {
            byId('evidenceSummary').textContent = '';
            diagnose.disabled = true;
            byId('diagnosisStatus').textContent = user ? '请先提交一段代码。' : '登录后可以保存提交并查看 AI 诊断。';
            markStale();
            return;
        }
        outputContent.replaceChildren();
        const evidence = submission.evidence;
        byId('evidenceSummary').textContent = evidence
            ? `提交 #${submission.submission_id} · ${submission.status} · 已执行 ${evidence.executed}/${evidence.total}，未执行 ${evidence.not_run}`
            : '这次历史提交没有证据快照，请重新提交。';
        (evidence?.cases || []).forEach(item => {
            const card = node('article', undefined, 'case-card ' + (item.passed ? 'case-pass' : 'case-fail'));
            card.dataset.caseId = item.id;
            card.append(node('h3', `用例 ${item.index} · ${item.status}`));
            if (item.is_public) {
                [['输入', item.input], ['预期输出', item.expected_output], ['实际输出', item.actual_output]].forEach(([label, value]) => {
                    const block = node('div', undefined, 'case-value');
                    block.append(node('span', label), node('pre', value || '（空）'));
                    card.append(block);
                });
                if (item.error) card.append(node('pre', item.error, 'case-error'));
                if (item.time != null) card.append(node('small', `执行服务总耗时 ${item.time} ms（含环境启动）`));
            } else card.append(node('p', '隐藏用例', 'panel-note'));
            cases.append(card);
        });
        submission.code.split('\n').forEach((text, index) => {
            const line = node('div', undefined, 'snapshot-line');
            line.dataset.line = String(index + 1);
            line.append(node('span', String(index + 1), 'line-number'), node('code', text || ' '));
            byId('submissionCode').append(line);
        });
        diagnose.disabled = !evidence || !['Wrong Answer', 'Runtime Error', 'Compile Error'].includes(submission.status);
        diagnose.textContent = submission.diagnosis ? '查看分析' : '分析错误';
        diagnose.hidden = diagnose.disabled;
        byId('diagnosisStatus').textContent = submission.diagnosis ? '已保存的分析'
            : submission.status === 'Accepted' ? '全部用例通过。' : '';
        showDiagnosis(submission.diagnosis);
        markStale();
    }
    async function restoreSubmission() {
        const ticket = ++restoreSequence;
        if (!user || !problem) return;
        try {
            const response = await fetch(`/api/problems/${encodeURIComponent(problem.id)}/latest-submission?language=${encodeURIComponent(activeLanguage)}`);
            const result = await response.json();
            if (ticket !== restoreSequence || !result.success) return;
            showSubmission(result.data);
        } catch (_) { /* Editing remains usable when history cannot load. */ }
    }
    function ready() {
        if (!userReady || !problem) return;
        if (!edited) restoreDraft();
        restoreSubmission();
    }
    window.addEventListener('practice:user', event => { user = event.detail; userReady = true; ready(); });
    window.addEventListener('practice:problem', event => {
        problem = event.detail;
        ready();
    });
    window.addEventListener('practice:submission', event => { restoreSequence += 1; showSubmission(event.detail); });
    window.addEventListener('auth:required', () => {
        try {
            sessionStorage.setItem('codelab:login-draft', JSON.stringify({user_id:user?.id,problem:getCurrentProblemId(),language:activeLanguage,code:editor.value,input:byId('customInput').value}));
        } catch (_) { /* Keep the editor usable if browser storage is unavailable. */ }
    });
    editor.addEventListener('input', () => { edited = true; saveDraft(); markStale(); });
    byId('customInput').addEventListener('input', saveDraft);
    language.addEventListener('change', () => {
        saveDraft(); activeLanguage = language.value;
        cancelInlineCompletion();
        cancelPending(); showSubmission(null);
        editor.value = ''; byId('customInput').value = '';
        restoreDraft(); markStale(); restoreSubmission();
    });
    diagnose.addEventListener('click', async () => {
        if (!submission) return;
        if (submission.diagnosis) { showDiagnosis(submission.diagnosis); return; }
        cancelPending();
        const ticket = sequence, id = submission.submission_id;
        const requestController = new AbortController();
        controller = requestController;
        const timer = setTimeout(() => requestController.abort(), 70000);
        diagnose.disabled = true;
        byId('cancelDiagnosisBtn').hidden = false;
        byId('diagnosisStatus').textContent = '正在分析…';
        try {
            const response = await UserSession.csrfFetch(`/api/submissions/${id}/diagnosis`, {
                method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}', signal: requestController.signal
            });
            const result = await response.json();
            if (ticket !== sequence || submission?.submission_id !== id) return;
            if (!response.ok || !result.success) throw new Error(UserSession.apiErrorMessage(result));
            showSubmission(result.data);
        } catch (error) {
            if (ticket !== sequence) return;
            if (UserSession.handleAuthError(error, byId('diagnosisStatus'))) return;
            byId('diagnosisStatus').textContent = error.name === 'AbortError' ? '等待超时，可重试。已有代码和证据已保留。' : error.message;
        } finally {
            clearTimeout(timer);
            if (ticket === sequence && submission?.submission_id === id) {
                diagnose.disabled = false;
                byId('cancelDiagnosisBtn').hidden = true;
            }
        }
    });
    byId('cancelDiagnosisBtn').addEventListener('click', () => {
        cancelPending(); diagnose.disabled = false;
        byId('diagnosisStatus').textContent = '已取消等待。后台请求可能仍在完成，稍后可重试读取。';
    });
})();
