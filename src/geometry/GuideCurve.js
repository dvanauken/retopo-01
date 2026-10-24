import { freeze, exactRecord, denseArray } from '../contracts/GuideData.js';
// Pure authored guide values. XYZ is the surface-guide extension to Draw 2D.
export const SPLINE_ALGORITHM = 'centripetal-catmull-rom-v2-surface-xyz';
export const LIMITS = Object.freeze({ guides: 48, points: 2048, samples: 8192, error: .002, step: .04 });
export const distance = (a, b) => Math.hypot(...a.map((v, i) => v - b[i]));
export function makeGuide(value) {
  const circle = value?.type === 'circle';
  exactRecord(value, ['id', 'type', 'closed', 'points', ...(circle ? ['radius', 'normal', 'axis'] : [])], value?.type === 'spline' ? ['algorithm'] : []);
  if (!value || !['polyline', 'spline', 'circle'].includes(value.type) || typeof value.closed !== 'boolean') throw new Error('Invalid guide type or closure.');
  if (typeof value.id !== 'string' || !value.id || !Array.isArray(value.points) || value.points.length < (circle ? 1 : value.closed ? 3 : 2) || value.points.length > LIMITS.points) throw new Error('A guide needs 2–2048 points, or at least 3 for a loop.');
  const ids = new Set();
  const points = denseArray(value.points).map(point => {
    exactRecord(point, ['id', 'position']);
    if (!point || typeof point.id !== 'string' || !point.id || ids.has(point.id)) throw new Error('Guide point IDs must be unique.');
    ids.add(point.id);
    if (denseArray(point.position).length !== 3 || !point.position.every(v => Number.isFinite(v) && Math.abs(v) < 1e6)) throw new Error('Guide positions must be finite source XYZ coordinates.');
    return { id: point.id, position: [...point.position] };
  });
  if (value.type === 'spline' && value.algorithm !== SPLINE_ALGORITHM) throw new Error('Unsupported surface spline algorithm.');
  if (circle) {
    if (!value.closed || points.length !== 1 || !Number.isFinite(value.radius) || value.radius <= 0 || value.radius >= 1e6) throw new Error('A Circle needs one center and a positive finite radius.');
    for (const v of [value.normal, value.axis]) if (denseArray(v).length !== 3 || !v.every(Number.isFinite) || Math.abs(Math.hypot(...v) - 1) > 1e-6) throw new Error('Invalid Circle plane.');
    if (Math.abs(value.normal.reduce((s, v, i) => s + v * value.axis[i], 0)) > 1e-6) throw new Error('Circle axes must be orthogonal.');
    return freeze({ id: value.id, type: 'circle', closed: true, points, radius: value.radius, normal: [...value.normal], axis: [...value.axis] });
  }
  if (points.every(p => distance(p.position, points[0].position) < 1e-10)) throw new Error('A guide must have a nonzero extent.');
  return freeze({ id: value.id, type: value.type, closed: value.closed, ...(value.type === 'spline' ? { algorithm: SPLINE_ALGORITHM } : {}), points });
}
export function fromCircle(center, radiusPoint, normal, idFactory) {
  const length = Math.hypot(...normal), n = normal.map(v => v / length), vector = radiusPoint.map((v, i) => v - center[i]);
  const height = vector.reduce((s, v, i) => s + v * n[i], 0), tangent = vector.map((v, i) => v - height * n[i]), radius = Math.hypot(...tangent);
  return makeGuide({ id: idFactory(), type: 'circle', closed: true, points: [{ id: idFactory(), position: center }], radius, normal: n, axis: tangent.map(v => v / radius) });
}
export function editPoints(guide) {
  if (guide.type !== 'circle') return guide.points;
  return [{ ...guide.points[0], role: 'center' }, { id: guide.id + ':radius', position: evaluate(guide, 0), role: 'radius' }];
}
export function fromPositions(positions, type = 'polyline', closed = false, idFactory, { detectClosure = false } = {}) {
  if (typeof idFactory !== 'function') throw new Error('An ID factory is required.');
  const values = positions.map(p => [...p]);
  if ((closed || detectClosure) && values.length > 2 && distance(values[0], values.at(-1)) < 1e-8) { closed = true; values.pop(); }
  return makeGuide({ id: idFactory(), type, closed, ...(type === 'spline' ? { algorithm: SPLINE_ALGORITHM } : {}), points: values.map(position => ({ id: idFactory(), position })) });
}
const finite = p => { if (!p.every(Number.isFinite)) throw new Error('spline-numerical-failure'); return p; };
const mix = (a, b, t) => finite(a.map((v, i) => v + (b[i] - v) * t));
function splineSpan(points, closed, span, t) {
  const n = points.length;
  const at = i => closed ? points[(i + n) % n] : i < 0 ? finite(points[0].map((v, k) => 2 * v - points[1][k])) : i >= n ? finite(points[n - 1].map((v, k) => 2 * v - points[n - 2][k])) : points[i];
  const p = [-1, 0, 1, 2].map(i => at(span + i)), knots = [0];
  for (let i = 1; i < 4; i++) {
    const next = knots[i - 1] + Math.max(1e-9, Math.pow(distance(p[i - 1], p[i]), .5));
    if (!Number.isFinite(next) || next <= knots[i - 1]) throw new Error('spline-numerical-failure');
    knots.push(next);
  }
  const u = knots[1] + t * (knots[2] - knots[1]);
  const lerp = (a, b, i, j) => mix(a, b, (u - knots[i]) / (knots[j] - knots[i]));
  const a = [lerp(p[0], p[1], 0, 1), lerp(p[1], p[2], 1, 2), lerp(p[2], p[3], 2, 3)];
  return lerp(lerp(a[0], a[1], 0, 2), lerp(a[1], a[2], 1, 3), 1, 2);
}
export function evaluate(guide, parameter) {
  if (!Number.isFinite(parameter)) throw new Error('Invalid curve parameter.');
  if (guide.type === 'circle') {
    const n = guide.normal, a = guide.axis, b = [n[1] * a[2] - n[2] * a[1], n[2] * a[0] - n[0] * a[2], n[0] * a[1] - n[1] * a[0]], length = Math.hypot(...b), t = Math.max(0, Math.min(2 * Math.PI, parameter));
    return finite(guide.points[0].position.map((v, i) => v + guide.radius * (Math.cos(t) * a[i] + Math.sin(t) * b[i] / length)));
  }
  const points = guide.points.map(p => p.position), spans = guide.closed ? points.length : points.length - 1;
  const u = Math.max(0, Math.min(spans, parameter)), span = Math.min(spans - 1, Math.floor(u));
  return guide.type === 'spline' ? splineSpan(points, guide.closed, span, u - span) : mix(points[span], points[(span + 1) % points.length], u - span);
}
// Cubic control-hull subdivision bounds the unprojected spline; surface lifting
// is a separate, explicitly bounded adapter operation, not an analytic spline.
export function flatten(guide, { maxSamples = LIMITS.points, error = LIMITS.error, step = LIMITS.step } = {}) {
  if (!Number.isSafeInteger(maxSamples) || maxSamples < 2 || !(error > 0) || !(step > 0)) throw new Error('Invalid guide sampling policy.');
  let work = 0;
  const sample = t => { if (++work > LIMITS.samples) throw new Error('sample-budget-exceeded'); return evaluate(guide, t); };
  if (guide.type === 'circle') {
    const angle = Math.min(2 * Math.acos(Math.max(-1, 1 - error / guide.radius)), 2 * Math.asin(Math.min(1, step / (2 * guide.radius))));
    const count = Math.max(12, Math.ceil(2 * Math.PI / angle));
    if (!Number.isFinite(count) || count + 1 > maxSamples) throw new Error('sample-budget-exceeded');
    const points = Array.from({ length: count }, (_, i) => sample(i * 2 * Math.PI / count)); points.push([...points[0]]); return points;
  }
  if (guide.type === 'polyline') return guide.points.map(p => [...p.position]).concat(guide.closed ? [[...guide.points[0].position]] : []);
  const out = [], spans = guide.closed ? guide.points.length : guide.points.length - 1;
  const lineDistance = (p, a, b) => {
    const d = b.map((v, i) => v - a[i]), d2 = d.reduce((s, v) => s + v * v, 0);
    const t = d2 ? Math.max(0, Math.min(1, p.reduce((s, v, i) => s + (v - a[i]) * d[i], 0) / d2)) : 0;
    return distance(p, mix(a, b, t));
  };
  const append = p => { if (out.length >= maxSamples) throw new Error('sample-budget-exceeded'); out.push(p); };
  const divide = (c, depth) => {
    if (++work > LIMITS.samples) throw new Error('sample-budget-exceeded');
    if (distance(c[0], c[3]) <= step && Math.max(lineDistance(c[1], c[0], c[3]), lineDistance(c[2], c[0], c[3])) <= error) return append(c[3]);
    if (depth >= 32) throw new Error('uncertifiable-error');
    const a = mix(c[0], c[1], .5), b = mix(c[1], c[2], .5), d = mix(c[2], c[3], .5), e = mix(a, b, .5), f = mix(b, d, .5), m = mix(e, f, .5);
    divide([c[0], a, e, m], depth + 1); divide([m, f, d, c[3]], depth + 1);
  };
  for (let i = 0; i < spans; i++) {
    const p = [sample(i), sample(i + 1 / 3), sample(i + 2 / 3), sample(i + 1)];
    const c1 = p[0].map((v, k) => (-5 * v + 18 * p[1][k] - 9 * p[2][k] + 2 * p[3][k]) / 6);
    const c2 = p[0].map((v, k) => (2 * v - 9 * p[1][k] + 18 * p[2][k] - 5 * p[3][k]) / 6);
    if (!i) append(p[0]); divide([p[0], finite(c1), finite(c2), p[3]], 0);
  }
  // Preserve authored endpoints exactly; subdivision never authors new vertices.
  out[0] = [...guide.points[0].position]; out[out.length - 1] = [...guide.points[guide.closed ? 0 : guide.points.length - 1].position];
  return out;
}
