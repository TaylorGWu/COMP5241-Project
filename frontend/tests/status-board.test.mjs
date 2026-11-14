import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire, Module } from 'node:module';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

// Transpile the real TSX and its actual UI primitive dependency, not a mock.
export function loadStatusBoard() {
  const require = createRequire(import.meta.url);
  function load(relative) {
    const path = fileURLToPath(new URL(relative, import.meta.url));
    const compiled = ts.transpileModule(readFileSync(path, 'utf8'), { compilerOptions: {
      jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
    }}).outputText;
    const compiledModule = new Module(path);
    compiledModule.filename = path;
    compiledModule.require = name => name === '@/components/ui' ? load('../components/ui.tsx') : require(name);
    compiledModule._compile(compiled, path);
    return compiledModule.exports;
  }
  return load('../components/StatusBoard.tsx');
}

test('renders explicit status and group order without inventing completion', () => {
  const { StatusBoard } = loadStatusBoard();
  const html = renderToStaticMarkup(React.createElement(StatusBoard, { groups: [
    { title: 'Must', items: [{ label: 'Editing', status: 'complete' }, { label: 'PDF', status: 'partial' }] },
    { title: 'Student', items: [{ label: 'Acceptance', status: 'unverified' }] },
    { title: 'Won’t', items: [{ label: 'Payments', status: 'excluded' }] },
  ] }));
  assert.equal((html.match(/<section/g) ?? []).length, 3);
  assert.equal((html.match(/<li /g) ?? []).length, 4);
  assert.ok(html.indexOf('Must') < html.indexOf('Student'));
  for (const value of ['Complete', 'Partial', 'To confirm', 'Out of scope']) assert.ok(html.includes(value));
  assert.ok(!html.includes('100%'));
});

test('group and item text is escaped rather than interpreted as HTML', () => {
  const { StatusBoard } = loadStatusBoard();
  const html = renderToStaticMarkup(React.createElement(StatusBoard, { groups: [
    { title: '<script>', items: [{ label: '<img onerror=bad>', status: 'unverified' }] },
  ] }));
  assert.ok(!html.includes('<script>'));
  assert.ok(!html.includes('<img '));
  assert.ok(html.includes('&lt;img'));
});
