import { freeze, validateInputTree } from '../contracts/GuideData.js';
import { makeGuide, fromPositions, LIMITS } from '../geometry/GuideCurve.js';
const canonical = value => Array.isArray(value) ? value.map(canonical) : value && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map(k => [k, canonical(value[k])])) : value;
export function encodeGuides(document, sourceSha256, curves) {
  return JSON.stringify(canonical({ format: 'retopo-guides', schemaVersion: 2, coordinateFrame: 'source', sourceSha256, guides: document.guides, curves })) + '\n';
}
export function decodeGuides(packet, sourceSha256, idFactory) {
  validateInputTree(packet);
  if (!packet || packet.coordinateFrame !== 'source') throw new Error('Use a source-space guide JSON file.');
  if (packet.sourceSha256 && packet.sourceSha256 !== sourceSha256) throw new Error('These guides belong to a different source mesh.');
  let guides;
  if (packet.schemaVersion !== undefined) {
    if (packet.schemaVersion !== 2 || packet.format !== 'retopo-guides' || packet.sourceSha256 !== sourceSha256 || !Array.isArray(packet.guides)) throw new Error('Unsupported guide file version or missing source identity.');
    guides = packet.guides.map(makeGuide);
  } else {
    if (!Array.isArray(packet.curves)) throw new Error('The guide file has no curves.');
    guides = packet.curves.map(c => fromPositions(c, 'polyline', false, idFactory, { detectClosure: true }));
  }
  if (guides.length > LIMITS.guides || new Set(guides.map(g => g.id)).size !== guides.length || guides.reduce((n, g) => n + g.points.length, 0) > LIMITS.samples) throw new Error('Too many guides/points or duplicate guide IDs.');
  return freeze(guides);
}
