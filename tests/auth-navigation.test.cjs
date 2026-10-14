const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const script = fs.readFileSync('static/js/user-session.js', 'utf8');
function session(path, referrer = '') {
    const location = new URL(path, 'http://localhost:5005');
    const listeners = {};
    const context = { URL, URLSearchParams, location, window: {}, document: {
        referrer, querySelectorAll: () => [],
        addEventListener: (event, handler) => { listeners[event] = handler; }
    }};
    vm.runInNewContext(script, context);
    return { ...context, api: context.window.UserSession, listeners };
}
test('practice query and analytics anchor survive login', () => {
    for (const path of ['/practice.html?problem_id=7&language=cpp', '/learn-analytics.html#leaderboard']) {
        const source = session(path);
        const login = session(source.api.loginUrl());
        assert.equal(login.api.returnPath(), path);
    }
});
test('registration detour preserves original destination', () => {
    const source = session('/practice.html?problem_id=9#editor');
    const login = session(source.api.loginUrl());
    const register = session(login.api.authUrl('/register.html'));
    assert.equal(session(register.api.loginUrl()).api.returnPath(), '/practice.html?problem_id=9#editor');
});
test('safe local fallback rejects external, invalid and auth destinations', () => {
    for (const next of ['https://evil.example/a', '//evil.example/a', 'javascript:alert(1)', 'http://[', '/login.html', '/register.html']) {
        assert.equal(session('/login.html?next=' + encodeURIComponent(next)).api.returnPath(), '/');
    }
    assert.equal(session('/login.html', 'http://localhost:5005/problem_selector.html').api.returnPath(), '/problem_selector.html');
    assert.equal(session('/login.html', 'https://evil.example/').api.returnPath(), '/');
});
test('dynamic login links use current anchor at click time', () => {
    const current = session('/learn-analytics.html');
    const link = { href: 'http://localhost:5005/login.html', dataset: {} };
    current.location.hash = '#leaderboard';
    current.listeners.click({target:{closest: () => link}});
    assert.equal(new URL(link.href, current.location.origin).searchParams.get('next'), '/learn-analytics.html#leaderboard');
});
test('successful login form navigates back; failed login stays on the form', async () => {
    for (const success of [true, false]) {
        const current = session('/login.html?next=%2Fpractice.html%3Fproblem_id%3D7%23editor');
        let submit;
        const elements = {
            loginForm: {addEventListener: (_, handler) => { submit = handler; }},
            username: {value: 'demo-user'}, password: {value: 'example-password'},
            formMessage: {}, submitBtn: {}
        };
        const location = { search: current.location.search, href: current.location.href };
        const html = fs.readFileSync('templates/login.html', 'utf8');
        const inline = html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
        vm.runInNewContext(inline, {
            document: {getElementById: id => elements[id]}, location, window: {location},
            URLSearchParams, UserSession: current.api,
            UIFeedback: {renderMessage(){}, setButtonLoading(){}, apiErrorMessage(){ return 'failed'; }},
            fetch: async () => ({json: async () => ({success})})
        });
        await submit({preventDefault(){}});
        assert.equal(location.href, success ? '/practice.html?problem_id=7#editor' : current.location.href);
    }
});
