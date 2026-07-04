<!-- github-pipeline-config -->
Pipeline configuration for the `github-pipeline` skills (resolver / evaluator / planner), read at use-time. You can edit these blocks by hand — just keep each block's `<!-- … -->` marker pair intact so the skills can find it. Re-run `github-pipeline-setup` to reconcile them (idempotent).
<!-- /github-pipeline-config -->

<!-- issue-resolver-fast-checks -->
- `./scripts/check-layer-imports.sh` — Layer-import boundary lint (fast, <5s)
- `CI=1 ./scripts/run-swiftlint.sh` — SwiftLint in CI strict mode
<!-- /issue-resolver-fast-checks -->

<!-- pr-evaluator-merge-policy -->
- standard: ask
- story: ask
<!-- /pr-evaluator-merge-policy -->
