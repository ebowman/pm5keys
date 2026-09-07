# eval_direct.py report -- LLM-direct key-sequence baseline

Comparison baseline: the LLM is asked to emit the PM5 key
sequence directly, instead of a WorkoutSpec JSON object. The real
pipeline (pm5keys.cli) never lets the LLM emit key presses --
this report exists to show the gap between that and asking it to.

RowErg only (rows with machines == BikeErg excluded).

backend: claude-cli, model: (default), k: 30, n rows: 14

## LLM-direct

- exact: 2/14 (14.3%)
- semantic: 2/14 (14.3%)
- unparsable: 0/14 (0.0%)

## Deterministic pipeline (spec.parse_spec + compile_keys.compile, no LLM)

- exact: 13/14 (92.9%)
- semantic: 13/14 (92.9%)

## Rows

| Title | Gold | LLM prediction | Exact? | Semantic? | Pipeline exact? |
|---|---|---|---|---|---|
| 2000/1500/1000/500m with three minutes rest | B-3D-C-D-2B-A-5C-4A-3B-E-C-D-C-A-5B-E-6C-E-C-D-C-A-5B-2E | B-3D-C-D-2B-A-5C-4A-3B-E-C-D-C-A-5B-4A-C-E-C-D-C-5A-C-2E | no | no | yes |
| 500m/1000m/500m/1000m/500m with two minutes rest. | B-3D-C-4A-2B-E-C-D-B-A-5C-E-C-D-C-A-5B-E-C-D-B-A-5C-E-C-D-C-A-5B-2E | B-3D-C-4A-2B-E-C-D-B-A-5C-E-C-D-C-A-5B-E-C-D-B-A-5C-E-C-D-C-A-5B-2E | yes | yes | yes |
| 1/2/1/2/1/2/1 minutes with 1 minute rest | B-4D-4A-B-E-D-B-E-D-C-E-D-B-E-D-C-E-D-B-E-D-C-2E | B-4D-B-4A-B-E-D-C-E-D-B-E-D-C-E-D-B-E-D-C-2E | no | no | yes |
| 12 x 1 min / 1 min easy | B-2D-B-4A-B-E | B-2D-B-5A-3B-E | no | no | yes |
| 4 x 1500m / 2 min easy | B-2D-A-D-B-5A-2B-E | B-2D-B-D-B-A-3C-4A-2B-E | no | no | yes |
| 5/4/3/2/1 minutes with 2 minutes rest | B-4D-4B-4A-2B-E-D-C-E-D-C-E-D-C-E-D-C-2E | B-4D-4A-B-E-D-B-E-D-B-E-D-B-2E | no | no | yes |
| 5/4/3/4/5 minutes with 2 minutes rest | B-4D-4B-4A-2B-E-D-C-E-D-C-E-D-B-E-D-B-2E | B-4D-B-B-4A-2B-E-D-C-E-D-B-2E | no | no | yes |
| 30 minute time trial | B-D-B-E | B-D-B-A-3C-E | no | no | yes |
| 5 x 1000m | B-2D-A-D-B-A-5C-5A-2B-E | B-2D-A-D-B-A-5C-4A-B-E | no | no | yes |
| 10 x 20 calories/:20 rest | B-2D-4C-4A-2B-E | B-2D-4C-3A-B-E | no | no | yes |
| 1000m | B-D-A-C-E | B-D-A-C-E | yes | yes | yes |
| 4 x 2023m, 3 minutes rest. | B-2D-A-D-2B-A-5C-A-2B-A-3B-2A-3B-E | B-2D-A-D-2B-A-5C-A-2B-A-4B-2A-3B-E | no | no | yes |
| 3000m, 3 minutes rest, 10 minutes work | B-3D-C-D-3B-A-5C-4A-3B-E-2D-B-A-C-2E | B-3D-5A-3B-A-2C-4A-B-E | no | no | yes |
| 2 rounds of 16 x 20 seconds work and 10 seconds rest | B-4D-A-2B-D-C-5A-B-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-4A-3B-A-C-E-D-4A-3C-A-B-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-4A-3B-A-C-2E | B-4D-4A-B-C-2A-2B-E-D-2E-D-2E | no | no | no |

## LLM mismatches

### 2000/1500/1000/500m with three minutes rest

- description: A 2000m interval, followed by a 1500m interval, then 1000m, then 500m. Three minutes light between intervals. (BikeErg: 4000/3000/2000/1000m)
- gold: `B-3D-C-D-2B-A-5C-4A-3B-E-C-D-C-A-5B-E-6C-E-C-D-C-A-5B-2E`
- predicted: `B-3D-C-D-2B-A-5C-4A-3B-E-C-D-C-A-5B-4A-C-E-C-D-C-5A-C-2E`
- unparsable: False
- semantic match: False
- simulated prediction: `{"machine": "all", "kind": "intervals_variable", "intervals": [{"work": {"distance_m": 2000}, "rest_s": 180}, {"work": {"distance_m": 1500}, "rest_s": 120}, {"work": {"distance_m": 500}, "rest_s": 60}], "notes": ""}`
- simulated gold: `{"machine": "all", "kind": "intervals_variable", "intervals": [{"work": {"distance_m": 2000}, "rest_s": 180}, {"work": {"distance_m": 1500}, "rest_s": 180}, {"work": {"distance_m": 1000}, "rest_s": 180}, {"work": {"distance_m": 500}, "rest_s": 180}], "notes": ""}`

### 1/2/1/2/1/2/1 minutes with 1 minute rest

- description: Seven alternating one and two minute intervals. One minute rest between each interval.
- gold: `B-4D-4A-B-E-D-B-E-D-C-E-D-B-E-D-C-E-D-B-E-D-C-2E`
- predicted: `B-4D-B-4A-B-E-D-C-E-D-B-E-D-C-E-D-B-E-D-C-2E`
- unparsable: False
- semantic match: False
- simulated prediction: `{"machine": "all", "kind": "intervals_variable", "intervals": [{"work": {"time_s": 120}, "rest_s": 60}, {"work": {"time_s": 60}, "rest_s": 60}, {"work": {"time_s": 120}, "rest_s": 60}, {"work": {"time_s": 60}, "rest_s": 60}, {"work": {"time_s": 120}, "rest_s": 60}, {"work": {"time_s": 60}, "rest_s": 60}], "notes": ""}`
- simulated gold: `{"machine": "all", "kind": "intervals_variable", "intervals": [{"work": {"time_s": 60}, "rest_s": 60}, {"work": {"time_s": 120}, "rest_s": 60}, {"work": {"time_s": 60}, "rest_s": 60}, {"work": {"time_s": 120}, "rest_s": 60}, {"work": {"time_s": 60}, "rest_s": 60}, {"work": {"time_s": 120}, "rest_s": 60}, {"work": {"time_s": 60}, "rest_s": 60}], "notes": ""}`

### 12 x 1 min / 1 min easy

- description: Twelve 1 minute pieces. One minute at light pressure between each piece.
- gold: `B-2D-B-4A-B-E`
- predicted: `B-2D-B-5A-3B-E`
- unparsable: False
- semantic match: False
- simulated prediction: `{"machine": "all", "kind": "intervals_time", "work": {"time_s": 60}, "rest_s": 30, "notes": ""}`
- simulated gold: `{"machine": "all", "kind": "intervals_time", "work": {"time_s": 60}, "rest_s": 60, "notes": ""}`

### 4 x 1500m / 2 min easy

- description: Complete four 1500 meter pieces. Continue at light pressure between each 1500. Note: for BikeErg, distance is 3000 meters.
- gold: `B-2D-A-D-B-5A-2B-E`
- predicted: `B-2D-B-D-B-A-3C-4A-2B-E`
- unparsable: False
- semantic match: False

### 5/4/3/2/1 minutes with 2 minutes rest

- description: Intervals of 5 minutes, 4 minutes, 3 minutes, 2 minutes, 1 minute. 2 minutes rest between each interval.
- gold: `B-4D-4B-4A-2B-E-D-C-E-D-C-E-D-C-E-D-C-2E`
- predicted: `B-4D-4A-B-E-D-B-E-D-B-E-D-B-2E`
- unparsable: False
- semantic match: False
- simulated prediction: `{"machine": "all", "kind": "intervals_variable", "intervals": [{"work": {"time_s": 60}, "rest_s": 60}, {"work": {"time_s": 120}, "rest_s": 60}, {"work": {"time_s": 180}, "rest_s": 60}, {"work": {"time_s": 240}, "rest_s": 60}], "notes": ""}`
- simulated gold: `{"machine": "all", "kind": "intervals_variable", "intervals": [{"work": {"time_s": 300}, "rest_s": 120}, {"work": {"time_s": 240}, "rest_s": 120}, {"work": {"time_s": 180}, "rest_s": 120}, {"work": {"time_s": 120}, "rest_s": 120}, {"work": {"time_s": 60}, "rest_s": 120}], "notes": ""}`

### 5/4/3/4/5 minutes with 2 minutes rest

- description: Intervals of 5 minutes, 4 minutes, 3 minutes, 4 minutes, 5 minutes. 2 minutes rest between each interval.
- gold: `B-4D-4B-4A-2B-E-D-C-E-D-C-E-D-B-E-D-B-2E`
- predicted: `B-4D-B-B-4A-2B-E-D-C-E-D-B-2E`
- unparsable: False
- semantic match: False
- simulated prediction: `{"machine": "all", "kind": "intervals_variable", "intervals": [{"work": {"time_s": 180}, "rest_s": 120}, {"work": {"time_s": 120}, "rest_s": 120}, {"work": {"time_s": 180}, "rest_s": 120}], "notes": ""}`
- simulated gold: `{"machine": "all", "kind": "intervals_variable", "intervals": [{"work": {"time_s": 300}, "rest_s": 120}, {"work": {"time_s": 240}, "rest_s": 120}, {"work": {"time_s": 180}, "rest_s": 120}, {"work": {"time_s": 240}, "rest_s": 120}, {"work": {"time_s": 300}, "rest_s": 120}], "notes": ""}`

### 30 minute time trial

- description: Do a 30 minute time trial, going for your personal best. Then enter your result in the Online Ranking and see where you stand with others of your age, gender and weight class.
- gold: `B-D-B-E`
- predicted: `B-D-B-A-3C-E`
- unparsable: False
- semantic match: False

### 5 x 1000m

- description: 5 x 1000m with 20 seconds rest
- gold: `B-2D-A-D-B-A-5C-5A-2B-E`
- predicted: `B-2D-A-D-B-A-5C-4A-B-E`
- unparsable: False
- semantic match: False
- simulated prediction: `{"machine": "all", "kind": "intervals_distance", "work": {"distance_m": 1000}, "rest_s": 60, "notes": ""}`
- simulated gold: `{"machine": "all", "kind": "intervals_distance", "work": {"distance_m": 1000}, "rest_s": 20, "notes": ""}`

### 10 x 20 calories/:20 rest

- description: Fixed intervals of 20 calories of work with 20 seconds of rest.
- gold: `B-2D-4C-4A-2B-E`
- predicted: `B-2D-4C-3A-B-E`
- unparsable: False
- semantic match: False
- simulated prediction: `{"machine": "all", "kind": "intervals_calorie", "work": {"calories": 20}, "rest_s": 60, "notes": ""}`
- simulated gold: `{"machine": "all", "kind": "intervals_calorie", "work": {"calories": 20}, "rest_s": 20, "notes": ""}`

### 4 x 2023m, 3 minutes rest.

- description: Four 2,023m pieces, with three minutes rest between intervals. (BikeErg: 4,046m)
- gold: `B-2D-A-D-2B-A-5C-A-2B-A-3B-2A-3B-E`
- predicted: `B-2D-A-D-2B-A-5C-A-2B-A-4B-2A-3B-E`
- unparsable: False
- semantic match: False
- simulated prediction: `{"machine": "all", "kind": "intervals_distance", "work": {"distance_m": 2024}, "rest_s": 180, "notes": ""}`
- simulated gold: `{"machine": "all", "kind": "intervals_distance", "work": {"distance_m": 2023}, "rest_s": 180, "notes": ""}`

### 3000m, 3 minutes rest, 10 minutes work

- description: A 3000m work interval, followed by 3 minutes rest. Then a 10 minute work interval. (BikeErg: 6000m) The goal is to maintain a faster average pace in the second work interval. Day 2 of the WOD Week Challenge.
- gold: `B-3D-C-D-3B-A-5C-4A-3B-E-2D-B-A-C-2E`
- predicted: `B-3D-5A-3B-A-2C-4A-B-E`
- unparsable: False
- semantic match: False

### 2 rounds of 16 x 20 seconds work and 10 seconds rest

- description: 16 intervals of 20 seconds work, with 10 seconds rest. Then rest for 3 minutes. Repeat the 16 intervals of 20 seconds work and 10 seconds rest. Day 6 of the WOD Week Challenge.
- gold: `B-4D-A-2B-D-C-5A-B-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-4A-3B-A-C-E-D-4A-3C-A-B-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-4A-3B-A-C-2E`
- predicted: `B-4D-4A-B-C-2A-2B-E-D-2E-D-2E`
- unparsable: False
- semantic match: False

