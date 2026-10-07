# V-11 results

The runtime registry now exposes `claude-sonnet-5-5` and `claude-opus-5-5` while retaining the existing Claude models and Sonnet 5 default. Usage pricing is $2/$10 per million input/output tokens for Sonnet 5.5 and $4/$20 for Opus 5.5, matching `/home/kesha/orchestra/app/models.py`.

Both models completed a short `Reply with exactly OK.` prompt through `backend.providers.claude_sdk.ClaudeSDKProvider`. Each provider used `options.cli_path=/usr/bin/claude` (system CLI 2.1.284) from a separate temporary directory. The raw provider events and usage payloads are in [claude-sonnet-5-5-provider.json](claude-sonnet-5-5-provider.json) and [claude-opus-5-5-provider.json](claude-opus-5-5-provider.json).

Calling `api_models()` returned the five Claude IDs, including both additions; its default remained `claude-sonnet-5`. The full requested gate passed on the corrected run: `567 passed in 49.70s`. The first run had 566 passes and one failure because the new test looked for per-record `price_status` in the aggregate; the test now checks the persisted record and aggregate `price_known`. The first-run output is retained in [pytest-first-run-failed.log](pytest-first-run-failed.log).

Restart/deployment visibility remains for the owner to verify after merge.
