# Reader security / content-handling notes (Slice 1)

1. Record IDs accepted only via `is_safe_record_id` (no path segments, no `..`).
2. External URLs must be `http`/`https` with a network location.
3. Reader body uses `classify_source_body` + `reader_content` sanitized plain text / structured paragraphs — never raw publisher HTML.
4. Interstitial / bot / consent states clear observed change and implication text.
5. Original source opens in a new browsing context with `rel="noopener noreferrer"`.
6. Unsupported/unreadable states explain the condition and route to diagnostics/review; they do not invent a body.
