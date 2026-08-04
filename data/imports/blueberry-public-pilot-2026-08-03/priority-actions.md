# Priority actions

Sixteen recommended actions arising from this package, ordered within three tiers. Each states what
to do, why the evidence supports doing it, and how to tell whether it worked.

These are **recommendations**, kept deliberately separate from facts, signals and assessments. A
recommendation is not evidence of anything. None of them is staged as an importable record.

Tier A actions are prerequisites for trusting anything else in the package. Tier B extends
coverage. Tier C changes how the platform works.

---

## Tier A - Do before relying on the dataset

### A1. Human review and approval of the 121 staged evidence records

All evidence is staged at `status: "in_review"` and is deliberately **not** in the feed. Import,
review, then run `--approve`. Until that happens the package is inert.

**Success test:** `scripts/import_package.py --approve` has been run knowingly, not as a reflex.

### A2. Retrieve the ten missing patent front pages

`coverage-gaps.md` section 3 lists ten patent entities carrying `status: "unverified"` because no
evidence record in the package captures the patent document. Their assignee and grant-date
attributes are currently unsupported.

**Why:** these are the only records in the package where an attribute has no evidence behind it.
Ten fetches removes that entire class of weakness.

**Success test:** zero patent entities with `status: "unverified"` and an empty `evidence_ids`.

### A3. Adjudicate the ten disputed facts

`conflicting-claims.md` lists ten. Four are resolvable from public records with modest effort
(Berry Blue ownership, Agrovision founding year, Mountain Blue founding year, SEKOYA member count).
Four require the source institution to explain itself (Optimus figures, Patrecia inventors,
Sentinel machine harvest, Costa VIP age). Two may be unresolvable (Blue Manila Brix, the duplicated
Eureka Sunrise export codes).

**Do not** resolve any of them by choosing the more plausible number.

**Success test:** each disputed fact has either a resolution with new evidence, or a reviewer note
saying it was examined and left open.

### A4. Confirm the Bonita patent correction is understood before it propagates

The package asserts that OZblu Bonita 'EB 9-12' is US PP28,358 and that PP25,358 is an unrelated
Aglaonema patent. The mis-cited number is preserved as `patent-uspp025358p3` with
`status: "historical"` and an empty `berry_ids`, so the error remains traceable.

**Why:** this correction contradicts material in circulation. If it is wrong, it is wrong in a way
that will be repeated.

**Success test:** a reviewer has independently opened both patent front pages.

### A5. Decide the role-vocabulary question

172 of the 176 validator warnings are advisory notices that a `roles[]` value sits outside the
proposed vocabulary. The entity schema does not constrain `roles[]`, so these are style advisories,
not defects - but 172 of them makes the warning stream unreadable.

Either adopt the vocabulary used here (`intellectual_property_right`, `cultivar`,
`measurable_attribute`, `genetics_licensor`, `rights_holder`, `consumer_brand` and the rest, listed
in `schema-assessment.md`), or narrow the package's roles to the existing proposed set.

**Success test:** validator warning count drops below 20, so that real warnings are visible.

## Tier B - Extend coverage

### B1. Run the registry sweep in Wave 5

CPVO, IP Australia in full, South Africa, Chile, Peru, Mexico. This is the single largest addition
of primary-source evidence available.

**Success test:** `sig-registry-participation-is-highly-uneven-between-breeders` can be moved to
`monitoring` or withdrawn.

### B2. Find a second independent variety trial

One independent trial supports the whole owner-versus-measured comparison. A second changes it from
an anecdote into a comparison.

**Success test:** at least two method-stating trials measuring at least one variety in common.

### B3. Establish standing monitoring on the four sources in `next-research-waves.md`

CFIA blueberry index monthly, Justia Costa Berry International monthly, CIOPORA quarterly, trade
press weekly. New denominations appear in registries before they appear in marketing.

**Success test:** a new denomination is detected from a registry rather than from a press release.

### B4. Map BluGenix marketing names to breeder selection codes

Bounty, Breeze, Cascade, Delight and Eterna are staged as marketing names because no retrieved
source maps them to selection codes. Costa Berry International's joint filings with Florida
Foundation Seed Producers are the likely place the codes appear.

**Why:** without this mapping, Costa's five headline varieties cannot be connected to their own IP.

**Success test:** each BluGenix name is linked to a patent or selection code by evidence, or
explicitly recorded as unmapped.

### B5. Sweep Spanish- and Chinese-language sources

Chile, Peru, Mexico, Spain and Yunnan are all under-covered for language reasons, not for lack of
activity. The BluGenix launch was covered in Chinese first.

**Success test:** at least ten evidence records from non-English primary sources.

### B6. Resolve the ownership question on Berry Blue, LLC via corporate filings

Hortifrut's blueberry IP position depends on it, and the two parties describe it differently.

**Success test:** a filing or instrument naming the members.

### B7. Add the variety backlog after the registry sweep, not before

The remaining Berry Blue, OZblu, Driscoll's, Plablue and Costa entries. Doing this before the
sweep means adding them twice.

**Success test:** the backlog table in `coverage-gaps.md` section 2 is empty.

## Tier C - Platform and process

### C1. Adopt the confidence-on-relationships enhancement, or accept the workaround permanently

The relationship schema has no confidence field. This package encodes confidence in the `notes`
field with a mandatory `confidence=<low|medium|high>; ` prefix on all 204 relationships
(limitation L-2). It works, and it is a string convention that nothing enforces.

`proposed-schema-enhancements.md` contains a backward-compatible field addition.

**Success test:** either the field exists, or the prefix convention is documented as permanent and
validated.

### C2. Decide whether signals become a first-class record type

Six signals are staged in `signals/` and are excluded from import because no schema exists for them
(limitation L-7). They are currently a directory of JSON that nothing reads.

**Success test:** either a signal schema and route exist, or the signals are converted to
strategic questions and the directory is retired.

### C3. Add provenance as a first-class concept on trait values

The package encodes provenance inside `variety.attributes.traits[]` as a per-trait string drawn
from a fixed set (`owner_or_marketer_claim`, `named_trial_measurement`, `independent_report`,
`regulatory_or_registry_record`, `analyst_inference`, `unresolved`). This is limitation L-4, and it
is the mechanism that keeps a marketing Brix figure from being displayed identically to a measured
one.

Nothing in the application currently reads it.

**Success test:** the variety page renders trait provenance, so a reader can see at a glance which
numbers came from the owner.

### C4. Institute a standing correction list

Four attribution errors were found in circulating sources during this pilot - the Bonita patent
number, the OZblu breeder identity, Advanced Berry Breeding's crop coverage, and the
Michigan-Blueberry-Growers-versus-Mountain-Blue-Orchards confusion. This is the basis of
`sig-breeder-and-patent-attribution-drift-in-public-sources`.

**Success test:** corrections are recorded as durable records rather than as notes in one package,
so the same error is not re-introduced by a later wave.

### C5. Never publish an owner-sourced trait figure without its provenance label

Every quantitative trait claim in this package that came from a breeder or marketer is classified
`claim`, not `fact`, and carries `owner_or_marketer_claim` provenance. Planasa's own 14-versus-13
Brix disagreement about a single variety is the argument for keeping this rule absolute.

**Success test:** no view in the application can display an owner-published number without its
provenance.
