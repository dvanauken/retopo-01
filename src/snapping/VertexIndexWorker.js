import { buildVertexProjection } from './VertexProjection.js';

let vertices = new Float64Array(), sourceKey = null;
self.onmessage = ({ data }) => {
  if (data.type === 'source') { vertices = data.vertices; sourceKey = data.sourceKey; return; }
  if (data.type !== 'project') return;
  try {
    if (data.sourceKey !== sourceKey) throw new Error('Source changed during vertex projection');
    const result = buildVertexProjection(vertices, data.matrix, data.width, data.height);
    self.postMessage({ id: data.id, key: data.key, sourceKey, ...result }, [result.screen.buffer]);
  } catch (error) { self.postMessage({ id: data.id, error: error.message }); }
};
