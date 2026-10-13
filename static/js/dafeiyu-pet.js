/* Local sprite playback and interactions for the Dafeiyu companion. */
(() => {
    const pet = document.getElementById('aiToggleBtn');
    const sprite = pet.querySelector('.pet-sprite');
    const caption = pet.querySelector('.pet-caption');
    const menu = document.getElementById('petActionMenu');
    const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
    const names = {idle: '陪你写代码', drag: '哎呀，被提起来啦！', fall: '慢慢放本鱼下来～',
        land: '站稳啦', wave: '本鱼来啦', think: '认真思考中', talk: '正在回答',
        dance: '活动一下', eat: '吃一口小鱼干', sleep: '休息一会儿', wake: '醒来啦', jump: '好耶！'};
    let atlas = null, state = 'idle', started = performance.now(), activity = 'idle';
    let lastInteraction = performance.now(), nextIdleAction = lastInteraction + 12000;
    let drag = null, fall = null, suppressClick = false, longPressTimer = null;
    let tilt = 0, targetTilt = 0, lastFrame = -1, frameRequest = null;
    let manualSleep = false;

    function play(next) {
        state = next;
        started = performance.now();
        pet.dataset.state = state;
        caption.textContent = names[state];
        lastFrame = -1;
    }
    function interact() {
        lastInteraction = performance.now();
        nextIdleAction = lastInteraction + 12000 + Math.random() * 8000;
    }
    function resumeActivity() {
        play(manualSleep && activity === 'idle' ? 'sleep' : activity);
        nextIdleAction = performance.now() + 12000 + Math.random() * 8000;
    }
    function setActivity(next) {
        const previous = activity;
        activity = ['think', 'talk'].includes(next) ? next : 'idle';
        interact();
        if (activity !== 'idle') manualSleep = false;
        if (drag || ['fall', 'land'].includes(state)) return;
        if (activity === 'idle' && previous === 'talk') play('wave');
        else resumeActivity();
    }
    window.DafeiyuPet = {setActivity};

    function clampPet(left, top) {
        const {width, height} = pet.getBoundingClientRect();
        const x = Math.max(0, Math.min(left, innerWidth - width));
        const y = Math.max(0, Math.min(top, innerHeight - height));
        Object.assign(pet.style, {left: `${x}px`, top: `${y}px`, right: 'auto', bottom: 'auto'});
        return {x, y};
    }
    function savePosition() {
        const {left, top} = pet.getBoundingClientRect();
        try { localStorage.setItem('dafeiyu-pet-position-v1', JSON.stringify({left, top})); } catch (_) {}
    }
    try {
        const stored = JSON.parse(localStorage.getItem('dafeiyu-pet-position-v1'));
        if (stored && Number.isFinite(stored.left) && Number.isFinite(stored.top)) clampPet(stored.left, stored.top);
    } catch (_) {}

    function hideMenu() { menu.hidden = true; }
    function showMenu() {
        clearTimeout(longPressTimer);
        interact();
        menu.hidden = false;
        const rect = pet.getBoundingClientRect();
        const width = menu.offsetWidth, height = menu.offsetHeight;
        menu.style.left = `${Math.max(8, Math.min(rect.left, innerWidth - width - 8))}px`;
        menu.style.top = `${Math.max(8, Math.min(rect.top - height, innerHeight - height - 8))}px`;
    }
    pet.addEventListener('contextmenu', event => { event.preventDefault(); showMenu(); });
    pet.addEventListener('keydown', event => {
        if (event.key === 'ContextMenu' || (event.shiftKey && event.key === 'F10')) {
            event.preventDefault(); showMenu(); menu.querySelector('button').focus();
        }
    });
    menu.addEventListener('click', event => {
        const button = event.target.closest('[data-pet-action]');
        if (!button) return;
        const action = button.dataset.petAction;
        manualSleep = action === 'sleep';
        play(action);
        hideMenu(); interact(); pet.focus({preventScroll: true});
    });
    document.addEventListener('pointerdown', event => {
        if (!pet.contains(event.target) && !menu.contains(event.target)) hideMenu();
    });
    document.addEventListener('keydown', event => {
        lastInteraction = performance.now();
        if (event.key === 'Escape' && !menu.hidden) { hideMenu(); pet.focus({preventScroll: true}); }
    });
    pet.addEventListener('pointerenter', () => {
        interact();
        if (state === 'sleep' && !manualSleep) play('wake');
    });
    pet.addEventListener('pointerdown', event => {
        if (event.button !== 0) return;
        hideMenu(); interact();
        const rect = pet.getBoundingClientRect();
        drag = {pointerId: event.pointerId, x: event.clientX, y: event.clientY,
            left: rect.left, top: rect.top, moved: false, lastX: event.clientX, lastAt: performance.now()};
        fall = null;
        suppressClick = false;
        pet.setPointerCapture(event.pointerId);
        longPressTimer = setTimeout(() => {
            if (drag && !drag.moved) { suppressClick = true; showMenu(); }
        }, 550);
    });
    pet.addEventListener('pointermove', event => {
        if (!drag || event.pointerId !== drag.pointerId) return;
        const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
        if (!drag.moved && Math.hypot(dx, dy) > 4) {
            drag.moved = true; suppressClick = true; manualSleep = false;
            clearTimeout(longPressTimer); hideMenu();
            pet.classList.add('is-dragging'); play('drag');
        }
        if (!drag.moved) return;
        const now = performance.now();
        targetTilt = Math.max(-16, Math.min(16, (event.clientX - drag.lastX) / Math.max(16, now - drag.lastAt) * 9));
        drag.lastX = event.clientX; drag.lastAt = now;
        clampPet(drag.left + dx, drag.top + dy);
    });
    function endDrag(event) {
        if (!drag || event.pointerId !== drag.pointerId) return;
        clearTimeout(longPressTimer);
        const moved = drag.moved;
        drag = null; targetTilt = 0;
        pet.classList.remove('is-dragging');
        if (!moved) return;
        const rect = pet.getBoundingClientRect();
        if (event.type === 'pointercancel' || reducedMotion.matches) { play('land'); savePosition(); return; }
        fall = {left: rect.left, from: rect.top, to: Math.min(innerHeight - rect.height, rect.top + 32)};
        play('fall');
    }
    pet.addEventListener('pointerup', endDrag);
    pet.addEventListener('pointercancel', endDrag);
    pet.addEventListener('lostpointercapture', endDrag);
    pet.addEventListener('click', event => {
        if (suppressClick && event.detail !== 0) {
            event.preventDefault(); event.stopImmediatePropagation(); suppressClick = false; return;
        }
        clearTimeout(longPressTimer);
        interact(); manualSleep = false;
        if (activity === 'idle') play(state === 'sleep' ? 'wake' : 'wave');
    }, true);

    function paint(now) {
        frameRequest = null;
        if (document.hidden) return;
        const elapsed = now - started;
        if (!drag && state === 'fall' && fall) {
            const progress = Math.min(1, elapsed / 180);
            clampPet(fall.left, fall.from + (fall.to - fall.from) * progress * progress);
            if (progress === 1) { fall = null; play('land'); savePosition(); }
        }
        if (atlas) {
            const clip = atlas.clips[state];
            const duration = clip.durations.reduce((sum, ms) => sum + ms, 0);
            if (!clip.loop && elapsed >= duration && !['sleep', 'fall'].includes(state)) {
                resumeActivity();
            }
            const activeClip = atlas.clips[state];
            const span = activeClip.durations.reduce((sum, ms) => sum + ms, 0);
            let time = Math.max(0, now - started);
            if (activeClip.loop) time %= span;
            let index = 0;
            if (reducedMotion.matches) index = state === 'sleep' ? activeClip.frames.length - 1 : 0;
            else while (index < activeClip.frames.length - 1 && time >= activeClip.durations[index]) time -= activeClip.durations[index++];
            const frame = activeClip.frames[index];
            if (frame !== lastFrame) {
                sprite.style.backgroundPosition = `${(frame % atlas.columns) / (atlas.columns - 1) * 100}% ${Math.floor(frame / atlas.columns) / (atlas.rows - 1) * 100}%`;
                pet.dataset.frame = String(frame);
                lastFrame = frame;
            }
        } else if (elapsed > 1200 && !['idle', 'think', 'talk', 'drag', 'fall', 'sleep'].includes(state)) {
            resumeActivity();
        }
        if (drag && now - drag.lastAt > 120) targetTilt = 0;
        tilt += (targetTilt - tilt) * .15;
        const lifted = state === 'drag';
        const jump = state === 'jump' ? -Math.sin(Math.PI * Math.min(1, elapsed / 1725)) * 16 : 0;
        sprite.style.transform = reducedMotion.matches ? 'none'
            : `translateY(${lifted ? -6 : jump}px) rotate(${tilt}deg) scale(${lifted ? '1.01, 1.05' : '1'})`;
        if (state === 'idle' && activity === 'idle' && !drag && !reducedMotion.matches && menu.hidden) {
            if (now - lastInteraction > 120000) play('sleep');
            else if (now > nextIdleAction) play(Math.random() < .5 ? 'wave' : 'dance');
        }
        frameRequest = requestAnimationFrame(paint);
    }
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) { cancelAnimationFrame(frameRequest); frameRequest = null; }
        else { interact(); if (frameRequest === null) frameRequest = requestAnimationFrame(paint); }
    });
    window.addEventListener('resize', () => {
        const rect = pet.getBoundingClientRect();
        clampPet(rect.left, rect.top);
        if (fall) fall.to = Math.max(0, Math.min(fall.to, innerHeight - rect.height));
        hideMenu();
    });
    window.addEventListener('practice:submission', event => {
        if (event.detail?.status === 'Accepted' && !drag && activity === 'idle') { interact(); play('jump'); }
    });

    play('idle');
    Promise.all([
        fetch('/static/images/dafeiyu/actions.json').then(response => {
            if (!response.ok) throw new Error('Animation manifest unavailable');
            return response.json();
        }),
        new Promise((resolve, reject) => {
            const image = new Image();
            image.onload = resolve; image.onerror = reject;
            image.src = '/static/images/dafeiyu/actions.webp';
        })
    ]).then(([manifest]) => {
        atlas = manifest;
        sprite.style.backgroundImage = 'url("/static/images/dafeiyu/actions.webp")';
        sprite.style.backgroundSize = `${atlas.columns * 100}% ${atlas.rows * 100}%`;
        pet.classList.add('has-actions');
        pet.dataset.ready = 'true';
        frameRequest = requestAnimationFrame(paint);
    }).catch(() => {
        pet.dataset.ready = 'false';
        // The existing local idle image still works if the action atlas cannot load.
        frameRequest = requestAnimationFrame(paint);
    });
})();
