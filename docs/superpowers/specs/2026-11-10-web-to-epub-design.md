# web-to-epub — Design Spec

> Date: 2026-11-10 (Asia/Hong_Kong)  
> Status: approved design (awaiting Helic review gate before implementation plan)  
> Intended home: Helic box/cloud computer CLI; later GitHub `yoursun0/web-to-epub`

---

## 1. Purpose

`web-to-epub` is a small Python CLI that turns a list of public article URLs into a single EPUB3 file. Each URL becomes one chapter. Main article text is extracted (ads, banners, chrome stripped); images are omitted. The tool runs on Helic's box/cloud computer for personal offline reading.

Success looks like: QA仔 runs the CLI against `fixtures/shen-de-mofangfan-ch1-20.txt` (first 20 chapters of 《神的模仿犯》by 林思之 from [uukanshu.cc/book/26186](https://uukanshu.cc/book/26186/#tuijian)) with `--title "神的模仿犯" --author "林思之"`, and opens an EPUB with ordered chapter titles and readable Chinese body text (site chrome/ads stripped). Novel-aggregation pages may be brittle or block bots; per-URL fail-continue still applies.

---

## 2. Non-goals / out of scope

The following are explicitly **not** in this project:

- Embedding or downloading images, figures, or media
- Login, cookies, sessions, CAPTCHA, or paywall bypass
- Crawling a site or RSS series to discover URLs (caller supplies the URL list)
- GUI, web UI, or daemon/service
- Parallel fetch orchestration beyond a simple sequential loop
- Custom CSS themes, fonts packaging, or ebook store metadata beyond title/author
- EPUB2-only targets (we ship EPUB3)
- Converting PDFs, local HTML files, or non-HTTP(S) sources

---

## 3. Approach (locked)

| Piece | Choice |
|-------|--------|
| Language | Python 3 |
| HTTP fetch | `httpx` (preferred) with a short timeout and a tool-identifying User-Agent |
| Main-content extract | `trafilatura` — title + body HTML/text, no images |
| EPUB assembly | `ebooklib` — EPUB3, one chapter item per successful URL |
| Entry point | Single module CLI, e.g. `python -m web_to_epub` or `web_to_epub` console script |

Fallback if `httpx` is unavailable in a constrained environment: stdlib `urllib.request` with the same timeout and User-Agent. Prefer documenting `httpx` as the primary dependency; keep the fetch behind a thin helper so swapping is local.

---

## 4. CLI interface

```text
web-to-epub URLS_FILE --title TITLE [--author AUTHOR] [-o OUTPUT]
```

| Argument | Required | Meaning |
|----------|----------|---------|
| `URLS_FILE` | yes | Path to text file listing URLs (see §5) |
| `--title` | yes | EPUB book title (Dublin Core title) |
| `--author` | no | EPUB creator/author string; if omitted, omit the creator metadata element |
| `-o` / `--output` | no | Output `.epub` path; default `./output.epub` relative to the process cwd |

Exit codes:

| Code | When |
|------|------|
| `0` | EPUB written; at least one chapter succeeded (failed URLs may still have been logged) |
| `1` | No chapters succeeded, or fatal CLI/usage error (missing file, missing `--title`, unreadable URL file) |
| `2` | Reserved for unexpected crash; prefer catching and exiting `1` with a message |

Stderr carries human-readable progress and per-URL failures. Stdout may print the final output path on success (one line) so scripts can capture it.

---

## 5. URL file format

- Encoding: UTF-8
- One URL per non-empty line
- Leading/trailing whitespace stripped
- Empty lines ignored
- Lines whose first non-whitespace character is `#` are comments and ignored
- Supported schemes: `http` and `https` only; other schemes are skipped with a stderr warning and count as that-line failure
- Duplicate URLs are kept in file order (same URL may appear as multiple chapters if listed twice)

Example:

```text
# weekend reading
https://example.com/article-one
https://example.com/article-two

# skip this for now
# https://example.com/paywalled
https://example.com/article-three
```

---

## 6. Pipeline

Sequential processing; no concurrency in v1.

1. **Parse CLI** — require `URLS_FILE` and `--title`; resolve `-o`.
2. **Load URL list** — read and filter per §5; if zero URLs remain after filtering, exit `1` with a clear message.
3. **For each URL (in order):**
   1. **Fetch** — GET with timeout (suggest 30s connect+read), follow redirects within http(s), User-Agent identifying the tool (e.g. `web-to-epub/0.1 (+https://github.com/yoursun0/web-to-epub)`).
   2. **Extract** — pass response body (and URL) to trafilatura; request HTML or plain text suitable for chapter body; **do not** fetch or embed images (disable image inclusion in trafilatura options / strip `<img>` if any remain).
   3. **Chapter title** — prefer trafilatura-extracted title; if missing, use the URL string.
   4. **Chapter body** — extracted main content only. If extraction returns empty/None, treat as failure for that URL.
   5. **On success** — append an in-memory chapter `{ title, html_or_xhtml_body, source_url }`.
   6. **On failure** — log to stderr: URL + short reason (HTTP status, timeout, extract empty, parse error); continue to next URL.
4. **Assemble EPUB** — if chapter list is empty, exit `1` without writing a file. Otherwise build EPUB3 with ebooklib:
   - Book title = `--title`
   - Creator = `--author` when provided
   - One spine/chapter document per successful URL, in list order
   - Nav/TOC entries use each chapter's title
   - Optional: include source URL as a small plain footer or `<meta>`/paragraph at chapter end for provenance (allowed; still text-only)
5. **Write** — write atomically where practical (write temp then rename) to `-o` path; print path; exit `0`.

Language: preserve Unicode; no forced Latin-1. Chapter XHTML must be well-formed enough for ebooklib (escape or let ebooklib helpers produce valid markup).

---

## 7. Dependencies

Runtime (pin loosely in `requirements.txt` / `pyproject.toml` at implementation time):

| Package | Role |
|---------|------|
| `trafilatura` | Main-content extraction |
| `ebooklib` | EPUB3 packaging |
| `httpx` | HTTP client (primary) |

Stdlib only for CLI (`argparse`), paths, and optional `urllib` fallback. No GUI frameworks. Python version target: 3.11+ (box default; document exact version in README at impl time).

---

## 8. Error handling

| Situation | Behavior |
|-----------|----------|
| Missing/unreadable URL file | stderr message; exit `1`; no EPUB |
| Missing `--title` | argparse error; exit `1` |
| Invalid URL / bad scheme | skip; stderr; continue |
| Network timeout / DNS / TLS error | skip; stderr; continue |
| HTTP 4xx/5xx | skip; stderr with status; continue |
| Empty extract | skip; stderr; continue |
| All URLs fail | stderr summary; exit `1`; **do not** write EPUB |
| Partial success | write EPUB of successes; stderr lists failures; exit `0` |
| Cannot write output path | stderr; exit `1` |

Do not retry aggressively in v1 (at most one attempt per URL). Do not prompt interactively.

---

## 9. Acceptance tests

### 9.1 Primary UAT (Helic-locked) — QA仔

Fixture: `fixtures/shen-de-mofangfan-ch1-20.txt` — 第1–20章 URLs for 《神的模仿犯》林思之, sourced from catalog https://uukanshu.cc/book/26186/#tuijian (skip the “latest chapter” pin; use ordered 第1章…第20章 links).

Command shape:

```text
web-to-epub fixtures/shen-de-mofangfan-ch1-20.txt \
  --title "神的模仿犯" --author "林思之" \
  -o /tmp/shen-de-mofangfan-ch1-20.epub
```

QA仔 checks:

1. Exit `0` if ≥1 chapter extracted (prefer all 20; document any skips).
2. EPUB opens in a common reader; TOC shows chapters in 第1…第20 order for successes.
3. Bodies are readable Chinese novel text; ads / site chrome / recommendation blocks do not dominate.
4. No images in the package.
5. Metadata title/author match the flags.

Note: uukanshu (and similar) may rate-limit, geo-block, or serve anti-bot HTML. That is an environment risk, not a reason to add login/bypass. Failures stay on the fail-continue path; if the site wholesale blocks the box, report blocker with sample stderr instead of forcing a green UAT.

### 9.2 Secondary checks (implementer)

1. **Comment/blank lines** — fixture comments do not become chapters.
2. **Partial failure** — mix one bad URL with two good ones → exit `0`, two chapters, stderr notes the failure.
3. **Total failure** — only bad URLs → exit `1`; no EPUB written (temp+rename).
4. **Text only** — no `<img>` / image items.
5. **Metadata** — `--author` present vs omitted.

Automated unit tests (impl plan): URL-file parser; empty extract → skip; N chapters → N spine items. Live network tests optional / skippable offline.

---

## 10. Repo layout (for implementation; not created in this commit)

```text
web-to-epub/
  docs/superpowers/specs/2026-11-10-web-to-epub-design.md  # this file
  fixtures/shen-de-mofangfan-ch1-20.txt                   # QA仔 UAT URL list
  README.md
  pyproject.toml   # or requirements.txt + setup
  src/web_to_epub/
    __init__.py
    __main__.py
    cli.py
    fetch.py
    extract.py
    epub_build.py
    url_file.py
  tests/
```

This tree currently holds the design spec plus the UAT fixture. No application code yet.

---

## 11. Implementation boundary

One implementation plan should cover: project scaffold, URL-file parser, fetch+extract+epub pipeline, CLI wiring, QA仔 UAT against `fixtures/shen-de-mofangfan-ch1-20.txt`, and a short README. No second phase is required for v1 usefulness. Defer GitHub `yoursun0/web-to-epub` remote creation until Helic asks; local git on the box is enough to start.

---

## 12. Spec self-review (2026-11-10)

- No TBD/TODO placeholders left.
- Approach, CLI, and pipeline agree: many URLs → one EPUB; one chapter per URL; text only; continue on failure; write only if ≥1 chapter.
- Scope fits a single implementation plan (small CLI, three libraries, sequential loop).
- Ambiguities resolved: default output path `./output.epub`; omit creator when `--author` absent; http(s) only; duplicates kept; images stripped/disabled; no retries beyond one attempt.
- Primary UAT locked to 《神的模仿犯》ch1–20 fixture for QA仔 (2026-11-10 Helic).
