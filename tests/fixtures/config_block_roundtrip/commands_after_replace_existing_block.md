<!-- github-pipeline-config -->
Pipeline configuration for the `github-pipeline` skills (resolver / evaluator / planner), read at use-time. You can edit these blocks by hand — just keep each block's `<!-- … -->` marker pair intact so the skills can find it. Re-run `github-pipeline-setup` to reconcile them (idempotent).
<!-- /github-pipeline-config -->

<!-- issue-resolver-fast-checks -->
- `./scripts/check-layer-imports.sh` — Layer-import boundary lint (fast, <5s)
- `CI=1 ./scripts/run-swiftlint.sh` — SwiftLint in CI strict mode
<!-- /issue-resolver-fast-checks -->

<!-- issue-resolver-canonical-suite -->
- full-suite: `./scripts/xcb.sh test`
- build-once: `./scripts/xcb.sh build-for-testing`
- retry-without-rebuild: `./scripts/xcb.sh test-without-building`
<!-- /issue-resolver-canonical-suite -->

<!-- pr-evaluator-merge-policy -->
- standard: auto
- story: ask
<!-- /pr-evaluator-merge-policy -->
