"""Platform limits the pipeline writes against.

One definition, imported by everything that needs it. The alternative — a literal in the write path
and another in whichever prep reports headroom — is the same two-places-disagree failure the
hardcoded doc-path lists were retired for: the copies drift, and the one that is wrong is the one
nobody reads until a write fails.
"""

# GitHub rejects any issue, PR, or comment body over this many CHARACTERS, at every endpoint it
# exposes — GraphQL `addComment` and REST `PATCH /repos/{owner}/{repo}/issues/comments/{id}` alike
# (observed 2026-08-26 on github.com, #38). The asymmetry that makes it sharp: an over-cap body can
# be read and deleted but never written, so a marker comment already over the limit cannot be
# edited in place at all — the only route is a compacted re-author.
#
# CHARACTERS, not bytes. `body_bytes` (the write receipts, `spill_bytes`) counts UTF-8 bytes, which
# for non-ASCII text runs AHEAD of the character count this limit is measured in. Gating on bytes
# would refuse a legal multibyte body and could never detect that it had; gating on characters can
# only ever be right. Do not "simplify" a consumer of this constant to `stat().st_size`.
BODY_CHAR_LIMIT = 65536


def body_size(text):
    """The size fact for one body against :data:`BODY_CHAR_LIMIT` — the one shape every script that
    reports size emits (``parse.py phases``' ``size``, ``plan_shipped.py check``'s ``main``), so two
    readers of one staged body cannot disagree.

    ``text`` is counted as given, in characters. Callers read the file untranslated
    (``newline=""``) so a ``\\r\\n`` counts as the two characters ``gh_persist``'s gate counts:
    universal-newline reading would undercount a CRLF body against the gate that actually refuses.
    ``over_limit`` is ``>``, matching that gate — a body exactly AT the limit still writes.
    """
    chars = len(text)
    return {
        "chars": chars,
        "limit_chars": BODY_CHAR_LIMIT,
        "headroom_chars": BODY_CHAR_LIMIT - chars,
        "over_limit": chars > BODY_CHAR_LIMIT,
    }
