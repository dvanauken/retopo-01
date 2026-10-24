"""Engine 0x28e230: collect active mode-one/two embedded source edges.

Input curves are ordered dictionaries with mode, active, primaryPairs,
alternatePoints and alternatePairs. Pair kind is deliberately not inspected:
the native consumer uses the second int32 as a source vertex identifier.
"""
def collect(curves, edges, vertex_offsets, vertex_edges):
    selected = []
    modes = {}
    for curve in curves:
        mode = int(curve['mode'])
        if mode not in (1, 2) or not curve['active']:
            continue
        pairs = curve['alternatePairs'] if len(curve['alternatePoints']) else curve['primaryPairs']
        for left, right in zip(pairs[:-1], pairs[1:]):
            a, b = int(left[1]), int(right[1])
            if a < 0 or a + 1 >= len(vertex_offsets):
                raise ValueError('Invalid embedded source vertex')
            for edge in vertex_edges[vertex_offsets[a]:vertex_offsets[a + 1]]:
                edge = int(edge)
                if b == int(edges[edge][0]) or b == int(edges[edge][1]):
                    selected.append(edge)
                    modes[edge] = mode
                    break
    return selected, modes
