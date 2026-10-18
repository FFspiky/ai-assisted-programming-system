(() => {
    const byId = id => document.getElementById(id);
    const editor = byId('codeInput'), language = byId('languageSelector');
    const section = byId('practiceReview'), timeline = byId('practiceTimeline'), status = byId('reviewStatus');
    let user = null, ready = false, busy = false, sequence = 0, latest = null, activeId = null, nextBefore = null;
    const proposals = new Map(), rows = new Map(), attempts = new Map();
    const states = {pending:'尚未采纳',accepted:'已采纳，待复测',rejected:'已拒绝',undone:'已撤销'};
    const actionNames = {accept:'采纳',reject:'拒绝',undo:'撤销',co_create:'共创候选已准备'};
    function el(tag, text = '', className = '') {
        const node = document.createElement(tag); node.textContent = text; node.className = className; return node;
    }
    function button(text, handler) {
        const node = el('button', text, 'evidence-button'); node.type = 'button'; node.addEventListener('click', handler); return node;
    }
    function diff(lines) {
        const pre = el('pre', '', 'review-diff');
        lines.forEach(line => pre.append(el('span', line + '\n', line.startsWith('+') ? 'diff-add' : line.startsWith('-') ? 'diff-remove' : '')));
        if (!lines.length) pre.textContent = '没有逐行差异。';
        return pre;
    }
    function time(value) { return new Date(value).toLocaleString('zh-CN', {hour12:false}); }
    function panel(text, key) {
        const details = el('details', '', 'review-entry'); details.dataset.reviewKey = key;
        details.append(el('summary', text)); return details;
    }
    function updateControls() {
        document.querySelectorAll('[data-proposal-card]').forEach(card => {
            const p = proposals.get(Number(card.dataset.proposalCard)); if (!p) return;
            const note = card.querySelector('[data-proposal-status]');
            card.dataset.proposalState = p.state;
            note.textContent = states[p.state] || p.state;
            if (p.state === 'accepted') {
                const tested = p.latest_test;
                if (tested && editor.value === tested.code) {
                    note.textContent = tested.status === 'Accepted' ? `这份代码通过当前 ${tested.total ?? '?'} 个用例。` : `这份代码上次复测：${tested.status}。`;
                    if (tested.code !== p.candidate_code) note.textContent += ' 通过与否以修改后的实际提交为准。';
                } else if (editor.value !== p.candidate_code) note.textContent = '已采纳；当前代码与建议不同，这份修改尚未复测。';
            }
            else if (p.state !== 'accepted' && editor.value !== p.base_code) note.textContent += ' · 编辑器已变化，采纳前请核对原代码。';
            card.dataset.proposalStale = String(p.state === 'accepted' ? editor.value !== p.candidate_code : editor.value !== p.base_code);
            card.querySelectorAll('[data-proposal-action]').forEach(node => {
                const action = node.dataset.proposalAction;
                node.hidden = action === 'undo' || action === 'retest' ? p.state !== 'accepted' : action === 'reject' ? !['pending','undone'].includes(p.state) : p.state === 'accepted';
                node.disabled = busy || (action === 'accept' && editor.value !== p.base_code)
                    || (action === 'undo' && editor.value !== p.candidate_code);
                node.title = node.disabled && !busy ? '代码已修改，不能直接覆盖；请查看差异并手动调整。' : '';
            });
        });
    }
    function attachProposal(p, target) {
        const stored = proposals.get(p.id);
        if (!stored || stored.revision <= p.revision) proposals.set(p.id, p);
        const details = panel('查看修改差异', 'proposal-'+p.id);
        details.dataset.proposalCard = String(p.id);
        details.append(el('p', '先核对修改，再决定是否采纳。采纳后需重新提交，才能验证结果。', 'proposal-introduction'));
        details.append(diff(p.diff));
        const base = panel('建议依据的原代码', 'base-'+p.id);
        base.append(el('pre', p.base_code, 'help-code')); details.append(base);
        const candidate = panel('候选代码', 'candidate-'+p.id);
        candidate.append(el('pre', p.candidate_code, 'help-code')); details.append(candidate);
        const note = el('p', '', 'panel-note'); note.dataset.proposalStatus = ''; details.append(note);
        const controls = el('div', '', 'diagnosis-actions');
        for (const [kind, label] of [['accept','采纳修改'],['reject','拒绝'],['undo','撤销采纳'],['retest','重新提交验证']]) {
            const action = button(label, () => kind === 'retest' ? retest(p.id) : act(p.id, kind, details));
            action.dataset.proposalAction = kind; controls.append(action);
        }
        details.append(controls);
        const message = el('p', '', 'review-message'); message.setAttribute('role','status'); details.append(message);
        target.append(details); queueMicrotask(updateControls);
    }
    function attach(record, target) {
        if (record.proposal) attachProposal(record.proposal, target);
        else if (record.source === 'panel' && record.level === 3 && record.result?.code) {
            target.append(el('p','这条旧提示没有精确替换范围。需要应用修改时，请重新请求局部修改。','panel-note'));
        }
    }
    async function act(id, kind, card) {
        if (busy) return;
        const p = proposals.get(id), code = editor.value, lang = language.value, problem = getCurrentProblemId();
        const message = card.querySelector('.review-message');
        const body = {action:kind,revision:p.revision,code,language:lang};
        const signature = JSON.stringify(body), key = `${id}:${kind}`;
        if (attempts.get(key)?.signature !== signature) attempts.set(key,{signature,id:crypto.randomUUID()});
        body.operation_id = attempts.get(key).id;
        busy = true; updateControls(); cancelInlineCompletion();
        const readonly = editor.readOnly; editor.readOnly = true;
        const disabled = [language, byId('submitBtn'), byId('runBtn'), byId('optimizeBtn')].map(node => [node,node.disabled]);
        disabled.forEach(([node])=>{node.disabled=true;});
        message.textContent = `正在保存${actionNames[kind]}…`;
        const controller = new AbortController(), timeout = setTimeout(()=>controller.abort(),15000);
        try {
            const response = await UserSession.csrfFetch(`/api/proposals/${id}/actions`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:controller.signal});
            const result = await response.json();
            if (!response.ok || !result.success) throw new Error(UserSession.apiErrorMessage(result));
            attempts.delete(key);
            proposals.set(id,result.data.proposal);
            if (kind !== 'reject') {
                if (editor.value !== code || language.value !== lang || getCurrentProblemId() !== problem) {
                    throw new Error('操作已记录，但编辑器期间发生变化，未覆盖代码。请刷新过程记录并核对。');
                }
                editor.value = result.data.editor_code;
                editor.dispatchEvent(new Event('input')); renderGhostLayer();
            }
            if (kind === 'accept') activeId = id;
            else if (activeId === id) activeId = null;
            message.textContent = kind === 'accept' ? '已采纳，尚未验证。' : `已${actionNames[kind]}。`;
            await load();
        } catch (error) {
            message.textContent = error.name === 'AbortError' ? '保存状态尚未确认，代码未改变。可重试读取或刷新记录。' : error.message || '操作未确认保存，代码未改变，请重试或刷新记录。';
            status.textContent = message.textContent;
        } finally {
            clearTimeout(timeout);
            editor.readOnly = readonly; disabled.forEach(([node,value])=>{node.disabled=value;});
            busy = false; updateControls();
        }
    }
    async function retest(id) {
        if (busy) return;
        activeId = id;
        await submitCode();
    }
    function renderHistory() {
        const opened = new Set([...timeline.querySelectorAll('details[open]')].map(node=>node.dataset.reviewKey));
        timeline.replaceChildren();
        [...rows.values()].sort((a,b)=>a.time.localeCompare(b.time)||a.key.localeCompare(b.key)).forEach(row=>{
            let item;
            if (row.type === 'submission') {
                const sub = row.value, evidence = sub.evidence;
                const label = sub.status === 'Accepted' ? `通过当前 ${evidence?.total ?? '?'} 个用例` : sub.status;
                item = panel(`${time(row.time)} · 提交 #${sub.submission_id} · ${label}`,row.key);
                item.append(el('p','实际提交的代码','panel-note'),el('pre',sub.code,'help-code'));
                (evidence?.cases || []).forEach(test=>{
                    const block = el('div','','review-case'); block.append(el('p',`用例 ${test.index} · ${test.status}${test.is_public?'':'（隐藏）'}`));
                    if (test.is_public) block.append(el('pre',`输入：${test.input || '（空）'}\n预期：${test.expected_output || '（空）'}\n实际：${test.actual_output || '（空）'}${test.error?'\n'+test.error:''}`,'help-code'));
                    item.append(block);
                });
            } else if (row.type === 'help') {
                const help = row.value;
                item = panel(`${time(row.time)} · 请求${LearningHelpUI.labels[help.level]} · ${help.state==='ready'?(help.shown_at?'已查看':'已生成'):help.state==='pending'?'生成未完成':'未生成成功'}`,row.key);
                item.append(el('p',`对应提交 #${help.submission_id} · ${help.mode==='free'?'自由辅助':'学习模式'}`,'panel-note'));
                if (help.state === 'ready') {
                    let loaded=false;
                    item.addEventListener('toggle',async()=>{
                        if (!item.open || loaded) return;
                        loaded=true;
                        const contents=el('div'); item.append(contents);
                        try {
                            const response=await fetch(`/api/help/${help.id}/review`); const result=await response.json();
                            if(!response.ok || !result.success) throw new Error(UserSession.apiErrorMessage(result));
                            LearningHelpUI.render(result.data,contents); LearningHelpUI.acknowledge(help.id);
                        } catch(error) { contents.textContent='读取失败：'+error.message; loaded=false; contents.append(button('重试',()=>{contents.remove();item.open=false;item.open=true;})); }
                    });
                }
            } else {
                const event=row.value;
                let label=actionNames[event.kind];
                if(event.kind==='retest') label=event.proposal_id ? (event.data.edited_after_accept?'采纳后代码又有修改，再次判题':'按建议代码再次判题') : event.data.parent_submission_id?'修改后再次判题':'开始本次练习';
                item=panel(`${time(row.time)} · ${label}`,row.key);
                item.append(el('p',event.submission_id ? `关联提交 #${event.submission_id}` : '从题目共创带回，尚未创建正式提交','panel-note'));
                if(event.kind==='retest') {
                    if(event.data.parent_submission_id) item.append(el('p',`承接提交 #${event.data.parent_submission_id}`,'panel-note'));
                    if(event.data.diff?.length) item.append(el('p','本次提交相对建议或前次提交的差异','panel-note'),diff(event.data.diff));
                } else {
                    const p=proposals.get(event.proposal_id); if(p) attachProposal(p,item);
                }
            }
            item.dataset.entryType = row.type;
            if (row.type === 'event') item.dataset.eventKind = row.value.kind;
            item.open=opened.has(row.key); timeline.append(item);
        });
        byId('reviewOlder').hidden = !nextBefore;
        updateControls();
    }
    async function load(older = false) {
        if (!user || !getCurrentProblemId()) return;
        const ticket=++sequence, problem=getCurrentProblemId(), lang=language.value;
        if(!older) ready=false;
        try {
            const response=await fetch(`/api/problems/${encodeURIComponent(problem)}/practice-history?language=${encodeURIComponent(lang)}${older&&nextBefore?'&before='+nextBefore:''}`,{cache:'no-store'});
            const result=await response.json();
            if(ticket!==sequence || problem!==getCurrentProblemId() || lang!==language.value) return;
            if(!response.ok || !result.success) throw new Error(UserSession.apiErrorMessage(result));
            const data=result.data;
            if(!older) {rows.clear(); latest=data.submissions[0]?.submission_id || null; activeId=data.active_proposal_id;}
            data.proposals.forEach(p=>proposals.set(p.id,p)); nextBefore=data.next_before;
            data.submissions.forEach(value=>rows.set('s'+value.submission_id,{key:'s'+value.submission_id,type:'submission',value,time:value.created_at.endsWith('Z')?value.created_at:value.created_at+'Z'}));
            data.helps.forEach(value=>rows.set('h'+value.id,{key:'h'+value.id,type:'help',value,time:value.created_at}));
            data.events.forEach(value=>rows.set('e'+value.id,{key:'e'+value.id,type:'event',value,time:value.created_at}));
            ready=true; section.hidden=!rows.size; status.textContent=''; renderHistory();
            const requested = Number(new URLSearchParams(location.search).get('co_create_proposal'));
            const candidate = proposals.get(requested);
            if (candidate?.source === 'co_create') {
                if (editor.dataset.untouchedTemplate === 'true') {
                    editor.value = candidate.base_code;
                    editor.dispatchEvent(new Event('input'));
                    renderGhostLayer();
                }
                const card = timeline.querySelector(`[data-proposal-card="${requested}"]`);
                if (card) {
                    for (let ancestor = card; ancestor; ancestor = ancestor.parentElement) {
                        if (ancestor.tagName === 'DETAILS') ancestor.open = true;
                        if (ancestor === section) break;
                    }
                    const messages = {
                        pending: '共创候选已带回。请核对差异后选择采纳；候选尚未替换当前代码。',
                        accepted: '这份共创候选已采纳。请查看实际复测记录确认结果，也可核对差异或撤销采纳。',
                        rejected: '这份共创候选已拒绝。可以重新核对差异后决定是否采纳，当前草稿仍保留。',
                        undone: '这份共创候选已撤销采纳。可以查看差异并重新决定，当前草稿仍保留。'
                    };
                    status.textContent = messages[candidate.state] || '共创候选记录已打开，请核对差异与最新状态。';
                }
            }
        } catch(error) {
            if(ticket!==sequence) return;
            section.hidden=false; status.textContent='过程记录读取失败：'+error.message+'。请重试，代码仍保留。';
        }
    }
    function context() {
        if(user && (!ready || busy)) throw new Error('练习记录尚未就绪，请稍后重试。');
        const p=proposals.get(activeId);
        return {parent_submission_id:latest, ...(p?.state==='accepted'?{proposal_id:p.id,proposal_revision:p.revision}:{})};
    }
    window.addEventListener('practice:user',event=>{user=event.detail; load();});
    window.addEventListener('practice:submission',event=>{latest=event.detail?.submission_id || null; load();});
    language.addEventListener('change',()=>{sequence++;proposals.clear();rows.clear();activeId=null;latest=null;section.hidden=true;load();});
    window.addEventListener('auth:required',()=>{sequence++;user=null;proposals.clear();rows.clear();activeId=null;latest=null;section.hidden=true;});
    editor.addEventListener('input',updateControls);
    byId('reviewReload').addEventListener('click',()=>load());
    byId('reviewOlder').addEventListener('click',()=>load(true));
    window.PracticeReview={attach,refresh:load,submissionContext:context};
})();
