# Atomic Extraction Qualification Harness V2

## Status and boundary

The harness is ready to consume Atomic Evidence Gold Set V1 through the
`atomic-evidence-gold-set-v1` contract. The canonical Gold Set is being authored
separately and was not present on origin when this implementation began; this
mission therefore commits only a minimal test fixture, not a competing
qualification benchmark.

Qualification grants permission to generate **untrusted** Atomic Evidence
proposals. It does not publish them, approve them, enable recurring extraction,
or change either human review gate.

## Existing architecture retained

V1 already provided the production extraction provider boundary, deterministic
transcript windows, the 12-case `atomic-ci-v1` synthetic benchmark, endpoint
probe, bounded real-transcript sample, immutable runtime run directory,
checksummed evaluation, Markdown review packet, explicit approval CLI,
integrity-linked marker, revocation, and runtime exact-match gate. V2 extends
those components rather than replacing them.

The available adapters remain:

- `openai-compatible`: local LM Studio and compatible chat-completions endpoints;
- `perplexity-agent`: Perplexity Agent API with one exact routed model;
- `perplexity-router`: optional Perplexity Router path where the account has access.

Perplexity is only transport. It receives no implicit trust, has no fallback
model list, and must pass the identical scorer and approval flow.

## Gold Set input contract

The top-level object supplies `gold_set_id`, positive integer `version`,
optional thresholds, and nonempty `cases`. Each case supports:

- a source artifact containing text or ordered segments and optional source metadata;
- expected atomic propositions with stable ID, normalized proposition,
  one or more exact excerpts, entity/geography/berry IDs, structured scope,
  claim type, deterministic matching terms, and optional timestamps;
- forbidden propositions expressed as exact phrases or required-term sets,
  with `critical` or `major` severity and a human reason;
- scoring metadata for review context.

Compatibility aliases are deliberately narrow (`benchmark_id`, `case_id`,
`expected_atomic_propositions`, `proposition`, and singular `exact_excerpt`).
Unknown fields fail closed so a changed fixture cannot silently receive a
different interpretation. When the canonical Gold Set lands, the harness must
be re-fetched and its actual file validated before a real candidate run.

## Deterministic scoring

`app/services/atomic_qualification.py` uses no judge model. Stable normalized
tokens, human-authored match terms, exact excerpt containment, repository IDs,
and scope terms produce these independent metrics:

- **precision**: matched proposals / all proposals;
- **recall**: matched expected propositions / all expected propositions;
- **atomicity**: proposals that do not cover multiple expected propositions;
- **grounding**: matched proposals whose excerpt occurs in the source and
  corresponds to an accepted exact Gold excerpt;
- **entity resolution**: set F1 across expected entity/geography/berry IDs;
- **scope preservation**: required Gold scope terms retained in proposal scope
  or statement;
- **overreach**: severity-weighted forbidden-rule penalty;
- **duplication**: deterministic exact/high-token-overlap duplicate penalty.

Default thresholds are 0.90 for precision, recall, atomicity, entity resolution,
and scope preservation; 1.0 for grounding and overreach; and 0.95 for
duplication. A critical forbidden inference is a hard failure regardless of the
average metrics. Gold Set thresholds are versioned fixture content and therefore
part of its SHA-bound identity.

One generic article summary can match at most one proposition for recall and is
also marked non-atomic if it carries the match terms of multiple expected
propositions. High recall cannot compensate for ownership, causality,
registry-to-commercialization, retailer-commitment, award-to-consumer-preference,
trial-universalization, or marketing-as-independent-verification overreach.

## Qualification run artifact

One evaluation retains, under gitignored `inbox/qualifications/`:

- exact provider, model, endpoint family and sanitized endpoint identity;
- prompt version, extraction version, generation/window settings, and full
  configuration fingerprint;
- synthetic benchmark and Gold Set ID/version/SHA;
- raw model response content and normalized proposals per Gold case;
- all case scores, failures, thresholds, and hard-failure flags;
- wall time, propositions, token telemetry, failure rate, and estimated cost
  when the provider reports it;
- real transcript sampling identity and results;
- checksum plus human review packet.

Raw responses never contain authorization headers because credentials are not
part of model prompts or artifact configuration. They may contain unpublished
source material, so they remain private runtime artifacts. A static-build
sentinel proves qualification output is excluded from public HTML.

## Human approval and invalidation

The only workflow is:

`RUN -> SCORE -> REVIEW PACKET -> EXPLICIT APPROVE -> MARKER`

Automated threshold success only makes the evaluation complete. It never calls
approval. Approval requires an operator identity and a checksum-valid complete
artifact. The V2 marker is bound to the exact provider, model, endpoint family,
sanitized endpoint, prompt version, extraction version, all material settings,
synthetic benchmark identity/SHA, Gold Set identity/SHA, evaluation SHA, and
operator decision. Any change requires a new run and approval.

The recurring runner additionally computes the current Gold Set SHA before it
accepts a marker. `BIOS_COLLECTION_ENABLE_EXTRACTION` remains off by default;
the production scheduler does not opt in.

## Running after the canonical Gold Set lands

```powershell
python scripts/qualify_extraction_model.py evaluate `
  --provider openai-compatible `
  --endpoint http://127.0.0.1:1234/v1 `
  --model <exact-local-model> `
  --gold-set-file benchmarks/atomic-evidence-gold-set-v1.json `
  --inbox-dir inbox
```

For Perplexity Agent, use `--provider perplexity-agent --model <exact-routed-model>`
with `PERPLEXITY_API_KEY` already set in the operator environment. Do not print
or copy the key. Candidate comparison should keep quality thresholds fixed and
report latency/cost separately.

No candidate was executed in this implementation session because the canonical
Gold Set was not yet available. That missing fixture—not infrastructure—is the
next external prerequisite. Credentials/endpoints must also already be safely
configured before comparing real models.
