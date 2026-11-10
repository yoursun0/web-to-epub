# web-to-epub

Turn a UTF-8 list of public article URLs into one EPUB3 book (one URL → one chapter). Text only — no images. Runs as a small Python 3.11+ CLI.

## Install

```bash
python3 -m pip install -e ".[dev]"
```

## Usage

```bash
web-to-epub URLS_FILE --title TITLE [--author AUTHOR] [-o OUTPUT]
```

- `URLS_FILE`: one URL per line; blank lines and `#` comments ignored; `http`/`https` only
- Default output: `./output.epub`
- Failed URLs are logged on stderr; the EPUB is written only if at least one chapter succeeds

## Primary UAT fixture

```bash
web-to-epub fixtures/shen-de-mofangfan-ch1-20.txt \
  --title "神的模仿犯" --author "林思之" \
  -o /tmp/shen-de-mofangfan-ch1-20.epub
```

Novel-aggregation sites may rate-limit or serve anti-bot HTML. Failures stay on the fail-continue path; this tool does not log in or bypass paywalls.

## Limits (v1)

- No images, GUI, crawling, or parallel fetch
- One HTTP attempt per URL
- Python 3.11+; dependencies: httpx, trafilatura, ebooklib
