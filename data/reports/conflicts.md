# Dataset consistency report

This file is generated, not hand-edited. Dataset: `data/dataset.jsonl` (27 rows).

Regenerate with: `pm5keys-data check --dataset data/dataset.jsonl --out data/reports/conflicts.md`

## 1. Label conflicts (same description + machines, different pm5)

No conflicts found.

## 1b. Title conflicts (same title + machines, different pm5)

No conflicts found.

## 2. Same sequence, different descriptions (informational)

### 1. Machines: `All Machines`, pm5: `B-2D-4B-4A-2B-E`

- Distinct descriptions: 2

  - (1x) 'Five 4 minute pieces. Two minutes at light pressure between each piece.'
  - (1x) 'Four 4 minute pieces. Two minutes at light pressure between each piece.'

## 3. Sanity tables

### First token of pm5

| token | count |
| --- | --- |
| `B` | 27 |

### pm5_expanded sequence length

min: 10, median: 20, max: 104

| bucket | count |
| --- | --- |
| 10-14 | 8 |
| 15-19 | 5 |
| 20-24 | 2 |
| 25-29 | 4 |
| 30-34 | 3 |
| 35-39 | 2 |
| 50-54 | 1 |
| 95-99 | 1 |
| 100-104 | 1 |

### Rows per machines label

| machines | count |
| --- | --- |
| `All Machines` | 15 |
| `BikeErg` | 6 |
| `RowErg and SkiErg` | 6 |

