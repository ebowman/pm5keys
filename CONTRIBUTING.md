# Contributing

## Fixtures must be scrubbed

Test fixtures under `tests/fixtures/` are derived from real "Workout of
the Day" e-mails and web pages. Before committing a new or updated
fixture, strip anything that identifies a real person or subscriber,
including:

- ESP (e.g. Campaign Monitor) tracking links and any subscriber-specific
  token embedded in them — replace the whole line/URL with
  `https://workoutoftheday.example/t/REDACTED`.
- Subscriber-specific unsubscribe/preferences links or tokens.
- Real e-mail addresses, names, or absolute local filesystem
  home-directory paths.

Never commit the actual private token(s) anywhere in the tree or in a
commit message — not even as an example. `tests/test_no_pii.py`
enforces this automatically: it walks the repo and fails if it finds
known personal-identifier *shapes* (a local home-directory path, an
e-mail address ending in `.ie`, an ESP tracking-link shape, or, for
anything under `tests/fixtures/`, the ESP domain fragment), plus any
extra substring you list in a local, gitignored `.pii-patterns.local`
file at the repo root (one per line) — use that file to keep guarding
for your own private tokens without ever committing them. Run the full
suite, including this check, before opening a PR:

```
python -m unittest discover -s tests -t .
```

If you add a new kind of personal identifier to scrub, extend
`tests/test_no_pii.py`'s built-in *pattern shapes* (not literal private
tokens) alongside the fixture change so the check keeps catching it.
