"""Presentation-only teaching aids grounded in existing educational records."""
from copy import deepcopy

PHOTO = {"image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Raspberry.jpg",
         "url": "https://commons.wikimedia.org/wiki/File:Raspberry.jpg",
         "title": "Raspberry fruit", "publisher": "Steffen Flor (Pro2), Wikimedia Commons",
         "license": "CC BY 2.5", "license_url": "https://creativecommons.org/licenses/by/2.5/",
         "caption": "A raspberry fruit. This photograph does not establish cane age or a pruning method.",
         "attribution": "Steffen Flor (Pro2) · CC BY 2.5 · displayed without alteration",
         "verified_at": "2026-10-02"}

# Original teaching sequences, not copied publisher graphics or quantitative models.
# Sources checked October 2, 2026; the original educational record stays unchanged.
DIAGRAMS = {
    "ipm": {
        "title": "A decision loop, not a spray calendar",
        "intro": "Explore the six parts of an IPM program. Prevention and monitoring continue through the cycle.",
        "limit": "Framework only. Action thresholds and product guidance depend on the crop, location and current regional guide.",
        "sources": [{"title": "UC IPM: how the framework works", "url": "https://ipm.ucanr.edu/what-is-ipm/"}],
        "steps": [
            {"title": "Identify", "icon": "search", "caption": "Know the organism", "detail": "Correct identification comes before choosing a control. Similar-looking damage may have different causes."},
            {"title": "Monitor", "icon": "eye", "caption": "Observe pests and damage", "detail": "Check the crop and record pest presence, abundance and damage over time."},
            {"title": "Decide", "icon": "branch", "caption": "Use action guidelines", "detail": "Monitoring and crop-specific guidelines inform whether action is needed; seeing a pest alone is not a spray instruction."},
            {"title": "Prevent", "icon": "leaf", "caption": "Reduce the opportunity", "detail": "Prevention changes conditions that favor pests. It is an ongoing part of the program, not just a fourth step."},
            {"title": "Combine tools", "icon": "tools", "caption": "Match tactics to the problem", "detail": "Combine suitable biological, cultural, physical or chemical approaches when management is needed."},
            {"title": "Check results", "icon": "loop", "caption": "Return to monitoring", "detail": "Assess what the action achieved and use that observation in the next decision."},
        ],
    },
    "harvest-robotics": {
        "title": "Finding a berry is only part of picking it",
        "intro": "Follow a schematic vision-guided picker from fruit detection to collection.",
        "limit": "Illustrative sequence grounded in Robofruit's 2023 research system. Designs vary. Detection, successful picking and fruit quality are different measures; this is not a commercial deployment claim.",
        "sources": [{"title": "Parsa and colleagues: Robofruit research paper (2023)", "url": "https://arxiv.org/abs/2301.03947"}],
        "steps": [
            {"title": "Locate", "icon": "eye", "caption": "Find fruit in the canopy", "detail": "The perception system estimates fruit position and ripeness. Leaves can hide a target from the camera."},
            {"title": "Approach", "icon": "branch", "caption": "Reach the selected fruit", "detail": "The picker must move to the fruit. Removing an occlusion is a separate challenge from recognizing fruit in an image."},
            {"title": "Detach", "icon": "tools", "caption": "Pick without crushing", "detail": "A picking mechanism must separate the fruit while limiting damage. A detected berry is not automatically a successfully harvested berry."},
            {"title": "Collect", "icon": "box", "caption": "Move the picked fruit", "detail": "The research system transports picked fruit through its collection mechanism. Picking percentages alone do not establish commercial packout."},
        ],
    },
    "sugar-acid-balance": {
        "title": "Flavor has more than one channel",
        "intro": "Explore the measurements and sensations behind a flavor claim. These are complementary dimensions, not a weighted score.",
        "limit": "Qualitative illustration, not a prediction of liking. The cited 2015 study assessed 19 southern highbush blueberry genotypes across three years; its results do not rank every berry or cultivar.",
        "sources": [{"title": "Gilbert and colleagues: blueberry flavor study (2015)", "url": "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0138494"}],
        "steps": [
            {"title": "Sweetness", "icon": "drop", "caption": "Sugars and soluble solids", "detail": "Chemical measurements help describe the sample. A soluble-solids reading is not identical to a person's sweetness rating."},
            {"title": "Tartness", "icon": "drop", "caption": "Acid context matters", "detail": "Acids contribute to sourness. A sugar figure alone leaves out this part of the taste experience."},
            {"title": "Aroma", "icon": "air", "caption": "Volatiles contribute", "detail": "Smell contributes to perceived flavor. Sugar and acid measurements do not describe all of the aroma compounds."},
            {"title": "Texture", "icon": "berry", "caption": "The feel of the fruit", "detail": "Texture is another sensory dimension. In the cited blueberry panels, texture liking was associated with overall liking."},
        ],
    },
    "visual-learning-aids": {
        "title": "Keep the picture connected to its source",
        "intro": "A useful teaching visual needs both a clear explanation and a clear reuse basis.",
        "limit": "Source links and original schematics do not prove a named farm's practice. A public page alone does not establish permission to copy its pictures.",
        "sources": [{"title": "Creative Commons: license types and conditions", "url": "https://creativecommons.org/cc-licenses/"}],
        "steps": [
            {"title": "Find the source", "icon": "search", "caption": "Identify the original work", "detail": "Keep the creator, source page and what the image actually depicts together. Avoid an unexplained image copied from a search result."},
            {"title": "Check reuse", "icon": "shield", "caption": "Read the specific terms", "detail": "Creative Commons licenses differ: some restrict changes or commercial use. Do not infer the license from the website category."},
            {"title": "Explain and credit", "icon": "box", "caption": "Caption beside the picture", "detail": "State the teaching point, credit the creator and link the reuse terms. Mark an original schematic as illustrative."},
            {"title": "Keep the boundary", "icon": "branch", "caption": "Teaching is not evidence", "detail": "A diagram can explain a mechanism. It does not establish that a company uses that mechanism, and it does not approve intelligence."},
        ],
    },
}

VIDEOS = {
    "ipm": {"title": "The scientific basis for IPM", "publisher": "UC Statewide IPM Program", "url": "https://www.youtube.com/watch?v=BljIAipO2Eg", "source_page": "https://ipm.ucanr.edu/what-is-ipm/", "caption": "UC IPM links this scientist's explanation. Open at the publisher; playback availability has not been verified."},
    "harvest-robotics": {"title": "Robofruit research demonstration", "publisher": "Robofruit paper authors", "url": "https://www.youtube.com/watch?v=v8gGAvsISXU", "source_page": "https://arxiv.org/abs/2301.03947", "caption": "Video linked by the paper's authors. A research demonstration is not proof of commercial deployment; playback availability has not been verified."},
}


def presentation(concept):
    row = deepcopy(concept)
    # Unspecific legacy 'typically CC' is not a verified reuse basis.
    row["teaching_figure"] = deepcopy(PHOTO) if row["slug"] == "primocane-floricane" else None
    row["cane_diagram"] = row["slug"] == "primocane-floricane"
    row["teaching_diagram"] = deepcopy(DIAGRAMS.get(row["slug"]))
    if row["cane_diagram"]:
        row["media"] = [dict(item, title="Raspberry fruit — Wikimedia Commons") if item.get("url") == PHOTO["url"] else item for item in row.get("media") or []]
        video = {
            "kind": "video", "title": "How Do I Prune Raspberries?",
            "publisher": "University of Maine · linked by University of Maryland Extension",
            "url": "https://youtu.be/pOzo4s9Z9jE?feature=shared",
            "caption": "Watch the pruning demonstration alongside the cane-year explanation. Advice remains regional.",
            "source_page": "https://extension.umd.edu/resource/growing-raspberries-and-blackberries-home-garden",
            "reuse_basis": "Publisher-curated link only; video not copied, hosted or autoplayed.",
        }
        if not any(item.get("url") == video["url"] for item in row.get("media") or []):
            row.setdefault("media", []).append(video)
    if row["slug"] in VIDEOS:
        video = {**VIDEOS[row["slug"]], "kind": "video", "reuse_basis": "Publisher-linked video only; not copied, hosted or autoplayed."}
        if not any(item.get("url") == video["url"] for item in row.get("media") or []):
            row.setdefault("media", []).append(video)
    return row
