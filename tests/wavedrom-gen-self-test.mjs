#!/usr/bin/env node

import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const skillDirectory = path.join(repositoryRoot, 'wavedrom-gen');
const server = path.join(skillDirectory, 'scripts', 'mcp-server.mjs');
const register = path.join(skillDirectory, 'scripts', 'register-mcp.mjs');
const outputDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'wavedrom-gen-self-test-'));
const source = "{ signal: [{ name: 'clk', wave: 'p.....' }, { name: 'valid', wave: '01..0.' }, { name: 'ready', wave: '0.1...' }, { name: 'data', wave: 'x.=..x', data: ['0x2A'] }] }";

function exchange(messages) {
  const input = `${messages.map((message) => JSON.stringify(message)).join('\n')}\n`;
  const child = spawnSync(process.execPath, [server, '--stdio'], {
    input,
    encoding: 'utf8',
    windowsHide: true,
    maxBuffer: 16 * 1024 * 1024,
  });
  assert.equal(child.status, 0, child.stderr || child.stdout);
  return child.stdout.trim().split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
}

try {
  const generic = spawnSync(process.execPath, [register, '--agent', 'generic'], { encoding: 'utf8', windowsHide: true });
  assert.equal(generic.status, 0, generic.stderr);
  const genericConfig = JSON.parse(generic.stdout);
  assert.equal(genericConfig.mcpServers['wavedrom-gen'].command, process.execPath);
  assert.equal(path.resolve(genericConfig.mcpServers['wavedrom-gen'].args[0]), server);

  for (const args of [
    ['--agent', 'codex', '--dry-run'],
    ['--agent', 'claude-code', '--scope', 'user', '--dry-run'],
  ]) {
    const dryRun = spawnSync(process.execPath, [register, ...args], { encoding: 'utf8', windowsHide: true });
    assert.equal(dryRun.status, 0, dryRun.stderr);
    assert.match(dryRun.stdout, /mcp add/);
    assert.match(dryRun.stdout, /mcp-server\.mjs/);
  }

  const responses = exchange([
    { jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'self-test', version: '1.0.0' } } },
    { jsonrpc: '2.0', method: 'notifications/initialized' },
    { jsonrpc: '2.0', id: 2, method: 'tools/list', params: {} },
    { jsonrpc: '2.0', id: 3, method: 'tools/call', params: { name: 'wavedrom_validate', arguments: { source, strict: true } } },
    { jsonrpc: '2.0', id: 4, method: 'tools/call', params: { name: 'wavedrom_render', arguments: { source, outputDirectory, baseName: 'handshake', formats: ['svg', 'png', 'html'], strict: true } } },
  ]);

  assert.equal(responses.length, 4);
  assert.deepEqual(responses[1].result.tools.map((tool) => tool.name), ['wavedrom_help', 'wavedrom_validate', 'wavedrom_render']);
  assert.equal(responses[2].result.structuredContent.valid, true);
  assert.equal(responses[3].result.structuredContent.rendered, true);
  for (const extension of ['json5', 'svg', 'png', 'html']) {
    const artifact = path.join(outputDirectory, `handshake.${extension}`);
    assert.ok(fs.existsSync(artifact), `Missing ${artifact}`);
    assert.ok(fs.statSync(artifact).size > 0, `Empty ${artifact}`);
  }

  const negative = exchange([
    { jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'self-test', version: '1.0.0' } } },
    { jsonrpc: '2.0', id: 2, method: 'tools/call', params: { name: 'wavedrom_validate', arguments: { source: "{ signal: [{ name: 'bad', wave: '0?' }] }" } } },
    { jsonrpc: '2.0', id: 3, method: 'tools/call', params: { name: 'wavedrom_render', arguments: { source, outputDirectory, baseName: 'handshake', formats: ['svg'] } } },
  ]);
  assert.equal(negative[1].result.isError, true);
  assert.equal(negative[2].result.isError, true);
  console.log('wavedrom-gen self-test passed');
} finally {
  fs.rmSync(outputDirectory, { recursive: true, force: true });
}
