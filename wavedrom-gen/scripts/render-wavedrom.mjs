#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { execFileSync, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (token === '--input' || token === '-i') args.input = argv[++i];
    else if (token === '--svg' || token === '-s') args.svg = argv[++i];
    else if (token === '--png' || token === '-p') args.png = argv[++i];
    else if (token === '--html') args.html = argv[++i];
    else if (token === '--strict') args.strict = true;
    else if (token === '--help' || token === '-h') args.help = true;
    else throw new Error(`Unknown argument: ${token}`);
  }
  return args;
}

function usage() {
  return 'Usage: node render-wavedrom.mjs --input <diagram.json5> --svg <diagram.svg> [--png <diagram.png>] [--html <diagram.html>] [--strict]';
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
    // The conventional roots above may still locate the CLI.
  }
  return [...new Set(roots)];
}

function resolveCli() {
  if (process.env.WAVEDROM_CLI_JS) {
    const explicit = path.resolve(process.env.WAVEDROM_CLI_JS);
    if (fs.existsSync(explicit)) return explicit;
  }
  try {
    for (const root of globalModuleRoots()) {
    const globalCli = path.join(root, 'wavedrom-cli', 'wavedrom-cli.js');
    if (fs.existsSync(globalCli)) return globalCli;
    }
  } catch {
    // Report a single actionable error below.
  }
  throw new Error('wavedrom-cli was not found. Install the official package with: npm install -g wavedrom-cli');
}

function assertOutput(filePath, kind) {
  if (!fs.existsSync(filePath)) throw new Error(`${kind} output was not created: ${filePath}`);
  const size = fs.statSync(filePath).size;
  if (size === 0) throw new Error(`${kind} output is empty: ${filePath}`);
  return size;
}

function escapeHtml(value) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function safeInlineScript(value) {
  return value.replace(/<\/script/gi, '<\\/script');
}

function resolveBrowserAssets(cliPath) {
  const packageDir = path.dirname(cliPath);
  const dependencyRoot = path.dirname(packageDir);
  const firstExisting = (candidates, kind) => {
    const match = candidates.find((candidate) => fs.existsSync(candidate));
    if (!match) throw new Error(`${kind} was not found. Checked: ${candidates.join(', ')}`);
    return match;
  };
  const waveBundle = firstExisting([
    path.join(packageDir, 'node_modules', 'wavedrom', 'wavedrom.unpkg.min.js'),
    path.join(dependencyRoot, 'wavedrom', 'wavedrom.unpkg.min.js'),
  ], 'WaveDrom browser bundle');
  const json5Bundle = firstExisting([
    path.join(packageDir, 'node_modules', 'json5', 'dist', 'index.min.js'),
    path.join(dependencyRoot, 'json5', 'dist', 'index.min.js'),
  ], 'JSON5 browser bundle');
  return {
    waveBundle: safeInlineScript(fs.readFileSync(waveBundle, 'utf8')),
    json5Bundle: safeInlineScript(fs.readFileSync(json5Bundle, 'utf8')),
  };
}

function buildHtmlPreview({ sourceName, sourceText, svgText, validationReport, waveBundle, json5Bundle }) {
  const inlineSvg = svgText.replace(/^\s*<\?xml[^>]*>\s*/i, '').replace(/^\s*<!DOCTYPE[^>]*>\s*/i, '');
  const validationJson = safeInlineScript(JSON.stringify(validationReport ?? { errors: [], warnings: [] }));
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="generator" content="wavedrom-gen skill">
  <meta data-wavedrom-preview="1">
  <title>${escapeHtml(sourceName)} — WaveDrom preview</title>
  <style>
    :root{color-scheme:light;--bg:#f4f7fb;--panel:#fff;--text:#172033;--muted:#667085;--line:#d8dee9;--accent:#155eef;--good:#067647;--bad:#b42318;--warn:#b54708;--code:#f8fafc}
    body.dark{color-scheme:dark;--bg:#0f172a;--panel:#172033;--text:#eef2ff;--muted:#a7b0c2;--line:#344054;--accent:#84adff;--good:#75e0a7;--bad:#fda29b;--warn:#fec84b;--code:#111827}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
    header{display:flex;gap:16px;align-items:center;justify-content:space-between;padding:14px 20px;background:var(--panel);border-bottom:1px solid var(--line)}
    h1{font-size:16px;margin:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.sub{color:var(--muted);font-size:12px}
    .toolbar{display:flex;gap:8px;flex-wrap:wrap}button{border:1px solid var(--line);border-radius:7px;padding:7px 10px;background:var(--panel);color:var(--text);cursor:pointer}button:hover{border-color:var(--accent);color:var(--accent)}button.primary{background:var(--accent);border-color:var(--accent);color:white}
    main{display:grid;grid-template-columns:minmax(320px,38%) 1fr;gap:12px;padding:12px;height:calc(100vh - 65px)}
    .panel{min-height:0;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden;display:flex;flex-direction:column}.panel-title{padding:10px 12px;border-bottom:1px solid var(--line);font-weight:600;display:flex;justify-content:space-between;align-items:center}
    textarea{width:100%;height:100%;resize:none;border:0;outline:0;padding:14px;background:var(--code);color:var(--text);font:13px/1.5 Consolas,"SFMono-Regular",monospace;tab-size:2}
    #diagram-scroll{flex:1;overflow:auto;padding:22px;background:white}#diagram{min-width:max-content}#diagram svg{display:block;max-width:none;height:auto}
    #report{border-top:1px solid var(--line);padding:9px 12px;max-height:150px;overflow:auto;color:var(--muted);font-size:12px}.ok{color:var(--good)}.error{color:var(--bad)}.warning{color:var(--warn)}
    .badge{border-radius:999px;padding:3px 8px;background:var(--code);font-size:12px;color:var(--muted)}
    @media(max-width:850px){main{grid-template-columns:1fr;height:auto}.panel{min-height:430px}header{align-items:flex-start;flex-direction:column}}
  </style>
</head>
<body>
  <header>
    <div><h1>${escapeHtml(sourceName)}</h1><div class="sub">Offline WaveDrom editor and preview · no network required</div></div>
    <div class="toolbar">
      <button class="primary" id="render">Render</button><button id="fit">Fit</button><button id="zoom-out">−</button><button id="zoom-in">＋</button>
      <button id="copy">Copy JSON5</button><button id="save-source">Download JSON5</button><button id="save-svg">Download SVG</button><button id="save-png">Download PNG</button><button id="theme">Theme</button>
    </div>
  </header>
  <main>
    <section class="panel"><div class="panel-title"><span>WaveJSON / JSON5</span><span class="badge">Ctrl/⌘ + Enter</span></div><textarea id="source" spellcheck="false">${escapeHtml(sourceText)}</textarea><div id="report"></div></section>
    <section class="panel"><div class="panel-title"><span>Timing diagram</span><span id="status" class="badge">Prevalidated</span></div><div id="diagram-scroll"><div id="diagram">${inlineSvg}</div></div></section>
  </main>
  <script>${json5Bundle}</script>
  <script>${waveBundle}</script>
  <script>
  (() => {
    'use strict';
    const INITIAL_VALIDATION = ${validationJson};
    const SOURCE_NAME = ${safeInlineScript(JSON.stringify(sourceName))};
    const editor = document.querySelector('#source');
    const diagram = document.querySelector('#diagram');
    const reportBox = document.querySelector('#report');
    const status = document.querySelector('#status');
    let zoom = 1;
    let timer;

    function validateModel(model) {
      const errors = [], warnings = [], nodes = new Set();
      let lanes = 0, boxes = 0;
      if (!model || typeof model !== 'object' || Array.isArray(model)) errors.push('Top level must be an object.');
      if (!model || !Array.isArray(model.signal)) errors.push('Top-level signal must be an array.');
      const walk = (entries, location) => {
        if (!Array.isArray(entries)) return;
        entries.forEach((lane, index) => {
          const place = location + '[' + index + ']';
          if (Array.isArray(lane)) { walk(lane.slice(1), place); return; }
          if (!lane || typeof lane !== 'object' || !Object.keys(lane).length) return;
          lanes += 1;
          if (typeof lane.name !== 'string') errors.push(place + ': missing string name.');
          if (typeof lane.wave !== 'string') { errors.push(place + ': missing string wave.'); return; }
          if (!/^[01.zx=ud2-9pPnNhHlL|]*$/.test(lane.wave)) errors.push(place + ': wave contains unsupported characters.');
          const count = [...lane.wave].filter(char => char === '=' || /[2-9]/.test(char)).length;
          boxes += count;
          const labels = Array.isArray(lane.data) ? lane.data.length : typeof lane.data === 'string' ? lane.data.trim().split(/\\s+/).filter(Boolean).length : 0;
          if (labels < count) errors.push(place + ': ' + count + ' data boxes need labels, but only ' + labels + ' were supplied.');
          if (labels > count) warnings.push(place + ': ' + labels + ' labels were supplied for ' + count + ' data boxes.');
          if (typeof lane.node === 'string') [...lane.node].forEach(char => { if (/^[A-Za-z0-9]$/.test(char)) { if (nodes.has(char)) errors.push(place + ': duplicate node ' + char + '.'); nodes.add(char); } });
        });
      };
      if (model && Array.isArray(model.signal)) walk(model.signal, 'signal');
      if (model && Array.isArray(model.edge)) model.edge.forEach((edge, index) => {
        const token = String(edge).trim().split(/\\s+/, 1)[0];
        const refs = token.match(/[A-Za-z0-9]/g) || [];
        if (refs.length < 2) errors.push('edge[' + index + '] has no recognizable endpoints.');
        else [refs[0], refs[refs.length - 1]].forEach(ref => { if (!nodes.has(ref)) errors.push('edge[' + index + '] references missing node: ' + ref); });
      });
      if (model && model.config && model.config.hscale !== undefined && (!Number.isInteger(model.config.hscale) || model.config.hscale < 1)) errors.push('config.hscale must be a positive integer.');
      return { errors, warnings, counts: { lanes, dataBoxes: boxes, nodes: nodes.size, edges: model && Array.isArray(model.edge) ? model.edge.length : 0 } };
    }

    function showReport(report) {
      reportBox.textContent = '';
      const summary = document.createElement('div');
      summary.className = report.errors.length ? 'error' : report.warnings.length ? 'warning' : 'ok';
      summary.textContent = report.errors.length ? report.errors.length + ' error(s)' : report.warnings.length ? report.warnings.length + ' warning(s)' : 'Validation passed';
      reportBox.append(summary);
      [...report.errors.map(x => ['error', x]), ...report.warnings.map(x => ['warning', x])].forEach(([kind, message]) => {
        const line = document.createElement('div'); line.className = kind; line.textContent = '• ' + message; reportBox.append(line);
      });
      if (report.counts) { const counts = document.createElement('div'); counts.textContent = 'Lanes ' + report.counts.lanes + ' · data boxes ' + report.counts.dataBoxes + ' · nodes ' + report.counts.nodes + ' · edges ' + report.counts.edges; reportBox.append(counts); }
    }

    function svgSize(svg) {
      const view = svg.viewBox && svg.viewBox.baseVal;
      return { width: view && view.width ? view.width : parseFloat(svg.getAttribute('width')) || 800, height: view && view.height ? view.height : parseFloat(svg.getAttribute('height')) || 400 };
    }
    function applyZoom() { const svg = diagram.querySelector('svg'); if (!svg) return; const size = svgSize(svg); svg.style.width = Math.max(100, size.width * zoom) + 'px'; }
    function fit() { const svg = diagram.querySelector('svg'); if (!svg) return; const size = svgSize(svg); const available = document.querySelector('#diagram-scroll').clientWidth - 44; zoom = Math.min(1, available / size.width); applyZoom(); }

    function render() {
      try {
        const model = JSON5.parse(editor.value);
        const report = validateModel(model);
        showReport(report);
        if (report.errors.length) throw new Error('Fix validation errors before rendering.');
        const tree = wavedrom.renderAny(0, model, wavedrom.waveSkin, false);
        diagram.innerHTML = wavedrom.onml.stringify(tree);
        status.textContent = report.warnings.length ? 'Rendered with warnings' : 'Rendered'; status.className = report.warnings.length ? 'badge warning' : 'badge ok';
        requestAnimationFrame(fit);
      } catch (error) {
        status.textContent = error.message; status.className = 'badge error';
        if (error.name === 'SyntaxError') showReport({ errors: [error.message], warnings: [] });
      }
    }

    function download(blob, name) { const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
    function currentSvg() { const svg = diagram.querySelector('svg'); if (!svg) throw new Error('Render the diagram first.'); const copy = svg.cloneNode(true); copy.setAttribute('xmlns', 'http://www.w3.org/2000/svg'); return new XMLSerializer().serializeToString(copy); }
    function baseName() { return SOURCE_NAME.replace(/\\.json5?$/i, '') || 'wavedrom-diagram'; }

    document.querySelector('#render').addEventListener('click', render);
    document.querySelector('#fit').addEventListener('click', fit);
    document.querySelector('#zoom-in').addEventListener('click', () => { zoom = Math.min(4, zoom * 1.2); applyZoom(); });
    document.querySelector('#zoom-out').addEventListener('click', () => { zoom = Math.max(.2, zoom / 1.2); applyZoom(); });
    document.querySelector('#copy').addEventListener('click', async () => { try { await navigator.clipboard.writeText(editor.value); status.textContent = 'JSON5 copied'; } catch { editor.select(); document.execCommand('copy'); status.textContent = 'JSON5 copied'; } });
    document.querySelector('#save-source').addEventListener('click', () => download(new Blob([editor.value], { type: 'application/json' }), SOURCE_NAME));
    document.querySelector('#save-svg').addEventListener('click', () => download(new Blob([currentSvg()], { type: 'image/svg+xml' }), baseName() + '.svg'));
    document.querySelector('#save-png').addEventListener('click', () => { const text = currentSvg(), blob = new Blob([text], { type: 'image/svg+xml' }), url = URL.createObjectURL(blob), image = new Image(); image.onload = () => { const size = svgSize(diagram.querySelector('svg')), canvas = document.createElement('canvas'); canvas.width = Math.ceil(size.width * 2); canvas.height = Math.ceil(size.height * 2); const ctx = canvas.getContext('2d'); ctx.fillStyle = 'white'; ctx.fillRect(0, 0, canvas.width, canvas.height); ctx.drawImage(image, 0, 0, canvas.width, canvas.height); canvas.toBlob(png => { download(png, baseName() + '.png'); URL.revokeObjectURL(url); }, 'image/png'); }; image.src = url; });
    document.querySelector('#theme').addEventListener('click', () => document.body.classList.toggle('dark'));
    editor.addEventListener('input', () => { clearTimeout(timer); status.textContent = 'Editing…'; status.className = 'badge'; timer = setTimeout(render, 500); });
    editor.addEventListener('keydown', event => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') { event.preventDefault(); render(); } });
    showReport(INITIAL_VALIDATION); requestAnimationFrame(fit);
  })();
  </script>
</body>
</html>`;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log(usage());
    return 0;
  }
  if (!args.input || !args.svg) throw new Error(usage());

  const input = path.resolve(args.input);
  const svg = path.resolve(args.svg);
  const png = args.png ? path.resolve(args.png) : undefined;
  const html = args.html ? path.resolve(args.html) : undefined;
  const scriptDir = path.dirname(fileURLToPath(import.meta.url));
  const validator = path.join(scriptDir, 'validate-wavejson.mjs');
  const validationArgs = [validator, '--input', input];
  if (args.strict) validationArgs.push('--strict');
  const validation = spawnSync(process.execPath, validationArgs, { encoding: 'utf8' });
  if (validation.status !== 0) {
    process.stdout.write(validation.stdout ?? '');
    process.stderr.write(validation.stderr ?? '');
    throw new Error(`WaveJSON validation failed with exit code ${validation.status}.`);
  }

  let validationReport;
  try { validationReport = JSON.parse(validation.stdout); } catch { validationReport = { errors: [], warnings: [] }; }

  fs.mkdirSync(path.dirname(svg), { recursive: true });
  if (png) fs.mkdirSync(path.dirname(png), { recursive: true });
  if (html) fs.mkdirSync(path.dirname(html), { recursive: true });
  const cli = resolveCli();
  const cliArgs = [cli, '-i', input, '-s', svg];
  if (png) cliArgs.push('-p', png);
  const rendered = spawnSync(process.execPath, cliArgs, { encoding: 'utf8' });
  if (rendered.status !== 0) {
    process.stdout.write(rendered.stdout ?? '');
    process.stderr.write(rendered.stderr ?? '');
    throw new Error(`wavedrom-cli failed with exit code ${rendered.status}.`);
  }

  const svgSize = assertOutput(svg, 'SVG');
  const svgText = fs.readFileSync(svg, 'utf8');
  if (!/<svg\b/i.test(svgText)) throw new Error(`SVG root was not found in: ${svg}`);
  const result = { input, svg, svgBytes: svgSize };
  if (png) {
    result.png = png;
    result.pngBytes = assertOutput(png, 'PNG');
  }
  if (html) {
    const browserAssets = resolveBrowserAssets(cli);
    const sourceText = fs.readFileSync(input, 'utf8');
    const htmlText = buildHtmlPreview({
      sourceName: path.basename(input), sourceText, svgText, validationReport, ...browserAssets,
    });
    fs.writeFileSync(html, htmlText, 'utf8');
    result.html = html;
    result.htmlBytes = assertOutput(html, 'HTML');
    if (!/<meta data-wavedrom-preview="1">/.test(htmlText)) throw new Error(`WaveDrom preview marker was not found in: ${html}`);
  }
  console.log(JSON.stringify(result, null, 2));
  return 0;
}

try {
  process.exitCode = main();
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
