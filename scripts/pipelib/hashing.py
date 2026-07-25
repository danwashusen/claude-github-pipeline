"""The sha256 helper used for write-receipt byte fidelity (architecture.md §3, §12).

``gh_persist.py`` (S21) verifies a body-bearing write's round-trip hash and reports
``body_sha256`` in the envelope so a caller can confirm byte-for-byte that what GitHub now holds
matches what was staged — without ever re-reading the write back to verify (architecture.md §12:
"a zero exit with a URL is authoritative and is never re-read to verify"). This module is the one
place that digest is computed, so every emitter produces it identically.
"""

import hashlib


def sha256_hex(data):
    """Return the lowercase hex sha256 digest of ``data`` (``bytes``).

    Raises ``TypeError`` on anything that isn't ``bytes``/``bytearray`` — callers must read the
    staged file in binary mode and hash the raw bytes, never a decoded ``str``, so the digest is
    insensitive to any text-decoding step and matches what a plain ``shasum -a 256`` on the same
    file would produce.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError(
            "pipelib.hashing.sha256_hex: expected bytes/bytearray, got %s" % type(data).__name__
        )
    return hashlib.sha256(data).hexdigest()


def sha256_hex_file(path):
    """Return the lowercase hex sha256 digest of the file at ``path`` (str or ``pathlib.Path``).

    Reads the file in binary mode in fixed-size chunks so a large staged body (a plan, a diff)
    never needs to be loaded whole into a Python ``str`` just to be hashed.
    """
    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
