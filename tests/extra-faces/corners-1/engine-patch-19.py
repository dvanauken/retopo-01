"""constrained-sizes-19: an optional face-size cap per constrained edge (applied to the constrained-edges-18 sources).

A row of the constrained-edge list may carry a fourth number, the largest face size allowed at
that edge as a fraction of the requested base size. With -size-caps the cap enters the size field
at the edge's two end vertices, is held there through the diffusion sweeps and spreads with them.
Lists without a fourth column, and runs without -size-caps, take the code paths of
constrained-edges-18 unchanged.
"""
from pathlib import Path
SRC = Path(r'C:\dbva\code\ghidra-workbench\work\retopo-guided-layout\QuadriFlow\src')


def edit(name, old, new, count=1):
    path = SRC / name
    text = path.read_bytes().decode('latin-1')
    if '\r\n' in text:
        old, new = old.replace('\n', '\r\n'), new.replace('\n', '\r\n')
    if text.count(old) != count:
        raise SystemExit(f'{name}: expected {count} occurrence(s), found {text.count(old)}: {old[:60]!r}')
    path.write_bytes(text.replace(old, new).encode('latin-1'))


edit('parametrizer.hpp', r'''    struct ConstrainedEdge { int a, b, mode; };
''', r'''    // `size`: largest face size at the edge as a fraction of the requested base size, 0 for none
    // (application policy, not a native field; used by ComputeSizeCaps only).
    struct ConstrainedEdge { int a, b, mode; double size; };
''')
edit('guide-constraints.hpp', r'''#include <set>
#include <stdexcept>
''', r'''#include <set>
#include <sstream>
#include <stdexcept>
''')
edit('guide-constraints.hpp', r'''// Modes 3 and 4 are not native modes. They keep what this engine did for preserved (sharp)
// edges before it had a lattice-line constraint.
''', r'''// Modes 3 and 4 are not native modes. They keep what this engine did for preserved (sharp)
// edges before it had a lattice-line constraint.
//
// A row may end with a fourth number in (0, 1]: the largest face size at that edge as a fraction
// of the requested base size (see ComputeSizeCaps). It is the application's sizing request, not
// a native field.
''')
edit('guide-constraints.hpp', r'''    for (int i = 0; i < count; ++i) {
        int a, b, mode;
        if (!(in >> a >> b >> mode) || mode < 1 || mode > 4 || !engine.count(a) || !engine.count(b) || a == b)
            throw std::runtime_error("Invalid constrained edge");
        Parametrizer::ConstrainedEdge edge{engine[a], engine[b], mode};
''', r'''    std::string line;
    std::getline(in, line);
    int sized = 0;
    for (int i = 0; i < count; ++i) {
        int a, b, mode;
        double size = 0;
        if (!std::getline(in, line)) throw std::runtime_error("Invalid constrained edge");
        std::istringstream row(line);
        if (!(row >> a >> b >> mode) || mode < 1 || mode > 4 || !engine.count(a) || !engine.count(b) || a == b)
            throw std::runtime_error("Invalid constrained edge");
        if (row >> size) {
            if (!(size > 0) || size > 1) throw std::runtime_error("Invalid constrained edge size");
            ++sized;
        } else size = 0;
        Parametrizer::ConstrainedEdge edge{engine[a], engine[b], mode, size};
''')
edit('guide-constraints.hpp', r'''        if (old != field.constrained_tags.end() && constrained_rank(field.constrained_edges[old->second].mode) > constrained_rank(edge.mode))
            edge.mode = field.constrained_edges[old->second].mode;
''', r'''        if (old != field.constrained_tags.end() && constrained_rank(field.constrained_edges[old->second].mode) > constrained_rank(edge.mode))
            edge.mode = field.constrained_edges[old->second].mode;
        // ... and the smaller of its sizes.
        if (old != field.constrained_tags.end() && field.constrained_edges[old->second].size > 0 &&
            (edge.size == 0 || field.constrained_edges[old->second].size < edge.size))
            edge.size = field.constrained_edges[old->second].size;
''')
edit('guide-constraints.hpp', r'''    printf("Constrained edges: %d listed, %d distinct source edges\n", count, (int)field.constrained_tags.size());
''', r'''    printf("Constrained edges: %d listed, %d distinct source edges\n", count, (int)field.constrained_tags.size());
    if (sized) printf("Constrained edge sizes: %d listed edges carry a face-size cap\n", sized);
''')
edit('parametrizer-scale.cpp', r'''    double base = hierarchy.mScale;
    std::vector<Vector2d> ratio(n, Vector2d(1, 1));
''', r'''    double base = hierarchy.mScale;
    std::vector<Vector2d> ratio(n, Vector2d(1, 1));
    // Face-size caps listed with constrained edges (application policy): the cap holds at the two end
    // vertices of every working edge of a listed edge, on both axes, as a fraction of the requested
    // base size. It is applied after the curvature sizes and again after every diffusion step, so the
    // minimum sweeps spread it and the means grade it without lifting it at the edge itself.
    std::vector<double> edge_cap;
    int capped_vertices = 0;
    for (const auto& tag : constrained_tags) {
        const double size = constrained_edges[tag.second].size;
        if (!(size > 0)) continue;
        if (edge_cap.empty()) edge_cap.assign(n, 1.0);
        for (int vertex : {tag.first.first, tag.first.second})
            if (vertex >= 0 && vertex < n) edge_cap[vertex] = std::min(edge_cap[vertex], size);
    }
    double cap_scale = 1.0;
    auto apply_edge_caps = [&]() {
        if (edge_cap.empty()) return;
        for (int i = 0; i < n; ++i) {
            if (edge_cap[i] >= 1.0) continue;
            const double limit = edge_cap[i] * cap_scale;
            for (int a = 0; a < 2; ++a) ratio[i][a] = std::min(ratio[i][a], limit);
        }
    };
    if (!edge_cap.empty()) {
        for (int i = 0; i < n; ++i) if (edge_cap[i] < 1.0) ++capped_vertices;
        printf("Size caps from constrained edges: %d vertices carry a listed face-size cap\n", capped_vertices);
    }
''')
edit('parametrizer-scale.cpp', r'''                next[i] = (step == 'a') ? Vector2d(acc / count) : acc;
            }
            ratio = next;
        }
        double low = 0.9 / max_ratio;
        for (int i = 0; i < n; ++i)
            for (int a = 0; a < 2; ++a) ratio[i][a] = std::min(1.0, std::max(low, ratio[i][a]));
    };
''', r'''                next[i] = (step == 'a') ? Vector2d(acc / count) : acc;
            }
            ratio = next;
            apply_edge_caps();
        }
        double low = 0.9 / max_ratio;
        for (int i = 0; i < n; ++i)
            for (int a = 0; a < 2; ++a) ratio[i][a] = std::min(1.0, std::max(low, ratio[i][a]));
    };
''')
edit('parametrizer-scale.cpp', r'''        sizes_for(scale_now);
        diffuse();
''', r'''        sizes_for(scale_now);
        cap_scale = base / scale_now;   // listed caps are fractions of the requested base size
        apply_edge_caps();
        diffuse();
''')
print('patched')
