"""Data pipeline for building the Concept2 WOD -> PM5 key-sequence
training dataset.

Subcommands (see __main__.py / the `pm5keys-data` console script):

    fetch       download raw WOD web pages
    parse       parse raw HTML pages into structured JSON records
    build       flatten parsed records into dataset.jsonl / dataset_unique.jsonl
    check       consistency report over dataset.jsonl
    split       leakage-free train/eval split of dataset_unique.jsonl
    crosscheck  cross-check WOD email bodies against web-derived records
"""
