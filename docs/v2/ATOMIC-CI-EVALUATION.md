# Atomic CI Extraction Evaluation

This harness evaluates the existing `atomic-ci-v1` provider. It does not add a
second extraction path and does not write trusted intelligence.

## Modes

```bash
python scripts/evaluate_extraction.py --probe

python scripts/evaluate_extraction.py --benchmark --model <model-name>

python scripts/evaluate_extraction.py \
  --transcript <transcript-artifact.json> \
  --sample-windows 5

python scripts/evaluate_extraction.py \
  --transcript <transcript-artifact.json> \
  --full
```

Configuration uses the existing `BIOS_EXTRACT_BASE_URL`,
`BIOS_EXTRACT_MODEL`, and `BIOS_EXTRACT_API_KEY` variables or the corresponding
CLI options. No host-specific adapters exist.

The probe submits one safe, zero-intelligence segment through the configured
structured-output mode. It reports missing configuration, reachability,
compatible response status, structured-output status, and latency without
printing the endpoint or API key.

Benchmark and transcript-preview runs write JSON reports under the gitignored
`inbox/evaluations/` directory. They never write `inbox/evidence/`. Generated
reports include provider/model, `atomic-ci-v1`, non-secret window settings,
runtime/token metrics when available, candidate diagnostics, and errors.

To create Evidence proposals after evaluation, the operator must explicitly
run a full transcript with `--persist-proposals`. That flag calls the existing
`TranscriptEvidenceExtractionService`; no evaluation-only proposal writer
exists. The resulting records remain draft, `in_review`, and require human
approval.

## Benchmark contract

The committed `benchmarks/atomic-ci-v1.json` fixture contains company-neutral
synthetic cases. Each case has timestamped transcript segments and behavioral
expectations rather than one mandatory natural-language answer:

- acceptable candidate-count range;
- phrase groups that should occur together in at least one candidate;
- qualifiers that must be retained;
- prohibited inference phrases;
- transcript segments that must support a candidate;
- minimum atomic separation;
- maximum proposed-link count;
- an optional conceptual CI category and operator note.

These checks measure contract adherence, not objective factual truth.

## Deterministic metrics

Reports distinguish:

- structurally valid response rate;
- valid versus provider-rejected candidates;
- invalid candidate count;
- duplicates removed;
- expected candidate-count compliance;
- zero-candidate correctness;
- qualifier checks;
- prohibited-inference hits;
- required transcript-span checks;
- atomic separation;
- unsupported/excess link count;
- unusually long, potentially summary-like candidates;
- excessive proposal volume;
- calls, elapsed time, and optional tokens.

Candidate diagnostics show the normalized statement, exact excerpt, derived
start/end timestamps, segment indexes, proposed links, provider, model, and
prompt version. This is a grounding aid, not an automated truth score.

## Human review rubric

Score a representative candidate sample from 0 to 3 on each dimension:

| Dimension | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| Grounding | Unsupported | Material support gap | Supported with minor ambiguity | Directly supported by cited excerpt |
| Atomicity | Summary or several claims | Requires major splitting | Mostly atomic; minor edit | One independently reviewable assertion |
| Qualifier fidelity | Meaning materially strengthened | Important qualifier weakened | Meaning preserved with minor edit | Attribution, timing, and uncertainty fully preserved |
| CI relevance | Not useful | Low-value/noisy | Worth review with minor edit | Clearly decision-relevant |
| Normalization | Meaning changed | Major rewrite needed | Concise with minor edit | Concise and meaning-preserving |
| Linking | Invented/unsupported | Material correction needed | Defensible with minor correction | Every proposed link directly supported |

Record short reviewer notes for every score below 2. Do not average scores into
false precision; use the dimension pattern and review effort to make the model
decision.

## Comparing models and configurations

Run the identical benchmark against each configured model and retain the
generated artifacts. Compare only a small set of operationally meaningful
controls: model, window size, overlap, temperature, and candidate limits.
Avoid broad parameter sweeps.

Before a full 1,212-segment episode, use five deterministic windows. Sampling
selects the first, evenly spaced middle positions, and last production windows;
the provider still uses the normal window construction, prompt, parsing,
validation, and dedupe path.

## Proposed automation decision threshold

Recurring extraction should remain disabled until an operator judges that:

- structured responses are near-perfect across repeated benchmark runs;
- there are no severe grounding or invented-link failures in a representative
  real-transcript sample;
- qualifier loss is rare and never materially reverses meaning;
- clear multi-claim cases separate reliably;
- no-intelligence and ambiguity cases do not create persistent noise;
- proposal volume and human correction time are operationally manageable;
- a sampled real episode earns mostly 2 or 3 rubric scores, with no grounding
  or qualifier-fidelity score of 0.

This is a decision framework, not a hardcoded gate. Even after a model clears
it, publication and atomic Evidence approval remain human-controlled.
