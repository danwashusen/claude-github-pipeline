"""Offline test harness package for github-pipeline v2.

Making ``tests/`` an importable package lets suites do ``from tests.support import gitsandbox``
(and, from S3 onward, ``from tests.support import envelope_asserts`` or similar shared
conformance helpers) instead of manipulating ``sys.path`` per test file. ``tests/run.py`` inserts
the repo root onto ``sys.path`` before discovery so this import form works both when run.py is
invoked directly and when a single ``test_*.py`` is run on its own (e.g. ``python3 -m unittest
tests.test_gitsandbox``).
"""
