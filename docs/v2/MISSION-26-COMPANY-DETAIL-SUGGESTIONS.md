# Mission 26 — Reviewable company details

Approved requirement: collect company links and professional contacts when possible, retain manual editing, and keep People within each company. This builds on the existing profile/history rather than creating canonical people or company relationships.

## Delivered behavior

Profile & links and People offer explicit public-detail research through the existing Perplexity background Agent API. The request includes the public catalog name, aliases and collected website only. Private website overrides, contacts, notes, article bodies and location annotations are not sent. Reading a page never starts or retrieves research.

Durable private reservations deduplicate the form token and an active company run, with at most two active company requests in this local workspace. Submission uncertainty blocks another automatic request. Existing provider references can be checked, stopped or reconnected explicitly; a reserved but unsubmitted request can be resumed or cancelled. Retrieval runs outside the application event loop. Failed retrieval retains the run for another check; stale responses do not replace a newer result. Configuration, actual returned model, original text/citations and review history stay private.

Structured suggestions require an exact provider-native cited source URL. Generated URLs in prose cannot establish provenance. Unsafe links, malformed fields and missing citations are excluded with visible limits; the original response remains available. Website, LinkedIn, social-profile and professional-contact cards distinguish the proposed detail, source explanation and human action. Partial results are labeled. Older runs and raw responses start closed.

The live result exposed bracketed provider references in source explanations. The reading projection now removes those technical markers, retains ordinary bracketed qualifications and preserves the original literal response. An unmatched additional source reference gets a plain-language caution. Source links remain prominent. The accepted contact's source history survives later manual edits; later literal analyst wording is preserved.

## Data and review guarantees

Nothing applies automatically. Each accepted suggestion is scoped to the company's private profile, checks the current profile revision and preserves unrelated edits. Replacing a saved field requires an explicit choice, including deliberately empty fields. Social acceptance adds to existing links rather than deleting them. A same-name existing contact is not replaced or duplicated; the analyst uses its existing editor. Source dates/role caveats stay in the suggestion, and stored mentions do not establish current employment.

The actual profile change, original suggestion/provenance and replay marker share one atomic profile-history commit. A repeated POST after response loss cannot add another contact or overwrite a later edit. Dismissal does not alter the profile. Existing restoration/reset functions retain prior history and accepted provenance. Canonical Entity, Relationship, Evidence, Fact, publication, identity and model-qualification records are untouched. Human review gates remain.

The store and serialization are local-worker scoped. This is not a per-account or distributed job system; those production release checks remain on the debt register. Logo URL/upload/manual editing remains available; automatic logo acquisition and rights review are not claimed here.

## Verification

135 focused Company, profile-research, Personal Digest, portfolio, Learn research and full static/private-sentinel tests passed, one existing reportlab warning, in 104.00 seconds before the final anchor and threadpool follow-up. Canonical validation passed. Final follow-up results and pushed-head checks are recorded in the PR/checklist. Deterministic required tests never use a live provider.

An isolated browser fixture exercised start/check, a saved blank blocked by native required selection, explicit single-field acceptance, a fictional private contact, company-only People/source disclosure and retained profile history. The fixture is labeled illustrative and lives only in ignored runtime. No real suggestion was accepted. A separate single live public-identity run completed with seven suggestions (website, LinkedIn, two social profiles, three professional contacts) and 56 native source URLs. The returned model was `openai/gpt-6-luna` through the configured `medium` preset. This tests transport and reviewability, not factual verification of the suggestions. The completed original capture stays under ignored `inbox/company-research-preview/live-public-capture/`.

The actual live suggestions were inspected in the company panel; default visible text had no `[web:…]` dumps. At a 390px viewport, page and content width were both 375px with a single proposal column. Keyboard source disclosures and action focus were checked; the temporary viewport was reset. Screenshots: `artifacts/design-sprint/company-research-review.png` and `company-research-mobile.png`. Private output is excluded from the public static snapshot.

## Remaining approved work

Source-assisted location/activity proposals and conflict reconciliation, subnational map/snapshot layers, wider country/statistics coverage, article-body/media availability, logo browser-upload/history acceptance, per-account/inter-process persistence, older-PR parity and combined canonical release remain open. Final release review precedes merge or deployment. Completing this slice does not complete the ongoing goal.


Final anchor/threadpool/static follow-up: **53 passed / one existing warning in 76.69 seconds**. No private research entered the static fixture. Required checks on the pushed draft head remain the next gate.
