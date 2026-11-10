# Native integer callback fixtures

These compact fixtures reproduce captured callback boundaries without an installed native engine or the Ghidra workbench. Run `python tests/test_native_integer_callback.py` from the repository root.

- `ellipsoid-v59.json`: earlier bounded regression; 156 geometric candidates, 152 residuals, 11 augmented constraints, 9 dependencies, 48 nested variables, 52 outer fixes.
- `island6-200.json`: the actual open rim requested at 200; 214 valid candidates plus 4 sentinel entries, 129 residuals, 160 constraints, 125 dependencies, 21 nested variables, 71 outer fixes. This native request produced 374 faces; the fixture does not claim an accepted 200-quad result.

The policy boundary inputs are native ordered root pairs, guide/seed ownership, float UV differences, and signed source-path integrals. Native residual rows, weights, targets, and constraint terms are comparison oracles. The complete nested solve starts after existing chart/guide dependencies have been substituted: it independently builds new mode2 dependencies, folds constants, compresses columns, adds regularizers, solves integer batches, and returns outer fixes. Native outputs are used only for assertions. Upstream original-mesh conditioning, admission, fields, charts, and final extraction are outside these tests.

Native engine SHA256 is recorded in each fixture. Every consumed capture file has its SHA256 in `provenance`. Captures are `work/zbrush/runtime/algorithm-recovery/debug/ellipsoid-100-v59` in the workbench and `runs/native-rim-investigation/native-captures/parameter/island6-keep-creases-200-angle30-a2` in this app. The reproducible packager is retained at `tests/fixtures/native_integer/package_fixture.py` and requires a fresh output path.

Reviewed code: `0x28fe70`, especially `0x291bc3..0x291c02` (mixed guide/seed acceptance), `0x291a91..0x291a9d` and `0x291bf5` (larger soft gaps retain their target), and mode2 `0x288f50` at `0x28935b..0x2893b1` (a row with no eligible scalar advances without becoming a pivot). Constant-only candidate rows can therefore be discarded; these are not assertions that every original candidate equation is simultaneously satisfied. General nonunit scalar pivots remain explicitly unsupported.
