#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);

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

function globalModuleRoots() {
  const scriptDir = path.dirname(fileURLToPath(import.meta.url));
  const roots = [
    path.resolve(scriptDir, '..', 'node_modules'),
    path.resolve(scriptDir, '..', '..', 'node_modules'),
  ];
  if (process.platform === 'win32' && process.env.APPDATA) {
    roots.push(path.join(process.env.APPDATA, 'npm', 'node_modules'));
  }
  try {
    const npmCli = path.join(path.dirname(process.execPath), 'node_modules', 'npm', 'bin', 'npm-cli.js');
    const root = fs.existsSync(npmCli)
      ? execFileSync(process.execPath, [npmCli, 'root', '-g'], { encoding: 'utf8' }).trim()
      : execFileSync('npm', ['root', '-g'], { encoding: 'utf8' }).trim();
    if (root) roots.push(root);
  } catch {
    // The conventional roots above may still resolve the dependency.
  }
  return [...new Set(roots)];
}

function loadJson5() {
  try {
    return require('json5');
  } catch {
    // Continue with the global wavedrom-cli dependency.
  }
  try {
    for (const root of globalModuleRoots()) {
    const candidates = [
      path.join(root, 'json5'),
      path.join(root, 'wavedrom-cli', 'node_modules', 'json5'),
    ];
    for (const candidate of candidates) {
      if (fs.existsSync(candidate)) return require(candidate);
    }
    }
  } catch {
    // Fall through to strict JSON parsing.
  }
  return { parse: JSON.parse };
}

function labelCount(data) {
  if (Array.isArray(data)) return data.length;
  if (typeof data === 'string') return data.trim() ? data.trim().split(/\s+/).length : 0;
  return 0;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log(usage());
    return 0;
  }
  if (!args.input) throw new Error(usage());

  const input = path.resolve(args.input);
  const report = { input, errors: [], warnings: [], counts: { lanes: 0, dataBoxes: 0, nodes: 0, edges: 0 } };
  if (!fs.existsSync(input)) {
    report.errors.push(`Input file does not exist: ${input}`);
    console.log(JSON.stringify(report, null, 2));
    return 1;
  }

  let source;
  try {
    source = loadJson5().parse(fs.readFileSync(input, 'utf8'));
  } catch (error) {
    report.errors.push(`JSON5 parse failed: ${error.message}`);
    console.log(JSON.stringify(report, null, 2));
    return 1;
  }

  if (!source || typeof source !== 'object' || Array.isArray(source)) {
    report.errors.push('The top level must be a WaveJSON object.');
  }
  if (!Array.isArray(source?.signal)) {
    report.errors.push('A timing diagram requires a top-level signal array.');
  }

  const nodes = new Set();
  const legalWave = /^[01.zx=ud2-9pPnNhHlL|]*$/;

  function validateLane(lane, location) {
    if (Array.isArray(lane)) {
      if (typeof lane[0] !== 'string' || lane[0].trim() === '') {
        report.errors.push(`${location}: a group must begin with a non-empty name.`);
      }
      lane.slice(1).forEach((child, index) => validateLane(child, `${location}[${index + 1}]`));
      return;
    }
    if (!lane || typeof lane !== 'object') {
      report.errors.push(`${location}: lane must be an object, spacer, or named group.`);
      return;
    }
    if (Object.keys(lane).length === 0) return;

    report.counts.lanes += 1;
    if (lane.wave !== undefined) {
      if (typeof lane.wave !== 'string') {
        report.errors.push(`${location}.wave must be a string.`);
      } else {
        if (!legalWave.test(lane.wave)) {
          const invalid = [...new Set([...lane.wave].filter((char) => !legalWave.test(char)))];
          report.errors.push(`${location}.wave contains unsupported characters: ${invalid.join(' ')}`);
        }
        const boxes = [...lane.wave].filter((char) => char === '=' || /[2-9]/.test(char)).length;
        report.counts.dataBoxes += boxes;
        const labels = labelCount(lane.data);
        if (labels < boxes) report.errors.push(`${location}: ${boxes} data boxes need labels, but only ${labels} were supplied.`);
        if (labels > boxes) report.warnings.push(`${location}: ${labels - boxes} extra data label(s) will not be consumed.`);
      }
      if (lane.name === undefined) report.warnings.push(`${location}: waveform lane has no name.`);
    } else if (lane.node === undefined) {
      report.warnings.push(`${location}: non-empty lane has neither wave nor node.`);
    }

    if (lane.node !== undefined) {
      if (typeof lane.node !== 'string') {
        report.errors.push(`${location}.node must be a string.`);
      } else {
        for (const marker of lane.node) {
          if (marker === '.' || /\s/.test(marker)) continue;
          if (!/[A-Za-z0-9]/.test(marker)) {
            report.errors.push(`${location}.node contains unsupported marker: ${marker}`);
          } else if (nodes.has(marker)) {
            report.errors.push(`${location}.node reuses node marker: ${marker}`);
          } else {
            nodes.add(marker);
          }
        }
      }
    }
  }

  if (Array.isArray(source?.signal)) {
    source.signal.forEach((lane, index) => validateLane(lane, `signal[${index}]`));
  }
  report.counts.nodes = nodes.size;

  if (source?.edge !== undefined && !Array.isArray(source.edge)) {
    report.errors.push('edge must be an array of strings.');
  }
  if (Array.isArray(source?.edge)) {
    report.counts.edges = source.edge.length;
    source.edge.forEach((edge, index) => {
      if (typeof edge !== 'string') {
        report.errors.push(`edge[${index}] must be a string.`);
        return;
      }
      const expression = edge.trim().split(/\s+/, 1)[0];
      const endpoints = expression.match(/[A-Za-z0-9]/g) ?? [];
      if (endpoints.length < 2) {
        report.warnings.push(`edge[${index}] endpoint syntax could not be checked: ${edge}`);
        return;
      }
      const from = endpoints[0];
      const to = endpoints[endpoints.length - 1];
      if (!nodes.has(from)) report.errors.push(`edge[${index}] references missing node: ${from}`);
      if (!nodes.has(to)) report.errors.push(`edge[${index}] references missing node: ${to}`);
    });
  }

  if (source?.config?.hscale !== undefined) {
    if (!Number.isInteger(source.config.hscale) || source.config.hscale <= 0) {
      report.errors.push('config.hscale must be a positive integer.');
    }
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
