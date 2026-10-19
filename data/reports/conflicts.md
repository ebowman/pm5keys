# Dataset consistency report

This file is generated, not hand-edited. Dataset: `data/dataset.jsonl` (55 rows).

Regenerate with: `pm5keys-data check --dataset data/dataset.jsonl --out data/reports/conflicts.md`

## 1. Label conflicts (same description + machines, different pm5)

No conflicts found.

## 1b. Title conflicts (same title + machines, different pm5)

No conflicts found.

## 2. Same sequence, different descriptions (informational)

### 1. Machines: `All Machines`, pm5: `B-2D-3B-4A-2B-E`

- Distinct descriptions: 3

  - (2x) 'Do five 3 minute pieces. Row/ski/ride for two minutes at light pressure between each piece.'
  - (1x) '6 work intervals of 3 minutes. 2 minutes light between each.'
  - (1x) 'Four 3 minute pieces. Two minutes at light pressure between each piece.'

### 2. Machines: `All Machines`, pm5: `B-2D-4B-4A-2B-E`

- Distinct descriptions: 2

  - (1x) 'Five 4 minute pieces. Two minutes at light pressure between each piece.'
  - (1x) 'Four 4 minute pieces. Two minutes at light pressure between each piece.'

### 3. Machines: `All Machines`, pm5: `B-2D-B-4A-B-E`

- Distinct descriptions: 2

  - (2x) 'Ten 1 minute pieces. One minute at light pressure between each piece.'
  - (1x) 'Twelve 1 minute pieces. One minute at light pressure between each piece.'

### 4. Machines: `BikeErg`, pm5: `B-2D-A-D-B-A-5C-4A-2B-E`

- Distinct descriptions: 2

  - (2x) '8 x 500m intervals with 2 minutes rest. (BikeErg: 1000m)'
  - (1x) 'Five 500 meter pieces. Two minutes at light pressure between each 500. (BikeErg: 1000m pieces)'

### 5. Machines: `RowErg and SkiErg`, pm5: `B-2D-5A-2B-E`

- Distinct descriptions: 2

  - (2x) '8 x 500m intervals with 2 minutes rest. (BikeErg: 1000m)'
  - (1x) 'Five 500 meter pieces. Two minutes at light pressure between each 500. (BikeErg: 1000m pieces)'

## 3. Sanity tables

### First token of pm5

| token | count |
| --- | --- |
| `B` | 55 |

### pm5_expanded sequence length

min: 10, median: 20, max: 104

| bucket | count |
| --- | --- |
| 10-14 | 17 |
| 15-19 | 10 |
| 20-24 | 3 |
| 25-29 | 8 |
| 30-34 | 6 |
| 35-39 | 4 |
| 50-54 | 3 |
| 95-99 | 2 |
| 100-104 | 2 |

### Rows per machines label

| machines | count |
| --- | --- |
| `All Machines` | 29 |
| `BikeErg` | 13 |
| `RowErg and SkiErg` | 13 |

