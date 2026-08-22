# Extraction Model Qualification

Model qualification is an operational permission to create **untrusted**
Atomic Evidence proposals. It is not Evidence approval and does not publish
Facts, Relationships, Assessments, or Recommendations.

## Configure a compatible endpoint

Use command options or environment variables. Keep credentials in the
environment only.

```powershell
$env:BIOS_EXTRACT_BASE_URL = "http://127.0.0.1:1234/v1"
$env:BIOS_EXTRACT_MODEL = "operator-selected-model"
$env:BIOS_EXTRACT_API_KEY = "runtime-secret-if-required"
```

The workflow records a sanitized endpoint identity without user information,
query strings, authorization headers, or API keys.

## 1. Probe

```bash
python scripts/qualify_extraction_model.py probe
```

The probe sends a no-intelligence structured-output request through the
production OpenAI-compatible provider. Success proves connectivity and
contract compatibility only. It never qualifies the model.

## 2. Evaluate

The normal evaluation runs the probe, the existing 12-case
`benchmarks/atomic-ci-v1.json` harness, and a bounded sample of the cached real
Lucentlands transcript.

```bash
python scripts/qualify_extraction_model.py evaluate \
  --inbox-dir inbox \
  --sample-windows 8
```

Use `--transcript-file` or `--transcript-item` if automatic cache resolution
is ambiguous. Evaluation only reads a normalized transcript cache; it never
downloads media or runs Whisper.

Real sampling selects evenly spaced positions from the deterministic
production transcript windows. This covers the beginning, interior, and end
reproducibly, but it is not semantic stratification and cannot guarantee that
every desired topic appears.

Each run creates a unique folder:

```text
inbox/qualifications/qualification-<timestamp>-<digest>/
  evaluation.json
  evaluation.sha256
  review.md
```

The existing `inbox/` ignore rule keeps these artifacts outside trusted
`data/` and static output. `review.md` shows the probe, benchmark failures,
headline metrics, grounded real-sample candidates, timestamps, legitimate
speaker labels, resolvable links, provenance, and a human scoring rubric.

## 3. Review and explicitly approve

Automated scores are decision support. They never issue a marker. After
reviewing the packet:

```bash
python scripts/qualify_extraction_model.py approve \
  --evaluation inbox/qualifications/<run>/evaluation.json \
  --provider openai-compatible \
  --model <exact-model> \
  --operator "<operator identity>"
```

Approval rejects incomplete stages, identity mismatches, missing operator
identity, or a modified evaluation. It creates
`qualification-marker.json` beside the evaluation by default. The marker is
bound to:

- provider and model;
- sanitized endpoint plus generation-setting fingerprint;
- `atomic-ci-v1`;
- benchmark ID, version, and file SHA-256;
- evaluation run ID and evaluation SHA-256;
- operator identity and qualification timestamp.

Changing the endpoint, model, prompt version, windowing, sampling-related
generation settings, candidate limits, response format, benchmark, or
evaluation invalidates reuse. A marker also stops working if its evaluation
artifact is missing or modified.

## 4. Use with recurring collection

Use the same endpoint, model, and extraction settings that were evaluated:

```bash
python scripts/run_collection.py \
  --all \
  --enable-extraction \
  --qualification-file inbox/qualifications/<run>/qualification-marker.json
```

The runner still writes only untrusted proposals to `inbox/evidence/`. Every
proposal requires individual human Evidence review.

## Revoke

```bash
python scripts/qualify_extraction_model.py revoke \
  --marker inbox/qualifications/<run>/qualification-marker.json
```

Revocation renames the marker with a `.revoked` suffix. The runner can no
longer load it. Evaluation history remains available for audit.

## Safe handling

Safe to retain locally: evaluation JSON, checksum, review packet, and marker.
They are runtime review artifacts, not trusted intelligence, and should not be
committed by default. Never commit credentials, authorization headers, private
endpoint query parameters, model caches, transcripts, media, or generated
model output into `data/`.
