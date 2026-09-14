# Dataset consistency report

This file is generated, not hand-edited. Dataset: `data/dataset.jsonl` (10 rows).

Regenerate with: `pm5keys-data check --dataset data/dataset.jsonl --out data/reports/conflicts.md`

## 1. Label conflicts (same description + machines, different pm5)

No conflicts found.

## 1b. Title conflicts (same title + machines, different pm5)

No conflicts found.

## 2. Same sequence, different descriptions (informational)

No variants found.

## 3. Sanity tables

### First token of pm5

| token | count |
| --- | --- |
| `B` | 10 |

### pm5_expanded sequence length

min: 10, median: 23.0, max: 96

| bucket | count |
| --- | --- |
| 10-14 | 3 |
| 15-19 | 2 |
| 25-29 | 2 |
| 35-39 | 1 |
| 50-54 | 1 |
| 95-99 | 1 |

### Rows per machines label

| machines | count |
| --- | --- |
| `All Machines` | 4 |
| `BikeErg` | 3 |
| `RowErg and SkiErg` | 3 |

