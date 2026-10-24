import * as THREE from 'three';
import { fromCircle, makeGuide, editPoints } from '../geometry/GuideCurve.js';

// Source-plane construction permits the center to lie over a through-hole.
export class CircleConstruction {
  constructor(ports) { this.ports = ports; }
  frame(x, y, pane) {
    const hit = this.ports.hit(x, y, pane);
    return hit ? { center: hit.point.toArray(), normal: hit.face.normal.toArray() } : null;
  }
  onPlane(x, y, pane, center, normal) {
    const plane = new THREE.Plane().setFromNormalAndCoplanarPoint(new THREE.Vector3(...normal), new THREE.Vector3(...center));
    const point = this.ports.ray(x, y, pane).intersectPlane(plane, new THREE.Vector3());
    if (!point) throw new Error('The Circle plane is edge-on to this view. Turn the view and try again.');
    return point.toArray();
  }
  preview(c, x, y) {
    const rim = this.ports.hit(x, y, c.pane), frame = c.frame || (rim ? { center: rim.point.toArray(), normal: rim.face.normal.toArray() } : null);
    if (!frame) throw new Error('Place the radius point on the source surface. The center may be over a hole.');
    const center = c.frame?.center || this.onPlane(...c.screen, c.pane, frame.center, frame.normal);
    const edge = this.onPlane(x, y, c.pane, center, frame.normal), ids = [c.id, c.id + ':center'];
    return fromCircle(center, edge, frame.normal, () => ids.shift());
  }
  edit(g, pointId, delta, pane) {
    const role = editPoints(g).find(p => p.id === pointId), center = g.points[0].position;
    const position = role?.role === 'radius' ? this.ports.nearest(role.position) : center;
    const screen = this.ports.project(position, pane), target = this.onPlane(screen.x + delta[0], screen.y + delta[1], pane, center, g.normal);
    if (role?.role === 'radius') {
      const radius = new THREE.Vector3(...target).distanceTo(new THREE.Vector3(...center));
      return makeGuide({ ...g, radius, axis: target.map((v, i) => (v - center[i]) / radius) });
    }
    return makeGuide({ ...g, points: [{ ...g.points[0], position: target }] });
  }
}
