#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { loadOfficialWaveDrom, renderOfficialSvg } from './wavedrom-engine.mjs';

const require = createRequire(import.meta.url);
const JSON5 = require('json5');
const { validateDatasheetConfig } = require('./datasheet-annotations.cjs');
const { lintModel } = require('./wavejson-lint.cjs');

function parseArgs(argv) {
  const args = { strict: false };
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (token === '--input' || token === '-i') args.input = argv[++i];
    else if (token === '--strict') args.strict = true;
    else if (token === '--help' || token === '-h') args.help = true;
    else throw new Error(`Unknown argument: ${token}`);
  }
  return args;
}

function usage() {
  return 'Usage: node validate-wavejson.mjs --input <diagram.json5> [--strict]';
}

function emptyReport(input) {
  let engine = { name: 'wavedrom', version: null, officialRenderValid: false, skins: [] };
  try {
    const official = loadOfficialWaveDrom();
    engine = { name: 'wavedrom', version: official.version, officialRenderValid: false, skins: official.skinNames };
  } catch {
    // The actionable dependency error is reported by the official render probe.
  }
  return {
    input,
    diagramType: 'unknown',
    engine,
    errors: [],
    warnings: [],
    counts: { lanes: 0, dataBoxes: 0, nodes: 0, edges: 0, annotations: 0, assignments: 0, registerFields: 0 },
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log(usage());
    return 0;
  }
  if (!args.input) throw new Error(usage());

  const input = path.resolve(args.input);
  const report = emptyReport(input);
  if (!fs.existsSync(input)) {
    report.errors.push(`Input file does not exist: ${input}`);
    console.log(JSON.stringify(report, null, 2));
    return 1;
  }

  let source;
  try {
    source = JSON5.parse(fs.readFileSync(input, 'utf8'));
  } catch (error) {
    report.errors.push(`JSON5 parse failed: ${error.message}`);
    console.log(JSON.stringify(report, null, 2));
    return 1;
  }

  const lint = lintModel(source, validateDatasheetConfig);
  report.diagramType = lint.diagramType;
  report.errors.push(...lint.errors);
  report.warnings.push(...lint.warnings);
  report.counts = lint.counts;

  try {
    const rendered = renderOfficialSvg(source);
    report.engine.version = rendered.version;
    report.engine.skins = rendered.skinNames;
    report.engine.officialRenderValid = true;
    report.diagramType = rendered.diagramType;
  } catch (error) {
    report.errors.push(`Official wavedrom render failed: ${error.message}`);
  }

  console.log(JSON.stringify(report, null, 2));
  if (report.errors.length > 0) return 1;
  if (args.strict && report.warnings.length > 0) return 2;
  return 0;
}

try {
  process.exitCode = main();
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
