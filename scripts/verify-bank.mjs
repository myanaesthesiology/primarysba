/**
 * Primary Revision source-fidelity and structural regression checker.
 * This is an integrity audit, NOT a verification against the original PDFs.
 * It does not alter question or explanation content.
 */
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const file = (relative) => join(root, relative);
const json = (relative) => JSON.parse(readFileSync(file(relative), 'utf8'));
const failures = [];
const warnings = [];
const flag = (id, code, message) => warnings.push({ id, code, message });
const fail = (code, message) => failures.push({ code, message });

const index = json('data/bank-index.json');
const search = json('data/search-index.json');
const shards = readdirSync(file('data')).filter((name) =>
  name.endsWith('.json') && !['bank-index.json', 'search-index.json'].includes(name)
).sort();
const questionData = shards.flatMap((name) => json('data/' + name));
const ids = new Set(index.map((q) => Number(q.id)));
const fullIds = new Set(questionData.map((q) => Number(q.id)));
const searchIds = new Set(search.map((q) => Number(q.id)));
const indexById = new Map(index.map((q) => [Number(q.id), q]));
const figures = new Set();

if (index.length !== 1102) fail('question-count', 'Expected 1,102 indexed questions; found ' + index.length);
if (ids.size !== index.length) fail('duplicate-index-id', 'Question index contains duplicate IDs');
if (fullIds.size !== questionData.length) fail('duplicate-source-id', 'Source chunks contain duplicate question IDs');
if (index.length !== questionData.length || [...ids].some((id) => !fullIds.has(id))) {
  fail('missing-question-data', 'Question metadata and source chunks do not have identical ID sets');
}
if (ids.size && (Math.min(...ids) !== 1 || Math.max(...ids) !== 1102)) {
  fail('id-range', 'Question IDs must cover the canonical 1–1102 range');
}
if (search.length !== 1102 || searchIds.size !== 1102 || [...ids].some((id) => !searchIds.has(id))) {
  fail('search-index', 'Search index does not cover every question ID exactly once');
}

for (const q of questionData) {
  const m = indexById.get(Number(q.id));
  if (!m || m.sourceCode !== q.sourceCode) {
    fail('source-metadata', 'Source chunk disagrees with index for question ' + q.id);
  }
  if (!String(q.stem || '').trim()) flag(q.id, 'missing-stem', 'Question stem empty');
  if (!String(q.explanation || '').trim()) flag(q.id, 'missing-explanation', 'Explanation empty');
  if (!Array.isArray(q.options) || !q.options.length) {
    flag(q.id, 'missing-options', 'Question has no answer options');
  } else {
    const keys = q.options.map((o) => String(o.key || ''));
    if (new Set(keys).size !== keys.length) flag(q.id, 'duplicate-option', 'Duplicate answer option key');
    if (!keys.includes(String(q.correctAnswer || ''))) flag(q.id, 'incorrect-answer-key', 'Answer key not in options');
    for (const opt of q.options) {
      if (!String(opt.text || '').trim()) flag(q.id, 'missing-option-text', 'Option ' + opt.key + ' has no text');
      if (!String(opt.html || '').trim()) flag(q.id, 'missing-option-rich', 'Option ' + opt.key + ' lacks rich text');
    }
  }
  if (!String(q.stemHtml || '').trim()) flag(q.id, 'missing-stem-rich', 'Rich stem formatting unavailable');
  if (!String(q.explanationHtml || '').trim()) flag(q.id, 'missing-explanation-rich', 'Rich explanation formatting unavailable');
  if (!q.sourceFile || !q.questionPage) flag(q.id, 'source-locator', 'Source filename or question page missing');
  for (const asset of [...(q.questionImages || []), ...(q.answerImages || [])]) {
    const src = String(asset.src || '').replace(/^\.\/+/, '');
    if (!src || !src.startsWith('figures/') || src.includes('..') || !existsSync(file(src))) {
      fail('missing-image', 'Question ' + q.id + ' figure missing: ' + String(asset.src || '(empty)'));
    } else {
      figures.add(src);
    }
  }
}

for (const asset of [
  'index.html', 'manifest.webmanifest', 'firebase-config.js', 'assets/app.css',
  'assets/app.js', 'service-worker.js', 'icons/icon-192.png', 'icons/icon-512.png'
]) {
  if (!existsSync(file(asset))) fail('missing-shell-asset', 'Missing PWA asset ' + asset);
}
const appJs = readFileSync(file('assets/app.js'), 'utf8');
for (const key of [
  'primary-revision-progress-v1',
  'primary-revision-autosave-v1',
  'primary-revision-study-sessions-v1'
]) {
  if (!appJs.includes(key)) fail('progress-key-changed', 'Existing progress storage key missing: ' + key);
}
if (!appJs.includes('PRIMARY_FIREBASE_CONFIG') || !appJs.includes('initFirebaseDiscussions')) {
  fail('discussions-integration', 'Firebase discussion integration was not preserved');
}
const sw = readFileSync(file('service-worker.js'), 'utf8');
for (const relative of ['data/bank-index.json', 'data/search-index.json', ...shards.map((s) => 'data/' + s), ...figures]) {
  if (!sw.includes(relative)) fail('offline-asset', 'Offline service-worker asset list omits ' + relative);
}
const report = {
  audit: 'Primary Revision automated structural and source-fidelity screening',
  limitation: 'Original printed or PDF source typography and clinical correctness are NOT independently verified.',
  question_count: index.length,
  data_chunks: shards,
  search_index_count: search.length,
  external_figure_count: figures.size,
  warnings_count: warnings.length,
  failures_count: failures.length,
  findings: warnings,
  failures
};
mkdirSync(file('qa'), { recursive: true });
writeFileSync(file('qa/primary-qa-report.json'), JSON.stringify(report, null, 2) + '\n');
console.log('Primary Revision QA:', index.length, 'questions;', shards.length, 'shards;', figures.size, 'figures;', warnings.length, 'content flags;', failures.length, 'structural failures');
console.log('Report: qa/primary-qa-report.json');
if (failures.length) {
  failures.slice(0, 25).forEach((item) => console.error(item.code + ': ' + item.message));
  process.exitCode = 1;
}
