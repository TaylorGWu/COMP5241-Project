import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { test } from 'node:test';

// A localhost page must not send credentialed requests to 127.0.0.1:
// SameSite=Lax cookies would be excluded even with credentials: include.
function bases(hostname, configured) {
  const env = { ...process.env };
  delete env.NEXT_PUBLIC_API_BASE;
  if (configured !== undefined) env.NEXT_PUBLIC_API_BASE = configured;
  const code = `globalThis.window = {location: {hostname: ${JSON.stringify(hostname)}, port: '3000'}};
    const {AUTH_API_BASE} = await import('./lib/auth.ts');
    const {API_BASE} = await import('./lib/api.ts');
    process.stdout.write(JSON.stringify([AUTH_API_BASE, API_BASE]));`;
  return JSON.parse(execFileSync(process.execPath, ['--experimental-strip-types', '--input-type=module', '-e', code], {
    cwd: new URL('..', import.meta.url), env, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'],
  }));
}

for (const [hostname, expected] of [
  ['localhost', 'http://localhost:8000'],
  ['127.0.0.1', 'http://127.0.0.1:8000'],
]) {
  test(`auth, media and exports share the page's loopback site on ${hostname}`, () => {
    assert.deepEqual(bases(hostname), [expected, expected]);
  });
}

test('explicit deployment API configuration is not rewritten', () => {
  assert.deepEqual(bases('localhost', 'https://api.example.test'), ['https://api.example.test', 'https://api.example.test']);
});
