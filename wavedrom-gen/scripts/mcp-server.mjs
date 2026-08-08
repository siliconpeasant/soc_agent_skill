#!/usr/bin/env node

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const SERVER_VERSION = '0.3.0';
const MAX_SOURCE_BYTES = 2 * 1024 * 1024;
const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const pluginRoot = path.resolve(scriptDir, '..');
const nestedSkillRoot = path.join(pluginRoot, 'skills', 'wavedrom-gen');
const skillRoot = fs.existsSync(path.join(pluginRoot, 'SKILL.md')) ? pluginRoot : nestedSkillRoot;
const validator = path.join(skillRoot, 'scripts', 'validate-wavejson.mjs');
const renderer = path.join(skillRoot, 'scripts', 'render-wavedrom.mjs');

const tools = [
  {
    name: 'wavedrom_help',
    title: 'WaveDrom generation help',
    description: 'Return versioned guidance for official WaveDrom signal, edge, skin, assign, reg, and optional Datasheet syntax.',
    inputSchema: {
      type: 'object',
      properties: {
        topic: {
          type: 'string',
          enum: ['overview', 'signal', 'edges', 'skins', 'assign', 'reg', 'datasheet'],
          default: 'overview',
        },
      },
      additionalProperties: false,
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  },
  {
    name: 'wavedrom_validate',
    title: 'Validate WaveJSON',
    description: 'Parse WaveJSON/JSON5, probe it with the pinned official wavedrom engine, and return non-blocking quality lint unless strict mode is requested.',
    inputSchema: {
      type: 'object',
      properties: {
        source: { type: 'string', description: 'Complete WaveJSON or JSON5 source text.' },
        strict: { type: 'boolean', default: false, description: 'Treat warnings as a failed validation.' },
      },
      required: ['source'],
      additionalProperties: false,
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  },
  {
    name: 'wavedrom_render',
    title: 'Render WaveDrom diagram',
    description: 'Validate WaveJSON, preserve its JSON5 source, render with the pinned official wavedrom main package, and optionally add Datasheet-grade timing dimensions to SVG, PNG, and offline HTML.',
    inputSchema: {
      type: 'object',
      properties: {
        source: { type: 'string', description: 'Complete WaveJSON or JSON5 source text.' },
        outputDirectory: { type: 'string', description: 'Absolute destination directory.' },
        baseName: { type: 'string', default: 'wavedrom-diagram', description: 'Portable filename stem without an extension.' },
        formats: {
          type: 'array',
          items: { type: 'string', enum: ['svg', 'png', 'html'] },
          uniqueItems: true,
          default: ['svg'],
        },
        strict: { type: 'boolean', default: false, description: 'Treat validation warnings as errors.' },
        overwrite: { type: 'boolean', default: false, description: 'Allow replacement of existing target files.' },
      },
      required: ['source', 'outputDirectory'],
      additionalProperties: false,
    },
    annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: false },
  },
];

function ensureSource(value) {
  if (typeof value !== 'string' || value.trim() === '') throw new Error('source must be a non-empty string.');
  if (Buffer.byteLength(value, 'utf8') > MAX_SOURCE_BYTES) throw new Error('source exceeds the 2 MiB limit.');
  return value;
}

function parseJson(text, context) {
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new Error(`${context} did not return JSON: ${error.message}`);
  }
}

function runNode(script, args) {
  const child = spawnSync(process.execPath, [script, ...args], {
    encoding: 'utf8',
    windowsHide: true,
    maxBuffer: 8 * 1024 * 1024,
  });
  return { status: child.status ?? 1, stdout: child.stdout ?? '', stderr: child.stderr ?? '' };
}

function validateSource(source, strict = false) {
  ensureSource(source);
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'wavedrom-gen-'));
  const input = path.join(tempDir, 'input.json5');
  try {
    fs.writeFileSync(input, source, 'utf8');
    const args = ['--input', input];
    if (strict) args.push('--strict');
    const result = runNode(validator, args);
    const report = parseJson(result.stdout, 'Validator');
    return {
      valid: result.status === 0,
      strict: Boolean(strict),
      diagramType: report.diagramType ?? 'unknown',
      engine: report.engine ?? {},
      errors: report.errors ?? [],
      warnings: report.warnings ?? [],
      counts: report.counts ?? {},
      exitCode: result.status,
    };
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
}

function help(topic = 'overview') {
  const common = {
    format: 'WaveJSON / JSON5',
    officialEngine: { package: 'wavedrom', version: '3.6.2' },
    compatibility: 'Inputs accepted by the pinned official renderAny engine are preserved and rendered. Strict mode adds optional quality lint.',
    supportedDiagramTypes: ['signal', 'assign', 'reg'],
    outputs: ['json5', 'svg', 'png', 'html'],
  };
  const topics = {
    overview: {
      workflow: [
        'For timing diagrams, extract clock domains, active edges, initial states, ordered events, latencies, transfer conditions, and assumptions.',
        'Generate a top-level signal array and use official WaveJSON syntax without inventing a parallel schema.',
        'Call wavedrom_validate, fix hard errors, review warnings, then call wavedrom_render.',
        'Treat official rendering as syntax compatibility proof, then review the picture against the timing contract.',
      ],
      minimalExample: "{ signal: [{ name: 'clk', wave: 'p....' }, { name: 'data', wave: 'x.=.x', data: ['A'] }] }",
    },
    signal: {
      waveCharacters: { '0/1': 'logic levels', 'x': 'unknown', 'z': 'high impedance', '.': 'extend previous state', '= or 2-9': 'labeled data boxes', 'p/P/n/N/h/H/l/L': 'clock forms and marked edges', 'u/d': 'pull transition states', '|': 'gap', '<...>': 'sub-cycle region' },
      laneFields: ['name', 'wave', 'data', 'node', 'period', 'phase'],
      topLevel: ['signal', 'edge', 'head', 'foot', 'config'],
      groups: "Use ['group name', lane, nested-group, ...]; use {} as a spacer.",
    },
    edges: {
      syntax: '<from><shape><to> optional label',
      shapes: ['-', '~', '-~', '~-', '-|', '|-', '-|-', '->', '~>', '-~>', '~->', '-|>', '|->', '-|->', '<->', '<~>', '<-~>', '<-|>', '<-|->', '+'],
      note: 'Endpoints are one-character node markers placed in lane.node strings.',
    },
    skins: {
      syntax: "config: { skin: 'default' }",
      available: ['default', 'narrow', 'dark', 'lowkey', 'narrower', 'narrowerer'],
      otherConfig: ['hscale', 'hbounds', 'arcFontSize'],
    },
    assign: {
      example: "{ assign: [['z', ['&', 'a', ['~', 'b']]]] }",
      note: 'Logic diagrams are passed directly to the official logidrom-backed renderer.',
    },
    reg: {
      example: "{ reg: [{ bits: 7, name: 0x37, attr: ['OPIVI'] }, { bits: 5, name: 'vd', type: 2 }], config: { lanes: 1, bits: 12 } }",
      note: 'Register diagrams are passed directly to the official bit-field-backed renderer.',
    },
    datasheet: {
      note: 'datasheet is a wavedrom-gen extension for signal diagrams only and is disabled unless explicitly present.',
      example: "datasheet: { annotations: [{ from: 'a', to: 'b', label: 'T_SETUP', kind: 'setup', placement: 'above' }] }",
      kinds: ['setup', 'hold', 'width', 'period', 'generic'],
    },
  };
  return { ...common, topic, ...(topics[topic] ?? topics.overview) };
}

function renderDiagram(args) {
  const source = ensureSource(args.source);
  if (typeof args.outputDirectory !== 'string' || !path.isAbsolute(args.outputDirectory)) {
    throw new Error('outputDirectory must be an absolute path.');
  }
  const outputDirectory = path.resolve(args.outputDirectory);
  const baseName = args.baseName ?? 'wavedrom-diagram';
  if (typeof baseName !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/.test(baseName)) {
    throw new Error('baseName must be 1-80 portable characters: letters, digits, dot, underscore, or hyphen.');
  }
  const requested = args.formats ?? ['svg'];
  if (!Array.isArray(requested) || requested.length === 0 || requested.some((item) => !['svg', 'png', 'html'].includes(item))) {
    throw new Error('formats must be a non-empty subset of svg, png, and html.');
  }
  const formats = [...new Set(['svg', ...requested])];
  const files = {
    source: path.join(outputDirectory, `${baseName}.json5`),
    svg: path.join(outputDirectory, `${baseName}.svg`),
  };
  if (formats.includes('png')) files.png = path.join(outputDirectory, `${baseName}.png`);
  if (formats.includes('html')) files.html = path.join(outputDirectory, `${baseName}.html`);
  const existing = Object.values(files).filter((file) => fs.existsSync(file));
  if (existing.length && args.overwrite !== true) {
    throw new Error(`Refusing to overwrite existing files: ${existing.join(', ')}`);
  }

  const validation = validateSource(source, args.strict === true);
  if (!validation.valid) return { rendered: false, validation };

  fs.mkdirSync(outputDirectory, { recursive: true });
  fs.writeFileSync(files.source, source, 'utf8');
  const renderArgs = ['--input', files.source, '--svg', files.svg];
  if (files.png) renderArgs.push('--png', files.png);
  if (files.html) renderArgs.push('--html', files.html);
  if (args.strict === true) renderArgs.push('--strict');
  const result = runNode(renderer, renderArgs);
  if (result.status !== 0) {
    throw new Error(`Renderer failed with exit code ${result.status}: ${(result.stderr || result.stdout).trim()}`);
  }
  const rendered = parseJson(result.stdout, 'Renderer');
  return {
    rendered: true,
    validation,
    requestedFormats: [...new Set(requested)],
    generatedFormats: formats,
    diagramType: rendered.diagramType,
    engine: rendered.engine,
    files,
    bytes: {
      source: fs.statSync(files.source).size,
      svg: rendered.svgBytes,
      ...(files.png ? { png: rendered.pngBytes } : {}),
      ...(files.html ? { html: rendered.htmlBytes } : {}),
    },
    datasheetAnnotations: rendered.datasheetAnnotations ?? 0,
  };
}

function toolResult(value, isError = false) {
  return {
    content: [{ type: 'text', text: JSON.stringify(value, null, 2) }],
    structuredContent: value,
    ...(isError ? { isError: true } : {}),
  };
}

function callTool(name, args = {}) {
  try {
    if (name === 'wavedrom_help') return toolResult(help(args.topic));
    if (name === 'wavedrom_validate') {
      const report = validateSource(args.source, args.strict === true);
      return toolResult(report, !report.valid);
    }
    if (name === 'wavedrom_render') {
      const result = renderDiagram(args);
      return toolResult(result, !result.rendered);
    }
    return toolResult({ error: `Unknown tool: ${name}` }, true);
  } catch (error) {
    return toolResult({ error: error.message }, true);
  }
}

function send(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

function success(id, result) {
  send({ jsonrpc: '2.0', id, result });
}

function failure(id, code, message) {
  send({ jsonrpc: '2.0', id: id ?? null, error: { code, message } });
}

function handle(message) {
  if (!message || message.jsonrpc !== '2.0' || typeof message.method !== 'string') {
    if (message?.id !== undefined) failure(message.id, -32600, 'Invalid Request');
    return;
  }
  const hasId = message.id !== undefined;
  if (message.method === 'initialize') {
    if (!hasId) return;
    success(message.id, {
      protocolVersion: message.params?.protocolVersion ?? '2025-03-26',
      capabilities: { tools: { listChanged: false } },
      serverInfo: { name: 'wavedrom-gen', version: SERVER_VERSION },
      instructions: 'Use wavedrom_help for syntax guidance, wavedrom_validate before rendering, and wavedrom_render for file artifacts.',
    });
    return;
  }
  if (message.method === 'notifications/initialized' || message.method === 'notifications/cancelled') return;
  if (!hasId) return;
  if (message.method === 'ping') return success(message.id, {});
  if (message.method === 'tools/list') return success(message.id, { tools });
  if (message.method === 'tools/call') {
    const name = message.params?.name;
    if (typeof name !== 'string') return failure(message.id, -32602, 'tools/call requires params.name.');
    return success(message.id, callTool(name, message.params?.arguments ?? {}));
  }
  failure(message.id, -32601, `Method not found: ${message.method}`);
}

let buffer = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => {
  buffer += chunk;
  let newline;
  while ((newline = buffer.indexOf('\n')) >= 0) {
    const line = buffer.slice(0, newline).trim();
    buffer = buffer.slice(newline + 1);
    if (!line) continue;
    try {
      handle(JSON.parse(line));
    } catch (error) {
      failure(null, -32700, `Parse error: ${error.message}`);
    }
  }
});
process.stdin.on('end', () => {
  const line = buffer.trim();
  if (!line) return;
  try {
    handle(JSON.parse(line));
  } catch (error) {
    failure(null, -32700, `Parse error: ${error.message}`);
  }
});
