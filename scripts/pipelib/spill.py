"""The spill helper: decide inline-vs-path for a verbatim section and produce its
``*_bytes``/``*_mode``/``*_path`` fields (architecture.md §3).

Any verbatim section (issue/PR body, thread, marker comment, diff) is inline in the envelope when
its byte size is at or under the threshold, and written through to a file under the session
scratch dir when larger — so neither the emitting script nor its caller holds an oversized payload
in a model's context. Diffs and line-comment sets are always spilled regardless of size (the
``force_path`` flag), per architecture.md §3's "Diffs and line-comment sets are always `path`."
"""

import os
from pathlib import Path

# Legacy v1 env var name (``skills/_shared`` / `CLAUDE.md`'s "Rule 8"); still honored as a
# fallback so a consuming repo's existing override keeps working during the v1/v2 coexistence
# window (architecture.md §11).
LEGACY_THRESHOLD_ENV_VAR = "GH_OPS_INLINE_THRESHOLD_BYTES"

# The v2 env var name (architecture.md §3). Takes precedence over the legacy name when both are
# set.
THRESHOLD_ENV_VAR = "GH_PIPELINE_INLINE_THRESHOLD_BYTES"

# architecture.md §3: "Threshold: GH_PIPELINE_INLINE_THRESHOLD_BYTES (default 25600; legacy
# GH_OPS_INLINE_THRESHOLD_BYTES honored)."
DEFAULT_THRESHOLD_BYTES = 25600


def resolve_threshold(env=None):
    """Resolve the active inline/path threshold in bytes, applying the documented precedence:

    1. ``GH_PIPELINE_INLINE_THRESHOLD_BYTES`` (new name) — honored if set and parses as an int.
    2. ``GH_OPS_INLINE_THRESHOLD_BYTES`` (legacy name) — honored if the new name is unset/unparsable
       and this one is set and parses as an int.
    3. :data:`DEFAULT_THRESHOLD_BYTES` (25600) — when neither is set or usable.

    ``env`` defaults to ``os.environ``; passing an explicit dict (as tests do) makes this
    deterministic and independent of the calling process's real environment.
    """
    source = env if env is not None else os.environ

    new_value = source.get(THRESHOLD_ENV_VAR)
    if new_value is not None:
        try:
            return int(new_value)
        except (TypeError, ValueError):
            pass  # fall through to legacy, per the documented precedence

    legacy_value = source.get(LEGACY_THRESHOLD_ENV_VAR)
    if legacy_value is not None:
        try:
            return int(legacy_value)
        except (TypeError, ValueError):
            pass  # fall through to the default

    return DEFAULT_THRESHOLD_BYTES


def spill_bytes(data, section_name, scratch_dir, env=None, force_path=False, filename=None):
    """Decide inline-vs-path for ``data`` (bytes) under ``section_name``, writing the file when
    the section spills.

    Returns a dict of the section's envelope fields, keyed by ``section_name``:
    ``{"<section_name>_bytes": N, "<section_name>_mode": "inline"|"path", "<section_name>_path":
    "<path>"}`` (the ``_path`` key is present **iff** mode is ``"path"``) plus, for an inline
    section, the bare field carrying the content itself (``"<section_name>": "<decoded text>"``)
    per architecture.md §4: "Inline-mode sections carry the content in the bare field
    (`issue_body`) alongside `*_bytes`." The bare field is decoded as UTF-8 text (pinned per
    architecture.md §1) — this helper is for text sections; binary payloads (a diff can be
    treated as text-safe UTF-8 in this codebase's git usage) still round-trip because ``git``
    output is UTF-8-pinned by the subprocess runner already.

    ``data`` must be ``bytes``; ``scratch_dir`` is the directory (created if missing) any spilled
    file is written under. ``force_path`` always spills regardless of size (diffs, line-comment
    sets). ``filename`` overrides the spilled file's name (defaults to ``"<section_name>.txt"``).
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError(
            "pipelib.spill.spill_bytes: data must be bytes/bytearray, got %s"
            % type(data).__name__
        )
    if not section_name:
        raise ValueError("pipelib.spill.spill_bytes: section_name must be non-empty")

    size = len(data)
    threshold = resolve_threshold(env=env)
    mode = "path" if (force_path or size > threshold) else "inline"

    fields = {"%s_bytes" % section_name: size, "%s_mode" % section_name: mode}

    if mode == "path":
        scratch_path = Path(scratch_dir)
        scratch_path.mkdir(parents=True, exist_ok=True)
        target = scratch_path / (filename if filename else "%s.txt" % section_name)
        with open(target, "wb") as fh:
            fh.write(data)
        fields["%s_path" % section_name] = str(target)
    else:
        fields[section_name] = data.decode("utf-8")

    return fields


def read_section(envelope, key):
    """The read-back counterpart of :func:`spill_bytes`: return section ``key``'s text from an
    envelope (or any dict carrying spill fields), whether the section was kept inline (the bare
    field) or spilled to disk (``<key>_mode == "path"`` → read ``<key>_path`` as UTF-8). Returns
    ``""`` when the section is absent entirely.

    This is the single home for the ``inline|path`` read-back that was previously restated per
    prep (`_extract_body` and inline equivalents) — a change to the spill-mode contract lands
    here and on :func:`spill_bytes` together, never in per-prep copies that can lag.
    """
    value = envelope.get(key)
    if value is None and envelope.get("%s_mode" % key) == "path":
        with open(envelope["%s_path" % key], "r", encoding="utf-8") as fh:
            return fh.read()
    return value or ""
