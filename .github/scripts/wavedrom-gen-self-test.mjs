#!/usr/bin/env node

import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const skillDirectory = path.join(repositoryRoot, 'wavedrom-gen');
const server = path.join(skillDirectory, 'scripts', 'mcp-server.mjs');
const register = path.join(skillDirectory, 'scripts', 'register-mcp.mjs');
const outputDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'wavedrom-gen-self-test-'));
const source = "{ signal: [{ name: 'clk', wave: '0..1..', node: '...c..' }, { name: 'valid', wave: '01..0.', node: '.v....' }, { name: 'ready', wave: '0.1...', node: '..r...' }, { name: 'data', wave: 'x.=..x', data: ['0x2A'], node: '..d...' }], datasheet: { annotations: [{ from: 'd', to: 'c', label: 'T_SETUP', kind: 'setup' }] } }";
const officialSignalSource = `{
  signal: [
    ['Protocol',
      { name: 'clk', wave: 'p.....|..', node: '.a...b...' },
      { name: 'sub', wave: '=2<10zuzd1x.1>2', data: ['A', 'B', 'C'], period: 2 },
      { name: 'data', wave: 'x.3..4.x.', data: ['ADDR', 'DATA'], node: '..c..d...' },
    ],
    {},
    { name: 'done', wave: '0....1.0.', node: '.....e...' },
  ],
  edge: ['a-b', 'a~b', 'a-~b', 'a~-b', 'a-|b', 'a|-b', 'a-|-b', 'a->b', 'a~>b', 'a-~>b', 'a~->b', 'a-|>b', 'a|->b', 'a-|->b', 'a<->b', 'a<~>b', 'a<-~>b', 'a<-|>b', 'a<-|->b', 'a+b'],
  head: { tick: 0, every: 2, text: ['tspan', ['tspan', { class: 'h2' }, 'Official '], ['tspan', { class: 'info' }, 'syntax']] },
  foot: { tock: 0, text: 'wavedrom@3.6.2' },
  config: { hscale: 2, hbounds: [0, 8], skin: 'narrowerer', arcFontSize: 12 },
}`;
const officialAssignSource = "{ assign: [['z', ['~&', ['~^', ['~', 'p0'], ['~', 'q0']], ['~', 'enable']]]] }";
const officialRegSource = "{ reg: [{ bits: 7, name: 0x37, attr: ['OPIVI'] }, { bits: 5, name: 'vd', type: 2 }, { bits: 3, name: 3 }, { bits: 5, name: 'simm5', type: 5 }], config: { lanes: 1, bits: 20 } }";

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
    { jsonrpc: '2.0', id: 3, method: 'tools/call', params: { name: 'wavedrom_help', arguments: { topic: 'edges' } } },
    { jsonrpc: '2.0', id: 4, method: 'tools/call', params: { name: 'wavedrom_validate', arguments: { source, strict: true } } },
    { jsonrpc: '2.0', id: 5, method: 'tools/call', params: { name: 'wavedrom_render', arguments: { source, outputDirectory, baseName: 'handshake', formats: ['svg', 'png', 'html'], strict: true } } },
    { jsonrpc: '2.0', id: 6, method: 'tools/call', params: { name: 'wavedrom_validate', arguments: { source: officialSignalSource, strict: true } } },
    { jsonrpc: '2.0', id: 7, method: 'tools/call', params: { name: 'wavedrom_validate', arguments: { source: officialAssignSource, strict: true } } },
    { jsonrpc: '2.0', id: 8, method: 'tools/call', params: { name: 'wavedrom_validate', arguments: { source: officialRegSource, strict: true } } },
  ]);

  assert.equal(responses.length, 8);
  assert.deepEqual(responses[1].result.tools.map((tool) => tool.name), ['wavedrom_help', 'wavedrom_validate', 'wavedrom_render']);
  assert.equal(responses[2].result.structuredContent.topic, 'edges');
  assert.ok(responses[2].result.structuredContent.shapes.includes('<-|->'));
  assert.equal(responses[3].result.structuredContent.valid, true);
  assert.equal(responses[3].result.structuredContent.engine.version, '3.6.2');
  assert.equal(responses[3].result.structuredContent.counts.annotations, 1);
  assert.equal(responses[4].result.structuredContent.rendered, true);
  assert.equal(responses[4].result.structuredContent.engine.version, '3.6.2');
  assert.equal(responses[4].result.structuredContent.datasheetAnnotations, 1);
  assert.equal(responses[5].result.structuredContent.diagramType, 'signal');
  assert.equal(responses[5].result.structuredContent.valid, true);
  assert.equal(responses[6].result.structuredContent.diagramType, 'assign');
  assert.equal(responses[6].result.structuredContent.valid, true);
  assert.equal(responses[7].result.structuredContent.diagramType, 'reg');
  assert.equal(responses[7].result.structuredContent.valid, true);
  for (const extension of ['json5', 'svg', 'png', 'html']) {
    const artifact = path.join(outputDirectory, `handshake.${extension}`);
    assert.ok(fs.existsSync(artifact), `Missing ${artifact}`);
    assert.ok(fs.statSync(artifact).size > 0, `Empty ${artifact}`);
  }
  const svg = fs.readFileSync(path.join(outputDirectory, 'handshake.svg'), 'utf8');
  assert.match(svg, /id="datasheet-dimension-0"/);
  assert.match(svg, /baseline-shift="sub"/);
  const html = fs.readFileSync(path.join(outputDirectory, 'handshake.html'), 'utf8');
  assert.match(html, /WaveDromDatasheet/);

  for (const name of ['axi4-read-write', 'qspi-quad-io-read', 'async-fifo-cdc', 'a-pgm-mode-datasheet']) {
    const input = path.join(skillDirectory, 'examples', `${name}.json5`);
    const svgOutput = path.join(outputDirectory, `${name}.svg`);
    const exampleRender = spawnSync(process.execPath, [
      path.join(skillDirectory, 'scripts', 'render-wavedrom.mjs'),
      '--input', input,
      '--svg', svgOutput,
      '--strict',
    ], { encoding: 'utf8', windowsHide: true });
    assert.equal(exampleRender.status, 0, exampleRender.stderr || exampleRender.stdout);
    assert.ok(fs.existsSync(svgOutput), `Missing rendered example ${svgOutput}`);
    assert.ok(fs.statSync(svgOutput).size > 0, `Empty rendered example ${svgOutput}`);
  }

  for (const [name, diagramSource, expectedType] of [
    ['official-signal', officialSignalSource, 'signal'],
    ['official-assign', officialAssignSource, 'assign'],
    ['official-reg', officialRegSource, 'reg'],
  ]) {
    const typeResponses = exchange([
      { jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'self-test', version: '1.0.0' } } },
      { jsonrpc: '2.0', id: 2, method: 'tools/call', params: { name: 'wavedrom_render', arguments: { source: diagramSource, outputDirectory, baseName: name, formats: ['svg'], strict: true } } },
    ]);
    assert.equal(typeResponses[1].result.structuredContent.rendered, true);
    assert.equal(typeResponses[1].result.structuredContent.diagramType, expectedType);
    assert.match(fs.readFileSync(path.join(outputDirectory, `${name}.svg`), 'utf8'), /<svg\b/);
  }

  for (const skin of ['default', 'narrow', 'dark', 'lowkey', 'narrower', 'narrowerer']) {
    const skinInput = path.join(outputDirectory, `skin-${skin}.json5`);
    const skinOutput = path.join(outputDirectory, `skin-${skin}.svg`);
    fs.writeFileSync(skinInput, `{ signal: [{ name: 'clk', wave: 'p....' }], config: { skin: '${skin}' } }`, 'utf8');
    const skinRender = spawnSync(process.execPath, [
      path.join(skillDirectory, 'scripts', 'render-wavedrom.mjs'),
      '--input', skinInput,
      '--svg', skinOutput,
      '--strict',
    ], { encoding: 'utf8', windowsHide: true });
    assert.equal(skinRender.status, 0, skinRender.stderr || skinRender.stdout);
    assert.match(fs.readFileSync(skinOutput, 'utf8'), /<svg\b/);
  }

  const parityInput = path.join(outputDirectory, 'parity.json5');
  const parityOutput = path.join(outputDirectory, 'parity.svg');
  fs.writeFileSync(parityInput, "{ signal: [{ name: 'clk', wave: 'p....' }, { name: 'data', wave: 'x.3.x', data: ['D0'] }] }", 'utf8');
  const officialCli = spawnSync(process.execPath, [path.join(skillDirectory, 'node_modules', 'wavedrom', 'bin', 'cli.js'), '--input', parityInput], { encoding: 'utf8', windowsHide: true });
  assert.equal(officialCli.status, 0, officialCli.stderr || officialCli.stdout);
  const parityRender = spawnSync(process.execPath, [path.join(skillDirectory, 'scripts', 'render-wavedrom.mjs'), '--input', parityInput, '--svg', parityOutput, '--strict'], { encoding: 'utf8', windowsHide: true });
  assert.equal(parityRender.status, 0, parityRender.stderr || parityRender.stdout);
  assert.equal(fs.readFileSync(parityOutput, 'utf8').trim(), officialCli.stdout.trim());

  const negative = exchange([
    { jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'self-test', version: '1.0.0' } } },
    { jsonrpc: '2.0', id: 2, method: 'tools/call', params: { name: 'wavedrom_validate', arguments: { source: "{ signal: [{ name: 'bad', wave: '0?' }] }" } } },
    { jsonrpc: '2.0', id: 3, method: 'tools/call', params: { name: 'wavedrom_validate', arguments: { source: "{ signal: [{ name: 'bad', wave: '0?' }] }", strict: true } } },
    { jsonrpc: '2.0', id: 4, method: 'tools/call', params: { name: 'wavedrom_validate', arguments: { source: '{ foo: 1 }' } } },
    { jsonrpc: '2.0', id: 5, method: 'tools/call', params: { name: 'wavedrom_render', arguments: { source, outputDirectory, baseName: 'handshake', formats: ['svg'] } } },
  ]);
  assert.equal(negative[1].result.structuredContent.valid, true);
  assert.ok(negative[1].result.structuredContent.warnings.length > 0);
  assert.equal(negative[2].result.isError, true);
  assert.equal(negative[3].result.isError, true);
  assert.equal(negative[4].result.isError, true);
  console.log('wavedrom-gen self-test passed');
} finally {
  fs.rmSync(outputDirectory, { recursive: true, force: true });
}
