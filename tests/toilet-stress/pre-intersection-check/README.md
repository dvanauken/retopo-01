# Superseded intermediate results

These outputs were produced before non-adjacent polygon intersections became an
acceptance requirement. Their `passed` fields describe the earlier, incomplete
checks, not qualification by the current solver.

The longer captured two-guide output has six detected non-adjacent face
intersections. The original source has four detected triangle contacts. See
`overlap-check.json` for the actual polygon pairs and the detector's scope.

The current results are in `../result.json`. The longer two-guide regression
remains unresolved and is rejected without exporting an accepted mesh.
