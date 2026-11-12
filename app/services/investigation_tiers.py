"""Assigned company tiers over the existing shared marks/history store only."""
from app.services import company_directory
from app.services.analyst_state_io import serialized_write

TIER_GROUPS = (("tier1", "Tier 1"), ("tier2", "Tier 2"), ("tier3", "Tier 3"),
               ("untiered", "Untiered"), ("watch", "Legacy watch"), ("muted", "Muted"),
               ("other_legacy", "Other legacy tier"))
GROUP_ORDER = {key: index for index, (key, _label) in enumerate(TIER_GROUPS)}


def assigned_tier(state, entity_id):
    tiers = state.get("entity_tiers")
    if tiers is None:
        tiers = {}
    if not isinstance(tiers, dict):
        raise ValueError("Assigned company tiers cannot be read; restore the saved marks before editing.")
    value = tiers.get(entity_id)
    if value is None or value == "":
        return "untiered"
    if not isinstance(value, str) or len(value) > 200:
        raise ValueError("An assigned company tier is invalid; restore the saved marks before editing.")
    return value


def tier_label(value):
    return company_directory.TIERS.get(value, "Unrecognized legacy tier")


def tier_group(value):
    return value if value in company_directory.TIERS else "other_legacy"


class TierConflict(ValueError):
    def __init__(self, entity_id, current):
        super().__init__("The assigned tier changed in another view. Reload before saving.")
        self.data = {"id": entity_id, "assigned_tier": current, "assigned_tier_label": tier_label(current)}


@serialized_write
def assign(inbox_dir, *, entity_id, tier, expected_tier=None, allowed):
    """Compare and call the existing mark writer under its reentrant runtime lock."""
    from app.landscape_explorer_routes import company_state
    if entity_id not in allowed:
        raise LookupError("This company is unavailable in the canonical company catalog.")
    if not isinstance(tier, str) or not tier or len(tier) > 200:
        raise ValueError("Choose a supported assigned company tier.")
    if expected_tier is not None and (not isinstance(expected_tier, str) or not expected_tier or len(expected_tier) > 200):
        raise ValueError("Supply the current assigned tier before saving.")
    current = assigned_tier(company_state(inbox_dir), entity_id)
    if expected_tier is not None and expected_tier != current:
        raise TierConflict(entity_id, current)
    # Existing legacy values may be retained, never offered as new assignments.
    if tier not in company_directory.CURRENT_TIERS and tier != current:
        raise ValueError("Choose Untiered, Tier 1, Tier 2 or Tier 3; existing legacy tiers may only be retained.")
    changed = tier != current
    if changed:
        company_directory.mark(inbox_dir, entity_id=entity_id, action="tier", value=tier, allowed=allowed)
    confirmed = assigned_tier(company_state(inbox_dir), entity_id)
    return {"id": entity_id, "assigned_tier": confirmed, "assigned_tier_label": tier_label(confirmed), "changed": changed}
