const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ctx = vm.createContext({});
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname, '../Selection.js'), 'utf8').replace(/^\.pragma library\s*/, ''), ctx);
const event = (version, date, kind = 'stable', confirmed = false) => ({version, date, kind, confirmed});
const data = {today: '2026-09-28', next: event('3.15.0', '2026-10-01'), branches: [
  {version: '3.14', first: '2025-10-07', events: [event('3.14.7', '2026-08-05', 'stable', true), event('3.14.8', '2026-10-06')]},
  {version: '3.16', first: '2027-10-06', events: [event('3.16.0a1', '2026-10-13', 'alpha'), event('3.16.0', '2027-10-05')]},
  {version: '3.9', first: '2020-10-05', events: []}
]};
assert.equal(ctx.nextRelease(data, '', 'feature'), data.next);
const patch = ctx.nextRelease(data, '3.14', 'feature');
assert.equal(patch.version, '3.14.8');
assert.equal(patch.days, 8);
assert.equal(ctx.nextRelease(data, '3.16', 'feature').version, '3.16.0');
assert.equal(ctx.nextRelease(data, '3.16', 'all').version, '3.16.0a1');
assert.equal(ctx.nextRelease(data, '3.9', 'feature'), null);
assert.equal(ctx.nextRelease(data, '9.99', 'all'), null);
assert.equal(ctx.nextRelease({...data, today: '2026-10-06'}, '3.14', 'stable').days, 0);
assert.equal(ctx.nextRelease({...data, today: '2026-10-07'}, '3.14', 'stable'), null);
data.branches[0].events[1].confirmed = true;
assert.equal(ctx.nextRelease(data, '3.14', 'stable'), null);
assert.ok(!('days' in data.branches[0].events[1]), 'Must not mutate cached events');
const fallback = {today: '2026-10-24', branches: [{version:'3.17', first:'2026-10-26', events:[]}]};
assert.equal(ctx.nextRelease(fallback, '3.17', 'feature').days, 2);
console.log('Favorites: automatic, patch, prerelease, no dates, unavailable series, today, past dates, confirmed releases, cache immutability and DST: OK');
