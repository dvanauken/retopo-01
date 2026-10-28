// Pure clip-space projection for the worker. Coordinates are CSS pixels in one pane.
export function buildVertexProjection(vertices, matrix, width, height) {
  const screen = new Float32Array(vertices.length); screen.fill(NaN);
  const bins = new Map(), cellSize = 16;
  for (let i = 0; i < vertices.length; i += 3) {
    const x = vertices[i], y = vertices[i + 1], z = vertices[i + 2];
    const w = matrix[3] * x + matrix[7] * y + matrix[11] * z + matrix[15];
    if (!(w > 0)) continue;
    const px = (matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12]) / w;
    const py = (matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13]) / w;
    const depth = (matrix[2] * x + matrix[6] * y + matrix[10] * z + matrix[14]) / w;
    if (depth < -1 || depth > 1 || px < -1 || px > 1 || py < -1 || py > 1) continue;
    const sx = (px + 1) * width / 2, sy = (1 - py) * height / 2;
    screen[i] = sx; screen[i + 1] = sy; screen[i + 2] = depth;
    const key = `${Math.floor(sx / cellSize)},${Math.floor(sy / cellSize)}`;
    if (!bins.has(key)) bins.set(key, []);
    bins.get(key).push(i / 3);
  }
  return { screen, bins, cellSize };
}
