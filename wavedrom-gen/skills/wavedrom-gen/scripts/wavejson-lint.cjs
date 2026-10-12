(function attachWaveDromGenLint(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.WaveDromGenLint = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function createWaveDromGenLint() {
  'use strict';

  const DOCUMENTED_WAVE = /^[01.zx=ud2-9pPnNhHlL|<>]*$/;
  const OFFICIAL_SKINS = new Set(['default', 'narrow', 'dark', 'lowkey', 'narrower', 'narrowerer']);

  function classifyDiagram(source) {
    if (!source || typeof source !== 'object' || Array.isArray(source)) return 'unknown';
    if (source.signal) return 'signal';
    if (source.assign) return 'assign';
    if (source.reg) return 'reg';
    return 'unknown';
  }

  function labelCount(data) {
    if (Array.isArray(data)) return data.length;
    if (typeof data === 'string') return data.trim() ? data.trim().split(/\s+/).length : 0;
    return 0;
  }

  function lintModel(source, validateDatasheetConfig) {
    const errors = [];
    const warnings = [];
    const counts = { lanes: 0, dataBoxes: 0, nodes: 0, edges: 0, annotations: 0, assignments: 0, registerFields: 0 };
    const diagramType = classifyDiagram(source);
    const nodes = new Set();

    if (!source || typeof source !== 'object' || Array.isArray(source)) {
      errors.push('The top level must be a WaveJSON object.');
      return { diagramType, errors, warnings, counts, nodes };
    }

    const presentTypes = ['signal', 'assign', 'reg'].filter((key) => source[key]);
    if (presentTypes.length === 0) errors.push('Use one official top-level diagram key: signal, assign, or reg.');
    if (presentTypes.length > 1) warnings.push(`Multiple diagram keys are present (${presentTypes.join(', ')}); official renderAny uses the first in signal, assign, reg order.`);

    function validateLane(lane, location) {
      if (Array.isArray(lane)) {
        if (typeof lane[0] !== 'string' || lane[0].trim() === '') warnings.push(`${location}: a group normally begins with a non-empty name.`);
        lane.slice(1).forEach((child, index) => validateLane(child, `${location}[${index + 1}]`));
        return;
      }
      if (!lane || typeof lane !== 'object') {
        warnings.push(`${location}: lane is not an object, spacer, or named group.`);
        return;
      }
      if (Object.keys(lane).length === 0) return;

      counts.lanes += 1;
      if (lane.wave !== undefined) {
        if (typeof lane.wave !== 'string') {
          warnings.push(`${location}.wave is not a string; the official engine may reject or ignore it.`);
        } else {
          if (!DOCUMENTED_WAVE.test(lane.wave)) {
            const invalid = [...new Set([...lane.wave].filter((char) => !DOCUMENTED_WAVE.test(char)))];
            warnings.push(`${location}.wave contains character(s) not documented by wavedrom@3.6.2: ${invalid.join(' ')}; the official engine renders unknown states as x.`);
          }
          const boxes = [...lane.wave].filter((char) => char === '=' || /[2-9]/.test(char)).length;
          const labels = labelCount(lane.data);
          counts.dataBoxes += boxes;
          if (labels < boxes) warnings.push(`${location}: ${boxes} data boxes have only ${labels} label(s).`);
          if (labels > boxes) warnings.push(`${location}: ${labels - boxes} extra data label(s) will not be consumed.`);
        }
        if (lane.name === undefined) warnings.push(`${location}: waveform lane has no name.`);
      }

      if (lane.node !== undefined) {
        if (typeof lane.node !== 'string') {
          warnings.push(`${location}.node is not a string.`);
        } else {
          for (const marker of lane.node) {
            if (marker === '.') continue;
            if (nodes.has(marker)) warnings.push(`${location}.node reuses node marker: ${marker}`);
            nodes.add(marker);
          }
        }
      }
    }

    if (diagramType === 'signal') {
      if (!Array.isArray(source.signal)) warnings.push('signal is not an array; the official engine may reject it.');
      else source.signal.forEach((lane, index) => validateLane(lane, `signal[${index}]`));

      if (source.edge !== undefined && !Array.isArray(source.edge)) warnings.push('edge is normally an array of strings.');
      if (Array.isArray(source.edge)) {
        counts.edges = source.edge.length;
        source.edge.forEach((edge, index) => {
          if (typeof edge !== 'string') {
            warnings.push(`edge[${index}] is not a string.`);
            return;
          }
          const expression = edge.trim().split(/\s+/, 1)[0];
          if (expression.length < 3) {
            warnings.push(`edge[${index}] has no recognizable endpoint/shape/endpoint expression: ${edge}`);
            return;
          }
          const from = expression[0];
          const to = expression[expression.length - 1];
          if (!nodes.has(from)) warnings.push(`edge[${index}] references missing node: ${from}`);
          if (!nodes.has(to)) warnings.push(`edge[${index}] references missing node: ${to}`);
        });
      }

      if (source.config?.hscale !== undefined) {
        const hscale = Number(source.config.hscale);
        if (!Number.isFinite(hscale) || hscale <= 0) warnings.push('config.hscale should be a positive number; the official engine falls back to 1.');
        else if (hscale > 100) warnings.push('config.hscale is capped at 100 by the official engine.');
      }
      if (source.config?.hbounds !== undefined && (!Array.isArray(source.config.hbounds) || source.config.hbounds.length !== 2)) {
        warnings.push('config.hbounds should be a two-element [minimum, maximum] array.');
      }
      if (source.config?.skin !== undefined && !OFFICIAL_SKINS.has(source.config.skin)) {
        warnings.push(`config.skin is not one of the skins shipped with wavedrom@3.6.2: ${[...OFFICIAL_SKINS].join(', ')}.`);
      }
    } else if (diagramType === 'assign') {
      counts.assignments = Array.isArray(source.assign) ? source.assign.length : 0;
    } else if (diagramType === 'reg') {
      counts.registerFields = Array.isArray(source.reg) ? source.reg.length : 0;
    }

    counts.nodes = nodes.size;
    if (source.datasheet !== undefined && diagramType !== 'signal') {
      errors.push('datasheet annotations are a wavedrom-gen extension for signal timing diagrams only.');
    } else if (typeof validateDatasheetConfig === 'function') {
      const datasheet = validateDatasheetConfig(source.datasheet, nodes, source.edge);
      errors.push(...datasheet.errors);
      warnings.push(...datasheet.warnings);
      counts.annotations = datasheet.count;
    }

    return { diagramType, errors, warnings, counts, nodes };
  }

  return { classifyDiagram, lintModel };
}));
