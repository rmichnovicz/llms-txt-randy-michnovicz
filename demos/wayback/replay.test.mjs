import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
const root = resolve(import.meta.dirname, '../..');
async function worker(version) {
  execFileSync('uv', ['run', 'python', 'scripts/wayback_demo.py', version], {cwd:root});
  const code = readFileSync(resolve(root, `evals/results/wayback-demo/${version}/_worker.js`));
  return (await import('data:text/javascript;base64,' + code.toString('base64'))).default;
}
test('real captures change at the same URL and HTTP validators detect the switch', async () => {
  const before = await worker('before'), after = await worker('after');
  const url = 'https://replay.example/site/';
  const a = await before.fetch(new Request(url));
  assert.equal(a.status,200);
  assert.match(await a.text(), /Modernizr/);
  const etag = a.headers.get('etag');
  assert.equal((await before.fetch(new Request(url,{headers:{'If-None-Match':etag}}))).status,304);
  assert.equal((await before.fetch(new Request(url,{headers:{'If-None-Match':'W/'+etag}}))).status,304);
  const b = await after.fetch(new Request(url,{headers:{'If-None-Match':etag}}));
  assert.equal(b.status,200);
  assert.notEqual(b.headers.get('etag'),etag);
  assert.equal(b.headers.get('x-replay-capture'),'20250531194832');
  assert.equal((await after.fetch(new Request(url,{headers:{'If-None-Match':b.headers.get('etag')}}))).status,304);
});
test('uncaptured pages are unavailable, not deleted; replay is read-only', async () => {
  const app = await worker('before');
  assert.equal((await app.fetch(new Request('https://replay.example/site/missing'))).status,503);
  assert.equal((await app.fetch(new Request('https://replay.example/site/',{method:'POST'}))).status,405);
  assert.equal(await (await app.fetch(new Request('https://replay.example/site/',{method:'HEAD'}))).text(),'');
});
test('provenance, scoped sitemap and inert archived content', async () => {
  const app = await worker('before');
  const manifest = await (await app.fetch(new Request('https://replay.example/provenance.json'))).json();
  assert.match(manifest.capture_url,/20221231202913id_/);
  const page = await (await app.fetch(new Request('https://replay.example/site/'))).text();
  assert.doesNotMatch(page,/<script\b|<iframe\b|<form\b/i);
  assert.match(page,/Historical replay/);
  assert.match(await (await app.fetch(new Request('https://replay.example/sitemap.xml'))).text(),/https:\/\/replay.example\/site\//);
});
