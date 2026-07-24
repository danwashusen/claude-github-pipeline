"""Offline tests for the resolver skill (docs/implementation.md S10).

Three offline surfaces the S10 DoD / Testing section names:

1. **Routing-table fixtures** (`vector` → `playbooks/<file>`). The router's visible routing table
   (`skills/resolver/SKILL.md` §2) maps a prep-derived `vector` to the one playbook a session reads.
   These tests parse that table, assert it covers exactly the four routable playbooks
   (standard / story / epic / comment-only), that each points at a real `playbooks/<file>`, and that
   the type→playbook mapping is byte-consistent with `prep_resolver._suggested_playbook` (the router
   "confirms `suggested_playbook` against the table", architecture.md §5).

2. **The interleaving pattern-grep, committed as a validator** (S10 DoD box 1). A test that greps the
   four routable playbooks (and the shared spine) for cross-type conditionals and fails on a hit —
   both `if … (epic|story|standard|comment-only) … else …` constructs AND "when the issue is a
   <type>"-style prose branches. The route IS the branch; a playbook is a linear narrative.

3. **`--dry-run` persist envelopes.** Every GitHub write the playbooks specify goes through
   `gh_persist.py` (SKILL.md §3; the resolver has no scriptless raw-gh executor). These run each such
   invocation with `--dry-run` against the offline shim and assert a conformant envelope (status ok,
   `would_run` present, no live gh call).

Plus the structural bar (router ≤150, router+largest playbook ≤584 = half of v1's 1169) and the
DoD-annotation byte-compat check against the S1 capture (S10 DoD box 2, offline half).

No network: gh_persist.py's `gh` calls resolve to the offline shim via tests/run.py's PATH wiring;
the dry-run path performs no gh call at all (asserted).
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
SKILL_DIR = REPO_ROOT / "skills" / "resolver"
ROUTER = SKILL_DIR / "SKILL.md"
PLAYBOOKS_DIR = SKILL_DIR / "playbooks"
REFERENCES_DIR = SKILL_DIR / "references"
GH_PERSIST = SCRIPTS_DIR / "gh_persist.py"

# The four routable playbooks (the spine is a shared file, not a routable route).
ROUTABLE_PLAYBOOKS = {"standard.md", "story.md", "epic.md", "comment-only.md"}
SPINE = "resolve-spine.md"

# Half of the v1 resolver SKILL.md (1169 lines, docs/specs/baseline.md §1) = 584 (floor).
V1_HALF_BAR = 1169 // 2

sys.path.insert(0, str(SCRIPTS_DIR))

import prep_resolver  # noqa: E402  (import after sys.path setup, by necessity)
from tests.support import envelope_asserts, shimenv  # noqa: E402
from tests.support.retired_tokens import FORBIDDEN_CONTRACT_TOKENS  # noqa: E402


# ---------------------------------------------------------------------------
# Router routing-table parse
# ---------------------------------------------------------------------------

# The router's §2 table rows carry a backticked `playbooks/<file>` in the SECOND cell. The first cell
# is a free-form vector description (e.g. `comment_only: true (…)` or `type: standard`), so we key the
# parse off the playbook cell and pull the driving token from the first cell.
_ROUTE_ROW_RE = re.compile(
    r"^\|\s*(?P<vector>[^|]+?)\s*\|\s*`(?P<playbook>playbooks/[a-z0-9-]+\.md)`\s*\|"
)


def _parse_router_routing_table(router_text):
    """Return an ordered list of (vector_cell, playbooks/<file>) parsed from the router's routing
    table. Rows whose second cell isn't a backticked `playbooks/<file>` path (the header and
    separator rows) don't match."""
    rows = []
    for line in router_text.splitlines():
        match = _ROUTE_ROW_RE.match(line)
        if match:
            rows.append((match.group("vector").strip(), match.group("playbook")))
    return rows


class RouterRoutingTableTests(unittest.TestCase):
    def setUp(self):
        self.router_text = ROUTER.read_text(encoding="utf-8")
        self.rows = _parse_router_routing_table(self.router_text)
        self.playbooks = [pb for _, pb in self.rows]

    def test_router_exists_and_has_frontmatter_pins(self):
        # Frontmatter model/effort pins carried verbatim from v1 (S10 DoD box 4).
        self.assertTrue(ROUTER.is_file(), "router SKILL.md must exist")
        head = "\n".join(self.router_text.splitlines()[:8])
        self.assertIn("name: resolver", head)
        self.assertIn("model: opus", head)
        self.assertIn("effort: xhigh", head)

    def test_routing_table_covers_exactly_the_four_routable_playbooks(self):
        self.assertEqual(
            {Path(pb).name for pb in self.playbooks},
            ROUTABLE_PLAYBOOKS,
            "router routing table must map exactly the four routable playbooks, got %r"
            % (sorted(Path(pb).name for pb in self.playbooks),),
        )

    def test_exactly_four_routable_playbooks_plus_one_spine_on_disk(self):
        # S10 DoD box 1: exactly four playbooks. The playbooks/ dir holds the four routable playbooks
        # plus the single shared spine (architecture.md §5: "a playbook may additionally pull in its
        # skill's single shared spine file").
        on_disk = {p.name for p in PLAYBOOKS_DIR.glob("*.md")}
        self.assertEqual(
            on_disk,
            ROUTABLE_PLAYBOOKS | {SPINE},
            "playbooks/ must be exactly the four routable playbooks + the one shared spine, got %r"
            % (sorted(on_disk),),
        )

    def test_every_routed_playbook_file_exists(self):
        for vector, playbook in self.rows:
            target = SKILL_DIR / playbook
            self.assertTrue(
                target.is_file(),
                "routing table maps %r -> %r but %s does not exist" % (vector, playbook, target),
            )

    def test_table_matches_prep_suggested_playbook_for_each_type(self):
        # architecture.md §5: prep proposes `suggested_playbook`; the router confirms it against the
        # table. Assert byte-consistency for each (type, comment_only) the vector can take.
        cases = [
            ("standard", False, "standard.md"),
            ("story", False, "story.md"),
            ("epic", False, "epic.md"),
            ("standard", True, "comment-only.md"),  # comment_only overrides type in prep
        ]
        for issue_type, comment_only, expected in cases:
            self.assertEqual(
                prep_resolver._suggested_playbook(issue_type, comment_only),
                expected,
                "prep _suggested_playbook(%r, %r) should be %r" % (issue_type, comment_only, expected),
            )
            self.assertIn(
                "playbooks/" + expected,
                self.playbooks,
                "the router table must route to playbooks/%s (prep proposes it)" % expected,
            )

    def test_prep_suggested_playbook_only_targets_files_the_table_lists(self):
        table_basenames = {Path(pb).name for pb in self.playbooks}
        for issue_type in ("standard", "story", "epic"):
            self.assertIn(prep_resolver._suggested_playbook(issue_type, False), table_basenames)
        self.assertIn(prep_resolver._suggested_playbook("standard", True), table_basenames)

    def test_spine_referenced_by_standard_and_story_only(self):
        # The shared spine (resolve-spine.md) is read by the two code-shipping routes; comment-only.md
        # and epic.md are distinct action flows that do NOT read the spine (architecture.md §5).
        spine_path = PLAYBOOKS_DIR / SPINE
        self.assertTrue(spine_path.is_file(), "the shared spine resolve-spine.md must exist")
        for name in ("standard.md", "story.md"):
            text = (PLAYBOOKS_DIR / name).read_text(encoding="utf-8")
            self.assertIn(SPINE, text, "%s must read the shared spine" % name)
        for name in ("comment-only.md", "epic.md"):
            text = (PLAYBOOKS_DIR / name).read_text(encoding="utf-8")
            self.assertNotIn(
                "resolve-spine.md](resolve-spine.md",
                text,
                "%s must NOT pull in the code-shipping spine (it is a distinct action flow)" % name,
            )


# ---------------------------------------------------------------------------
# Router structural bar (S10 DoD boxes 1, 5, 7)
# ---------------------------------------------------------------------------


def _iter_md(dir_path):
    yield from sorted(dir_path.rglob("*.md"))


def _fence_stripped_lines(path):
    """Yield (lineno, line, in_fence) for a markdown file, tracking ``` fenced code blocks so a
    prose mention of a banned command (describing what NOT to do) is distinguishable from an actual
    command in a code block."""
    in_fence = False
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            yield i, line, in_fence
            continue
        yield i, line, in_fence


class RouterStructuralBarTests(unittest.TestCase):
    def test_router_at_most_150_lines(self):
        n = len(ROUTER.read_text(encoding="utf-8").splitlines())
        self.assertLessEqual(n, 150, "router SKILL.md is %d lines (bar: <= 150)" % n)

    def test_router_plus_largest_playbook_at_most_half_v1(self):
        # S10 DoD box 7 / prd.md §10: router + largest playbook <= half of v1's 1169 = 584.
        router_lines = len(ROUTER.read_text(encoding="utf-8").splitlines())
        playbook_lines = {
            p.name: len(p.read_text(encoding="utf-8").splitlines())
            for p in PLAYBOOKS_DIR.glob("*.md")
        }
        largest = max(playbook_lines.values())
        self.assertLessEqual(
            router_lines + largest,
            V1_HALF_BAR,
            "router (%d) + largest playbook (%d) = %d exceeds %d (half of v1's 1169): %r"
            % (router_lines, largest, router_lines + largest, V1_HALF_BAR, playbook_lines),
        )


class PlaybookInterleavingGrepTests(unittest.TestCase):
    """S10 DoD box 1: the interleaving pattern-grep, committed as a validator. A playbook is a linear
    narrative for exactly one route — zero cross-type conditionals. This fails on either form of
    type-interleaving in any playbook (routable or the spine):

      - an `if … <type> … else …` conditional construct, and
      - a `when the issue/PR/type is a <type>` prose branch.

    Both are the constructs a v1-to-v2 whittle would leave behind; the route IS the branch, so a
    playbook that switches on the type has drifted off the §5 bar.
    """

    # Conditional construct: `if <...> (type) <...> else`.
    _IF_ELSE = re.compile(
        r"\bif\b[^.\n]{0,50}\b(story|standard|epic|comment-only)\b[^.\n]{0,50}\belse\b",
        re.IGNORECASE,
    )
    # Prose branch: `when (the issue|the pr|the type|it's) [is] (a|an) <type>`.
    _WHEN_TYPE = re.compile(
        r"\bwhen (the (issue|pr|type) is|it.?s)\s+(a |an )?(story|standard|epic|comment-only)\b",
        re.IGNORECASE,
    )

    def test_playbooks_have_no_cross_type_conditionals(self):
        for playbook in PLAYBOOKS_DIR.glob("*.md"):
            text = playbook.read_text(encoding="utf-8")
            for i, line in enumerate(text.splitlines(), 1):
                self.assertIsNone(
                    self._IF_ELSE.search(line),
                    "playbook %s:%d looks like a cross-type conditional: %r"
                    % (playbook.name, i, line),
                )
                self.assertIsNone(
                    self._WHEN_TYPE.search(line),
                    "playbook %s:%d looks like a when-<type> prose branch: %r"
                    % (playbook.name, i, line),
                )


class ContractTokenGateTests(unittest.TestCase):
    """S10 DoD box 5: grep gates over skills/resolver/ — zero retired-executor tokens, zero v1 skill-invocation
    namespace strings, zero GATHER_/PERSIST_ op names, zero §P IDs, zero raw persist/gather writes,
    zero ref-arithmetic. Prose that *describes* a banned form (a pitfall telling you NOT to hand-roll
    `gh issue create`, or the audit note explaining the v1 `git show <ref>:` reads it replaced) is
    allowed OUTSIDE a code fence; an actual command inside a ``` fence is a violation."""

    def test_no_github_ops_or_old_names_or_op_names_or_pids(self):
        forbidden = FORBIDDEN_CONTRACT_TOKENS
        for path in _iter_md(SKILL_DIR):
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                hit = forbidden.search(line)
                self.assertIsNone(
                    hit,
                    "forbidden contract token under skills/resolver/ at %s:%d — %r"
                    % (path.relative_to(REPO_ROOT), i, hit.group(0) if hit else None),
                )

    def test_no_raw_persist_or_gather_writes_in_code_fences(self):
        # A persist/gather WRITE that bypasses gh_persist.py: gh issue|pr create/edit/comment/review/
        # close/reopen, or gh api ... DELETE. Only flag inside a ``` code fence (a real command); the
        # resolver has no scriptless raw-gh executor (merge is the evaluator's), so any such command
        # is a violation. Sub-agent self-fetch READS (gh issue view / gh api ...comments) are not
        # writes and don't match.
        raw_write = re.compile(
            r"\bgh\s+(issue|pr)\s+(create|edit|comment|review|close|reopen)\b"
            r"|\bgh\s+api\b[^\n]*\bDELETE\b"
        )
        for path in _iter_md(SKILL_DIR):
            for i, line, in_fence in _fence_stripped_lines(path):
                if not in_fence:
                    continue
                hit = raw_write.search(line)
                self.assertIsNone(
                    hit,
                    "raw gh persist/gather WRITE in a code fence at %s:%d — %r"
                    % (path.relative_to(REPO_ROOT), i, hit.group(0) if hit else None),
                )

    def test_no_ref_arithmetic_in_code_fences(self):
        # Banned ref-arithmetic (architecture.md §6/§10): git show <ref>:<path> and git grep <ref>.
        # A bare `git show <commit>` single-commit view is permitted; only <ref>:<path> extraction and
        # `git grep <ref>` are banned. Flag only inside a code fence.
        ref_arith = re.compile(r"\bgit\s+show\s+\S+:\S|\bgit\s+grep\b[^\n]*\s+[a-z]+/[^\s-]")
        for path in _iter_md(SKILL_DIR):
            for i, line, in_fence in _fence_stripped_lines(path):
                if not in_fence:
                    continue
                hit = ref_arith.search(line)
                self.assertIsNone(
                    hit,
                    "ref-arithmetic in a code fence at %s:%d — %r"
                    % (path.relative_to(REPO_ROOT), i, hit.group(0) if hit else None),
                )

    def test_no_w_slash_shorthand(self):
        # CLAUDE.md's banned-shorthand validator is `grep -rnE '\bw/'` (word-boundary), so "review/"
        # (w preceded by a word char) is not a hit — only a standalone "w/" abbreviation is.
        w_shorthand = re.compile(r"\bw/")
        for path in _iter_md(SKILL_DIR):
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                self.assertIsNone(
                    w_shorthand.search(line),
                    "banned w/ shorthand at %s:%d — %r" % (path.relative_to(REPO_ROOT), i, line),
                )


# ---------------------------------------------------------------------------
# --dry-run persist envelopes for the writes the playbooks specify
# ---------------------------------------------------------------------------


def _run_persist(args, body_text=None):
    """Run gh_persist.py <args> as a real subprocess under the offline shim. When body_text is given,
    write it to a temp file and substitute @BODY@ in args with the path. Returns
    (completed_process, parsed_envelope_or_None)."""
    env = shimenv.intercepted_env(base_env=os.environ, fixture_case=None)
    ctx = None
    if body_text is not None:
        ctx = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
        ctx.write(body_text)
        ctx.close()
        args = [a.replace("@BODY@", ctx.name) for a in args]
    try:
        proc = subprocess.run(
            [sys.executable, str(GH_PERSIST)] + args,
            env=env,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
    finally:
        if ctx is not None:
            os.unlink(ctx.name)
    envelope = None
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    if len(lines) == 1:
        envelope = json.loads(lines[0])
    return proc, envelope


class PlaybookPersistDryRunTests(unittest.TestCase):
    """Each GitHub write the resolver playbooks specify, run with --dry-run: a conformant envelope,
    status ok, `would_run` present, exit 0, no live gh call. These are the exact gh_persist invocation
    SHAPES the playbooks name (spine S5 PR create; S6 issue-body DoD projection + Phase tracker;
    comment-only S2; epic.md S4 integration PR + S5 body-tick + the baseline comments)."""

    def _assert_dry_run_ok(self, proc, envelope, expected_op):
        self.assertEqual(proc.returncode, 0, msg="stderr: %s" % proc.stderr)
        self.assertIsNotNone(envelope, "expected exactly one envelope on stdout")
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope.get("status"), "ok")
        self.assertEqual(envelope.get("op"), expected_op)
        self.assertTrue(envelope.get("dry_run"))
        self.assertIn("would_run", envelope)

    def test_dod_projection_edit_body_dry_run(self):
        # spine S6: gh_persist.py edit-body <repo> <issue> <issue-body-projected.md>
        proc, env = _run_persist(
            ["edit-body", "octo/widgets", "142", "@BODY@", "--dry-run"],
            body_text="## Definition of done\n- [x] Export CSV (closed by phase 2, commit abc1234)\n",
        )
        self._assert_dry_run_ok(proc, env, "edit-body")

    def test_comment_only_answer_dry_run(self):
        # comment-only.md S2: gh_persist.py comment <repo> issue <issue> <comment.md>
        proc, env = _run_persist(
            ["comment", "octo/widgets", "issue", "142", "@BODY@", "--dry-run"],
            body_text="This issue is blocked by the open question in #77.\n",
        )
        self._assert_dry_run_ok(proc, env, "comment")

    def test_epic_baseline_comment_dry_run(self):
        # epic.md S3 / epic-flow.md: gh_persist.py comment <repo> issue <epic> <baseline.md>
        proc, env = _run_persist(
            ["comment", "octo/widgets", "issue", "150", "@BODY@", "--dry-run"],
            body_text="🤖 Baseline established\n- Epic branch SHA: abc1234\n- Main SHA: abc1234\n- Result: green\n- Date: 2026-07-09\n",
        )
        self._assert_dry_run_ok(proc, env, "comment")

    def test_epic_body_tick_edit_body_dry_run(self):
        # epic.md S5: gh_persist.py edit-body <repo> <epic> <epic-body-closed.md>
        proc, env = _run_persist(
            ["edit-body", "octo/widgets", "150", "@BODY@", "--dry-run"],
            body_text="## Stories\n- [x] #151\n## Definition of done\n- [x] all shipped\n",
        )
        self._assert_dry_run_ok(proc, env, "edit-body")

    def test_dry_run_makes_no_live_gh_call(self):
        # Belt-and-braces: the dry-run path must not touch gh at all. A clean exit 0 with a would_run
        # envelope (and no url) IS the proof no gh call fired.
        proc, env = _run_persist(
            ["comment", "octo/widgets", "issue", "142", "@BODY@", "--dry-run"],
            body_text="answer\n",
        )
        self.assertEqual(proc.returncode, 0, msg="stderr: %s" % proc.stderr)
        self.assertTrue(env.get("dry_run"))
        self.assertNotIn("url", env, "a dry-run must not carry a live-write url")


class PrCreateContractTests(unittest.TestCase):
    """The PR-open write-path gap this step originally reported is CLOSED: the coordinator
    authorized an additive `create-pr` op on `gh_persist.py` within S10 (architecture.md §2 "if a
    needed operation has no script, extend a script"), landed alongside this skill cutover. These
    tests assert the op's existence + contract (the resolver playbooks' actual invocation shape) at
    the resolver-cutover layer; the op's own exhaustive coverage (happy path, --draft, EMPTY_BODY_FILE,
    AUTH_REQUIRED, dry-run, usage errors, receipts) lives in
    `tests/test_gh_persist.py::CreatePrHappyPathTests`."""

    def test_gh_persist_has_create_pr_subcommand_with_required_flags(self):
        proc = subprocess.run(
            [sys.executable, str(GH_PERSIST), "create-pr", "--help"],
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        help_text = proc.stdout + proc.stderr
        for flag in ("--title", "--base", "--head", "--draft", "--dry-run"):
            self.assertIn(flag, help_text, "gh_persist.py create-pr must accept %s" % flag)

    def test_standard_route_pr_open_dry_run(self):
        # spine S5 fresh-mode first push, standard route: base main, ready (no --draft).
        proc, env = _run_persist(
            [
                "create-pr", "octo/widgets", "@BODY@", "--title", "Add CSV export (#142)",
                "--base", "main", "--head", "142-add-csv-export", "--dry-run",
            ],
            body_text="## Doc grounding\ncites architecture.md §3\n",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        envelope_asserts.assert_full_envelope_conformance(env)
        self.assertEqual(env.get("op"), "create-pr")
        self.assertTrue(env.get("dry_run"))
        self.assertIn("would_run", env)
        self.assertNotIn("--draft", env["would_run"])

    def test_story_route_pr_open_dry_run_bases_on_epic_branch(self):
        # story.md: base is the parent epic's integration branch, never main.
        proc, env = _run_persist(
            [
                "create-pr", "octo/widgets", "@BODY@", "--title", "Add export service (#151)",
                "--base", "epic/150-chat-session-ux-polish", "--head", "151-add-export-service",
                "--dry-run",
            ],
            body_text="This story targets the `epic/150-chat-session-ux-polish` integration branch.\n",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertEqual(env.get("op"), "create-pr")
        self.assertIn("epic/150-chat-session-ux-polish", env["would_run"])

    def test_multi_phase_pr_open_dry_run_carries_draft_flag(self):
        # spine S4/S5: a multi-phase issue opens the PR as draft; the last-phase handoff later
        # flips it ready via the sanctioned `gh pr ready` toggle (architecture.md §10), unaffected
        # by this op.
        proc, env = _run_persist(
            [
                "create-pr", "octo/widgets", "@BODY@", "--title", "feat(llm): #640 spike harness",
                "--base", "main", "--head", "640-spike", "--draft", "--dry-run",
            ],
            body_text="## Phase tracker\n- [ ] Phase 1 — substrate\n",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("--draft", env["would_run"])

    def test_epic_integration_pr_open_dry_run(self):
        # epic.md S4: base main, head the epic integration branch.
        proc, env = _run_persist(
            [
                "create-pr", "octo/widgets", "@BODY@", "--title", "Epic #150: Chat & session UX polish",
                "--base", "main", "--head", "epic/150-chat-session-ux-polish", "--dry-run",
            ],
            body_text="## Goal\n…\nFixes #150\n",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertEqual(env.get("op"), "create-pr")

    def test_playbooks_route_pr_open_through_create_pr_not_a_fabricated_flag_set(self):
        # The resolve-spine.md / epic.md prose must name the real op (create-pr), not the
        # non-existent `create --base/--head` shape this step originally (wrongly) drafted.
        for playbook in ("resolve-spine.md", "epic.md"):
            text = (PLAYBOOKS_DIR / playbook).read_text(encoding="utf-8")
            self.assertIn(
                "create-pr",
                text,
                "%s must route PR-open through gh_persist.py create-pr" % playbook,
            )

    def test_spine_mandates_the_closing_keyword_on_fresh_pr_open(self):
        # Filed defect (S10 live parity, scenario 1 D2 — docs/specs/parity/resolver.md): v1
        # (SKILL.md:888) mandates the PR body carry `Fixes #<number>` (or `Closes #<number>`) so
        # GitHub auto-links and auto-closes on merge; v2's spine had listed every OTHER PR-body
        # section (Doc grounding / Plan / Audit override / Plan override / Phase tracker /
        # Predecessor) but omitted this mandate, so v2 PRs never auto-closed. Regression guard: the
        # spine's fresh-mode PR-open prose must state the mandate.
        text = (PLAYBOOKS_DIR / "resolve-spine.md").read_text(encoding="utf-8")
        self.assertRegex(
            text,
            r"Fixes #<issue-number>.{0,40}Closes\s*\n?\s*#<issue-number>",
            "resolve-spine.md must mandate the closing keyword (Fixes/Closes #<issue-number>) on "
            "fresh-PR open, per v1 SKILL.md:888",
        )
        self.assertIn(
            "must be `Fixes #<issue-number>`",
            text,
            "the closing keyword must be stated as mandatory, not optional prose",
        )

    def test_spine_mandates_the_v1_fresh_pr_title_shape(self):
        # D4 (checked, ruled MANDATED): v1 SKILL.md:885 passes a literal --title "Fix: <summary>
        # (#<issue-number>)" to `gh pr create` -- not free prose, a command-line argument every
        # fresh-PR-open takes. The spine must be faithful to that shape (it also feeds the
        # evaluator's squash-subject derivation, which reads a Conventional-Commits-prefixed title).
        text = (PLAYBOOKS_DIR / "resolve-spine.md").read_text(encoding="utf-8")
        self.assertIn(
            'Fix: <summary> (#<issue-number>)',
            text,
            "resolve-spine.md must mandate the v1 fresh-PR title shape, per SKILL.md:885",
        )

    def test_create_pr_dry_run_with_closing_keyword_and_mandated_title(self):
        # End-to-end dry-run proof: the exact title shape + a body whose first line is the closing
        # keyword round-trips cleanly through gh_persist.py create-pr.
        proc, env = _run_persist(
            [
                "create-pr", "octo/widgets", "@BODY@",
                "--title", "Fix: greet() returns a personalized greeting (#142)",
                "--base", "main", "--head", "142-add-csv-export", "--dry-run",
            ],
            body_text="Fixes #142\n\n## Doc grounding\ncites architecture.md §3\n",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertEqual(env.get("op"), "create-pr")
        self.assertIn("Fix: greet() returns a personalized greeting (#142)", env["would_run"])


class ArtifactRenderingByteCompatTests(unittest.TestCase):
    """S10 DoD box 2 (offline half): the DoD-projection annotation forms the resolver writes must diff
    clean against the S1-captured closed set (docs/specs/examples/dod-annotations.md). The three
    resolver-authored ticked forms are contract tokens (the evaluator + planner parse them verbatim),
    so each must appear byte-for-byte in the resolver's dod-projection-rule.md."""

    EXAMPLES_DIR = REPO_ROOT / "docs" / "specs" / "examples"

    # The three ticked forms the resolver authors (dod-annotations.md capture rows for "resolver §9").
    RESOLVER_FORMS = (
        "- [x] <text> (closed by phase <N>, commit <short-sha>)",
        "- [x] <text> (closed by phase <N>, operator action <ISO-date>)",
        "- [x] <text> (closed by commit <short-sha>)",
    )

    def test_resolver_annotation_forms_present_in_s1_capture(self):
        # Guard the source: each resolver-authored form must be a row in the S1 capture verbatim, so
        # the byte-compat check below is anchored to the frozen contract, not a moving target.
        capture = (self.EXAMPLES_DIR / "dod-annotations.md").read_text(encoding="utf-8")
        for form in self.RESOLVER_FORMS:
            self.assertIn(form, capture, "S1 dod-annotations capture must carry %r" % form)

    def test_projection_rule_renders_each_resolver_form_byte_compatible(self):
        rule = (REFERENCES_DIR / "dod-projection-rule.md").read_text(encoding="utf-8")
        for form in self.RESOLVER_FORMS:
            self.assertIn(
                form,
                rule,
                "dod-projection-rule.md must render the annotation form %r byte-for-byte (it "
                "diverges from the S1 capture otherwise — box 2)" % form,
            )


class QuestionTypeHandoffVariantTests(unittest.TestCase):
    """Filed defect (S10 live parity, scenario 3 D1 — docs/specs/parity/resolver.md): a `question`-type
    issue's terminal handoff must follow skills/_shared/handoff-format.md's question-type rule (omit
    research:/plan: entirely, add an Audience: line) — v2 had rendered `· plan: ✗` and dropped
    Audience:. Fixed in comment-only.md's Handoff section (dispatches by the issue's own type) +
    handoff-renderings.md (a dedicated "Terminal — question-type issue" shape). These tests assert the
    fix without editing _shared (render, don't restate)."""

    RENDERINGS = REFERENCES_DIR / "handoff-renderings.md"
    COMMENT_ONLY = PLAYBOOKS_DIR / "comment-only.md"

    @staticmethod
    def _fenced_blocks(path, fence="```"):
        text = path.read_text(encoding="utf-8")
        blocks, cur, inb = [], [], False
        for line in text.splitlines():
            if line.strip() == fence:
                if inb:
                    blocks.append("\n".join(cur))
                    cur = []
                    inb = False
                else:
                    inb = True
                continue
            if inb:
                cur.append(line)
        return blocks

    def test_question_type_variant_present_and_shaped_per_shared_contract(self):
        text = self.RENDERINGS.read_text(encoding="utf-8")
        self.assertIn(
            "## Terminal — question-type issue",
            text,
            "handoff-renderings.md must carry a dedicated question-type terminal shape",
        )
        # Isolate the actual RENDERED example (the fenced ## Handoff block) -- the surrounding prose
        # legitimately explains the rule by naming the forbidden marker ("do not render `plan: ✗`
        # here"), which must not itself trip a naive whole-section grep (same fence-scoping
        # discipline as ContractTokenGateTests' raw-gh / ref-arithmetic checks).
        rendered_blocks = [b for b in self._fenced_blocks(self.RENDERINGS) if "## Handoff" in b]
        question_rendering = next(
            (b for b in rendered_blocks if "· question" in b and "**Audience:**" in b), None
        )
        self.assertIsNotNone(
            question_rendering, "the question-type section must contain a rendered ## Handoff example"
        )
        # The Issue: line for this shape must end at the type marker `· question` -- no plan:/research:
        # segment at all (handoff-format.md:33: "the research: and plan: markers omitted").
        self.assertRegex(
            question_rendering,
            r"\*\*Issue:\*\* #\d+ — [^\n]+ · open · question\s*\n",
            "the question-type Issue: line must end at '· question' with no plan:/research: marker",
        )
        self.assertNotRegex(
            question_rendering,
            r"plan:\s*[✓✗]",
            "the RENDERED question-type shape must never carry a plan: marker (handoff-format.md's "
            "rule) -- prose explaining the rule is fine; the example itself must not regress",
        )
        self.assertIn(
            "**Audience:**",
            question_rendering,
            "the question-type shape must carry the Audience: line per handoff-format.md",
        )

    def test_non_pr_resolution_shape_unchanged_for_build_types(self):
        # The pre-existing "Terminal — non-PR resolution" shape (OQ refusal / triage / decline on a
        # build-type issue) still renders its plan: marker -- only the question-type issue's own
        # handoff omits it.
        text = self.RENDERINGS.read_text(encoding="utf-8")
        self.assertIn("## Terminal — non-PR resolution", text)
        section = text.split("## Terminal — non-PR resolution", 1)[1].split(
            "## Terminal — question-type issue", 1
        )[0]
        self.assertIn("plan:", section)

    def test_comment_only_playbook_dispatches_by_issue_type(self):
        text = self.COMMENT_ONLY.read_text(encoding="utf-8")
        self.assertIn(
            "question-type issue",
            text,
            "comment-only.md's Handoff section must route a genuine question-type issue to the "
            "dedicated rendering, not the build-type Terminal — non-PR resolution shape",
        )
        self.assertIn("non-PR resolution", text)


class ReRouteHandoffMarkerTests(unittest.TestCase):
    """Filed defect (S10 live parity, scenario 2 D1 — docs/specs/parity/resolver.md): the multi-phase
    re-route worked example (and two siblings) carried an off-closed-set `✓` glyph on the PR-line
    `review:`/`health:` markers, contradicting the reference's own forward-scoped intro. RULING (per
    _shared/handoff-format.md's actual field definitions, evaluator-owned — see the D1 annotation):
    `not run` is the conformant value on EVERY resolver-authored handoff, forward or re-route alike,
    because those two fields denote the evaluator's posted verdict / health-cache result, never "the
    resolver's own /review loop or §8 gate ran." These tests assert every rendered PR-line in
    handoff-renderings.md stays on the closed set, and that the intro states the unconditional scope."""

    RENDERINGS = REFERENCES_DIR / "handoff-renderings.md"
    STANDARD = PLAYBOOKS_DIR / "standard.md"

    @staticmethod
    def _fenced_blocks(path, fence="```"):
        text = path.read_text(encoding="utf-8")
        blocks, cur, inb = [], [], False
        for line in text.splitlines():
            if line.strip() == fence:
                if inb:
                    blocks.append("\n".join(cur))
                    cur = []
                    inb = False
                else:
                    inb = True
                continue
            if inb:
                cur.append(line)
        return blocks

    def test_no_pr_line_carries_an_off_closed_set_review_or_health_glyph(self):
        # The closed set has no bare-checkmark value for either field (handoff-format.md:52-53) --
        # every rendered PR: line's review:/health: segment must be one of the defined values, never
        # a raw ✓/✗ glyph standing in for "ran, no formal verdict."
        off_vocab = re.compile(r"\b(review|health):\s*[✓✗]")
        for block in self._fenced_blocks(self.RENDERINGS):
            if "**PR:**" not in block:
                continue
            self.assertNotRegex(
                block,
                off_vocab,
                "an off-closed-set ✓/✗ glyph on review:/health: survives in a rendered PR: line: %r"
                % block,
            )

    def test_every_resolver_authored_pr_line_before_evaluator_action_is_not_run(self):
        # Every PR: line rendered by a shape that fires BEFORE the evaluator has acted (forward opens,
        # every re-route) must carry review: not run / health: not run. The two shapes that legitimately
        # carry an evaluator-populated value (the plan-currency re-route, which CAN carry a value the
        # evaluator posted on a PRIOR pass) are the only exception, and even there review: stays not run
        # in the frozen worked example -- so this asserts the floor: review: not run appears on every
        # PR: line in the file (a stricter, always-true invariant this reference's worked examples
        # satisfy today).
        text = self.RENDERINGS.read_text(encoding="utf-8")
        pr_lines = [
            line for block in self._fenced_blocks(self.RENDERINGS)
            for line in block.splitlines() if line.strip().startswith("**PR:**")
        ]
        self.assertTrue(pr_lines, "expected at least one rendered PR: line")
        for line in pr_lines:
            self.assertIn(
                "review: not run",
                line,
                "every resolver-authored PR: line must carry review: not run (the evaluator hasn't "
                "acted yet on any resolver exit): %r" % line,
            )
        self.assertIn(
            "not run",
            text,
            "handoff-renderings.md must still document the not-run rule",
        )

    def test_intro_states_the_unconditional_not_run_scope(self):
        # Regression guard for the root cause: the intro must not scope the not-run rule to forward
        # exits only -- it must explicitly cover every re-route too (including mid-phases continue).
        text = self.RENDERINGS.read_text(encoding="utf-8")
        self.assertIn(
            "every resolver-authored handoff",
            text,
            "the intro must state the not-run rule unconditionally, not forward-exit-scoped",
        )
        self.assertIn(
            "AND every re-route",
            text,
            "the intro must explicitly cover re-routes, including the mid-phases continue-mode case",
        )
        self.assertNotIn(
            'on a resolver forward exit because the resolver never runs',
            text,
            "the old forward-scoped phrasing (the root-cause ambiguity) must not survive",
        )

    def test_standard_playbook_states_the_rule_inline_for_multiphase_shapes(self):
        # The routed playbook must not depend entirely on the reference getting the rule right --
        # restate it inline for the multi-phase bullet, where the D1 defect actually surfaced.
        text = self.STANDARD.read_text(encoding="utf-8")
        self.assertIn(
            "review: not run · health: not run",
            text,
            "standard.md's multi-phase bullet must restate the not-run rule inline",
        )


if __name__ == "__main__":
    unittest.main()
