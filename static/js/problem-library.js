(() => {
    const $ = id => document.getElementById(id);
    let user = null, page = 1, pages = 1, sequence = 0, controller = null, matchedIds = [];
    function readURL() {
        const p = new URLSearchParams(location.search);
        for (const [name,id] of [['q','searchInput'],['difficulty','difficultyFilter'],['state','stateFilter']]) $(id).value=p.get(name)||'';
        page=Math.max(1,Number(p.get('page'))||1); return p;
    }
    let initialParams=readURL();
    function params(includePage=true) {
        const p=new URLSearchParams();
        for(const [name,id] of [['q','searchInput'],['category','categoryFilter'],['difficulty','difficultyFilter'],['state','stateFilter']]) {
            const value=$(id).value.trim();if(value)p.set(name,value);
        }
        if(includePage)p.set('page',String(page));return p;
    }
    function node(tag,text,className='') {const el=document.createElement(tag);el.textContent=text;el.className=className;return el;}
    function render(p) {
        const card=node('article','','problem-card'),top=node('div','','problem-card-top');
        const difficulty=node('span',p.difficulty,'problem-difficulty');difficulty.dataset.difficulty=p.difficulty;
        top.append(node('span',p.id,'problem-card-id'),difficulty);
        card.append(top,node('h2',p.title,'card-title'),node('span',p.category_name,'problem-category'),node('p',p.description,'card-description'));
        const tags=node('div','','problem-tags');(p.tags||[]).forEach(t=>tags.append(node('span',t)));card.append(tags);
        const actions=node('div','','card-actions');
        const state=node('span',user?({accepted:'已通过',attempted:'尝试未通过',unattempted:'未尝试'}[p.practice_state]||'未尝试'):'登录后记录进度','practice-state');state.dataset.state=p.practice_state;
        const link=node('a','开始练习 →','btn-select'),query=params();query.set('problem',p.id);link.href='/practice.html?'+query;
        link.addEventListener('click',()=>{
            try{sessionStorage.setItem('codelab:problem-list',JSON.stringify({ids:matchedIds,owner:user?.id||null,filter:params(false).toString()}));}catch(_){/* Filters remain in the URL. */}
        });
        actions.append(state,link);card.append(actions);return card;
    }
    async function load() {
        controller?.abort();controller=new AbortController();const ticket=++sequence;
        $('problemGrid').setAttribute('aria-busy','true');$('libraryError').hidden=true;$('resultCount').textContent='正在加载题目…';
        $('previousPage').disabled=$('nextPage').disabled=true;
        try {
            const response=await fetch('/api/problems?'+params(),{signal:controller.signal,cache:'no-store'}),result=await response.json();
            if(ticket!==sequence)return;
            if(!response.ok||!result.success)throw new Error(UserSession.apiErrorMessage(result));
            const data=result.data;page=data.page;pages=data.pages;matchedIds=data.ids;
            const category=initialParams?.get('category')||$('categoryFilter').value;
            $('categoryFilter').replaceChildren(new Option('全部分类',''));
            data.categories.filter(c=>c.count||c.id===category).forEach(c=>$('categoryFilter').append(new Option(`${c.name} (${c.count})`,c.id)));
            $('categoryFilter').value=category;
            if(initialParams){initialParams=null;if(category)return load();}
            $('problemGrid').replaceChildren(...data.problems.map(render));$('libraryEmpty').hidden=data.total>0;
            $('libraryTotal').textContent=`题库 ${data.categories.reduce((sum,c)=>sum+c.count,0)} 题`;
            $('resultCount').textContent=`找到 ${data.total} 道题目`;$('pagePosition').textContent=`第 ${page} / ${pages} 页`;
            $('previousPage').disabled=page<=1;$('nextPage').disabled=page>=pages;
            history.replaceState(null,'','/problem_selector.html?'+params());
        } catch(error) {
            if(ticket!==sequence||error.name==='AbortError')return;
            $('problemGrid').replaceChildren();$('libraryEmpty').hidden=true;$('libraryError').hidden=false;
            $('libraryError').querySelector('span').textContent='题目加载失败：'+error.message;$('resultCount').textContent='暂时无法读取题库';
        } finally {if(ticket===sequence)$('problemGrid').setAttribute('aria-busy','false');}
    }
    function reset(){['searchInput','categoryFilter','difficultyFilter','stateFilter'].forEach(id=>$(id).value='');page=1;load();}
    $('librarySearch').addEventListener('submit',e=>{e.preventDefault();page=1;load();});
    ['categoryFilter','difficultyFilter','stateFilter'].forEach(id=>$(id).addEventListener('change',()=>{page=1;load();}));
    ['clearFilters','emptyClear'].forEach(id=>$(id).addEventListener('click',reset));$('retryLibrary').addEventListener('click',load);
    $('previousPage').addEventListener('click',()=>{page--;load();});$('nextPage').addEventListener('click',()=>{page++;load();});
    window.addEventListener('popstate',()=>{initialParams=readURL();load();});
    UserSession.init().then(value=>{user=value;$('stateFilter').disabled=!user;$('stateHint').hidden=!!user;if(!user)$('stateFilter').value='';load();});
})();
