# compile_keys.py --verify report (PM3/PM4)

Per-row verification of pm5_model.py's simulator and compile_keys.py's
compiler against every row of spec_parsed.jsonl. See
compile_keys.py's module docstring for what each category means.
Rows whose gold pm34 sequence is null (calorie workouts, which PM3/PM4 do not support) are skipped: 0 skipped.

| Title | Machines | Category | Gold (PM3/PM4) | Compiled |
|---|---|---|---|---|
| 8 x 500m, 2 minutes rest | RowErg and SkiErg | EXACT | `B-D-C-4A-2B-E` | `B-D-C-4A-2B-E` |
| 8 x 500m, 2 minutes rest | BikeErg | EXACT | `B-D-C-D-B-A-5C-4A-2B-E` | `B-D-C-D-B-A-5C-4A-2B-E` |
| 1/3/5/3/1 minutes with 2 minutes rest | All Machines | EXACT | `B-D-E-D-4A-2B-E-D-2B-E-D-2B-E-D-2C-E-D-2C-2E` | `B-D-E-D-4A-2B-E-D-2B-E-D-2B-E-D-2C-E-D-2C-2E` |
| 5 x 750m / 2 min easy | RowErg and SkiErg | EXACT | `B-D-C-2B-A-5B-3A-2B-E` | `B-D-C-2B-A-5B-3A-2B-E` |
| 5 x 750m / 2 min easy | BikeErg | EXACT | `B-D-C-D-B-5A-2B-E` | `B-D-C-D-B-5A-2B-E` |
| 500m/1000m/500m/1000m/500m with two minutes rest. | RowErg and SkiErg | EXACT | `B-D-E-C-4A-2B-E-C-D-B-A-5C-E-C-D-C-A-5B-E-C-D-B-A-5C-E-C-D-C-A-5B-2E` | `B-D-E-C-4A-2B-E-C-D-B-A-5C-E-C-D-C-A-5B-E-C-D-B-A-5C-E-C-D-C-A-5B-2E` |
| 500m/1000m/500m/1000m/500m with two minutes rest. | BikeErg | EXACT | `B-D-E-C-D-B-A-5C-4A-2B-E-C-D-B-E-C-D-C-E-C-D-B-E-C-D-C-2E` | `B-D-E-C-D-B-A-5C-4A-2B-E-C-D-B-E-C-D-C-E-C-D-B-E-C-D-C-2E` |
| 1/2/3/4/5/6 minutes with 1 minute rest | All Machines | EXACT | `B-D-E-D-4A-B-E-D-B-E-D-B-E-D-B-E-D-B-E-D-B-2E` | `B-D-E-D-4A-B-E-D-B-E-D-B-E-D-B-E-D-B-E-D-B-2E` |
| 10 x 1 min / 1 min easy | All Machines | EXACT | `B-2D-4A-B-E` | `B-2D-4A-B-E` |
| 1:00, 1:30, 2:00, 2:30, 3:00, 3:30, 4:00 - equal work and rest. | All Machines | EQUIVALENT | `B-D-E-D-4A-B-E-D-A-3B-4A-3B-E-D-B-A-3C-3A-B-A-3C-E-D-A-3B-4A-3B-E-D-B-A-3C-3A-B-A-3C-E-D-A-3B-4A-3B-E-D-B-A-3C-3A-B-A-3C-2E` | `B-D-E-D-4A-B-E-D-A-3B-4A-3B-E-D-B-A-3C-3A-B-A-3C-E-D-A-3B-4A-3B-E-D-B-A-3C-3A-B-A-3C-E-D-A-3B-4A-3B-E-D-B-A-3C-2E` |
| 6 x 1000m, 2 minutes rest | RowErg and SkiErg | EXACT | `B-D-C-D-B-A-5C-4A-2B-E` | `B-D-C-D-B-A-5C-4A-2B-E` |
| 6 x 1000m, 2 minutes rest | BikeErg | EXACT | `B-D-C-D-2B-A-5C-4A-2B-E` | `B-D-C-D-2B-A-5C-4A-2B-E` |
| 5 x 3 min / 2 min easy | All Machines | EXACT | `B-2D-2B-4A-2B-E` | `B-2D-2B-4A-2B-E` |
| 12 x 250m / 45 sec easy | RowErg and SkiErg | EXACT | `B-D-4C-A-5B-4A-4B-A-5B-E` | `B-D-4C-A-5B-4A-4B-A-5B-E` |
| 12 x 250m / 45 sec easy | BikeErg | EXACT | `B-D-C-5A-4B-A-5B-E` | `B-D-C-5A-4B-A-5B-E` |
| 10 x 2:30 / 30 seconds easy | All Machines | EXACT | `B-2D-B-A-3B-4A-3B-E` | `B-2D-B-A-3B-4A-3B-E` |
| 6 x 500m / 1 min easy | RowErg and SkiErg | EXACT | `B-D-C-4A-B-E` | `B-D-C-4A-B-E` |
| 6 x 500m / 1 min easy | BikeErg | EXACT | `B-D-C-D-B-A-5C-4A-B-E` | `B-D-C-D-B-A-5C-4A-B-E` |
| 2 min, 3 min, 4 min, 3 min, 2 min pyramid / 2 min easy | All Machines | EXACT | `B-D-E-D-B-4A-2B-E-D-B-E-D-B-E-D-C-E-D-C-2E` | `B-D-E-D-B-4A-2B-E-D-B-E-D-B-E-D-C-E-D-C-2E` |

## Non-EXACT rows in detail

### 1:00, 1:30, 2:00, 2:30, 3:00, 3:30, 4:00 - equal work and rest. (All Machines)

- category: EQUIVALENT
- gold: `B-D-E-D-4A-B-E-D-A-3B-4A-3B-E-D-B-A-3C-3A-B-A-3C-E-D-A-3B-4A-3B-E-D-B-A-3C-3A-B-A-3C-E-D-A-3B-4A-3B-E-D-B-A-3C-3A-B-A-3C-2E`
- compiled: `B-D-E-D-4A-B-E-D-A-3B-4A-3B-E-D-B-A-3C-3A-B-A-3C-E-D-A-3B-4A-3B-E-D-B-A-3C-3A-B-A-3C-E-D-A-3B-4A-3B-E-D-B-A-3C-2E`
- spec: `{"kind": "intervals_variable", "intervals": [{"work": {"time_s": 60}, "rest_s": 60}, {"work": {"time_s": 90}, "rest_s": 90}, {"work": {"time_s": 120}, "rest_s": 120}, {"work": {"time_s": 150}, "rest_s": 150}, {"work": {"time_s": 180}, "rest_s": 180}, {"work": {"time_s": 210}, "rest_s": 210}, {"work": {"time_s": 240}, "rest_s": 0}], "machine": "all", "notes": ""}`
- sim(gold): `{"machine": "all", "kind": "intervals_variable", "intervals": [{"work": {"time_s": 60}, "rest_s": 60}, {"work": {"time_s": 90}, "rest_s": 90}, {"work": {"time_s": 120}, "rest_s": 120}, {"work": {"time_s": 150}, "rest_s": 150}, {"work": {"time_s": 180}, "rest_s": 180}, {"work": {"time_s": 210}, "rest_s": 210}, {"work": {"time_s": 240}, "rest_s": 240}], "notes": ""}`
- sim(compiled): `{"machine": "all", "kind": "intervals_variable", "intervals": [{"work": {"time_s": 60}, "rest_s": 60}, {"work": {"time_s": 90}, "rest_s": 90}, {"work": {"time_s": 120}, "rest_s": 120}, {"work": {"time_s": 150}, "rest_s": 150}, {"work": {"time_s": 180}, "rest_s": 180}, {"work": {"time_s": 210}, "rest_s": 210}, {"work": {"time_s": 240}, "rest_s": 210}], "notes": ""}`

