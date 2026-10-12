#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const server = path.join(scriptDir, 'mcp-server.mjs');
const serverArgs = [server, '--stdio'];

function usage() {
  return [
    'Usage: node scripts/register-mcp.mjs --agent <codex|claude-code|generic> [options]',
    '',
    'Options:',
    '  --scope <local|project|user>  Claude Code scope (default: user)',
    '  --dry-run                     Print the registration command only',
    '  --force                       Replace an existing registration',
    '  --help                        Show this help',
  ].join('\n');
}

function parseArgs(argv) {
  const options = { scope: 'user', dryRun: false, force: false };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === '--agent') options.agent = argv[++index];
    else if (token === '--scope') options.scope = argv[++index];
    else if (token === '--dry-run') options.dryRun = true;
    else if (token === '--force') options.force = true;
    else if (token === '--help' || token === '-h') options.help = true;
    else throw new Error(`Unknown argument: ${token}\n${usage()}`);
  }
  return options;
}

function quote(value) {
  const text = String(value);
  if (/^[A-Za-z0-9_./:=+-]+$/.test(text)) return text;
  return `"${text.replaceAll('"', '\\"')}"`;
}

function commandLine(command, args) {
  return [command, ...args].map(quote).join(' ');
}

function run(command, args, { allowFailure = false, capture = false } = {}) {
  const child = spawnSync(command, args, {
    encoding: 'utf8',
    windowsHide: true,
    stdio: capture ? 'pipe' : 'inherit',
  });
  if (child.error) throw new Error(`Could not launch ${command}: ${child.error.message}`);
  if (!allowFailure && child.status !== 0) {
    throw new Error(`${command} exited with code ${child.status}.`);
  }
  return child;
}

function registrationExists(command) {
  return run(command, ['mcp', 'get', 'wavedrom-gen'], { allowFailure: true, capture: true }).status === 0;
}

function replaceIfNeeded(command, options) {
  if (!registrationExists(command)) return;
  if (!options.force) {
    throw new Error('An MCP server named wavedrom-gen is already registered. Re-run with --force only if replacement is intentional.');
  }
  run(command, ['mcp', 'remove', 'wavedrom-gen']);
}

function registerCodex(options) {
  const args = ['mcp', 'add', 'wavedrom-gen', '--', process.execPath, ...serverArgs];
  if (options.dryRun) return console.log(commandLine('codex', args));
  replaceIfNeeded('codex', options);
  run('codex', args);
  console.log('Registered wavedrom-gen with Codex.');
}

function registerClaude(options) {
  if (!['local', 'project', 'user'].includes(options.scope)) {
    throw new Error('--scope must be local, project, or user for Claude Code.');
  }
  const args = ['mcp', 'add', '--scope', options.scope, 'wavedrom-gen', '--', process.execPath, ...serverArgs];
  if (options.dryRun) return console.log(commandLine('claude', args));
  replaceIfNeeded('claude', options);
  run('claude', args);
  console.log(`Registered wavedrom-gen with Claude Code at ${options.scope} scope.`);
}

function printGeneric() {
  console.log(JSON.stringify({
    mcpServers: {
      'wavedrom-gen': {
        command: process.execPath,
        args: serverArgs,
      },
    },
  }, null, 2));
}

function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) return console.log(usage());
  if (!fs.existsSync(server)) throw new Error(`MCP server was not found: ${server}`);
  if (options.agent === 'codex') return registerCodex(options);
  if (options.agent === 'claude-code') return registerClaude(options);
  if (options.agent === 'generic') return printGeneric();
  throw new Error(`--agent must be codex, claude-code, or generic.\n${usage()}`);
}

try {
  main();
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
