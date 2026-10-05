# Dataset consistency report

This file is generated, not hand-edited. Dataset: `data/dataset.jsonl` (36 rows).

Regenerate with: `pm5keys-data check --dataset data/dataset.jsonl --out data/reports/conflicts.md`

## 1. Label conflicts (same description + machines, different pm5)

No conflicts found.

## 1b. Title conflicts (same title + machines, different pm5)

No conflicts found.

## 2. Same sequence, different descriptions (informational)

### 1. Machines: `All Machines`, pm5: `B-2D-3B-4A-2B-E`

- Distinct descriptions: 3

  - (1x) '6 work intervals of 3 minutes. 2 minutes light between each.'
  - (1x) 'Do five 3 minute pieces. Row/ski/ride for two minutes at light pressure between each piece.'
  - (1x) 'Four 3 minute pieces. Two minutes at light pressure between each piece.'

### 2. Machines: `All Machines`, pm5: `B-2D-4B-4A-2B-E`

- Distinct descriptions: 2

  - (1x) 'Five 4 minute pieces. Two minutes at light pressure between each piece.'
  - (1x) 'Four 4 minute pieces. Two minutes at light pressure between each piece.'

### 3. Machines: `BikeErg`, pm5: `B-2D-A-D-B-A-5C-4A-2B-E`

- Distinct descriptions: 2

  - (1x) '8 x 500m intervals with 2 minutes rest. (BikeErg: 1000m)'
  - (1x) 'Five 500 meter pieces. Two minutes at light pressure between each 500. (BikeErg: 1000m pieces)'

### 4. Machines: `RowErg and SkiErg`, pm5: `B-2D-5A-2B-E`

- Distinct descriptions: 2

  - (1x) '8 x 500m intervals with 2 minutes rest. (BikeErg: 1000m)'
  - (1x) 'Five 500 meter pieces. Two minutes at light pressure between each 500. (BikeErg: 1000m pieces)'

## 3. Sanity tables

### First token of pm5

| token | count |
| --- | --- |
| `B` | 36 |

### pm5_expanded sequence length

min: 10, median: 20.0, max: 104

| bucket | count |
| --- | --- |
| 10-14 | 11 |
| 15-19 | 6 |
| 20-24 | 2 |
| 25-29 | 7 |
| 30-34 | 3 |
| 35-39 | 3 |
| 50-54 | 2 |
| 95-99 | 1 |
| 100-104 | 1 |

### Rows per machines label

| machines | count |
| --- | --- |
| `All Machines` | 20 |
| `BikeErg` | 8 |
| `RowErg and SkiErg` | 8 |

