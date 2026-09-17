# Production briefing view-model contract (Slice 1)

See also prototype contract at `prototypes/daily-intelligence-briefing-v2/docs/VIEW-MODEL-CONTRACT.md` (design evidence only).

## Page

- `title`, `subtitle`, `as_of`
- `filters` / `filter_options` / `query_string` / `clear_href`
- `what_changed_bands[]` (`id`, `label`, `count`, `items`)
- `needs_attention[]`, `historical_context[]`, `unknown_publication_dates[]`
- `coverage_pulse`
- `selected_reader`
- `prototype_fixture_used=false`, `fixture_dependency=null`

## Item

- identity: `id`, `headline`, `canonical_url`, `source_id`, `source_name`
- dates: `publication_date`, `capture_date`, `recency_band`, `recency_label`
- context: `berries`, `regions`, `topics`, `entities[]`
- quality: `readable_body_state`, `usable_in_app`, `acquisition_outcome`, `review_trust_state`
- meaning: `observed_change`, `analyst_implication`, `implication_available`
- handoffs: `profile_url`, `landscape_url`, `reader_href`, `intelligence_href`
- attention: `attention_reason`, `attention_label`

Unavailable fields return honest empty/null values — never invented copy.
