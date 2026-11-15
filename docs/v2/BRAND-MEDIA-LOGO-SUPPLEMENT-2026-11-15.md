# Supplemental company logo references — November 15, 2026

Five additional existing competitors have source-verified official raster logo
references ready for the additive media installer. This is a prepared source
package, **not a production installation or complete company-logo coverage**.

| Existing company | Selected official mark | Matte |
|---|---|---|
| Plantas de Navarra, S.A. (Planasa) | Planasa Genetics wordmark displayed on the official company homepage | Light |
| Advanced Berry Breeding B.V. | Advanced Berry Breeding full wordmark and raspberry emblem | Dark |
| Fresh Forward | Fresh Forward Breeding & Marketing wordmark | Dark |
| Fresas Nuevos Materiales S.A. | FNM company wordmark and strawberry emblem | Light |
| Masiá Ciscar | Company wordmark and strawberry emblem | Light |

The source package is
`data/configuration/brand_media_logos_supplement_20261115.json`. Its companion
`brand_media_logos_supplement_20261115_sources.json` records the exact homepage
and image URLs, homepage SHA256, image SHA256 at inspection, dimensions,
inspection time, classification and source locator. Each actual raster was
visually inspected. All five references are hosted by the same official site as
their source page, so no external-CDN exception or application code change is
needed. The Planasa image explicitly retains its Genetics label. The unrelated
Fresh Forward consultancy is not used.

The original 47-reference seed and 20-entity cohort are unchanged. The existing
installer accepts this separate five-entity payload within its current bounds:

```text
python scripts/seed_brand_media.py --inbox EXPLICIT_RUNTIME_INBOX --data EXPLICIT_CANONICAL_DATA --seed data/configuration/brand_media_logos_supplement_20261115.json
```

The command above is a read-only plan. The release owner must use the normal
runtime backup, writer coordination, source/hash and fresh-baseline checks
before an explicit `--apply` installation. Existing raw analyst decisions,
rejections and primary-image choices remain authoritative. Applying the same
payload again must add zero records and perform no write.

These are requested original-source references, with visible publisher credit.
Verified-license display, caching and export grants remain false. No image
binary is included in the committed package or stored in application media;
local inspection artifacts are private QA files. No provider call, paid
collection, canonical company mutation, new relationship or crop scope is
introduced. Dark mattes preserve the source pixels and make white lettering
readable through the existing presentation field.

Angus Soft Fruits' official homepages returned HTTP 403 during this bounded
attempt; its separate Good Natured consumer brand is not substituted. The
current ABZ official webpage hostname could not be resolved, and Marionnet's
official homepage closed the connection. Those gaps remain open, as does wider
company coverage. No favicon proxy was used.

Offline acceptance installed the original 47 references in an isolated inbox,
planned five additions without writing, applied those five, preserved every
original raw row, delivered all selected company logos as source references,
and confirmed a zero-write idempotent rerun. Production acceptance must be
recorded separately after an actual installation.
