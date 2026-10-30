"""Original, qualitative teaching aids; never measurements or catalog evidence.

Specific source pages were checked on 2026-10-28. The stored curriculum is
preserved: these explanations and citations are presentation overlays only.
"""

SOURCES = {
    "wax": ("University of Bristol · why blueberries are blue (2024)", "https://www.bristol.ac.uk/cabot/news/2024/blueberries.html"),
    "botrytis": ("UC IPM · strawberry Botrytis fruit rot", "https://ipm.ucanr.edu/agriculture/strawberry/botrytis-fruit-rot/"),
    "chill": ("UF/IFAS · blueberry dormancy and chilling models (HS968)", "https://edis.ifas.ufl.edu/publication/HS216/pdf"),
    "clean": ("National Clean Plant Network · what clean plants mean", "https://www.nationalcleanplantnetwork.org/faqs"),
    "strawberry": ("UC Davis · strawberry quality and handling (1996)", "https://postharvest.ucdavis.edu/produce-facts-sheets/strawberry"),
    "bushberry": ("UC Davis · bushberry quality and handling (1998)", "https://postharvest.ucdavis.edu/produce-facts-sheets/bushberry"),
    "beds": ("NC State · Southern Regional Strawberry Plasticulture Production Guide", "https://content.ces.ncsu.edu/southern-regional-strawberry-plasticulture-production-guide"),
    "canes": ("NC State · blackberry fruiting habits and training", "https://content.ces.ncsu.edu/blackberries-for-the-home-garden"),
    "compression": ("USDA ARS · blackberry compression versus subjective firmness (2000)", "https://www.ars.usda.gov/research/publications/publication/?seqNo115=110134"),
    "flavor": ("Gilbert and colleagues · blueberry sensory study (2015)", "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0138494"),
    "harvest": ("University of Maine · wild blueberry harvesting and postharvest handling", "https://extension.umaine.edu/blueberries/post-harvest-handling/"),
    "roots": ("UC IPM · strawberry Phytophthora crown and root rot", "https://ipm.ucanr.edu/agriculture/strawberry/phytophthora-crown-and-root-rot/"),
    "blueberry": ("University of Minnesota · blueberry establishment and soil testing", "https://extension.umn.edu/garden-and-home/yard-and-garden/gardening-in-minnesota/growing-blueberries-in-the-home-garden"),
    "tunnel": ("University of Minnesota · high tunnel raspberries (reviewed 2022)", "https://extension.umn.edu/agriculture/specialty-crops/commercial-fruit-production/raspberry-farming/growing-high-tunnel-raspberries"),
    "swd": ("UC IPM · spotted-wing drosophila on blueberry", "https://ipm.ucanr.edu/agriculture/blueberry/spotted-wing-drosophila/"),
    "virus": ("UC IPM · strawberry virus diseases", "https://ipm.ucanr.edu/home-and-landscape/strawberry-virus-diseases/"),
    "aroma": ("Korean-bred strawberry VOC study · Frontiers in Plant Science (2024)", "https://www.frontiersin.org/journals/plant-science/articles/10.3389/fpls.2024.1360050/full"),
}


def _visual(title, intro, limit, sources, steps, *, illustration=None, mode="factors"):
    return {
        "title": title, "intro": intro, "limit": limit,
        "checked_on": "October 28, 2026", "mode": mode,
        "illustration": illustration,
        "sources": [{"title": SOURCES[key][0], "url": SOURCES[key][1]} for key in sources],
        "steps": [dict(zip(("title", "icon", "caption", "detail"), step)) for step in steps],
    }


DIAGRAMS = {
    "bloom": _visual(
        "The blue starts at the surface", "Here, bloom means fruit wax. Explore the layers behind a blueberry’s appearance.",
        "A schematic, not a microscope image. Wax appearance does not identify a variety, pesticide residue or fruit quality.", ["wax"], [
            ("Wax crystals", "berry", "A fruit-made coating", "Tiny structures in the outer wax scatter light. The powdery appearance is part of the fruit surface, not a flower."),
            ("Reflected light", "sun", "Structure changes what we see", "The Bristol study traced the blue appearance to the wax structure’s scattering of blue and ultraviolet light."),
            ("Pigmented skin", "eye", "Color has more than one cause", "The darker pigments beneath the wax and the optical effect of the coating are different contributors to appearance."),
        ], illustration="wax"),
    "botrytis": _visual(
        "An infection can start before rot is visible", "Follow one possible flower-to-fruit route in strawberry gray mold.",
        "Fruit can also be infected directly. This is not a diagnosis or a pesticide schedule.", ["botrytis"], [
            ("Flower", "flower", "A possible entry point", "Cool, wet conditions can favor flower infection by Botrytis."),
            ("Quiet infection", "eye", "Symptoms may wait", "Infection may remain latent while fruit develops. A clean-looking fruit is not a laboratory test."),
            ("Ripening fruit", "berry", "Rot becomes apparent", "Disease may emerge as fruit ripens; wetness and infected material matter in interpreting the risk."),
        ], mode="process"),
    "chill-hours": _visual(
        "Winter cold and spring warmth do different jobs", "Keep winter dormancy, chilling models and later bud development separate.",
        "This is not a chill calculator or freeze forecast. Models and requirements vary; Florida evergreen systems need separate treatment.", ["chill"], [
            ("Dormancy", "moon", "A seasonal plant state", "Deciduous blueberry production includes a winter dormancy period. Do not apply this pattern to every evergreen system."),
            ("Chill model", "thermometer", "A way to count exposure", "Chilling Hours and the Dynamic Model describe cold exposure differently. Their outputs cannot simply be interchanged."),
            ("Bud development", "sun", "Warmth has a later role", "After dormancy requirements are met, warming can advance growth and change susceptibility to a later freeze."),
        ], mode="process"),
    "clean-planting-stock": _visual(
        "Clean starts with testing, not appearance", "Explore the difference between a clean-plant program and a promise of immunity.",
        "Tests target specified pathogens. State certification and National Clean Plant Network foundation work have different roles.", ["clean"], [
            ("Test", "search", "Look for targeted pathogens", "An apparently healthy plant can carry a pathogen. A test has a defined scope; it does not screen for every possible problem."),
            ("Maintain", "shield", "Protect foundation material", "Clean-plant programs maintain tested foundation plants for propagation. NCPN does not itself certify nursery plants."),
            ("Propagate", "leaf", "Keep the chain traceable", "Vegetative propagation can pass pathogens to new plants. Starting with tested material reduces a route of introduction; it does not make plants immune."),
        ], mode="process"),
    "color": _visual(
        "Describe the color before judging the fruit", "Separate visible appearance, harvest maturity and the eating experience.",
        "Color standards are crop-specific. This drawing is not a calibrated color chart or a fruit grade.", ["strawberry", "wax"], [
            ("Appearance", "eye", "What the surface shows", "Lighting, skin pigments and surface coatings affect the color we see. Blueberry wax is one example."),
            ("Maturity", "calendar", "Interpret within the crop", "Strawberry maturity guidance uses surface color. That does not make one color rule suitable for every berry crop."),
            ("Other qualities", "berry", "Color leaves questions open", "Firmness and flavor are assessed separately. A photograph cannot establish sweetness or storage performance."),
        ]),
    "double-cropping": _visual(
        "Same bed or same cane? Ask which one", "The phrase has more than one production meaning. Compare the two before interpreting a claim.",
        "Neither system is automatic, universal or guaranteed to be profitable. Repeated picking within one crop is another situation.", ["beds", "canes"], [
            ("Reuse the bed", "bed", "Strawberries, then another crop", "The NC State strawberry guide describes removing the strawberry crop and using the bed and drip system for a follow-up crop, such as a vegetable crop."),
            ("Retain fruiting canes", "branch", "Two cane-fruit windows", "Some primocane-fruiting blackberries have early and late crop potential. Whether both crops are useful depends on the variety and regional system."),
            ("Check the claim", "search", "Name plants, place and timing", "Ask whether the source means the same plants, reused infrastructure or two distinct crops. Do not treat these as equivalent."),
        ], mode="comparison"),
    "firmness": _visual(
        "A firmness value needs its test method", "Compare resistance to a test with a person’s judgment of the berry.",
        "This illustrates compression only. Machines, samples and units differ; it is not a calibration or a prediction of shelf life.", ["compression"], [
            ("Apply a load", "tools", "Compress a fruit sample", "An instrument measures the response under a specified compression method. How the sample is tested belongs with the result."),
            ("Record the response", "ruler", "Keep method and condition", "Record the fruit condition and test setup before comparing results. A bare firmness number leaves these out."),
            ("Compare carefully", "eye", "Human ratings are different", "The ARS blackberry study compared compression with subjective ratings and identified limits in separating soft stored fruit. One method is not a universal substitute for another."),
        ], illustration="compression", mode="process"),
    "flavor": _visual(
        "A flavor claim needs both fruit and people", "Compare chemistry, sensory response and the sample’s growing context.",
        "The blueberry study describes its tested genotypes and conditions. It does not rank all berries or predict individual preferences.", ["flavor"], [
            ("Chemistry", "drop", "Sugars, acids and volatiles", "Soluble solids alone leave out acid and aroma contributions."),
            ("Sensory response", "berry", "What people experience", "Sweetness, sourness, flavor intensity and liking are different ratings. A chemical result is not itself a preference score."),
            ("Sample context", "calendar", "Place and harvest matter", "Genotype and growing conditions affect fruit composition. Keep the sampled crop, season and method attached to a comparison."),
        ]),
    "fruit-size": _visual(
        "Large by weight or by width?", "Choose the measurement before comparing two descriptions.",
        "A schematic measurement example. No cultivar, commercial grade or size-to-flavor relationship is implied.", ["bushberry"], [
            ("Mass", "scale", "Weight of a sampled fruit", "A mass measurement answers how heavy the sample is. Keep its units and sampling method."),
            ("Diameter", "ruler", "Width in a stated direction", "A diameter describes a distance, not mass. Fruit shape means the direction of measurement matters."),
            ("Sample spread", "berry", "One large berry is not a crop", "Appearance and size are quality descriptors. To compare a crop, ask for the sample and its range rather than a single showcase fruit."),
        ]),
    "harvest-methods": _visual(
        "Picking and delivering saleable fruit are different steps", "Follow fruit from detachment to cooling, keeping damage in view.",
        "Grounded in blueberry handling guidance, including wild blueberry systems. No machine, variety or labor-saving claim is rated here.", ["harvest"], [
            ("Detach", "tools", "Hand, rake or machine", "The crop and harvest system determine how fruit is removed. The method’s name alone does not establish the quality delivered."),
            ("Catch and move", "box", "Impacts can bruise fruit", "Drop distances, rough movement and packing-line handling can add damage after fruit leaves the plant."),
            ("Cool and assess", "thermometer", "Check the delivered fruit", "Pre-cooling and maintaining storage conditions matter alongside the harvesting method. Assess marketable fruit, not only picking speed."),
        ], mode="process"),
    "phytophthora": _visual(
        "Water connects the pathogen to the root", "Explore a soilborne infection route described for strawberry Phytophthora.",
        "Species, crops and diagnoses differ. Waterlogging alone does not prove infection; this is not treatment guidance.", ["roots"], [
            ("Soil", "bed", "A place the pathogen can persist", "Phytophthora can survive in soil; infected planting material and contaminated water also matter to prevention."),
            ("Water", "drop", "Saturated pores enable movement", "In saturated soil, swimming spores can move through water-filled pores toward plant tissue."),
            ("Roots and crown", "roots", "Damage can impair the plant", "Root and crown infection can lead to poor growth or collapse. Similar visible symptoms need proper diagnosis."),
        ], illustration="roots", mode="process"),
    "plasticulture": _visual(
        "The bed is a production system", "Explore a simplified cross-section of a strawberry plasticulture bed.",
        "Based on a Southern US regional guide. Spacing, inputs and seasonal practice vary; this is not a construction plan.", ["beds"], [
            ("Raised soil", "bed", "A shaped planting bed", "The raised bed supports the crop as part of a managed field system."),
            ("Plastic cover", "shield", "A surface around the plants", "The mulch covers the bed; plants grow through openings. This is different from a tunnel above the crop."),
            ("Drip irrigation", "drop", "Water delivered to the bed", "Drip lines are part of the system described in the guide. The drawing specifies no irrigation rate or fertilizer recipe."),
        ], illustration="bed"),
    "precocity": _visual(
        "Early needs a starting point and a milestone", "Separate time to first fruit from the date a crop ripens in a season.",
        "The Minnesota source gives regional blueberry establishment context, not a universal number of years or a cultivar ranking.", ["blueberry"], [
            ("Starting point", "leaf", "What was planted, and when?", "Plant age and establishment conditions belong with a time-to-production claim."),
            ("Milestone", "calendar", "First fruit or a larger harvest?", "First fruit, a substantial crop and mature plant size are different milestones. State which one is being described."),
            ("Comparison", "search", "Use the same basis", "Compare like planting material and similar conditions. An earlier seasonal harvest is a different meaning of early."),
        ]),
    "protected-culture": _visual(
        "A cover changes the environment; it does not remove it", "Compare the shelter a tunnel provides with the management it still needs.",
        "This example is Minnesota raspberry high tunnels, not all greenhouse or substrate production. A cover does not guarantee winter harvest.", ["tunnel"], [
            ("Shelter", "shield", "Exclude direct rainfall", "A high tunnel changes exposure to rain and can extend the growing season."),
            ("Ventilation", "air", "Heat and humidity still matter", "The covered environment requires ventilation. Excess heat and humidity can create new problems."),
            ("Water and crop", "drop", "Manage the conditions inside", "The crop still needs irrigation and disease management. The response depends on its fruiting habit and local conditions."),
        ]),
    "shelf-life": _visual(
        "Days mean little without storage conditions", "Keep handling, the storage environment and the end point together.",
        "A qualitative handling framework from older UC Davis guidance. No universal storage duration or current product instructions are supplied.", ["bushberry"], [
            ("Starting condition", "berry", "Maturity, injury and decay", "The fruit entering storage already has a condition. Cooling cannot erase pre-existing injury."),
            ("Storage", "thermometer", "Temperature and water loss", "Cooling and maintaining suitable conditions affect deterioration. A shelf-life claim should describe its cold chain."),
            ("End point", "eye", "Define acceptable quality", "Ask what ended the test: appearance, decay, texture or another criterion. Different end points do not yield equivalent day counts."),
        ], mode="process"),
    "soil-ph": _visual(
        "Test the root environment before changing it", "Keep soil acidity, nutrient access and drainage in the same picture.",
        "Blueberry context from Minnesota Extension. This is not a dosing guide; a leaf symptom alone does not establish soil pH.", ["blueberry"], [
            ("Sample the soil", "search", "Measure the planting area", "A soil test gives evidence about pH. Guessing from leaf color leaves other causes unresolved."),
            ("Root environment", "roots", "Acidity affects nutrient access", "Blueberries need acidic soil, but soil structure and drainage also matter."),
            ("Check again", "loop", "Changes take time", "Amendments do not act instantly. Follow-up testing checks the actual response rather than assuming a treatment worked."),
        ], illustration="roots", mode="process"),
    "spotted-wing-drosophila": _visual(
        "The important action happens inside the fruit", "Explore the egg-to-larva part of spotted-wing drosophila’s life cycle.",
        "Identification and monitoring need local guidance. A fruit mark, fly photograph or trap catch alone does not diagnose a lot of fruit.", ["swd"], [
            ("Female fly", "search", "Can attack intact ripening fruit", "The serrated egg-laying structure allows females to penetrate soft-skinned fruit."),
            ("Egg", "berry", "Laid within the skin", "Eggs are placed in the fruit; the name spotted-wing refers to the male’s wing marking, not a requirement that females show that spot."),
            ("Larva", "loop", "Feeds within the fruit", "Larvae develop inside fruit and later leave or partly leave it to pupate. Development varies with conditions."),
        ], mode="process"),
    "strawberry-viruses": _visual(
        "A healthy-looking plant can still carry a virus", "Separate introduction, spread and confirmation.",
        "Symptoms and vectors vary among viruses. This is not a field diagnosis or a promise that vector control prevents every infection.", ["virus"], [
            ("Plant material", "leaf", "Propagation can carry infection", "Viruses can pass through vegetative propagation into daughter plants."),
            ("Vectors", "branch", "Some spread through insects", "Insects such as strawberry aphids transmit a number of viruses. Do not assume all viruses share one vector."),
            ("Confirmation", "search", "Symptoms are not enough", "Single infections may show little obvious damage; multiple infections can be more severe. Testing resolves questions that appearance cannot."),
        ]),
    "texture": _visual(
        "A bite contains more than a firmness number", "Compare a texture experience with a rating of how much someone liked it.",
        "The cited blueberry study used texture liking, not a universal instrument score for crispness, juiciness or every berry crop.", ["flavor"], [
            ("Mouthfeel", "berry", "What eating the fruit feels like", "Texture covers the physical eating experience. It is separate from measuring sugar or aroma compounds."),
            ("Liking", "eye", "A person’s evaluation", "A texture-liking rating asks for preference. It is not the same as measuring how intense one texture attribute is."),
            ("Interpretation", "search", "Association has a scope", "Texture liking was associated with overall liking in the blueberry panel study. That does not establish that one machine reading predicts everyone’s preference."),
        ]),
    "trellis-training": _visual(
        "Support follows the cane’s growth and fruiting habit", "Explore a simplified supported bramble canopy.",
        "No trellis dimensions or pruning prescription are implied. Trailing, erect and primocane-fruiting systems need different decisions.", ["canes"], [
            ("Support", "trellis", "Hold canes in position", "Wires or other supports keep a trained cane canopy arranged in space."),
            ("Train growth", "branch", "Match the growth habit", "Erect and trailing blackberries are trained differently. A single drawing is not a universal system."),
            ("Track cane age", "calendar", "Know what has fruited", "Fruiting habit and cane age inform what is retained or removed. Support does not change a variety’s fruiting habit."),
        ], illustration="trellis"),
    "volatile-aroma": _visual(
        "A list of compounds is not a flavor score", "Follow the distinction between detecting aroma chemistry and testing its sensory meaning.",
        "The 2024 study profiled strawberry cultivars. Chemical abundance alone does not establish consumer liking or a universal berry aroma.", ["aroma"], [
            ("Sample", "berry", "Keep the cultivar and conditions", "The study compared a defined collection of strawberry cultivars. Its scope belongs with its results."),
            ("Identify", "air", "Measure volatile compounds", "GC–MS characterizes volatile compounds in the sampled fruit. This differs from reading soluble solids."),
            ("Interpret", "eye", "Connect chemistry to experience", "A chemical profile needs sensory context before it supports a claim about what people perceive or prefer."),
        ], mode="process"),
    "winter-production": _visual(
        "Write the harvest window on a regional calendar", "Separate season extension from a promise of fruit all winter.",
        "These are regional tunnel-production examples, not proof that a named variety or farm supplies a market year-round.", ["beds", "tunnel"], [
            ("Place", "sun", "Whose winter?", "State the production region and the market’s season. Winter is not the same calendar window worldwide."),
            ("System", "shield", "Cover and crop response", "Tunnels can shift harvest windows, but cultivar response, planting date and management still matter."),
            ("Actual harvest", "calendar", "Check the dates and volume", "An extended season is not automatically continuous winter production. Ask what was harvested in the stated location and period."),
        ]),
}

# Match the two original fields rather than replacing later human edits. The
# original values remain in the record and in a collapsed explanation on screen.
DOUBLE_CROPPING_LEGACY = {
    "summary": "A production strategy that takes two distinct harvest cycles from the same planting within one season, most established today in strawberry plasticulture systems.",
    "what_is_it": "Double cropping is a production strategy where a grower takes two distinct harvest cycles from the same planting within a single season or annual cycle, rather than one. In strawberries this is closely tied to plasticulture: annual hill culture on raised, plastic-covered, fumigated beds with drip irrigation, which shortens time-to-harvest compared to older matted-row systems and creates the production flexibility that makes multiple cropping windows commercially viable.",
}
DOUBLE_CROPPING_CLARIFICATION = {
    "summary": "Double cropping can mean reusing a strawberry bed for a follow-up crop, or taking two cane-fruit harvests. Check which plants and production system the source means.",
    "what_is_it": "The NC State strawberry guide describes removing strawberries and growing a follow-up crop on the reused beds. In some primocane-fruiting blackberries, double cropping refers to early and late fruiting potential. These are different systems; neither is simply repeated picking from a single harvest.",
}
