# Imagery & Fallback Policy — Product Visual System V1

## Principles

- Imagery supports reading; it is not decoration-first.
- Never hotlink arbitrary remote images in prototypes or as “factual” article photos.
- Never use AI-generated images as if they were captured article imagery.
- Prefer captured/local assets with known provenance when showing a real article image.

## Cases

| Situation | Treatment | Notes |
|---|---|---|
| Legitimate article image available | Show captured/local image in media slot (16:9 or square card crop) | Caption/source optional |
| Company / source identity only | Monogram / initials on soft navy-tint field | Use when no article image |
| No image | Dashed empty slot with “No image” | Do not invent filler photos |
| Unavailable remote image | Broken/unavailable slot (danger-tint, “Unavailable”) | After failed load; keep layout stable |
| Non-company entity | Distinct entity slot (region/variety/etc. label) | Avoid fake logos |
| Video / podcast | Dark media-type marker (▶ Video / Podcast) | Not a fake thumbnail of content |

## Honesty rules

- Bot-wall, cookie, empty, and navigation-shell records should not display successful article imagery.
- Historical context may show image if captured, but labeling remains historical.
- Unknown-date content retains date limitation regardless of image presence.

## Production guidance

- Wire `onerror` → unavailable treatment.
- Store image availability on the briefing/view model; don’t probe randomly at render time in a way that blocks first paint.
- Competitor Landscape identity marks can reuse the identity slot language.
