"""Presentation-only teaching aids grounded in existing educational records."""
from copy import deepcopy

PHOTO = {"image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Raspberry.jpg",
         "url": "https://commons.wikimedia.org/wiki/File:Raspberry.jpg",
         "title": "Raspberry fruit", "publisher": "Steffen Flor (Pro2), Wikimedia Commons",
         "license": "CC BY 2.5", "license_url": "https://creativecommons.org/licenses/by/2.5/",
         "caption": "A raspberry fruit. This photograph does not establish cane age or a pruning method.",
         "attribution": "Steffen Flor (Pro2) · CC BY 2.5 · displayed without alteration",
         "verified_at": "2026-10-02"}


def presentation(concept):
    row = deepcopy(concept)
    # Unspecific legacy 'typically CC' is not a verified reuse basis.
    row["teaching_figure"] = PHOTO if row["slug"] == "primocane-floricane" else None
    row["cane_diagram"] = row["slug"] == "primocane-floricane"
    if row["cane_diagram"]:
        row["media"] = [dict(item, title="Raspberry fruit — Wikimedia Commons") if item.get("url") == PHOTO["url"] else item for item in row.get("media") or []]
        row["media"] = list(row.get("media") or []) + [{
            "kind": "video", "title": "How Do I Prune Raspberries?",
            "publisher": "University of Maine · linked by University of Maryland Extension",
            "url": "https://youtu.be/pOzo4s9Z9jE?feature=shared",
            "caption": "Watch the pruning demonstration alongside the cane-year explanation. Advice remains regional.",
            "source_page": "https://extension.umd.edu/resource/growing-raspberries-and-blackberries-home-garden",
            "reuse_basis": "Publisher-curated link only; video not copied, hosted or autoplayed.",
        }]
    return row
