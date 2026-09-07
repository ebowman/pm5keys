# Dataset consistency report

This file is generated, not hand-edited. Dataset: `data/dataset.jsonl` (1950 rows).

Regenerate with: `pm5keys-data check --dataset data/dataset.jsonl --out data/reports/conflicts.md`

## 1. Label conflicts (same description + machines, different pm5)

No conflicts found.

## 1b. Title conflicts (same title + machines, different pm5)

### 1. Title: '5 x 1000m'

- Machines: `All Machines`
- Distinct pm5 variants: 2

  - `B-2D-A-D-B-A-5C-5A-2B-E`
    - count: 7
    - date range: 2023-02-17..2026-04-04
    - sample dates: 2023-02-17, 2023-07-14, 2024-01-20, 2024-04-26, 2024-10-25, 2025-02-04
  - `B-2D-A-D-B-A-5C-4A-B-E`
    - count: 5
    - date range: 2022-08-19..2023-11-05
    - sample dates: 2022-08-19, 2022-11-04, 2023-03-15, 2023-06-13, 2023-11-05

## 2. Same sequence, different descriptions (informational)

### 1. Machines: `All Machines`, pm5: `B-2D-2B-4A-B-E`

- Distinct descriptions: 2

  - (30x) 'Row six 2 minute pieces. Row for one minute at light pressure between each piece.'
  - (29x) 'Eight 2 minute pieces. One minute at light pressure between each piece.'

### 2. Machines: `All Machines`, pm5: `B-2D-2B-A-3B-4A-3B-E`

- Distinct descriptions: 2

  - (28x) '10 work intervals of 2 minutes and 30 seconds, with 30 seconds recovery between each interval.'
  - (2x) '7 rounds of 2 minutes 30 seconds work, with 30 seconds rest between each round. * The 2023 World Rowing Indoor Champs will feature a new multi event competition - The Versa. To qualify, competitors must complete two challenges by November 28. This is one of those challenges, with scores for total work distance and distance in the first 2:30 round. More details available from worldrowing.com'

### 3. Machines: `All Machines`, pm5: `B-2D-3B-4A-2B-E`

- Distinct descriptions: 3

  - (31x) 'Do five 3 minute pieces. Row/ski/ride for two minutes at light pressure between each piece.'
  - (23x) 'Four 3 minute pieces. Two minutes at light pressure between each piece.'
  - (20x) '6 work intervals of 3 minutes. 2 minutes light between each.'

### 4. Machines: `All Machines`, pm5: `B-2D-4B-4A-2B-E`

- Distinct descriptions: 3

  - (21x) 'Four 4 minute pieces. Two minutes at light pressure between each piece.'
  - (16x) 'Five 4 minute pieces. Two minutes at light pressure between each piece.'
  - (8x) 'Six 4 minute pieces. Two minutes at light pressure between each piece.'

### 5. Machines: `All Machines`, pm5: `B-2D-4C-A-5B-2A-B-E`

- Distinct descriptions: 2

  - (14x) 'Twelve 25 Calorie pieces. One minute at light pressure between each piece.'
  - (9x) 'Eight 25 calorie pieces. One minute at light pressure between each piece.'

### 6. Machines: `All Machines`, pm5: `B-2D-B-4A-B-E`

- Distinct descriptions: 2

  - (43x) 'Ten 1 minute pieces. One minute at light pressure between each piece.'
  - (29x) 'Twelve 1 minute pieces. One minute at light pressure between each piece.'

### 7. Machines: `All Machines`, pm5: `B-D-B-E`

- Distinct descriptions: 2

  - (15x) 'Do a 30 minute time trial, going for your personal best. Then enter your result in the Online Ranking and see where you stand with others of your age, gender and weight class.'
  - (1x) 'Row, ski or ride for 30 minutes. This workout can be done in conjunction with workouts two and three of the Skeleton Crew Challenge, As The Flywheel Spins podcast.'

### 8. Machines: `BikeErg`, pm5: `B-2D-A-D-2B-A-5C-4A-2B-E`

- Distinct descriptions: 2

  - (24x) '6 intervals of 1000m followed by 2 minutes rest. (BikeErg: 2000m)'
  - (7x) '8 X 1000m with 2 minutes rest (BikeErg: 2000m)'

### 9. Machines: `BikeErg`, pm5: `B-2D-A-D-2B-A-5C-4A-B-E`

- Distinct descriptions: 2

  - (23x) 'Four 1000 meter pieces. One minute at light pressure between each 1000. (BikeErg: 2000m pieces)'
  - (16x) 'Five 1000 meter pieces. One minute at light pressure between each 1000. (BikeErg: 2000m pieces)'

### 10. Machines: `BikeErg`, pm5: `B-2D-A-D-B-A-5C-4A-2B-E`

- Distinct descriptions: 2

  - (34x) '8 x 500m intervals with 2 minutes rest. (BikeErg: 1000m)'
  - (25x) 'Five 500 meter pieces. Two minutes at light pressure between each 500. (BikeErg: 1000m pieces)'

### 11. Machines: `BikeErg`, pm5: `B-D-A-D-B-A-2C-E`

- Distinct descriptions: 2

  - (11x) '5000 meter time trial, going for your personal best. Enter your result in the Online Ranking and see where you stand with others of your age, gender and weight class. (BikeErg: 10,000m)'
  - (4x) "5000 meter workout. Concept2 will donate $5 to women's charities (up to a maximum of $20,000) for anyone, whatever gender or sex, who does a 5000m piece and signs up to the International Women's Day challenge on their Online Logbook. (BikeErg: 10,000m)"

### 12. Machines: `BikeErg`, pm5: `B-D-A-E`

- Distinct descriptions: 5

  - (4x) 'Complete 1000m as fast as you can. (BikeErg:2000m) *Today marks the start of the SkiErg World Sprints, a virtual SkiErg championship. To take part you just need to ski 1000m between now and Sunday. More details can be found in the Challenges section of the Concept2 logbook.'
  - (2x) 'Complete 1000m as fast as you can. (BikeErg:2000m) *The World Rowing Virtual Indoor Sprints are taking place between March 6-10, 2024. To take part you need to row 1000m. More details can be found in the Challenges section of the Concept2 logbook.'
  - (1x) 'Complete 1000m as fast as you can. (BikeErg:2000m) *The World Rowing Virtual Indoor Sprints are taking place between March 4-8, 2026. To take part you need to row 1000m. More details can be found in the Challenges section of the Concept2 logbook.'
  - (1x) 'Complete 1000m as fast as you can. (BikeErg:2000m) *The World Rowing Virtual Indoor Sprints are taking place between March 5-9, 2025. To take part you need to row 1000m. More details can be found in the Challenges section of the Concept2 logbook.'
  - (1x) 'Complete 1000m as fast as you can. (BikeErg:2000m) *The World Rowing Virtual Indoor Sprints are taking place between March 8-12, 2023. To take part you need to row 1000m. More details can be found in the Challenges section of the Concept2 logbook.'

### 13. Machines: `RowErg and SkiErg`, pm5: `B-2D-5A-2B-E`

- Distinct descriptions: 2

  - (34x) '8 x 500m intervals with 2 minutes rest. (BikeErg: 1000m)'
  - (25x) 'Five 500 meter pieces. Two minutes at light pressure between each 500. (BikeErg: 1000m pieces)'

### 14. Machines: `RowErg and SkiErg`, pm5: `B-2D-A-D-B-A-5C-4A-2B-E`

- Distinct descriptions: 2

  - (24x) '6 intervals of 1000m followed by 2 minutes rest. (BikeErg: 2000m)'
  - (7x) '8 X 1000m with 2 minutes rest (BikeErg: 2000m)'

### 15. Machines: `RowErg and SkiErg`, pm5: `B-2D-A-D-B-A-5C-4A-B-E`

- Distinct descriptions: 2

  - (23x) 'Four 1000 meter pieces. One minute at light pressure between each 1000. (BikeErg: 2000m pieces)'
  - (16x) 'Five 1000 meter pieces. One minute at light pressure between each 1000. (BikeErg: 2000m pieces)'

### 16. Machines: `RowErg and SkiErg`, pm5: `B-D-A-3B-E`

- Distinct descriptions: 2

  - (11x) '5000 meter time trial, going for your personal best. Enter your result in the Online Ranking and see where you stand with others of your age, gender and weight class. (BikeErg: 10,000m)'
  - (4x) "5000 meter workout. Concept2 will donate $5 to women's charities (up to a maximum of $20,000) for anyone, whatever gender or sex, who does a 5000m piece and signs up to the International Women's Day challenge on their Online Logbook. (BikeErg: 10,000m)"

### 17. Machines: `RowErg and SkiErg`, pm5: `B-D-A-C-E`

- Distinct descriptions: 5

  - (4x) 'Complete 1000m as fast as you can. (BikeErg:2000m) *Today marks the start of the SkiErg World Sprints, a virtual SkiErg championship. To take part you just need to ski 1000m between now and Sunday. More details can be found in the Challenges section of the Concept2 logbook.'
  - (2x) 'Complete 1000m as fast as you can. (BikeErg:2000m) *The World Rowing Virtual Indoor Sprints are taking place between March 6-10, 2024. To take part you need to row 1000m. More details can be found in the Challenges section of the Concept2 logbook.'
  - (1x) 'Complete 1000m as fast as you can. (BikeErg:2000m) *The World Rowing Virtual Indoor Sprints are taking place between March 4-8, 2026. To take part you need to row 1000m. More details can be found in the Challenges section of the Concept2 logbook.'
  - (1x) 'Complete 1000m as fast as you can. (BikeErg:2000m) *The World Rowing Virtual Indoor Sprints are taking place between March 5-9, 2025. To take part you need to row 1000m. More details can be found in the Challenges section of the Concept2 logbook.'
  - (1x) 'Complete 1000m as fast as you can. (BikeErg:2000m) *The World Rowing Virtual Indoor Sprints are taking place between March 8-12, 2023. To take part you need to row 1000m. More details can be found in the Challenges section of the Concept2 logbook.'

## 3. Sanity tables

### First token of pm5

| token | count |
| --- | --- |
| `B` | 1950 |

### pm5_expanded sequence length

min: 4, median: 20.0, max: 107

| bucket | count |
| --- | --- |
| 0-4 | 26 |
| 5-9 | 59 |
| 10-14 | 457 |
| 15-19 | 355 |
| 20-24 | 185 |
| 25-29 | 253 |
| 30-34 | 290 |
| 35-39 | 124 |
| 40-44 | 28 |
| 45-49 | 40 |
| 50-54 | 69 |
| 55-59 | 2 |
| 85-89 | 3 |
| 95-99 | 31 |
| 100-104 | 27 |
| 105-109 | 1 |

### Rows per machines label

| machines | count |
| --- | --- |
| `All Machines` | 1096 |
| `BikeErg` | 427 |
| `RowErg and SkiErg` | 427 |

