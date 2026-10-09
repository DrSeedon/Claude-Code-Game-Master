# Claude-Code-Game-Master-orchestrator — personal notes

- AI-table rig: run the BRANCH's `tools/verify_rig.sh` (`git show <branch>:tools/verify_rig.sh > /tmp/x.sh`),
  not main's. On 2026-10-09 the #27 rig with main's script silently skipped the new `tests/e2e` step
  (25 browser tests instead of 34) and reported PASS; the branch script found 2 real e2e failures.
