"""Exact official-page image bindings established by the bounded cohort run.

These public references were observed in each publisher's own retained HTML
and visually inspected. This is no host-wide CDN permission, image transport,
license grant, cache permission or export permission. Existing identity,
source-state and asset-specific display checks still apply.
"""

SOURCE_PROOFS = ({'entity_id': 'brand-fruitist',
  'source_page_url': 'https://www.fruitist.com/',
  'image_url': 'https://cdn.prod.website-files.com/67eb354a3bfe8fdee496f42f/680164b4b87b7cf6ccde6c65_jumbo-packaging.avif',
  'source_html_sha256': 'dfc3386de057e084f04340e50b560fc64d2637112693b513ac55dab6122e4f68',
  'checked_at': '2026-11-12T02:06:56.606264+00:00'},
 {'entity_id': 'brand-fruitist',
  'source_page_url': 'https://www.fruitist.com/',
  'image_url': 'https://cdn.prod.website-files.com/67eb354a3bfe8fdee496f42f/680164b4a426cb28ad7e7553_jumbo-bag.avif',
  'source_html_sha256': 'dfc3386de057e084f04340e50b560fc64d2637112693b513ac55dab6122e4f68',
  'checked_at': '2026-11-12T02:06:56.606264+00:00'},
 {'entity_id': 'company-berryworld',
  'source_page_url': 'https://www.berryworld.com/about/planet/pack',
  'image_url': 'https://berryworld-brand.transforms.svdcdn.com/production/consumer/timeline/PACK-2_2024-03-15-135931_eroh.png?w=800&auto=compress%2Cformat&fit=crop&dm=1710511171&s=36687449573795bf8a08ceda17c02872',
  'source_html_sha256': '1ccfed825b12640f4d8b319abad9cf9a55083b5907062af1bbef9b419229dbd2',
  'checked_at': '2026-11-12T02:06:56.606264+00:00'},
 {'entity_id': 'brand-fruitist',
  'source_page_url': 'https://www.fruitist.com/',
  'image_url': 'https://cdn.prod.website-files.com/67eb354a3bfe8fdee496f42f/67ec64c60a844bf46a150b59_appclip.png',
  'source_html_sha256': 'dfc3386de057e084f04340e50b560fc64d2637112693b513ac55dab6122e4f68',
  'checked_at': '2026-11-12T02:43:31.085861+00:00'})
VERIFIED_EXTERNAL_REFERENCES = frozenset(
    (row['source_page_url'], row['image_url']) for row in SOURCE_PROOFS
)


def verified_external_reference(image_url, source_page_url):
    return (source_page_url, image_url) in VERIFIED_EXTERNAL_REFERENCES
