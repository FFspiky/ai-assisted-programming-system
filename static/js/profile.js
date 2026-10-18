(() => {
    const byId = id => document.getElementById(id);
    let currentUser = null;
    const languageNames = {python: 'Python', cpp: 'C++', java: 'Java'};
    const statusNames = {'Accepted':'通过', 'Wrong Answer':'答案错误', 'Runtime Error':'运行错误', 'Compile Error':'编译错误', 'Time Limit Exceeded':'运行超时', 'Environment Error':'执行环境不可用', 'Output Limit Exceeded':'输出超限', 'Resource Limit Exceeded':'资源超限', 'Busy':'执行繁忙'};
    const tabs = [...document.querySelectorAll('[data-tab]')];

    function element(tag, text, className = '') {
        const el = document.createElement(tag);
        if (text !== undefined) el.textContent = text;
        el.className = className;
        return el;
    }
    function message(id, text, type = 'success') {
        const box = byId(id);
        box.hidden = false;
        box.textContent = text;
        box.dataset.type = type;
    }
    function openTab(id) {
        tabs.forEach(tab => {
            const selected = tab.dataset.tab === id;
            tab.setAttribute('aria-selected', String(selected));
            tab.tabIndex = selected ? 0 : -1;
            byId(tab.dataset.tab).hidden = !selected;
        });
    }
    tabs.forEach((tab, index) => {
        tab.addEventListener('click', () => openTab(tab.dataset.tab));
        tab.addEventListener('keydown', event => {
            let next;
            if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
            if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
            if (event.key === 'Home') next = 0;
            if (event.key === 'End') next = tabs.length - 1;
            if (next === undefined) return;
            event.preventDefault();
            openTab(tabs[next].dataset.tab);
            tabs[next].focus();
        });
    });
    byId('editProfileBtn').addEventListener('click', () => { openTab('settingsPanel'); byId('displayName').focus(); });

    function fillForm(user) {
        [['displayName','display_name'],['profileUsername','username'],['profileEmail','email'],['profileBioInput','bio'],['profileLocation','location']].forEach(([id,key]) => {byId(id).value = user[key] || '';});
        byId('emailPassword').value = '';
        byId('emailPasswordField').hidden = true;
        byId('emailPassword').required = false;
    }
    function renderUser(user, fill = true) {
        currentUser = user;
        byId('profileAvatar').src = user.avatar_url || UserSession.defaultAvatar;
        byId('profileName').textContent = user.display_name || user.username;
        byId('profileHandle').textContent = '@' + user.username;
        byId('profileBio').textContent = user.bio || '';
        const meta = byId('profileMeta'); meta.replaceChildren();
        const items = [['fa-map-marker-alt',user.location],['fa-envelope',user.email],['fa-star',`${user.points} 积分`]];
        if (user.created_at) items.push(['fa-calendar-alt',new Date(user.created_at).toLocaleDateString('zh-CN',{year:'numeric',month:'long'})+'加入']);
        items.filter(([,value])=>value).forEach(([icon,value])=>{
            const row = element('li');
            const symbol = element('i',undefined,'fas '+icon); symbol.setAttribute('aria-hidden','true');
            row.append(symbol,element('span',value)); meta.append(row);
        });
        document.querySelectorAll('.user-info').forEach(el => UserSession.renderUser(el,user));
        byId('resetAvatarBtn').disabled = !user.avatar_url;
        if (fill) fillForm(user);
    }
    function duration(seconds) {
        const minutes = Math.floor(seconds / 60);
        if (!minutes) return seconds ? '不足 1 分钟' : '0 分钟';
        return minutes < 60 ? `${minutes} 分钟` : `${Math.floor(minutes / 60)} 小时 ${minutes % 60} 分`;
    }
    function renderBreakdown(id, items, label, total, empty) {
        const host = byId(id); host.replaceChildren();
        if (!items.length) {host.append(element('p',empty,'empty-state')); return;}
        items.forEach(item => {
            const row = element('div',undefined,'breakdown-row');
            const heading = element('div',undefined,'breakdown-label');
            heading.append(element('span',label(item)),element('span',String(item.count)));
            const bar = element('div',undefined,'breakdown-bar');
            const fill = element('span'); fill.style.width = `${total ? item.count / total * 100 : 0}%`;
            bar.append(fill);row.append(heading,bar);host.append(row);
        });
    }
    function renderStats(stats) {
        const metrics = [
            ['练过题数',stats.attempted_problems,'按题目去重'], ['已通过',stats.solved_problems,'通过全部用例的题目'],
            ['累计提交',stats.total_submissions,'包含同题多次提交'], ['提交通过率',stats.acceptance_rate+'%','通过次数 / 提交次数'],
            ['练习时长',duration(stats.practice_seconds),'练习页累计在线时长'], ['活跃天数',stats.active_days,'近一年有提交的天数']
        ];
        byId('statsGrid').replaceChildren(...metrics.map(([label,value,detail])=>{
            const card = element('div',undefined,'profile-stat');
            card.append(element('span',label,'stat-label'),element('strong',String(value),'stat-number'),element('span',detail,'stat-detail'));
            return card;
        }));
        const grid = byId('activityGrid'); grid.replaceChildren();
        const months = byId('activityMonths'); months.replaceChildren();
        let previousMonth = null;
        stats.activity.forEach((day,index) => {
            const cell = element('div',undefined,'activity-cell');
            cell.dataset.level = day.count === 0 ? '0' : day.count < 3 ? '1' : day.count < 6 ? '2' : day.count < 10 ? '3' : '4';
            cell.title = `${day.date} · ${day.count} 次提交`;
            cell.setAttribute('role','listitem');cell.setAttribute('aria-label',cell.title);
            grid.append(cell);
            if (index % 7 === 0) {
                const month = Number(day.date.slice(5,7));
                const label = element('span',month !== previousMonth ? month+'月' : '');
                months.append(label); previousMonth = month;
            }
        });
        byId('activityCaption').textContent = `${stats.active_days} 天练习 · 按北京时间记录`;
        const activityScroll = document.querySelector('.activity-scroll');
        new ResizeObserver(() => {activityScroll.scrollLeft = activityScroll.scrollWidth;}).observe(activityScroll);
        renderBreakdown('languageStats',stats.languages,item=>languageNames[item.language] || item.language,stats.total_submissions,'还没有语言使用记录');
        renderBreakdown('difficultyStats',stats.difficulties,item=>item.difficulty,stats.solved_problems,'还没有通过的题目');
        const recent = byId('recentSubmissions'); recent.replaceChildren();
        if (!stats.recent_submissions.length) {recent.append(element('p','还没有提交记录。选择一道题开始练习吧。','empty-state'));return;}
        const table = element('table',undefined,'profile-table');
        const head = element('thead'), heading = element('tr');
        ['题目','语言','结果','提交时间'].forEach(text=>heading.append(element('th',text)));head.append(heading);
        const body = element('tbody');
        stats.recent_submissions.forEach(sub=>{
            const row = element('tr'), title = element('td');
            const link = element('a',sub.title);link.href = '/practice.html?problem='+encodeURIComponent(sub.problem_id);title.append(link);
            const status = element('td'); status.append(element('span',statusNames[sub.status] || sub.status,'submission-status '+(sub.status==='Accepted'?'accepted':'failed')));
            row.append(title,element('td',languageNames[sub.language] || sub.language),status,element('td',new Date(sub.timestamp).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false})));
            body.append(row);
        });
        table.append(head,body);recent.append(table);
    }
    async function api(url, options) {
        const response = await UserSession.csrfFetch(url,options);
        const result = await response.json().catch(()=>({}));
        if (!response.ok || !result.success) throw new Error(UserSession.apiErrorMessage(result,'操作失败，请稍后重试'));
        return result.data;
    }
    function showError(id,error) {
        byId(id).hidden = false;
        if (!UserSession.handleAuthError(error,byId(id))) message(id,error.message,'error');
    }
    byId('profileEmail').addEventListener('input',()=>{
        const changed = byId('profileEmail').value.trim() !== currentUser?.email;
        byId('emailPasswordField').hidden = !changed;
        byId('emailPassword').required = changed;
    });
    byId('profileForm').addEventListener('submit',async event=>{
        event.preventDefault();
        const button = event.submitter; button.disabled = true;
        const oldUsername = currentUser.username;
        try {
            const fields = Object.fromEntries(new FormData(event.target));
            if (fields.email.trim() !== currentUser.email) fields.current_password = byId('emailPassword').value;
            const data = await api('/api/profile',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(fields)});
            renderUser(data.user);
            message('profileFormMessage',oldUsername !== data.user.username ? '资料已保存，下次请使用新用户名登录。' : '资料已保存');
        } catch(error) {showError('profileFormMessage',error);} finally {button.disabled = false;}
    });
    byId('resetProfileForm').addEventListener('click',()=>{if(currentUser) fillForm(currentUser); byId('profileFormMessage').hidden = true;});
    const avatarButtons = [byId('changeAvatarBtn'),byId('uploadAvatarBtn'),byId('resetAvatarBtn'), ...document.querySelectorAll('[data-avatar-preset]')];
    const selectAvatar = () => byId('avatarFile').click();
    byId('changeAvatarBtn').addEventListener('click',selectAvatar);
    byId('uploadAvatarBtn').addEventListener('click',selectAvatar);
    async function updateAvatar(options) {
        avatarButtons.forEach(button=>{button.disabled=true;});
        try {
            const data = await api('/api/profile/avatar',options);
            renderUser(data.user,false);
            message('avatarMessage',options.method==='DELETE'?'已恢复默认头像':'头像已更新');
        } catch(error) {showError('avatarMessage',error);}
        finally {avatarButtons.forEach(button=>{button.disabled=false;});byId('resetAvatarBtn').disabled=!currentUser?.avatar_url;byId('avatarFile').value='';}
    }
    document.querySelectorAll('[data-avatar-preset]').forEach(button => {
        button.addEventListener('click', () => updateAvatar({method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({preset:button.dataset.avatarPreset})}));
    });
    byId('avatarFile').addEventListener('change',()=>{
        const file = byId('avatarFile').files[0]; if(!file) return;
        if (file.size > 2*1024*1024) {message('avatarMessage','头像不能超过 2 MB','error');byId('avatarFile').value='';return;}
        const data = new FormData();data.append('avatar',file);
        updateAvatar({method:'POST',body:data});
    });
    byId('resetAvatarBtn').addEventListener('click',()=>updateAvatar({method:'DELETE'}));
    byId('passwordForm').addEventListener('submit',async event=>{
        event.preventDefault();
        if(byId('newPassword').value!==byId('confirmPassword').value) {message('passwordMessage','两次输入的新密码不一致','error');return;}
        const button=event.submitter;button.disabled=true;
        try {
            await api('/api/profile/password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({current_password:byId('currentPassword').value,new_password:byId('newPassword').value})});
            event.target.reset();
            location.href='/login.html?password=updated&next=%2Fprofile.html';
        } catch(error) {showError('passwordMessage',error);button.disabled=false;}
    });
    async function load() {
        byId('profileAvatar').src=UserSession.defaultAvatar;
        await UserSession.init();
        try {
            const data=await api('/api/profile');renderUser(data.user);renderStats(data.stats);byId('profileStatus').hidden=true;
        } catch(error) {showError('profileStatus',error);}
        finally {byId('profilePage').setAttribute('aria-busy','false');}
    }
    load();
})();
