# Dataset consistency report

This file is generated, not hand-edited. Dataset: `data/dataset.jsonl` (20 rows).

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
| `B` | 20 |

### pm5_expanded sequence length

min: 10, median: 19.5, max: 104

| bucket | count |
| --- | --- |
| 10-14 | 5 |
| 15-19 | 5 |
| 20-24 | 2 |
| 25-29 | 4 |
| 35-39 | 1 |
| 50-54 | 1 |
| 95-99 | 1 |
| 100-104 | 1 |

### Rows per machines label

| machines | count |
| --- | --- |
| `All Machines` | 8 |
| `BikeErg` | 6 |
| `RowErg and SkiErg` | 6 |

