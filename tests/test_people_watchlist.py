from app.services.people_watchlist import discover_people, people_model


def test_people_come_from_structured_inventor_fields_only():
    entities = [
        {
            "id": "patent-uspp-demo",
            "entity_type": "patent",
            "name": "USPP demo",
            "berry_ids": ["berry-blueberry"],
            "attributes": {"inventor": "Vincent David Mazzardis"},
        },
        {
            "id": "breeding_program-demo",
            "entity_type": "breeding_program",
            "name": "Demo program",
            "berry_ids": ["berry-strawberry"],
            "attributes": {"named_inventors": ["Douglas Shaw", "not a name"]},
        },
        {
            "id": "company-x",
            "entity_type": "company",
            "name": "Invented Co",
            "description": "Led by Jane Imaginary who is not a structured field",
            "attributes": {},
        },
    ]
    people = discover_people(entities)
    names = {row["canonical_name"] for row in people}
    assert "Vincent David Mazzardis" in names
    assert "Douglas Shaw" in names
    assert "Jane Imaginary" not in names
    assert all(row["monitoring_coverage"] == "discovery-only" for row in people)
    assert all(row["social_coverage"] == "provider-unavailable" for row in people)
    model = people_model(entities)
    assert model["count"] == 2
    assert "provider-unavailable" in model["disclosure"]
