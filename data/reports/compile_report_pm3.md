# compile_keys.py --verify report (PM3/PM4)

Per-row verification of pm5_model.py's simulator and compile_keys.py's
compiler against every row of spec_parsed.jsonl. See
compile_keys.py's module docstring for what each category means.
Rows whose gold pm34 sequence is null (calorie workouts, which PM3/PM4 do not support) are skipped: 5 skipped.

| Title | Machines | Category | Gold (PM3/PM4) | Compiled |
|---|---|---|---|---|
| 1/3/5/3/1 minutes with 2 minutes rest | All Machines | EXACT | `B-D-E-D-4A-2B-E-D-2B-E-D-2B-E-D-2C-E-D-2C-2E` | `B-D-E-D-4A-2B-E-D-2B-E-D-2B-E-D-2C-E-D-2C-2E` |
| 10 x 1 min / 1 min easy | All Machines | EXACT | `B-2D-4A-B-E` | `B-2D-4A-B-E` |
| 8/6/4/2 minutes with 3 minutes rest | All Machines | EXACT | `B-D-E-D-7B-4A-3B-E-D-2C-E-D-2C-E-D-2C-2E` | `B-D-E-D-7B-4A-3B-E-D-2C-E-D-2C-E-D-2C-2E` |
| 1 min, 2 min, 3 min, 4 min, 3 min, 2 min, 1 min pyramid / 1 min easy | All Machines | EXACT | `B-D-E-D-4A-B-E-D-B-E-D-B-E-D-B-E-D-C-E-D-C-E-D-C-2E` | `B-D-E-D-4A-B-E-D-B-E-D-B-E-D-B-E-D-C-E-D-C-E-D-C-2E` |
| 4/3/2/1/2/3/4 minutes with 2 minutes rest | All Machines | EXACT | `B-D-E-D-3B-4A-2B-E-D-C-E-D-C-E-D-C-E-D-B-E-D-B-E-D-B-2E` | `B-D-E-D-3B-4A-2B-E-D-C-E-D-C-E-D-C-E-D-B-E-D-B-E-D-B-2E` |
| 12 x 250m / 45 sec easy | RowErg and SkiErg | EXACT | `B-D-4C-A-5B-4A-4B-A-5B-E` | `B-D-4C-A-5B-4A-4B-A-5B-E` |
| 12 x 250m / 45 sec easy | BikeErg | EXACT | `B-D-C-5A-4B-A-5B-E` | `B-D-C-5A-4B-A-5B-E` |
| 2 min, 3 min, 4 min, 3 min, 2 min pyramid / 2 min easy | All Machines | EXACT | `B-D-E-D-B-4A-2B-E-D-B-E-D-B-E-D-C-E-D-C-2E` | `B-D-E-D-B-4A-2B-E-D-B-E-D-B-E-D-C-E-D-C-2E` |
| 2000/1500/1000/500m with three minutes rest | RowErg and SkiErg | EXACT | `B-D-E-C-D-2B-A-5C-4A-3B-E-C-D-C-A-5B-E-6C-E-C-D-C-A-5B-2E` | `B-D-E-C-D-2B-A-5C-4A-3B-E-C-D-C-A-5B-E-6C-E-C-D-C-A-5B-2E` |
| 2000/1500/1000/500m with three minutes rest | BikeErg | EXACT | `B-D-E-C-D-4B-A-5C-4A-3B-E-C-D-C-E-C-D-C-E-C-D-C-2E` | `B-D-E-C-D-4B-A-5C-4A-3B-E-C-D-C-E-C-D-C-E-C-D-C-2E` |
| 6 x 500m / 1 min easy | RowErg and SkiErg | EXACT | `B-D-C-4A-B-E` | `B-D-C-4A-B-E` |
| 6 x 500m / 1 min easy | BikeErg | EXACT | `B-D-C-D-B-A-5C-4A-B-E` | `B-D-C-D-B-A-5C-4A-B-E` |
| 20 x 45s work, 45s rest | All Machines | EQUIVALENT | `B-2D-A-4B-D-C-2A-5B-3A-4B-A-5B-E` | `B-2D-C-A-4B-A-5B-3A-4B-A-5B-E` |
| 8 x 500m, 2 minutes rest | RowErg and SkiErg | EXACT | `B-D-C-4A-2B-E` | `B-D-C-4A-2B-E` |
| 8 x 500m, 2 minutes rest | BikeErg | EXACT | `B-D-C-D-B-A-5C-4A-2B-E` | `B-D-C-D-B-A-5C-4A-2B-E` |
| 500m/1000m/500m/1000m/500m with two minutes rest. | RowErg and SkiErg | EXACT | `B-D-E-C-4A-2B-E-C-D-B-A-5C-E-C-D-C-A-5B-E-C-D-B-A-5C-E-C-D-C-A-5B-2E` | `B-D-E-C-4A-2B-E-C-D-B-A-5C-E-C-D-C-A-5B-E-C-D-B-A-5C-E-C-D-C-A-5B-2E` |
| 500m/1000m/500m/1000m/500m with two minutes rest. | BikeErg | EXACT | `B-D-E-C-D-B-A-5C-4A-2B-E-C-D-B-E-C-D-C-E-C-D-B-E-C-D-C-2E` | `B-D-E-C-D-B-A-5C-4A-2B-E-C-D-B-E-C-D-C-E-C-D-B-E-C-D-C-2E` |
| Intervals of 6/3/3/1/1/1 minutes with 2 minutes rest. | All Machines | EXACT | `B-D-E-D-5B-4A-2B-E-D-3C-E-D-E-D-2C-E-D-E-D-2E` | `B-D-E-D-5B-4A-2B-E-D-3C-E-D-E-D-2C-E-D-E-D-2E` |
| 5 x 750m / 2 min easy | RowErg and SkiErg | EXACT | `B-D-C-2B-A-5B-3A-2B-E` | `B-D-C-2B-A-5B-3A-2B-E` |
| 5 x 750m / 2 min easy | BikeErg | EXACT | `B-D-C-D-B-5A-2B-E` | `B-D-C-D-B-5A-2B-E` |
| 1/2/3/4/5/4/3/2/1 minutes with 2 minutes rest | All Machines | EXACT | `B-D-E-D-4A-2B-E-D-B-E-D-B-E-D-B-E-D-B-E-D-C-E-D-C-E-D-C-E-D-C-2E` | `B-D-E-D-4A-2B-E-D-B-E-D-B-E-D-B-E-D-B-E-D-C-E-D-C-E-D-C-E-D-C-2E` |
| 5 x 3 min / 2 min easy | All Machines | EXACT | `B-2D-2B-4A-2B-E` | `B-2D-2B-4A-2B-E` |
| 1:00, 1:30, 2:00, 2:30, 3:00, 3:30, 4:00 - equal work and rest. | All Machines | EQUIVALENT | `B-D-E-D-4A-B-E-D-A-3B-4A-3B-E-D-B-A-3C-3A-B-A-3C-E-D-A-3B-4A-3B-E-D-B-A-3C-3A-B-A-3C-E-D-A-3B-4A-3B-E-D-B-A-3C-3A-B-A-3C-2E` | `B-D-E-D-4A-B-E-D-A-3B-4A-3B-E-D-B-A-3C-3A-B-A-3C-E-D-A-3B-4A-3B-E-D-B-A-3C-3A-B-A-3C-E-D-A-3B-4A-3B-E-D-B-A-3C-2E` |
| 1/2/1/2/1/2/1 minutes with 1 minute rest | All Machines | EXACT | `B-D-E-D-4A-B-E-D-B-E-D-C-E-D-B-E-D-C-E-D-B-E-D-C-2E` | `B-D-E-D-4A-B-E-D-B-E-D-C-E-D-B-E-D-C-E-D-B-E-D-C-2E` |
| 6 x 2 min / 1 min easy | All Machines | EXACT | `B-2D-B-4A-B-E` | `B-2D-B-4A-B-E` |
| 1/2/3/4/5 minutes with 2 minutes rest | All Machines | EXACT | `B-D-E-D-4A-2B-E-D-B-E-D-B-E-D-B-E-D-B-2E` | `B-D-E-D-4A-2B-E-D-B-E-D-B-E-D-B-E-D-B-2E` |
| 2/3/2/3/2/3/2 minutes with 1 minute rest | All Machines | EXACT | `B-D-E-D-B-4A-B-E-D-B-E-D-C-E-D-B-E-D-C-E-D-B-E-D-C-2E` | `B-D-E-D-B-4A-B-E-D-B-E-D-C-E-D-B-E-D-C-E-D-B-E-D-C-2E` |
| 12 x 1 min / 1 min easy | All Machines | EXACT | `B-2D-4A-B-E` | `B-2D-4A-B-E` |
| 8 x 2 min / 1 min easy | All Machines | EXACT | `B-2D-B-4A-B-E` | `B-2D-B-4A-B-E` |
| 4 x 1500m / 2 min easy | RowErg and SkiErg | EXACT | `B-D-C-D-B-5A-2B-E` | `B-D-C-D-B-5A-2B-E` |
| 4 x 1500m / 2 min easy | BikeErg | EXACT | `B-D-C-D-3B-A-5C-4A-2B-E` | `B-D-C-D-3B-A-5C-4A-2B-E` |
| 10 x 2:30 / 30 seconds easy | All Machines | EXACT | `B-2D-B-A-3B-4A-3B-E` | `B-2D-B-A-3B-4A-3B-E` |
| 1/2/3/4/5/6 minutes with 1 minute rest | All Machines | EXACT | `B-D-E-D-4A-B-E-D-B-E-D-B-E-D-B-E-D-B-E-D-B-2E` | `B-D-E-D-4A-B-E-D-B-E-D-B-E-D-B-E-D-B-E-D-B-2E` |
| 5/4/3/2/1 minutes with 2 minutes rest | All Machines | EXACT | `B-D-E-D-4B-4A-2B-E-D-C-E-D-C-E-D-C-E-D-C-2E` | `B-D-E-D-4B-4A-2B-E-D-C-E-D-C-E-D-C-E-D-C-2E` |
| 50 - 40 - 30 - 20 - 10 Cals with 2 minutes easy | All Machines | EXACT | `B-D-E-B-3A-2B-E-B-C-E-B-C-E-B-C-E-B-C-2E` | `B-D-E-B-3A-2B-E-B-C-E-B-C-E-B-C-E-B-C-2E` |
| 20 - 40 - 60 - 80 - 100 Cal with 2 minutes easy | All Machines | EXACT | `B-D-E-B-3C-3A-2B-E-3B-E-3B-E-3B-E-B-D-B-A-8C-2E` | `B-D-E-B-3C-3A-2B-E-3B-E-3B-E-3B-E-B-D-B-A-8C-2E` |
| 5 x 500m / 2 min easy | RowErg and SkiErg | EXACT | `B-D-C-4A-2B-E` | `B-D-C-4A-2B-E` |
| 5 x 500m / 2 min easy | BikeErg | EXACT | `B-D-C-D-B-A-5C-4A-2B-E` | `B-D-C-D-B-A-5C-4A-2B-E` |
| 6 x 1000m, 2 minutes rest | RowErg and SkiErg | EXACT | `B-D-C-D-B-A-5C-4A-2B-E` | `B-D-C-D-B-A-5C-4A-2B-E` |
| 6 x 1000m, 2 minutes rest | BikeErg | EXACT | `B-D-C-D-2B-A-5C-4A-2B-E` | `B-D-C-D-2B-A-5C-4A-2B-E` |
| 3/4/5/4/3 minutes with 2 minutes rest | All Machines | EXACT | `B-D-E-D-2B-4A-2B-E-D-B-E-D-B-E-D-C-E-D-C-2E` | `B-D-E-D-2B-4A-2B-E-D-B-E-D-B-E-D-C-E-D-C-2E` |
| 4 x 1000m / 1 min easy | RowErg and SkiErg | EXACT | `B-D-C-D-B-A-5C-4A-B-E` | `B-D-C-D-B-A-5C-4A-B-E` |
| 4 x 1000m / 1 min easy | BikeErg | EXACT | `B-D-C-D-2B-A-5C-4A-B-E` | `B-D-C-D-2B-A-5C-4A-B-E` |
| 4 x 3 min / 2 min easy | All Machines | EXACT | `B-2D-2B-4A-2B-E` | `B-2D-2B-4A-2B-E` |
| 4 x 4 min / 2 min easy | All Machines | EXACT | `B-2D-3B-4A-2B-E` | `B-2D-3B-4A-2B-E` |
| 10/20/30/40/50/60 Calories.  1 minute rest between intervals. | All Machines | EXACT | `B-D-E-B-4C-3A-B-E-2B-E-2B-E-2B-E-2B-E-2B-2E` | `B-D-E-B-4C-3A-B-E-2B-E-2B-E-2B-E-2B-E-2B-2E` |
| 10 x 1:40 / 20 seconds easy | All Machines | GOLD_VARIABLE | `B-D-E-D-A-4B-4A-2B-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-2E` | `B-2D-A-4B-4A-2B-E` |
| 6 x 3 minutes with 2 minutes light. | All Machines | EXACT | `B-2D-2B-4A-2B-E` | `B-2D-2B-4A-2B-E` |
| 5/4/3/4/5 minutes with 2 minutes rest | All Machines | EXACT | `B-D-E-D-4B-4A-2B-E-D-C-E-D-C-E-D-B-E-D-B-2E` | `B-D-E-D-4B-4A-2B-E-D-C-E-D-C-E-D-B-E-D-B-2E` |
| 3 x 1000m / 3 min easy | RowErg and SkiErg | EXACT | `B-D-C-D-B-A-5C-4A-3B-E` | `B-D-C-D-B-A-5C-4A-3B-E` |
| 3 x 1000m / 3 min easy | BikeErg | EXACT | `B-D-C-D-2B-A-5C-4A-3B-E` | `B-D-C-D-2B-A-5C-4A-3B-E` |
| 6/5/4/3/2/1 minutes with 1 minute rest | All Machines | EXACT | `B-D-E-D-5B-4A-B-E-D-C-E-D-C-E-D-C-E-D-C-E-D-C-2E` | `B-D-E-D-5B-4A-B-E-D-C-E-D-C-E-D-C-E-D-C-E-D-C-2E` |
| 4 x 4 min / 3 min easy | All Machines | EXACT | `B-2D-3B-4A-3B-E` | `B-2D-3B-4A-3B-E` |
| 2000m/3 minutes rest/1000m/2 minutes rest/500m | RowErg and SkiErg | EQUIVALENT | `B-D-E-C-D-2B-A-5C-4A-3B-E-C-D-C-5A-C-E-C-D-C-A-5B-4A-C-2E` | `B-D-E-C-D-2B-A-5C-4A-3B-E-C-D-C-5A-C-E-C-D-C-A-5B-2E` |
| 2000m/3 minutes rest/1000m/2 minutes rest/500m | BikeErg | EQUIVALENT | `B-D-E-C-D-4B-A-5C-4A-3B-E-C-D-2C-5A-C-E-C-D-C-5A-C-2E` | `B-D-E-C-D-4B-A-5C-4A-3B-E-C-D-2C-5A-C-E-C-D-C-2E` |
| 5 x 1000m / 1 min easy | RowErg and SkiErg | EXACT | `B-D-C-D-B-A-5C-4A-B-E` | `B-D-C-D-B-A-5C-4A-B-E` |
| 5 x 1000m / 1 min easy | BikeErg | EXACT | `B-D-C-D-2B-A-5C-4A-B-E` | `B-D-C-D-2B-A-5C-4A-B-E` |
| 4 x 5 min / 2 min easy | All Machines | EXACT | `B-2D-4B-4A-2B-E` | `B-2D-4B-4A-2B-E` |
| 5 x 4 min / 2 min easy | All Machines | EXACT | `B-2D-3B-4A-2B-E` | `B-2D-3B-4A-2B-E` |
| 8 x 1 min / 3 min easy | All Machines | EXACT | `B-2D-4A-3B-E` | `B-2D-4A-3B-E` |
| 30 minute time trial | All Machines | EXACT | `B-D-B-E` | `B-D-B-E` |
| 10,000 meter time trial | RowErg and SkiErg | EXACT | `B-D-A-D-B-A-2C-E` | `B-D-A-D-B-A-2C-E` |
| 10,000 meter time trial | BikeErg | EXACT | `B-D-A-D-2B-A-2C-E` | `B-D-A-D-2B-A-2C-E` |
| 5000m time trial | RowErg and SkiErg | EXACT | `B-D-A-3B-E` | `B-D-A-3B-E` |
| 5000m time trial | BikeErg | EXACT | `B-D-A-D-B-A-2C-E` | `B-D-A-D-B-A-2C-E` |
| 5 x 4 min / 1 min easy | All Machines | EXACT | `B-2D-3B-4A-B-E` | `B-2D-3B-4A-B-E` |
| 4 x 6 minutes with three minutes rest | All Machines | EXACT | `B-2D-5B-4A-3B-E` | `B-2D-5B-4A-3B-E` |
| 3 x 2000m, 3 minutes rest.  (BikeErg: 4,000m) | RowErg and SkiErg | EXACT | `B-D-C-D-2B-A-5C-4A-3B-E` | `B-D-C-D-2B-A-5C-4A-3B-E` |
| 3 x 2000m, 3 minutes rest.  (BikeErg: 4,000m) | BikeErg | EXACT | `B-D-C-D-4B-A-5C-4A-3B-E` | `B-D-C-D-4B-A-5C-4A-3B-E` |
| 6 x 4 min / 2 min easy | All Machines | EXACT | `B-2D-3B-4A-2B-E` | `B-2D-3B-4A-2B-E` |
| 8 x 1000m | RowErg and SkiErg | EXACT | `B-D-C-D-B-A-5C-4A-2B-E` | `B-D-C-D-B-A-5C-4A-2B-E` |
| 8 x 1000m | BikeErg | EXACT | `B-D-C-D-2B-A-5C-4A-2B-E` | `B-D-C-D-2B-A-5C-4A-2B-E` |
| 5 x 1000m | All Machines | EXACT | `B-D-C-D-B-A-5C-5A-2B-E` | `B-D-C-D-B-A-5C-5A-2B-E` |
| 5 min, 10 min, 15 min, 10 min, 5 min pyramid / 2 min easy | All Machines | GOLD_MISMATCH | `B-D-E-D-4B-4A-2B-E-2D-B-A-5C-E-D-5B-E-D-5C-E-D-5B-2E` | `B-D-E-D-4B-4A-2B-E-2D-B-A-5C-E-D-5B-E-D-5C-E-2D-C-A-5B-2E` |
| 5 x 1000m | All Machines | EXACT | `B-D-C-D-B-A-5C-4A-B-E` | `B-D-C-D-B-A-5C-4A-B-E` |
| 12 x 3 min / 1 min easy | All Machines | EXACT | `B-2D-2B-4A-B-E` | `B-2D-2B-4A-B-E` |
| 1000m | RowErg and SkiErg | EXACT | `B-D-A-C-E` | `B-D-A-C-E` |
| 1000m | BikeErg | EXACT | `B-D-A-E` | `B-D-A-E` |
| 5000m for International Women's Day | RowErg and SkiErg | EXACT | `B-D-A-3B-E` | `B-D-A-3B-E` |
| 5000m for International Women's Day | BikeErg | EXACT | `B-D-A-D-B-A-2C-E` | `B-D-A-D-B-A-2C-E` |
| 6000m | RowErg and SkiErg | EXACT | `B-D-A-4B-E` | `B-D-A-4B-E` |
| 6000m | BikeErg | EXACT | `B-D-A-D-B-E` | `B-D-A-D-B-E` |
| 1900m | RowErg and SkiErg | EXACT | `B-D-A-C-A-9B-E` | `B-D-A-C-A-9B-E` |
| 1900m | BikeErg | EXACT | `B-D-A-B-A-8B-E` | `B-D-A-B-A-8B-E` |
| 3333m | RowErg and SkiErg | EXACT | `B-D-A-B-A-3B-A-3B-A-3B-E` | `B-D-A-B-A-3B-A-3B-A-3B-E` |
| 3333m | BikeErg | EXACT | `B-D-A-4B-A-6B-A-6B-A-6B-E` | `B-D-A-4B-A-6B-A-6B-A-6B-E` |
| 7 x 2:30, 30 seconds rest | All Machines | EXACT | `B-2D-B-A-3B-4A-3B-E` | `B-2D-B-A-3B-4A-3B-E` |
| 3 X 12 Minutes with 2 Minutes Rest | All Machines | EXACT | `B-3D-B-A-B-4A-2B-E` | `B-3D-B-A-B-4A-2B-E` |
| 4 x 2023m, 3 minutes rest. | RowErg and SkiErg | EXACT | `B-D-C-D-2B-A-5C-A-2B-A-3B-2A-3B-E` | `B-D-C-D-2B-A-5C-A-2B-A-3B-2A-3B-E` |
| 4 x 2023m, 3 minutes rest. | BikeErg | EXACT | `B-D-C-D-4B-A-5C-A-4B-A-6B-2A-3B-E` | `B-D-C-D-4B-A-5C-A-4B-A-6B-2A-3B-E` |
| 10 x 1 minute / 30 seconds rest | All Machines | EXACT | `B-2D-5A-3B-E` | `B-2D-5A-3B-E` |
| 1000m for the 2024 World Rowing Virtual Indoor Sprints | RowErg and SkiErg | EXACT | `B-D-A-C-E` | `B-D-A-C-E` |
| 1000m for the 2024 World Rowing Virtual Indoor Sprints | BikeErg | EXACT | `B-D-A-E` | `B-D-A-E` |
| 3000m, 3 minutes rest, 10 minutes work | RowErg and SkiErg | EXACT | `B-D-E-C-D-3B-A-5C-4A-3B-E-2D-B-A-C-2E` | `B-D-E-C-D-3B-A-5C-4A-3B-E-2D-B-A-C-2E` |
| 3000m, 3 minutes rest, 10 minutes work | BikeErg | EXACT | `B-D-E-C-D-6B-A-5C-4A-3B-E-2D-B-A-C-2E` | `B-D-E-C-D-6B-A-5C-4A-3B-E-2D-B-A-C-2E` |
| 30 minutes | All Machines | EXACT | `B-D-B-E` | `B-D-B-E` |
| 2 x 10 minutes / 2 minutes rest | All Machines | EXACT | `B-3D-B-A-C-4A-2B-E` | `B-3D-B-A-C-4A-2B-E` |
| 60 minutes | All Machines | EXACT | `B-D-B-D-B-A-3C-E` | `B-D-B-D-B-A-3C-E` |
| 1/2/3/1/2/2 minutes with 2 minutes rest | All Machines | EXACT | `B-D-E-D-4A-2B-E-D-B-E-D-B-E-D-2C-E-D-B-E-D-2E` | `B-D-E-D-4A-2B-E-D-B-E-D-B-E-D-2C-E-D-B-E-D-2E` |
| 2000m | RowErg and SkiErg | EXACT | `B-D-A-E` | `B-D-A-E` |
| 2000m | BikeErg | EXACT | `B-D-A-2B-E` | `B-D-A-2B-E` |
| 1000m | RowErg and SkiErg | EXACT | `B-D-A-C-E` | `B-D-A-C-E` |
| 1000m | BikeErg | EXACT | `B-D-A-E` | `B-D-A-E` |
| 4 x 1776m / 2 min easy | RowErg and SkiErg | GOLD_VARIABLE | `B-D-E-C-D-B-A-2B-A-7B-A-6B-2A-2B-E-C-E-C-E-C-2E` | `B-D-C-D-B-A-2B-A-7B-A-6B-2A-2B-E` |
| 4 x 1776m / 2 min easy | BikeErg | GOLD_VARIABLE | `B-D-E-C-D-3B-2A-5B-A-2B-2A-2B-E-C-E-C-E-C-2E` | `B-D-C-D-3B-2A-5B-A-2B-2A-2B-E` |
| 4 x 2024m, 3 minutes rest. | RowErg and SkiErg | EXACT | `B-D-C-D-2B-A-5C-A-2B-A-4B-2A-3B-E` | `B-D-C-D-2B-A-5C-A-2B-A-4B-2A-3B-E` |
| 4 x 2024m, 3 minutes rest. | BikeErg | EXACT | `B-D-C-D-4B-A-5C-A-4B-A-8B-2A-3B-E` | `B-D-C-D-4B-A-5C-A-4B-A-8B-2A-3B-E` |
| 1000m for the 2025 World Rowing Virtual Indoor Sprints | RowErg and SkiErg | EXACT | `B-D-A-C-E` | `B-D-A-C-E` |
| 1000m for the 2025 World Rowing Virtual Indoor Sprints | BikeErg | EXACT | `B-D-A-E` | `B-D-A-E` |
| 1000m for the 2026 World Rowing Virtual Indoor Sprints | RowErg and SkiErg | EXACT | `B-D-A-C-E` | `B-D-A-C-E` |
| 1000m for the 2026 World Rowing Virtual Indoor Sprints | BikeErg | EXACT | `B-D-A-E` | `B-D-A-E` |

## Non-EXACT rows in detail

### 20 x 45s work, 45s rest (All Machines)

- category: EQUIVALENT
- gold: `B-2D-A-4B-D-C-2A-5B-3A-4B-A-5B-E`
- compiled: `B-2D-C-A-4B-A-5B-3A-4B-A-5B-E`
- spec: `{"kind": "intervals_time", "work": {"time_s": 45}, "rest_s": 45, "count": 20, "machine": "all", "notes": ""}`
- sim(gold): `{"machine": "all", "kind": "intervals_time", "work": {"time_s": 45}, "rest_s": 45, "notes": ""}`
- sim(compiled): `{"machine": "all", "kind": "intervals_time", "work": {"time_s": 45}, "rest_s": 45, "notes": ""}`

### 1:00, 1:30, 2:00, 2:30, 3:00, 3:30, 4:00 - equal work and rest. (All Machines)

- category: EQUIVALENT
- gold: `B-D-E-D-4A-B-E-D-A-3B-4A-3B-E-D-B-A-3C-3A-B-A-3C-E-D-A-3B-4A-3B-E-D-B-A-3C-3A-B-A-3C-E-D-A-3B-4A-3B-E-D-B-A-3C-3A-B-A-3C-2E`
- compiled: `B-D-E-D-4A-B-E-D-A-3B-4A-3B-E-D-B-A-3C-3A-B-A-3C-E-D-A-3B-4A-3B-E-D-B-A-3C-3A-B-A-3C-E-D-A-3B-4A-3B-E-D-B-A-3C-2E`
- spec: `{"kind": "intervals_variable", "intervals": [{"work": {"time_s": 60}, "rest_s": 60}, {"work": {"time_s": 90}, "rest_s": 90}, {"work": {"time_s": 120}, "rest_s": 120}, {"work": {"time_s": 150}, "rest_s": 150}, {"work": {"time_s": 180}, "rest_s": 180}, {"work": {"time_s": 210}, "rest_s": 210}, {"work": {"time_s": 240}, "rest_s": 0}], "machine": "all", "notes": ""}`
- sim(gold): `{"machine": "all", "kind": "intervals_variable", "intervals": [{"work": {"time_s": 60}, "rest_s": 60}, {"work": {"time_s": 90}, "rest_s": 90}, {"work": {"time_s": 120}, "rest_s": 120}, {"work": {"time_s": 150}, "rest_s": 150}, {"work": {"time_s": 180}, "rest_s": 180}, {"work": {"time_s": 210}, "rest_s": 210}, {"work": {"time_s": 240}, "rest_s": 240}], "notes": ""}`
- sim(compiled): `{"machine": "all", "kind": "intervals_variable", "intervals": [{"work": {"time_s": 60}, "rest_s": 60}, {"work": {"time_s": 90}, "rest_s": 90}, {"work": {"time_s": 120}, "rest_s": 120}, {"work": {"time_s": 150}, "rest_s": 150}, {"work": {"time_s": 180}, "rest_s": 180}, {"work": {"time_s": 210}, "rest_s": 210}, {"work": {"time_s": 240}, "rest_s": 210}], "notes": ""}`

### 10 x 1:40 / 20 seconds easy (All Machines)

- category: GOLD_VARIABLE
- gold: `B-D-E-D-A-4B-4A-2B-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-E-D-2E`
- compiled: `B-2D-A-4B-4A-2B-E`
- spec: `{"kind": "intervals_time", "work": {"time_s": 100}, "rest_s": 20, "count": 10, "machine": "all", "notes": ""}`
- sim(gold): `{"machine": "all", "kind": "intervals_variable", "intervals": [{"work": {"time_s": 100}, "rest_s": 20}, {"work": {"time_s": 100}, "rest_s": 20}, {"work": {"time_s": 100}, "rest_s": 20}, {"work": {"time_s": 100}, "rest_s": 20}, {"work": {"time_s": 100}, "rest_s": 20}, {"work": {"time_s": 100}, "rest_s": 20}, {"work": {"time_s": 100}, "rest_s": 20}, {"work": {"time_s": 100}, "rest_s": 20}, {"work": {"time_s": 100}, "rest_s": 20}, {"work": {"time_s": 100}, "rest_s": 20}], "notes": ""}`
- sim(compiled): `{"machine": "all", "kind": "intervals_time", "work": {"time_s": 100}, "rest_s": 20, "notes": ""}`

### 2000m/3 minutes rest/1000m/2 minutes rest/500m (RowErg and SkiErg)

- category: EQUIVALENT
- gold: `B-D-E-C-D-2B-A-5C-4A-3B-E-C-D-C-5A-C-E-C-D-C-A-5B-4A-C-2E`
- compiled: `B-D-E-C-D-2B-A-5C-4A-3B-E-C-D-C-5A-C-E-C-D-C-A-5B-2E`
- spec: `{"kind": "intervals_variable", "intervals": [{"work": {"distance_m": 2000}, "rest_s": 180}, {"work": {"distance_m": 1000}, "rest_s": 120}, {"work": {"distance_m": 500}, "rest_s": 0}], "machine": "rower", "notes": ""}`
- sim(gold): `{"machine": "all", "kind": "intervals_variable", "intervals": [{"work": {"distance_m": 2000}, "rest_s": 180}, {"work": {"distance_m": 1000}, "rest_s": 120}, {"work": {"distance_m": 500}, "rest_s": 60}], "notes": ""}`
- sim(compiled): `{"machine": "all", "kind": "intervals_variable", "intervals": [{"work": {"distance_m": 2000}, "rest_s": 180}, {"work": {"distance_m": 1000}, "rest_s": 120}, {"work": {"distance_m": 500}, "rest_s": 120}], "notes": ""}`

### 2000m/3 minutes rest/1000m/2 minutes rest/500m (BikeErg)

- category: EQUIVALENT
- gold: `B-D-E-C-D-4B-A-5C-4A-3B-E-C-D-2C-5A-C-E-C-D-C-5A-C-2E`
- compiled: `B-D-E-C-D-4B-A-5C-4A-3B-E-C-D-2C-5A-C-E-C-D-C-2E`
- spec: `{"kind": "intervals_variable", "intervals": [{"work": {"distance_m": 4000}, "rest_s": 180}, {"work": {"distance_m": 2000}, "rest_s": 120}, {"work": {"distance_m": 1000}, "rest_s": 0}], "machine": "bikeerg", "notes": ""}`
- sim(gold): `{"machine": "all", "kind": "intervals_variable", "intervals": [{"work": {"distance_m": 4000}, "rest_s": 180}, {"work": {"distance_m": 2000}, "rest_s": 120}, {"work": {"distance_m": 1000}, "rest_s": 60}], "notes": ""}`
- sim(compiled): `{"machine": "all", "kind": "intervals_variable", "intervals": [{"work": {"distance_m": 4000}, "rest_s": 180}, {"work": {"distance_m": 2000}, "rest_s": 120}, {"work": {"distance_m": 1000}, "rest_s": 120}], "notes": ""}`

### 5 min, 10 min, 15 min, 10 min, 5 min pyramid / 2 min easy (All Machines)

- category: GOLD_MISMATCH
- gold: `B-D-E-D-4B-4A-2B-E-2D-B-A-5C-E-D-5B-E-D-5C-E-D-5B-2E`
- compiled: `B-D-E-D-4B-4A-2B-E-2D-B-A-5C-E-D-5B-E-D-5C-E-2D-C-A-5B-2E`
- spec: `{"kind": "intervals_variable", "intervals": [{"work": {"time_s": 300}, "rest_s": 120}, {"work": {"time_s": 600}, "rest_s": 120}, {"work": {"time_s": 900}, "rest_s": 120}, {"work": {"time_s": 600}, "rest_s": 120}, {"work": {"time_s": 300}, "rest_s": 0}], "machine": "all", "notes": ""}`
- sim(gold): `{"machine": "all", "kind": "intervals_variable", "intervals": [{"work": {"time_s": 300}, "rest_s": 120}, {"work": {"time_s": 600}, "rest_s": 120}, {"work": {"time_s": 900}, "rest_s": 120}, {"work": {"time_s": 600}, "rest_s": 120}, {"work": {"time_s": 900}, "rest_s": 120}], "notes": ""}`
- sim(compiled): `{"machine": "all", "kind": "intervals_variable", "intervals": [{"work": {"time_s": 300}, "rest_s": 120}, {"work": {"time_s": 600}, "rest_s": 120}, {"work": {"time_s": 900}, "rest_s": 120}, {"work": {"time_s": 600}, "rest_s": 120}, {"work": {"time_s": 300}, "rest_s": 120}], "notes": ""}`

### 4 x 1776m / 2 min easy (RowErg and SkiErg)

- category: GOLD_VARIABLE
- gold: `B-D-E-C-D-B-A-2B-A-7B-A-6B-2A-2B-E-C-E-C-E-C-2E`
- compiled: `B-D-C-D-B-A-2B-A-7B-A-6B-2A-2B-E`
- spec: `{"kind": "intervals_distance", "work": {"distance_m": 1776}, "rest_s": 120, "count": 4, "machine": "rower", "notes": ""}`
- sim(gold): `{"machine": "all", "kind": "intervals_variable", "intervals": [{"work": {"distance_m": 1776}, "rest_s": 120}, {"work": {"distance_m": 1776}, "rest_s": 120}, {"work": {"distance_m": 1776}, "rest_s": 120}, {"work": {"distance_m": 1776}, "rest_s": 120}], "notes": ""}`
- sim(compiled): `{"machine": "all", "kind": "intervals_distance", "work": {"distance_m": 1776}, "rest_s": 120, "notes": ""}`

### 4 x 1776m / 2 min easy (BikeErg)

- category: GOLD_VARIABLE
- gold: `B-D-E-C-D-3B-2A-5B-A-2B-2A-2B-E-C-E-C-E-C-2E`
- compiled: `B-D-C-D-3B-2A-5B-A-2B-2A-2B-E`
- spec: `{"kind": "intervals_distance", "work": {"distance_m": 3552}, "rest_s": 120, "count": 4, "machine": "bikeerg", "notes": ""}`
- sim(gold): `{"machine": "all", "kind": "intervals_variable", "intervals": [{"work": {"distance_m": 3552}, "rest_s": 120}, {"work": {"distance_m": 3552}, "rest_s": 120}, {"work": {"distance_m": 3552}, "rest_s": 120}, {"work": {"distance_m": 3552}, "rest_s": 120}], "notes": ""}`
- sim(compiled): `{"machine": "all", "kind": "intervals_distance", "work": {"distance_m": 3552}, "rest_s": 120, "notes": ""}`

