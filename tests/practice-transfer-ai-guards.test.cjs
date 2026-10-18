'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const practice = fs.readFileSync(path.join(root, 'static/js/practice.js'), 'utf8');
const helpScript = fs.readFileSync(path.join(root, 'static/js/learning-help.js'), 'utf8');
function shippedFunction(name) {
  const found = practice.match(new RegExp(`^(?:async )?function ${name}\\([^\\n]*\\) \\{[\\s\\S]*?^\\}`, 'm'));
  assert.ok(found, `Missing shipped function ${name}`);
  return found[0];
}

test('active or pending independent practice prevents AI requests and suggestion insertion', async () => {
  for (const state of ['pending', 'active']) {
    let requests = 0, cancelled = 0, notified = 0, mutations = 0;
    const context = vm.createContext({
      window: {PracticeTransfer: {blocksAI: true, [state]: true, notifyBlocked() {notified++;}}},
      LearningHelpUI: {get: () => ({ready: true, mode: 'free'})},
      UserSession: {csrfFetch: async () => {requests++; throw new Error('Unexpected AI request');}},
      cancelInlineCompletion() {cancelled++;}, clearTimeout() {}, inlineDebounceTimer: null,
      document: {getElementById() {mutations++; throw new Error('AI must stop before reading or changing the editor');}},
    });
    for (const name of ['scheduleInlineCompletion', 'requestInlineCompletion', 'acceptInlineSuggestion',
      'optimizeCode', 'sendMessage', 'setChatWindowOpen']) vm.runInContext(shippedFunction(name), context);
    vm.runInContext('scheduleInlineCompletion(true); acceptInlineSuggestion(); setChatWindowOpen(true);', context);
    await vm.runInContext('requestInlineCompletion(1)', context);
    await vm.runInContext('optimizeCode()', context);
    await vm.runInContext('sendMessage()', context);
    assert.equal(requests, 0);
    assert.equal(mutations, 0);
    assert.equal(cancelled, 3);
    assert.equal(notified, 3);
  }
});

test('ordinary free assistance still schedules inline completion', () => {
  const editor = {};
  let scheduled = 0;
  const context = vm.createContext({
    window: {}, LearningHelpUI: {get: () => ({ready: true, mode: 'free'})},
    codeInput: editor, practiceUser: {id: 1}, inlineComposing: false, inlineRetryAfter: 0,
    inlineDebounceTimer: null, inlineRequestId: 0, document: {activeElement: editor},
    clearTimeout() {}, setTimeout() {scheduled++; return 1;}, requestInlineCompletion() {},
  });
  vm.runInContext(shippedFunction('scheduleInlineCompletion'), context);
  vm.runInContext('scheduleInlineCompletion()', context);
  assert.equal(scheduled, 1);
});

test('independent mode masks help locally and restores preferences without saving account changes', async () => {
  const listeners = new Map(), calls = [];
  const node = () => ({value: '', disabled: false, textContent: '', addEventListener() {}});
  const mode = node(), level = node(), status = node(), completion = node();
  const window = {
    PracticeTransfer: {blocksAI: false},
    addEventListener(name, fn) {if (!listeners.has(name)) listeners.set(name, []); listeners.get(name).push(fn);},
    dispatchEvent(event) {for (const fn of listeners.get(event.type) || []) fn(event);},
  };
  const context = vm.createContext({window,
    document: {
      querySelectorAll(selector) {return selector === '[data-help-mode]' ? [mode] : selector === '[data-help-select]' ? [level] : [];},
      getElementById(id) {return id === 'completionStatus' ? completion : status;},
    },
    CustomEvent: class {constructor(type, init) {this.type = type; this.detail = init?.detail;}},
    fetch: async (url, options = {}) => {calls.push({url, method: options.method || 'GET'}); return {
      ok: true, json: async () => ({success: true, data: {mode: 'free', revision: 3}}),
    };},
    UserSession: {csrfFetch: async () => {throw new Error('Must not write account preferences');}},
  });
  vm.runInContext(helpScript, context);
  window.dispatchEvent({type: 'practice:user', detail: {id: 1}});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(window.LearningHelpUI.get().mode, 'free');
  assert.equal(window.LearningHelpUI.get().ready, true);
  window.PracticeTransfer.blocksAI = true;
  window.dispatchEvent({type: 'practice:transfer-mode'});
  assert.equal(window.LearningHelpUI.get().ready, false);
  assert.equal(mode.disabled, true);
  assert.match(completion.textContent, /收起/);
  window.PracticeTransfer.blocksAI = false;
  window.dispatchEvent({type: 'practice:transfer-mode'});
  assert.equal(window.LearningHelpUI.get().mode, 'free');
  assert.equal(window.LearningHelpUI.get().ready, true);
  assert.equal(mode.disabled, false);
  assert.equal(calls.filter(item => item.method !== 'GET').length, 0);
});
