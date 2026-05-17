(function () {
    const defaultAvatar = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iI2EwYWVjMCI+PHBhdGggZD0iTTEyIDJDNi40OCAyIDIgNi40OCAyIDEyczQuNDggMTAgMTAgMTAgMTAtNC40OCAxMC0xMFMxNy41MiAyIDEyIDJ6bTAgM2MxLjY2IDAgMyAxLjM0IDMgM3MtMS4zNCAzLTMgMy0zLTEuMzQtMy0zIDEuMzQtMyAzLTN6bTAgMTRjLTIuNjcgMC04IDEuMzQtOCA0djJoMTZjMC0yLjY2LTUuMzMtNC04LTR6Ii8+PC9zdmc+';

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

    let csrfToken = null;
    let csrfTokenPromise = null;

    async function getCsrfToken() {
        if (csrfToken) {
            return csrfToken;
        }
        if (!csrfTokenPromise) {
            csrfTokenPromise = fetch('/api/csrf-token')
                .then(async (response) => {
                    if (!response.ok) {
                        throw new Error('CSRF token 获取失败');
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
        return fetch(url, options);
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
                    <a href="/login.html">登录</a>
                    <a href="/register.html">注册</a>
                </div>
            </div>
            <div class="user-avatar">
                <img src="${defaultAvatar}" alt="默认头像">
            </div>
        `;
    }

    function renderUser(container, user, options) {
        const points = user && typeof user.points !== 'undefined' ? user.points : 0;
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
            <div class="user-avatar">
                <img src="${escapeHtml(options.avatarUrl || defaultAvatar)}" alt="用户头像">
            </div>
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
        csrfFetch,
        escapeHtml,
        getCsrfToken,
        init,
        logout,
        renderGuest,
        renderUser
    };
})();
