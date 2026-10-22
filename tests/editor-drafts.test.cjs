'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('static/js/evidence.js', 'utf8');
const templates = {python: 'import sys\nprint(sys.stdin.read())\n', cpp: 'int main() {}\n'};
const flush = () => new Promise(resolve => setImmediate(resolve));

function editorPage(drafts = {}) {
    const nodes = new Map(), events = new Map(), storage = new Map();
    function node(id) {
        if (!nodes.has(id)) nodes.set(id, {
            value: '', dataset: {}, children: [], hidden: false, textContent: '', handlers: new Map(),
            classList: {add() {}, remove() {}, toggle() {}},
            addEventListener(name, handler) { this.handlers.set(name, handler); },
            setAttribute() {}, querySelectorAll() { return []; }, replaceChildren() { this.children = []; },
        });
        return nodes.get(id);
    }
    const key = lang => `codelab:draft:v2:guest:TEST:${lang}`;
    Object.entries(drafts).forEach(([lang, value]) => storage.set(key(lang), JSON.stringify(value)));
    node('languageSelector').value = 'python';
    let resolveCatalog;
    const catalog = new Promise(resolve => { resolveCatalog = resolve; });
    const localStorage = {getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value)};
    const context = vm.createContext({
        document: {getElementById: node, querySelectorAll: () => []},
        window: {addEventListener: (name, callback) => events.set(name, callback)},
        location: {search: '', href: 'http://test/practice.html?problem=TEST'},
        history: {replaceState() {}}, localStorage, sessionStorage: {getItem: () => null},
        fetch: () => catalog, URL, URLSearchParams, renderGhostLayer() {}, cancelInlineCompletion() {},
        getCurrentProblemId: () => 'TEST', outputContent: node('outputContent'),
        LearningHelpUI: {get: () => ({ready: true}), labels: {}},
    });
    vm.runInContext(source, context);
    events.get('practice:user')({detail: null});
    events.get('practice:problem')({detail: {id: 'TEST'}});
    return {
        node, storage, key,
        metadata: async () => { resolveCatalog({json: async () => ({data: {languages: Object.entries(templates).map(([id, starter_code]) => ({id, starter_code}))}})}); await flush(); },
        input(value) { node('codeInput').value = value; node('codeInput').handlers.get('input')(); },
        language(value) { node('languageSelector').value = value; node('languageSelector').handlers.get('change')(); },
    };
}

test('new Python and C++ editors stay blank before and after delayed metadata', async () => {
    const page = editorPage();
    assert.equal(page.node('codeInput').value, '');
    await page.metadata();
    assert.equal(page.node('codeInput').value, '');
    page.language('cpp');
    assert.equal(page.node('codeInput').value, '');
    page.language('python');
    assert.equal(page.node('codeInput').value, '');
});

test('legacy untouched templates are removed in both languages while test input survives', async () => {
    const page = editorPage({python: {code: templates.python, input: '59'}, cpp: {code: templates.cpp, input: '3600'}});
    await page.metadata();
    assert.equal(page.node('codeInput').value, '');
    assert.equal(page.node('customInput').value, '59');
    assert.equal(JSON.parse(page.storage.get(page.key('python'))).code, '');
    page.language('cpp');
    assert.equal(page.node('codeInput').value, '');
    assert.equal(page.node('customInput').value, '3600');
});

test('real drafts and explicitly saved empty drafts survive language switches', async () => {
    const page = editorPage({python: {code: 'print(59)', input: 'saved'}, cpp: {code: '', input: ''}});
    await page.metadata();
    assert.equal(page.node('codeInput').value, 'print(59)');
    page.language('cpp');
    assert.equal(page.node('codeInput').value, '');
    page.input('int main() { return 0; }');
    page.language('python');
    assert.equal(page.node('codeInput').value, 'print(59)');
    page.language('cpp');
    assert.equal(page.node('codeInput').value, 'int main() { return 0; }');
});

test('late metadata does not erase user edits or an intentional new template-shaped draft', async () => {
    const page = editorPage({python: {code: templates.python, input: ''}});
    page.input(templates.python + '# my code');
    await page.metadata();
    assert.equal(page.node('codeInput').value, templates.python + '# my code');
    const explicit = editorPage({python: {version: 3, code: templates.python, input: ''}});
    await explicit.metadata();
    assert.equal(explicit.node('codeInput').value, templates.python);
});

test('switching languages before metadata arrives still migrates the old untouched template', async () => {
    const page = editorPage({python: {code: templates.python, input: ''}});
    page.language('cpp');
    await page.metadata();
    page.language('python');
    assert.equal(page.node('codeInput').value, '');
});

test('old Hello World drafts are cleared without waiting for metadata', () => {
    const code = '# 示例Python代码\ndef greet(name):\n    return f"Hello, {name}!"\n\nprint(greet("World"))\n';
    const page = editorPage({python: {code, input: 'keep'}});
    assert.equal(page.node('codeInput').value, '');
    assert.equal(page.node('customInput').value, 'keep');
});
