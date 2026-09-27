"""Read back the comment thread a ``gh_gather.run`` envelope already carries.

Every reader that locates a marker comment by scanning the thread (the research dossier, the epic
delivery log, the shipped-phase records) needs the same inline-vs-path read-back of the
``thread`` section. It lived as a verbatim local copy in two preps; a third consumer
(``prep_resolver``) is what promotes it here — one home, so the copies cannot drift.
"""

import json
from pathlib import Path


def load_thread(envelope):
    """Parse ``envelope``'s ``thread`` field (inline text or path-mode file) back into the list of
    normalized comment dicts ``gh_gather.run`` produced. Never re-fetches — a thread scan costs zero
    extra ``gh`` calls, which is the whole reason the marker readers scan rather than gather."""
    if envelope.get("thread_mode") == "path":
        text = Path(envelope["thread_path"]).read_text(encoding="utf-8")
    else:
        text = envelope.get("thread")
    if not text:
        return []
    return json.loads(text)
