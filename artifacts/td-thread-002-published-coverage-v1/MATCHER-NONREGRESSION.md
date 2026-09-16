# Matcher non-regression

`items_form_thread()` was not edited. Thresholds remain:

| Constant | Value | Role |
|---|---|---|
| `DATE_PROXIMITY_EXACT_TITLE_DAYS` | 14 | Exact normalized title reprints; also the universe window alias |
| `DATE_PROXIMITY_EVENT_DAYS` | 7 | Same primary company/variety + strong title evidence |
| `DATE_PROXIMITY_TRANSLATION_DAYS` | 1 | Translation-style extra-token overlap |
| `MIN_EVENT_JACCARD` | 0.45 | Residual title Jaccard after company tokens |

Membership still requires one of:

- canonical URL identity (`_same_url`);
- exact normalized title (`_exact_title_reprint`);
- stored same-event `evidence_links` (`follows_up` / `same_signal` / qualified `corroborates` / `contradicts`);
- same primary company or variety **plus** strong title/date evidence (`_strong_event_edge`);
- the existing company↔variety cross-subject edge (`_cross_subject_event_edge`).

Still insufficient:

- co-mention of a company or variety;
- weak title overlap / generic crop words;
- shared berry type or region;
- generic patent-monitor “assignee already linked” corroboration.

Thread presentation is still organizational: `trust_label` is “Organizational grouping”; members keep their own Trusted / Pending badges. Grouping never writes `status` / `review_state`.
