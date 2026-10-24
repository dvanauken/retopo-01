// Import-free mechanical boundary validation. No document or browser authority.
export const freeze = value => {
  if (value && typeof value === 'object') { Object.values(value).forEach(freeze); Object.freeze(value); }
  return value;
};
export function exactRecord(value, required, optional = []) {
  if (!value || typeof value !== 'object' || ![Object.prototype, null].includes(Object.getPrototypeOf(value))) throw new Error('Expected a plain guide record.');
  const descriptors = Object.getOwnPropertyDescriptors(value), allowed = new Set([...required, ...optional]);
  if (Reflect.ownKeys(descriptors).some(k => typeof k !== 'string' || !allowed.has(k) || !('value' in descriptors[k])) || required.some(k => !descriptors[k])) throw new Error('Unexpected or missing guide fields.');
  return value;
}
export function denseArray(value) {
  if (!Array.isArray(value)) throw new Error('Expected a dense guide array.');
  for (let i = 0; i < value.length; i++) if (!Object.prototype.hasOwnProperty.call(value, i)) throw new Error('Sparse guide arrays are invalid.');
  return value;
}
export function validateInputTree(root) {
  const pending = [[root, 0]]; let count = 0;
  while (pending.length) {
    const [value, depth] = pending.pop();
    if (++count > 100000 || depth > 32) throw new Error('The guide file is too complex.');
    if (!value || typeof value !== 'object') continue;
    for (const key of Object.keys(value)) {
      if (['__proto__', 'prototype', 'constructor'].includes(key)) throw new Error('Unsafe guide data key.');
      pending.push([value[key], depth + 1]);
    }
  }
}
