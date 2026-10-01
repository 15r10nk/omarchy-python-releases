const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const context = vm.createContext({});
const root = path.join(__dirname, '..');
vm.runInContext(fs.readFileSync(path.join(root, 'Translations.js'), 'utf8').replace(/^\.pragma library\s*/, ''), context);
const { messages, resolveLanguage, text, eventVersion } = context;
const languages = ['de', 'en', 'fr', 'es', 'it', 'pt', 'nl', 'pl', 'ru', 'tr', 'zh', 'ja', 'ko'];
assert.deepEqual(Object.keys(messages).sort(), languages.sort());
for (const language of languages) {
  assert.deepEqual(Object.keys(messages[language]).sort(), Object.keys(messages.en).sort());
  for (const key of Object.keys(messages.en)) {
    const placeholders = value => [...value.matchAll(/\{\w+\}/g)].map(m => m[0]).sort();
    assert.deepEqual(placeholders(messages[language][key]), placeholders(messages.en[key]), `${language}.${key}`);
    assert.ok(messages[language][key].trim(), `${language}.${key} is empty`);
  }
  for (const locale of [language, `${language}_XX`, `${language}-XX`, `${language}_XX.UTF-8`, `${language.toUpperCase()}_XX@variant`]) {
    assert.equal(resolveLanguage(locale), language, locale);
  }
}
for (const locale of ['C', 'POSIX', '', 'default', 'ar_EG', 'constructor', '__proto__']) assert.equal(resolveLanguage(locale), 'en');
assert.equal(resolveLanguage('fr_CA'), 'fr');
assert.equal(resolveLanguage('es_MX'), 'es');
assert.equal(resolveLanguage('pt_BR'), 'pt');
assert.equal(resolveLanguage('zh-Hans-CN'), 'zh');
assert.equal(text('en', 'days', {n: 5}), 'in 5 days');
assert.equal(text('de', 'days', {n: 5}), 'in 5 Tagen');
assert.equal(text('fr', 'oneDay'), 'dans 1 jour');
assert.equal(text('es', 'days', {n: 3}), 'en 3 días');
assert.equal(text('pl', 'shortOneDay'), '1 dzień');
assert.equal(text('unknown', 'oneDay'), 'in 1 day');
assert.equal(eventVersion({kind: 'development', version: '3.15 Entwicklung'}), '3.15');
assert.equal(eventVersion({kind: 'rc', version: '3.15.0rc1'}), '3.15.0rc1');
const widget = fs.readFileSync(path.join(root, 'Panel.qml'), 'utf8');
for (const [, key] of widget.matchAll(/\bt\("([^"]+)"\s*[,)]/g)) assert.ok(messages.en[key], `Missing translation: ${key}`);
assert.ok(!widget.includes('selectLanguage'));
assert.ok(!widget.includes('languagePreference'));
assert.ok(!widget.includes('setting("language"'));
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'manifest.json'), 'utf8'));
assert.ok(!('language' in manifest.barWidget.defaults));
assert.ok(!manifest.barWidget.schema.some(s => s.key === 'language'));
console.log('13 complete translation catalogs, placeholders, regional locales, fallback and removal of language overrides: OK');
