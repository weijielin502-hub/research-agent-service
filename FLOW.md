# Current workflow and result format

```mermaid
flowchart TD
    A[Enter topic in browser] --> B[POST /api/runs]
    B --> C[Save queued run in SQLite]
    C --> D[Background task starts]
    D --> E[Search topic with Tavily or fixture]
    E --> F[Normalize URLs, remove duplicate URLs and titles]
    F --> G{At least 3 usable sources?}
    G -- No --> H[Search topic + overview once]
    H --> I[Merge and normalize results]
    G -- Yes --> J{Tavily live mode?}
    I --> S{Any usable sources?}
    S -- Yes --> J
    S -- No --> R[Mark run failed]
    J -- Yes --> X[Use Tavily raw page bodies; retry missing bodies with Extract]
    X --> Y{Any complete page bodies?}
    Y -- No --> R
    Y -- Yes --> L[Send every body or every body chunk to model]
    L --> M{Citations use extracted source IDs?}
    M -- No --> R
    M -- Yes --> O[Save answer, source metadata and run trace]
    J -- No, fixture --> N[Extractive summary from synthetic snippets]
    N --> O
    O --> P[Browser shows answer, source links and steps]
    E -- Search error --> Q{Another query available?}
    Q -- Yes --> H
    Q -- No --> R
```

Each Tavily request asks for at most 20 basic search results with `include_raw_content=markdown`. Missing bodies are retried with the Tavily Extract API. The agent uses at most two fixed search queries; a second query runs only if the first leaves fewer than three usable search results. Deduplication and extraction failures may leave fewer than 20 complete pages.

Live runs may specify `time_range` (`day`, `week`, `month`, `year`) or custom `start_date`/`end_date` (`YYYY-MM-DD`), but not both. A selected window enables Tavily's `filter_by_published_date`, excluding pages with unknown publication dates. With no window, date filtering is disabled. Every search attempt records measured HTTP response latency and its fixed `basic` search depth; completed runs record total elapsed time. `GET /api/metrics` averages search latency across calls and report latency across completed runs in the latest 20 provider runs, with counts for context.

Every available complete page body is read by the model. Up to 100,000 characters of combined body text go directly to a final synthesis call. Larger inputs are split into consecutive 100,000-character chunks; each chunk is sent to the model, and the resulting notes feed a final cited synthesis. No body is cut at 800 characters or silently truncated. Runs above 5,000,000 total extracted characters fail with an explicit limit error. Long pages increase model calls, time and API usage. Full bodies are held during processing; the run record stores source URLs, search snippets and body lengths, not the full copyrighted page text. No date window or independent fact checking is implemented.

## Result fields

- `answer`: a model-written brief with numbered citations in live mode, or an extractive brief in offline fixture mode.
- `sources`: title, canonical URL, search snippet, Tavily score, domain, local citation ID, `body_chars` and `content_type`. A source with `content_type=search_snippet_only` was not sent to the live model.
- `summary_mode`: `model` or `extractive`.
- `searched_results`, `extracted_pages`, `extraction_failures`: counts and URLs that make missing bodies visible.
- `coverage_warning`: true when fewer than three usable full-page sources were found in live mode.
- `queries_used`: one or two.
- Run metadata: status, search attempts, step events and any error are stored in SQLite and exposed through `GET /api/runs/{id}`.

The browser displays this result. Live runs do not currently create a Markdown file; `examples/sample-brief.md` is generated separately from the synthetic fixture by `scripts/generate_example.py`.
