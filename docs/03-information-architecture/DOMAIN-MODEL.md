# Information Architecture and Domain Model

## Core lifecycle

Source → Capture → Structure → Connect → Assess → Narrate → Report

The lifecycle is inspired by SSCANR, but the application treats it as an operational workflow rather than a separate reporting module.

## Root object: Evidence

Every article, note, report, observation, image, patent, presentation, or direct submission enters as evidence. Evidence preserves what was received and where it came from.

## Derived objects

### Fact

A concise statement supported by evidence. Facts may be active, disputed, superseded, or withdrawn.

### Entity

A stable object such as a company, variety, source, berry, brand, breeding program, geography, retailer, trait, person, patent, or product.

### Relationship

An explicit connection between two entities, such as owns, develops, licenses, distributes, grows, trials, sells, carries, partners-with, or operates-in.

### Assessment

An analyst interpretation of one or more facts.

### Signal

A monitored pattern supported by multiple evidence or fact records.

### Recommendation

A proposed action, such as read, test, commercially review, or monitor.

### Strategic question

An enduring question that organizes evidence and analysis around a decision need.

### Intelligence product

An assembled view such as a berry landscape, competitor profile, variety profile, weekly digest, testing queue, patent landscape, or onboarding workspace.

## Required first-class dimensions

- Berry
- Competitor / market entity
- Source

Additional normalized dimensions:

- Geography
- Brand
- Variety
- Retailer
- Event type
- Evidence type
- Trait
- Strategic question

## Published lineage

Recommendation → Assessment/Signal → Facts → Evidence → Source

Every published object must expose this chain.
