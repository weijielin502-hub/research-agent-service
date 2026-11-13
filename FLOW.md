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
    G -- Yes --> J[Build answer]
    I --> S{Any usable sources?}
    S -- Yes --> J
    S -- No --> R[Mark run failed]
    J --> K{Model key and model configured?}
    K -- Yes --> L[Model summary with source IDs]
    L --> M{Cited IDs exist?}
    M -- No --> N[Extractive summary from up to 4 sources]
    M -- Yes --> O[Save answer, sources and run trace]
    K -- No --> N
    N --> O
    O --> P[Browser shows answer, source links and steps]
    E -- Search error --> Q{Another query available?}
    Q -- Yes --> H
    Q -- No --> R
```

Each Tavily request asks for at most five basic search results. The agent currently uses at most two fixed queries; it does not ask a model to create the search plan. A second query runs only if the first leaves fewer than three usable sources. No date window or independent fact checking is implemented.

## Result fields

- `answer`: either a model-written brief with numbered citations, or an extractive list of up to four source snippets.
- `sources`: title, canonical URL, content snippet, Tavily score, domain and local citation ID.
- `summary_mode`: `model` or `extractive`.
- `coverage_warning`: true when fewer than three usable sources were found.
- `queries_used`: one or two.
- Run metadata: status, search attempts, step events and any error are stored in SQLite and exposed through `GET /api/runs/{id}`.

The browser displays this result. Live runs do not currently create a Markdown file; `examples/sample-brief.md` is generated separately from the synthetic fixture by `scripts/generate_example.py`.
