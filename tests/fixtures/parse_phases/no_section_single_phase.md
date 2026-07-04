## Approach
A single-phase bug-fix plan — `## Phases` is correctly omitted entirely per plan-schema.md
("multi-phase issues only — omit for single-phase").

## Changes (file-level)
- `src/widgets/save_button.py` — guard the double-submit race with a debounce flag
