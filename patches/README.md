The `enable-unguided-fallback.patch` change is already integrated in `23a8818`.
It is retained here as the small, reviewable patch used to coordinate edits to
`curved_quad.py`; applying it again is unnecessary.

The patch was briefly separated at the user's request and then reintegrated
when the user authorized merging it. Applying it to an isolated copy reproduced
the exact dispatcher used in the successful 150/600 toilet browser tests. The
final audit verifies that the working dispatcher again has those exact bytes
and that the other session's edits remain unchanged.

See `tests/toilet-final-audit/result.json` for the current integration status.
The earlier `dispatch-separation/result.json` records the temporary separation,
not the final state. The patch preserves the shared file's CRLF line endings.
