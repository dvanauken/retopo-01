import * as THREE from 'three';

// Clip finite triangles at both depth planes before perspective division.
export function clipDepth(polygon) {
  for (const sign of [1, -1]) {
    const output = [];
    for (let i = 0; i < polygon.length; i++) {
      const a = polygon[i], b = polygon[(i + 1) % polygon.length];
      const da = a[3] + sign * a[2], db = b[3] + sign * b[2];
      if (da >= 0) output.push(a);
      if ((da >= 0) !== (db >= 0)) { const t = da / (da - db); output.push(a.map((v, k) => v + (b[k] - v) * t)); }
    }
    polygon = output;
  }
  return polygon;
}

function contained(mesh, camera, pane, box) {
  mesh.updateWorldMatrix(true, false);
  const matrix = new THREE.Matrix4().multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse).multiply(mesh.matrixWorld);
  const attribute = mesh.geometry.attributes.position, indices = mesh.geometry.index;
  const vector = new THREE.Vector4(), points = Array.from({ length: attribute.count }, (_, i) => vector.set(attribute.getX(i), attribute.getY(i), attribute.getZ(i), 1).applyMatrix4(matrix).toArray());
  const count = indices ? indices.count : points.length;
  let any = false;
  for (let i = 0; i < count; i += 3) {
    const triangle = [0, 1, 2].map(j => points[indices ? indices.getX(i + j) : i + j]);
    for (const p of clipDepth(triangle)) {
      if (p[3] <= 0) continue;
      any = true;
      const x = pane.left + (p[0] / p[3] + 1) * pane.width / 2, y = pane.top + (1 - p[1] / p[3]) * pane.height / 2;
      if (x < box.left - .5 || x > box.right + .5 || y < box.top - .5 || y > box.bottom + .5) return false;
    }
  }
  return any;
}

// Visibility is tested at the renderer's actual pixel resolution with depth testing.
// All opaque source surfaces participate, including objects outside the marquee.
export function partMarquee(renderer, camera, pane, objects, a, b) {
  const box = { left: Math.min(a[0], b[0]), right: Math.max(a[0], b[0]), top: Math.min(a[1], b[1]), bottom: Math.max(a[1], b[1]) };
  const eligible = objects.map(o => contained(o.mesh, camera, pane, box));
  if (!eligible.some(Boolean)) return [];
  const scene = new THREE.Scene(), materials = [];
  for (let i = 0; i < objects.length; i++) {
    const original = objects[i].mesh, id = i + 1;
    const material = new THREE.ShaderMaterial({
      uniforms: { idColor: { value: new THREE.Vector3((id & 255) / 255, ((id >> 8) & 255) / 255, ((id >> 16) & 255) / 255) } },
      vertexShader: 'void main(){gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
      fragmentShader: 'uniform vec3 idColor; void main(){gl_FragColor=vec4(idColor,1.0);}',
      side: original.material.side, blending: THREE.NoBlending, toneMapped: false,
    });
    const mesh = new THREE.Mesh(original.geometry, material); mesh.matrixAutoUpdate = false; mesh.matrix.copy(original.matrixWorld); scene.add(mesh); materials.push(material);
  }
  const ratio = renderer.getPixelRatio(), width = Math.max(1, Math.round(pane.width * ratio)), height = Math.max(1, Math.round(pane.height * ratio));
  const target = new THREE.WebGLRenderTarget(width, height, { depthBuffer: true });
  const old = { target: renderer.getRenderTarget(), viewport: renderer.getViewport(new THREE.Vector4()), scissor: renderer.getScissor(new THREE.Vector4()), scissorTest: renderer.getScissorTest(), clear: renderer.getClearColor(new THREE.Color()), alpha: renderer.getClearAlpha() };
  const pixels = new Uint8Array(width * height * 4), visible = new Set();
  try {
    renderer.setRenderTarget(target); renderer.setViewport(0, 0, width / ratio, height / ratio); renderer.setScissorTest(false); renderer.setClearColor(0, 0); renderer.clear(); renderer.render(scene, camera);
    renderer.readRenderTargetPixels(target, 0, 0, width, height, pixels);
    for (let i = 0; i < pixels.length; i += 4) { const id = pixels[i] + (pixels[i + 1] << 8) + (pixels[i + 2] << 16) - 1; if (eligible[id]) visible.add(objects[id].id); }
  } finally {
    renderer.setRenderTarget(old.target); renderer.setViewport(old.viewport); renderer.setScissor(old.scissor); renderer.setScissorTest(old.scissorTest); renderer.setClearColor(old.clear, old.alpha);
    target.dispose(); materials.forEach(m => m.dispose());
  }
  return objects.filter(o => visible.has(o.id)).map(o => o.id);
}
