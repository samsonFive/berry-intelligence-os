# Canonical Entity Identity Integrity V1

Audit of checked-in canonical Companies and Varieties on
`origin/v2/intelligence-os`, plus the Planasa reconciliation.

This is data-quality work. No fuzzy merge. No body rewrite.

## Counts on the audited corpus

| Class | Living count | Exact name duplicates | Alias collisions | Other confirmed | Probable / needs review |
|---|---:|---:|---:|---:|---:|
| Companies | 51 | 0 | 0 | 1 redirect (`company-planasa-2`) | 0 live pairs |
| Varieties | 64 | 0 | 0 | 0 | 0 live pairs |

`company-planasa-2` is **not** a checked-in entity file. It is the ID
`unique_entity_id("company", "Planasa")` mints after `company-planasa`
already exists, because review publish previously matched exact names
only and ignored aliases.

## Planasa

| ID | Name | Aliases | Verdict |
|---|---|---|---|
| `company-planasa` | Plantas de Navarra, S.A. | Planasa | Surviving canonical identity |
| `company-planasa-2` | (publish-path trade-name duplicate) | — | CONFIRMED DUPLICATE of `company-planasa` |

They are the same legal/commercial entity (Planasa is the trading name
of Plantas de Navarra, S.A.), not a parent/subsidiary pair and not a
distinct regional company. The `-2` ID is an accidental duplicate-import
pattern from alias-blind publish, not a second firm.

Surviving ID: `company-planasa`. Retired ID: `company-planasa-2`.

Old hrefs `/entities/company/company-planasa-2` redirect to the survivor.
Search, Report Builder (via living entities), and Company Compare follow
the same redirect map so coverage cannot double-count.

## Other companies left unresolved

- Costa Group Holdings vs Costa Berry International: **DISTINCT**
  (parent / patent-holding counterpart; no shared alias).
- Planasa vs Advanced Berry Breeding: **DISTINCT** parent/subsidiary.
- Bisa Trading vs Prunus Persica: **DISTINCT** joint OZblu patent
  assignees that happen to own the same patents. Not merged.
- Allberry B.V. vs Advanced Berry Breeding: **UNKNOWN** — Allberry has
  no company entity (TD-ENT-002). Not invented here.

## Varieties

Last Call (`variety-last-call`) and FC11-164 (`variety-fc11-164`) are
**DISTINCT**: different parentage, USPP025386 vs USPP034903, different
Canadian PBR numbers. Not merged.

No exact canonical/alias, breeder-code, or registration-id collisions
were present in the checked-in Variety corpus. Inbox candidate conflicts
remain review-only and were not bulk-reconciled.

## Merge primitive

`app/services/entity_identity_merge.py` merges only when both records
exist and a caller names the survivor. It unions aliases, rewrites
explicit ID fields, dedupes identical relationships, and never rewrites
Evidence bodies. Publish now matches folded aliases before creating a
new Company, so a later "Planasa" attach cannot mint `-2`.
