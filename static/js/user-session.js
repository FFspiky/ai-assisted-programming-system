(function () {
    const defaultAvatar = '/static/images/brand-v1/avatars/whale.png';

    function escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return String(text || '').replace(/[&<>"']/g, function (m) { return map[m]; });
    }

    function apiErrorMessage(result, fallback = '请求失败') {
        if (!result) return fallback;
        if (typeof result.error === 'string') return result.error;
        if (result.error && result.error.message) return result.error.message;
        if (result.message) return result.message;
        return fallback;
    }

    let csrfToken = null;
    let csrfTokenPromise = null;

    function safeReturnPath(value) {
        if (!value) return '/';
        try {
            const target = new URL(value, location.origin);
            if (target.origin !== location.origin || target.username || target.password ||
                ['/login.html', '/register.html'].includes(target.pathname)) return '/';
            return target.pathname + target.search + target.hash;
        } catch (_) { return '/'; }
    }

    function returnPath() {
        if (['/login.html', '/register.html'].includes(location.pathname)) {
            const params = new URLSearchParams(location.search);
            return safeReturnPath(params.has('next') ? params.get('next') : document.referrer);
        }
        return location.pathname + location.search + location.hash;
    }

    function authUrl(page) {
        return page + '?next=' + encodeURIComponent(returnPath());
    }

    function loginUrl() {
        return authUrl('/login.html');
    }

    // Cover static links, dynamically rendered prompts and newly selected anchors.
    function updateAuthLink(link) {
        if (!link) return;
        const target = new URL(link.href, location.origin);
        if (target.origin === location.origin &&
            ['/login.html', '/register.html'].includes(target.pathname) &&
            (!target.searchParams.has('next') || link.dataset.returnToCurrent === 'true')) {
            target.searchParams.set('next', returnPath());
            link.href = target.pathname + target.search + target.hash;
            link.dataset.returnToCurrent = 'true';
        }
    }
    document.querySelectorAll('a[href]').forEach(updateAuthLink);
    document.addEventListener('click', event => updateAuthLink(event.target.closest('a[href]')), true);
    document.addEventListener('auxclick', event => updateAuthLink(event.target.closest('a[href]')), true);

    function authRequired() {
        csrfToken = null;
        const error = new Error('请先登录后再操作。');
        error.code = 'AUTH_REQUIRED';
        return error;
    }

    function promptLogin(container, message = '登录后即可继续操作。') {
        window.dispatchEvent(new Event('auth:required'));
        container.replaceChildren();
        const text = document.createElement('span');
        text.textContent = message + ' ';
        const link = document.createElement('a');
        link.href = loginUrl();
        link.dataset.returnToCurrent = 'true';
        link.textContent = '去登录';
        link.style.color = 'var(--accent, #4895ef)';
        container.append(text, link);
    }

    function handleAuthError(error, container, message) {
        if (error.code !== 'AUTH_REQUIRED') return false;
        promptLogin(container, message);
        return true;
    }

    async function getCsrfToken() {
        if (csrfToken) {
            return csrfToken;
        }
        if (!csrfTokenPromise) {
            csrfTokenPromise = fetch('/api/csrf-token')
                .then(async (response) => {
                    if (response.status === 401) throw authRequired();
                    if (!response.ok) {
                        throw new Error('暂时无法验证登录状态，请刷新后重试。');
                    }
                    const result = await response.json();
                    csrfToken = result.csrf_token;
                    return csrfToken;
                })
                .finally(() => {
                    csrfTokenPromise = null;
                });
        }
        return csrfTokenPromise;
    }

    async function csrfFetch(url, options = {}) {
        const method = (options.method || 'GET').toUpperCase();
        if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method)) {
            const token = await getCsrfToken();
            const headers = new Headers(options.headers || {});
            headers.set('X-CSRF-Token', token);
            options = { ...options, headers };
        }
        const response = await fetch(url, options);
        if (response.status === 401) throw authRequired();
        if (response.status === 403) {
            const result = await response.clone().json().catch(() => ({}));
            if (result.error?.code === 'CSRF_INVALID') {
                csrfToken = null;
                throw new Error('登录状态已更新，请刷新后重试。');
            }
        }
        return response;
    }

    async function logout(redirectTo) {
        await csrfFetch('/api/logout', { method: 'POST' });
        window.location.href = redirectTo || '/index.html';
    }

    function renderGuest(container) {
        container.innerHTML = `
            <div class="user-details">
                <div class="username">访客</div>
                <div class="user-stats">
                    <a href="${escapeHtml(loginUrl())}" data-return-to-current="true">登录</a>
                    <a href="${escapeHtml(authUrl('/register.html'))}" data-return-to-current="true">注册</a>
                </div>
            </div>
            <a class="user-avatar" href="${escapeHtml(loginUrl())}" data-return-to-current="true" aria-label="登录后返回当前页">
                <img src="${defaultAvatar}" alt="默认头像">
            </a>
        `;
    }

    function renderUser(container, user, options = {}) {
        const points = String(user?.points ?? 0);
        const records = options.showRecords
            ? '<span class="show-records" style="cursor:pointer;">刷题记录</span>'
            : '';
        container.innerHTML = `
            <div class="user-details">
                <div class="username">${escapeHtml(user.username)}</div>
                <div class="user-stats">
                    ${records}
                    <span>积分: ${escapeHtml(points)}</span>
                    <a href="#" class="logout-link" style="color: #f72585; cursor: pointer; margin-left: 15px; text-decoration: none;">登出</a>
                </div>
            </div>
            <a class="user-avatar" href="/profile.html" aria-label="个人主页" title="个人主页">
                <img src="${escapeHtml(user.avatar_url || options.avatarUrl || defaultAvatar)}" alt="用户头像" style="object-fit:cover;">
            </a>
        `;

        container.querySelector('.logout-link')?.addEventListener('click', async (event) => {
            event.preventDefault();
            await logout(options.logoutRedirect);
        });

        container.querySelector('.show-records')?.addEventListener('click', () => {
            if (typeof options.onRecordsClick === 'function') {
                options.onRecordsClick();
            } else {
                window.location.href = '/practice.html';
            }
        });
    }

    function migrateDrafts(user) {
        try {
            const prefix = `codelab:draft:v1:${user.username}:`;
            Object.keys(localStorage).filter(key => key.startsWith(prefix)).forEach(key => {
                const stable = `codelab:draft:v2:${user.id}:` + key.slice(prefix.length);
                if (!localStorage.getItem(stable)) localStorage.setItem(stable, localStorage.getItem(key));
                localStorage.removeItem(key);
            });
        } catch (_) { /* Storage may be disabled by the browser. */ }
    }

    async function init(options = {}) {
        const containers = document.querySelectorAll(options.selector || '.user-info');
        if (!containers.length) {
            return null;
        }

        try {
            const response = await fetch('/api/current_user');
            if (!response.ok) {
                containers.forEach(renderGuest);
                if (typeof options.onGuest === 'function') options.onGuest();
                return null;
            }

            const result = await response.json();
            if (!result.success) {
                containers.forEach(renderGuest);
                if (typeof options.onGuest === 'function') options.onGuest();
                return null;
            }

            migrateDrafts(result.user);
            containers.forEach((container) => renderUser(container, result.user, options));
            getCsrfToken().catch((error) => console.error('CSRF token 初始化失败', error));
            if (typeof options.onAuthenticated === 'function') options.onAuthenticated(result.user);
            return result.user;
        } catch (error) {
            console.error('获取用户信息失败', error);
            containers.forEach(renderGuest);
            if (typeof options.onGuest === 'function') options.onGuest(error);
            return null;
        }
    }

    window.UserSession = {
        defaultAvatar,
        apiErrorMessage,
        csrfFetch,
        escapeHtml,
        getCsrfToken,
        handleAuthError,
        init,
        loginUrl,
        authUrl,
        returnPath,
        safeReturnPath,
        logout,
        promptLogin,
        renderGuest,
        renderUser
    };
})();
