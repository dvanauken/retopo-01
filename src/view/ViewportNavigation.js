import * as THREE from 'three';

// Camera math only: the application's single pointer route owns capture/lifecycle.
export class ViewportNavigation extends THREE.EventDispatcher {
  constructor(camera, replaceCamera = () => {}) {
    super(); this.camera = camera; this.target = new THREE.Vector3();
    this.replaceCamera = replaceCamera; this.fov = camera.fov; this.span = 1; this.aspect = 1;
    this.enabled = false; this.minDistance = .01; this.maxDistance = 100;
    this.last = ''; this.gesture = null;
  }
  update() {
    this.camera.lookAt(this.target); this.camera.updateMatrixWorld();
    const stamp = [...this.camera.position, ...this.target, this.camera.near, this.camera.far, this.camera.type, this.span, this.aspect].join(',');
    if (stamp !== this.last) { this.last = stamp; this.dispatchEvent({ type: 'change' }); }
  }
  resize(aspect) {
    this.aspect = aspect;
    if (this.camera.isOrthographicCamera) {
      this.camera.top = this.span / 2; this.camera.bottom = -this.span / 2;
      this.camera.left = -this.span * aspect / 2; this.camera.right = this.span * aspect / 2;
    } else this.camera.aspect = aspect;
    this.camera.updateProjectionMatrix();
  }
  setProjection(kind) {
    const ortho = kind === 'orthographic', previous = this.camera;
    if (ortho === !!previous.isOrthographicCamera) return;
    const distance = previous.position.distanceTo(this.target), tangent = Math.tan(THREE.MathUtils.degToRad(this.fov / 2));
    if (ortho) this.span = 2 * distance * tangent;
    const next = ortho ? new THREE.OrthographicCamera() : new THREE.PerspectiveCamera(this.fov);
    next.position.copy(previous.position); next.up.copy(previous.up); next.near = previous.near; next.far = previous.far;
    if (!ortho) next.position.sub(this.target).normalize().multiplyScalar(this.span / (2 * tangent)).add(this.target);
    this.camera = next; this.replaceCamera(next); this.resize(this.aspect); this.update();
  }
  standardView(name) {
    const directions = { front: [0, -1, 0], top: [0, -.000001, 1], right: [1, 0, 0], isometric: [1, -1, 1] };
    if (!directions[name]) return;
    if (name === 'isometric') this.setProjection('orthographic');
    const distance = this.camera.position.distanceTo(this.target);
    this.camera.position.copy(this.target).addScaledVector(new THREE.Vector3(...directions[name]).normalize(), distance); this.update();
  }
  begin(kind, x, y, rect) {
    this.gesture = { kind, x, y, rect };
    this.dispatchEvent({ type: 'start' });
  }
  move(x, y) {
    const g = this.gesture; if (!g) return;
    const dx = x - g.x, dy = y - g.y; g.x = x; g.y = y;
    if (g.kind === 'pan') {
      const units = (this.camera.isOrthographicCamera ? this.span : 2 * this.camera.position.distanceTo(this.target) * Math.tan(THREE.MathUtils.degToRad(this.fov / 2))) / g.rect.height;
      const right = new THREE.Vector3().setFromMatrixColumn(this.camera.matrixWorld, 0);
      const up = new THREE.Vector3().setFromMatrixColumn(this.camera.matrixWorld, 1);
      const delta = right.multiplyScalar(-dx * units).addScaledVector(up, dy * units);
      this.camera.position.add(delta); this.target.add(delta);
    } else {
      const q = new THREE.Quaternion().setFromUnitVectors(this.camera.up, new THREE.Vector3(0, 1, 0));
      const offset = this.camera.position.clone().sub(this.target).applyQuaternion(q);
      const spherical = new THREE.Spherical().setFromVector3(offset);
      spherical.theta -= 2 * Math.PI * dx / g.rect.height;
      spherical.phi = THREE.MathUtils.clamp(spherical.phi - 2 * Math.PI * dy / g.rect.height, .001, Math.PI - .001);
      offset.setFromSpherical(spherical).applyQuaternion(q.invert());
      this.camera.position.copy(this.target).add(offset);
    }
    this.update();
  }
  end() { if (!this.gesture) return; this.gesture = null; this.dispatchEvent({ type: 'end' }); }
  dolly(delta, x, y, rect) {
    this.resize(rect.width / rect.height); this.update();
    const caster = new THREE.Raycaster(); caster.setFromCamera(new THREE.Vector2((x - rect.left) / rect.width * 2 - 1, 1 - (y - rect.top) / rect.height * 2), this.camera);
    const ray = caster.ray;
    const normal = this.camera.getWorldDirection(new THREE.Vector3());
    const anchor = ray.intersectPlane(new THREE.Plane().setFromNormalAndCoplanarPoint(normal, this.target), new THREE.Vector3());
    if (!anchor) return;
    const ortho = this.camera.isOrthographicCamera, tangent = Math.tan(THREE.MathUtils.degToRad(this.fov / 2));
    const distance = ortho ? this.span / (2 * tangent) : this.camera.position.distanceTo(this.target);
    const ratio = THREE.MathUtils.clamp(distance * Math.exp(THREE.MathUtils.clamp(delta * .001, -1, 1)), this.minDistance, this.maxDistance) / distance;
    if (ortho) {
      const shift = this.target.clone().sub(anchor).multiplyScalar(ratio - 1);
      this.camera.position.add(shift); this.target.add(shift); this.span *= ratio; this.resize(this.aspect);
    } else {
      this.camera.position.sub(anchor).multiplyScalar(ratio).add(anchor);
      this.target.sub(anchor).multiplyScalar(ratio).add(anchor);
    }
    this.update();
  }
  frame(points, aspect) {
    const box = new THREE.Box3().setFromPoints(points.map(p => new THREE.Vector3(...p)));
    if (box.isEmpty()) return;
    const center = box.getCenter(new THREE.Vector3());
    let direction = this.camera.position.clone().sub(this.target);
    if (direction.lengthSq() < 1e-12) direction.set(2.7, -4.2, 3.4);
    direction.normalize(); this.camera.position.copy(center).add(direction); this.target.copy(center); this.update();
    const right = new THREE.Vector3().setFromMatrixColumn(this.camera.matrixWorld, 0), up = new THREE.Vector3().setFromMatrixColumn(this.camera.matrixWorld, 1);
    const tangent = Math.tan(THREE.MathUtils.degToRad(this.fov / 2));
    let distance = .01, span = .001, depth = 0;
    for (const p of points) {
      const offset = new THREE.Vector3(...p).sub(center);
      distance = Math.max(distance, offset.dot(direction) + 1.15 * Math.max(Math.abs(offset.dot(up)) / tangent, Math.abs(offset.dot(right)) / (tangent * aspect)));
      span = Math.max(span, 2.3 * Math.max(Math.abs(offset.dot(up)), Math.abs(offset.dot(right)) / aspect));
      depth = Math.max(depth, Math.abs(offset.dot(direction)));
    }
    const radius = Math.max(box.getBoundingSphere(new THREE.Sphere()).radius, .001);
    if (this.camera.isOrthographicCamera) { this.span = span; distance = Math.max(span / (2 * tangent), depth + radius); }
    this.minDistance = Math.max(.0001, radius * .01); this.maxDistance = Math.max(18, distance * 20);
    this.camera.near = Math.max(.00001, radius * .001); this.camera.far = Math.max(100, distance + radius * 100);
    this.camera.position.copy(center).addScaledVector(direction, distance); this.resize(aspect); this.update();
  }
  snapshot() { return { projection: this.camera.isOrthographicCamera ? 'orthographic' : 'perspective', position: this.camera.position.toArray(), target: this.target.toArray(), distance: this.camera.position.distanceTo(this.target), verticalSpan: this.camera.isOrthographicCamera ? this.span : 2 * this.camera.position.distanceTo(this.target) * Math.tan(THREE.MathUtils.degToRad(this.fov / 2)), fov: this.fov, near: this.camera.near, far: this.camera.far, navigating: !!this.gesture }; }
}
