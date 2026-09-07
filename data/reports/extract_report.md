# pm5keys.llm.eval_extract report

backend: claude-cli, model: (default), k: 25, n rows: 14

Overall accuracy: 14/14 (100.0%)

## Per-kind accuracy

| Kind | Correct | Total |
|---|---|---|
| intervals_calorie | 1 | 1 |
| intervals_distance | 3 | 3 |
| intervals_time | 1 | 1 |
| intervals_variable | 7 | 7 |
| single_distance | 1 | 1 |
| single_time | 1 | 1 |

## Rows

| Title | Kind | Correct | Exact-sequence-match | Note |
|---|---|---|---|---|
| 2000/1500/1000/500m with three minutes rest | intervals_variable | yes | yes |  |
| 500m/1000m/500m/1000m/500m with two minutes rest. | intervals_variable | yes | yes |  |
| 1/2/1/2/1/2/1 minutes with 1 minute rest | intervals_variable | yes | yes |  |
| 12 x 1 min / 1 min easy | intervals_time | yes | yes |  |
| 4 x 1500m / 2 min easy | intervals_distance | yes | yes |  |
| 5/4/3/2/1 minutes with 2 minutes rest | intervals_variable | yes | yes |  |
| 5/4/3/4/5 minutes with 2 minutes rest | intervals_variable | yes | yes |  |
| 30 minute time trial | single_time | yes | yes |  |
| 5 x 1000m | intervals_distance | yes | yes |  |
| 10 x 20 calories/:20 rest | intervals_calorie | yes | yes |  |
| 1000m | single_distance | yes | yes |  |
| 4 x 2023m, 3 minutes rest. | intervals_distance | yes | yes |  |
| 3000m, 3 minutes rest, 10 minutes work | intervals_variable | yes | yes |  |
| 2 rounds of 16 x 20 seconds work and 10 seconds rest | intervals_variable | yes | no |  |

## First 20 mismatches

