Wrote the review to [docs/tasks/codex-review-sdk-comparison.md](/mnt/data/Projects/Python/orchestra/worktrees/mnt-data-projects-python-claude-code-game-master/research-sdk-compare/docs/tasks/codex-review-sdk-comparison.md).

Key verdict: the main research claims are source-backed, but I marked a few as overstated:
- provider-caught errors usually still get `done`; escaped server errors do not
- `tools_registry.py` is called by `server.py`, but only affects API execution because SDK ignores `tools`
- “no frontend changes” for partial streaming is wrong until `Chat.tsx` consumes all queued frames
- session fork and `0.0.0.0` + `bypassPermissions` should be higher priority than the migration plan says

I did not run tests; this was a source-evidence review.