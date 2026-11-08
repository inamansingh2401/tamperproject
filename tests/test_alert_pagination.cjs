const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../Tamper_admin/frontend/api.js'), 'utf8');

(async () => {
    const urls = [];
    const first = Array.from({length: 500}, (_, i) => ({id: 1000-i}));
    const context = {window: {}, console, URLSearchParams};
    vm.createContext(context);
    vm.runInContext(source, context);
    context.authFetch = async url => {
        urls.push(url);
        return {ok: true, json: async () => urls.length === 1 ? first : [{id: 499}]};
    };
    const rows = await context.window.SafeTrackAPI.getAlerts();
    assert.equal(rows.length, 501);
    assert.equal(new URL(urls[1]).searchParams.get('before_id'), '501');
    assert.equal(rows[500].id, 499);
    context.authFetch = async () => ({ok: false});
    await assert.rejects(context.window.SafeTrackAPI.getAlerts(), /Failed to load alerts/);
    context.authFetch = async () => ({ok: true, json: async () => first});
    await assert.rejects(context.window.SafeTrackAPI.getAlerts(), /did not advance/);
    console.log('PASS: alert client follows keyset pages and propagates request failures');
})().catch(error => { console.error(error); process.exitCode = 1; });
