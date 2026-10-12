import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);

export const OFFICIAL_SKIN_NAMES = Object.freeze([
  'default',
  'narrow',
  'dark',
  'lowkey',
  'narrower',
  'narrowerer',
]);

function candidatePackageRoots() {
  const scriptDir = path.dirname(fileURLToPath(import.meta.url));
  const roots = [
    path.resolve(scriptDir, '..', 'node_modules', 'wavedrom'),
    path.resolve(scriptDir, '..', '..', 'node_modules', 'wavedrom'),
  ];
  if (process.platform === 'win32' && process.env.APPDATA) {
    roots.push(path.join(process.env.APPDATA, 'npm', 'node_modules', 'wavedrom'));
  }
  return [...new Set(roots)];
}

function resolvePackageDirectory() {
  try {
    return path.dirname(require.resolve('wavedrom/package.json'));
  } catch {
    const packageRoot = candidatePackageRoots().find((candidate) => fs.existsSync(path.join(candidate, 'package.json')));
    if (packageRoot) return packageRoot;
  }
  throw new Error('The official wavedrom package was not found. Run npm ci --omit=dev in the wavedrom-gen skill directory.');
}

let cached;

export function loadOfficialWaveDrom() {
  if (cached) return cached;
  const packageDirectory = resolvePackageDirectory();
  const packageJson = require(path.join(packageDirectory, 'package.json'));
  const api = require(packageDirectory);
  const skins = {};
  for (const name of OFFICIAL_SKIN_NAMES) {
    const skinPath = path.join(packageDirectory, 'skins', `${name}.js`);
    if (!fs.existsSync(skinPath)) throw new Error(`Official WaveDrom skin is missing: ${name}`);
    Object.assign(skins, require(skinPath));
  }
  cached = {
    api,
    packageDirectory,
    skins,
    version: packageJson.version,
    skinNames: [...OFFICIAL_SKIN_NAMES],
  };
  return cached;
}

export function classifyDiagram(source) {
  if (!source || typeof source !== 'object' || Array.isArray(source)) return 'unknown';
  if (source.signal) return 'signal';
  if (source.assign) return 'assign';
  if (source.reg) return 'reg';
  return 'unknown';
}

export function renderOfficialSvg(source, indent) {
  const engine = loadOfficialWaveDrom();
  const diagramType = classifyDiagram(source);
  if (diagramType === 'unknown') {
    throw new Error('Official WaveDrom requires one supported top-level diagram key: signal, assign, or reg.');
  }
  const tree = engine.api.renderAny(0, source, engine.skins, false);
  if (!Array.isArray(tree) || tree[0] !== 'svg') {
    throw new Error(`Official WaveDrom did not produce an SVG for diagram type: ${diagramType}`);
  }
  const svg = engine.api.onml.stringify(tree, indent);
  if (!/<svg\b/i.test(svg)) throw new Error('Official WaveDrom output does not contain an SVG root.');
  return {
    svg,
    diagramType,
    version: engine.version,
    skinNames: engine.skinNames,
  };
}
