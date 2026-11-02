# compile_keys.py --verify report (PM3/PM4)

Per-row verification of pm5_model.py's simulator and compile_keys.py's
compiler against every row of spec_parsed.jsonl. See
compile_keys.py's module docstring for what each category means.
Rows whose gold pm34 sequence is null (calorie workouts, which PM3/PM4 do not support) are skipped: 0 skipped.

| Title | Machines | Category | Gold (PM3/PM4) | Compiled |
|---|---|---|---|---|

## Non-EXACT rows in detail

