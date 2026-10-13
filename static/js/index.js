// Homepage demonstrations use fixed examples; real exercises remain in practice.js.
(() => {
  'use strict';
  const root = document.getElementById('cl-ocean');
  if (!root) return;
  window.UserSession?.init();
  const q = (selector, parent = root) => parent.querySelector(selector);
  const qa = (selector, parent = root) => [...parent.querySelectorAll(selector)];
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const state = {motion: !reduced.matches, step: 0, help: 1, manualDemo: false};
  for (const [id, mount] of [['oc-practice-template', 'oc-home-practice'], ['oc-chat-template', 'oc-home-chat']]) {
    q('#' + mount).append(document.getElementById(id).content.cloneNode(true));
  }
  const demo = q('#oc-home-practice');
  q('[data-problem-progress]', demo).textContent = '示例题目';
  q('[data-problem-content]', demo).textContent = '给定一个整数，判断它是否为 3 的幂。示例：27 → true；45 → false。';
  qa('textarea', demo).forEach(el => el.readOnly = true);
  qa('select', demo).forEach(el => el.disabled = true);
  qa('.og-chat-help-controls select').forEach(el => el.disabled = true);
  for (const title of ['3的幂', '4的幂']) {
    const card = document.createElement('article'); card.className = 'og-problem-card';
    const titleNode = document.createElement('div'); titleNode.className = 'og-card-title'; titleNode.textContent = title;
    const difficulty = document.createElement('div'); difficulty.className = 'og-card-description'; difficulty.textContent = '简单';
    const actions = document.createElement('div'); actions.className = 'og-card-actions';
    const link = document.createElement('a'); link.className = 'og-select'; link.href = '/problem_selector.html'; link.textContent = '选择';
    actions.append(link); card.append(titleNode, difficulty, actions); q('#oc-mini-library').append(card);
  }
  const codeWrong='n = int(input())\n\ndef is_power_of_three(n):\n    return n > 0 and n % 3 == 0\n\nprint(str(is_power_of_three(n)).lower())';
  const codeRight='n = int(input())\n\ndef is_power_of_three(n):\n    while n > 1 and n % 3 == 0:\n        n //= 3\n    return n == 1\n\nprint(str(is_power_of_three(n)).lower())';
  const helpNames=['概念线索','定位与解释','局部修改','完整参考'];
  const helpExplanations=['先回想“幂”的含义，自己决定下一步怎么做。','把反馈和代码联系起来，理解判断条件为什么不够。','看到一个关键修改，再自己完成剩余部分。','需要时查看完整示例，再回到自己的思路验证。'];
  const helpTexts=[
    ['试着从定义出发。','3 的幂由若干个 3 相乘得到。一个数可以被 3 整除，是否就说明它的所有因子都满足这个条件？','可以先比较 27 和 45，找找它们的区别。'],
    ['整除，只验证了一步。','n % 3 == 0 只能说明当前的 n 含有因子 3。45 满足这个条件，但 45 = 3 × 3 × 5，还含有因子 5。','你需要继续检查除以 3 之后剩下的数。'],
    ['让检查继续下去。','反复除以 3，直到不能继续整除。最后检查剩下的是不是 1。','while n > 1 and n % 3 == 0:\n    n //= 3\nreturn n == 1'],
    ['完整参考 · 再自己验证一次。','这个写法也处理了 0、负数和 1。可以分别试试 27、45 与 1，验证边界。',codeRight]
  ];
  function textNode(tag,text,cls){const e=document.createElement(tag);e.textContent=text;if(cls)e.className=cls;return e;}
  function renderDemo(){const step=state.step;qa('[data-demo-step]').forEach(b=>b.setAttribute('aria-pressed',Number(b.dataset.demoStep)===step));q('[data-code]',demo).value=step===3?codeRight:codeWrong;const out=q('[data-output]',demo);out.replaceChildren();if(step===0)out.append(textNode('span','代码输出将显示在此处...'));if(step===1){out.append(textNode('span','true','oc-fail'),textNode('p','示例运行：输入 45，输出 true。对照题目预期 false，判断条件还需要检查。','oc-caption'));}if(step===2){out.append(textNode('span','true','oc-fail'),textNode('p','概念线索：一个数能被 3 整除，就一定是 3 的幂吗？试着比较 27 和 45。','og-diagnosis-content'));}if(step===3){out.append(textNode('span','false','oc-pass'),textNode('p','修改后示例：反复除以 3，最后检查是否剩下 1。输入 45，得到 false。','oc-caption'));}out.classList.remove('oc-animate-change');requestAnimationFrame(()=>out.classList.add('oc-animate-change'));const captions=['从题目开始，在熟悉的编辑器里写下思路。','运行后，对照输入和输出，发现值得检查的地方。','先获得一点概念线索，把推理过程留给自己。','修改判断，再次验证。让这一次错误成为下一次理解。'];q('#oc-demo-caption').textContent=captions[step];}
  function renderHelp(level){state.help=level;q('#oc-help-number').textContent='0'+level;q('#oc-help-name').textContent=helpNames[level-1];q('#oc-help-explain').textContent=helpExplanations[level-1];qa('[data-help-level]').forEach(b=>b.setAttribute('aria-pressed',Number(b.dataset.helpLevel)===level));helpContent(q('#oc-help-content'),level);}
  function helpContent(target,level){const parts=[...helpTexts[level-1]];target.replaceChildren(textNode('h3',parts[0]),textNode('p',parts[1]),textNode(level>=3?'pre':'p',parts[2]));target.classList.remove('oc-animate-change');requestAnimationFrame(()=>target.classList.add('oc-animate-change'));}
  function selectCase(value){const fail=value==='45';qa('[data-case]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.case===value));const cards=qa('.oc-evidence-original .og-case-card');cards[0].classList.toggle('is-highlight',!fail);cards[1].classList.toggle('is-highlight',fail);q('#oc-evidence-note').textContent=fail?'45 可以被 3 整除，但它不是 3 的幂。':'27 = 3 × 3 × 3，这个用例通过了。';}

  function renderMotion() {
    root.dataset.motion = state.motion ? 'on' : 'off';
    const toggle = q('#oc-motion-toggle');
    toggle.setAttribute('aria-pressed', String(state.motion));
    q('span', toggle).textContent = state.motion ? '暂停动效' : '播放动效';
    q('i', toggle).className = 'fas fa-' + (state.motion ? 'pause' : 'play');
    if (atlas && state.motion) loadSheet('dense-wave.png').then(syncPet).catch(() => {});
    syncPet();
  }
  function scrollTo(selector) {
    q(selector)?.scrollIntoView({behavior: state.motion ? 'smooth' : 'instant', block: 'center'});
  }
  // Animate the existing local atlas. Offscreen/hidden/reduced-motion states stop timers.
  const art = q('.oc-companion-art');
  const portrait = q('img', art);
  const pet = document.createElement('button');
  pet.type = 'button'; pet.className = 'oc-home-pet';
  pet.setAttribute('aria-label', '让达菲郁跳一小段舞');
  portrait.before(pet); pet.append(portrait);
  const sprite = document.createElement('span'); sprite.className = 'oc-home-pet-sprite'; sprite.setAttribute('aria-hidden', 'true'); pet.append(sprite);
  let atlas, petVisible = false, welcomed = false, clip = 'idle', frame = 0, petTimer;
  let petRemaining = 0, petDeadline = 0;
  const petActive = () => atlas && petVisible && state.motion && !document.hidden;
  function drawPet() {
    const current = atlas.clips[clip];
    const cell = current.frames[frame];
    sprite.style.backgroundImage = `url("/static/images/dafeiyu/home/${current.sheet}")`;
    sprite.style.backgroundSize = `${current.columns * 100}% ${current.rows * 100}%`;
    sprite.style.backgroundPosition = `${cell % current.columns / (current.columns - 1) * 100}% ${current.rows === 1 ? 0 : Math.floor(cell / current.columns) / (current.rows - 1) * 100}%`;
    pet.dataset.action = clip;
  }
  function syncPet() {
    if (petTimer) {
      petRemaining = Math.max(0, petDeadline - performance.now());
      clearTimeout(petTimer); petTimer = undefined;
    }
    if (!petActive()) return;
    if (!welcomed && readySheets.has('dense-wave.png')) { welcomed = true; clip = 'wave'; frame = 0; petRemaining = 0; }
    drawPet();
    const duration = petRemaining || atlas.clips[clip].durations[frame];
    petRemaining = 0; petDeadline = performance.now() + duration;
    petTimer = setTimeout(() => {
      petTimer = undefined; frame++;
      if (frame >= atlas.clips[clip].frames.length) { clip = 'idle'; frame = 0; }
      syncPet();
    }, duration);
  }
  const sheetLoads = new Map();
  const readySheets = new Set();
  let requestedAction = 0;
  function loadSheet(sheet) {
    if (!sheetLoads.has(sheet)) {
      sheetLoads.set(sheet, new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => { readySheets.add(sheet); resolve(); };
        img.onerror = () => { sheetLoads.delete(sheet); reject(new Error('Pet sheet unavailable')); };
        img.src = '/static/images/dafeiyu/home/' + sheet;
      }));
    }
    return sheetLoads.get(sheet);
  }
  async function playPet(action) {
    if (!petActive()) return;
    const request = ++requestedAction;
    try { await loadSheet(atlas.clips[action].sheet); } catch { return; }
    if (request !== requestedAction || !petActive()) return;
    welcomed = true;
    clearTimeout(petTimer); petTimer = undefined; petRemaining = 0;
    clip = action; frame = 0; syncPet();
  }
  pet.addEventListener('click', () => playPet('dance'));
  // Warm the dance sheet on intent; it is not needed for the initial page load.
  const warmDance = () => { if (state.motion) loadSheet('dense-dance.png').catch(() => {}); };
  pet.addEventListener('pointerenter', warmDance);
  pet.addEventListener('focus', warmDance);
  let petLoaded;
  function loadPet() {
    if (petLoaded) return;
    petLoaded = true;
    Promise.all([
      fetch('/static/images/dafeiyu/home/actions.json').then(r => { if (!r.ok) throw new Error('Atlas unavailable'); return r.json(); }),
      loadSheet('idle-front.png')
    ]).then(([data]) => {
      atlas = data;
      pet.classList.add('is-loaded'); drawPet(); syncPet();
      if (state.motion) loadSheet('dense-wave.png').then(syncPet).catch(() => {});
    }).catch(() => { petLoaded = false; /* Preserve the portrait on failure. */ });
  }
  const petObserver = new IntersectionObserver(entries => {
    petVisible = entries[0].isIntersecting;
    if (petVisible) loadPet();
    syncPet();
  }, {threshold: .25});
  petObserver.observe(art);

  function sendDemoMessage() {
    const chat = q('#oc-home-chat');
    const input = q('[data-chat-input]', chat);
    if (!input.value.trim()) return;
    q('.og-user-message .og-message-bubble', chat).textContent = input.value.trim();
    q('[data-reply]', chat).textContent = '这是对话演示。练习时，达菲郁会结合你主动附带的题目、代码和运行结果来帮助你。点击“开始练习”，试着一起解决一道题吧。';
    input.value = ''; playPet('talk');
  }
  q('[data-chat-input]').addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.isComposing) { event.preventDefault(); sendDemoMessage(); }
  });
  root.addEventListener('click', event => {
    const button = event.target.closest('button');
    if (!button) return;
    if (button.id === 'oc-motion-toggle') { state.motion = !state.motion && !reduced.matches; renderMotion(); }
    if (button.dataset.scroll) scrollTo('#' + button.dataset.scroll);
    if (button.hasAttribute('data-open-feedback')) { selectCase('45'); scrollTo('#oc-feedback-demo'); }
    if (button.hasAttribute('data-demo-step')) { state.manualDemo = true; state.step = Number(button.dataset.demoStep); renderDemo(); }
    if (button.hasAttribute('data-help-level')) renderHelp(Number(button.dataset.helpLevel));
    if (button.hasAttribute('data-case')) selectCase(button.dataset.case);
    if (demo.contains(button)) {
      if (button.hasAttribute('data-run')) state.step = 1;
      if (button.hasAttribute('data-optimize')) state.step = 2;
      if (button.hasAttribute('data-submit')) state.step = 3;
      state.manualDemo = true; renderDemo();
    }
    if (button.hasAttribute('data-attach')) {
      const context = q('[data-context]'); context.hidden = !context.hidden;
      button.setAttribute('aria-pressed', String(!context.hidden));
      button.textContent = context.hidden ? '附带当前练习' : '取消附带';
      q('[data-context-status]').textContent = context.hidden ? '由你决定分享哪些上下文' : '示例上下文已附带';
      playPet('talk');
    }
    if (button.hasAttribute('data-chat-send')) sendDemoMessage();
  });
  const revealObserver = new IntersectionObserver(entries => entries.forEach(entry => {
    if (entry.isIntersecting) { entry.target.classList.add('is-visible'); revealObserver.unobserve(entry.target); }
  }), {threshold: .08});
  qa('.oc-reveal').forEach(el => { el.classList.add('is-ready'); revealObserver.observe(el); });
  let demoVisible = false;
  const demoObserver = new IntersectionObserver(entries => { demoVisible = entries[0].isIntersecting; }, {threshold: .25});
  demoObserver.observe(q('#oc-demo'));
  const oceanObserver = new IntersectionObserver(entries => {
    entries[0].target.classList.toggle('is-offscreen', !entries[0].isIntersecting);
  });
  oceanObserver.observe(q('.oc-ocean'));
  const demoTimer = setInterval(() => {
    // Do not replace content underneath keyboard focus or after manual interaction.
    if (!state.motion || state.manualDemo || document.hidden || !demoVisible || q('#oc-demo').contains(document.activeElement)) return;
    state.step = (state.step + 1) % 4; renderDemo();
  }, 6500);
  document.addEventListener('visibilitychange', () => { root.dataset.hidden = String(document.hidden); syncPet(); });
  reduced.addEventListener('change', () => { state.motion = !reduced.matches; renderMotion(); });
  window.addEventListener('pagehide', event => {
    if (!event.persisted) { clearInterval(demoTimer); clearTimeout(petTimer); petObserver.disconnect(); demoObserver.disconnect(); oceanObserver.disconnect(); revealObserver.disconnect(); }
  });
  renderDemo(); renderMotion();
})();
