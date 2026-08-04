# Berry Intelligence OS — Product Requirements Document

**Version:** 0.1  
**Status:** Foundational draft for Claude Code implementation

## 1. Executive summary

Berry Intelligence OS is a local-first, JSON-backed intelligence platform for understanding the global berry marketplace. It captures evidence from articles, patents, trade shows, trip reports, team observations, retail visits, research, and other sources; structures that evidence into linked entities, facts, relationships, assessments, signals, and recommendations; and publishes explainable intelligence products for product leaders and broader cross-functional audiences.

The V1 begins operationally with blueberry while preserving a multi-berry foundation for blueberry, raspberry, strawberry, and blackberry. Berry, competitor, and source are first-class filter dimensions from the beginning.

## 2. Problem statement

Competitive intelligence is often fragmented across presentations, inboxes, spreadsheets, personal notes, shared drives, and individual memory. This creates repeated research, inconsistent terminology, weak provenance, difficult onboarding, and reports that become obsolete shortly after publication.

The product must create a living market memory in which new evidence strengthens existing understanding rather than starting another isolated document.

## 3. Primary users

### Intelligence analyst / system owner

Captures, reviews, structures, publishes, and maintains intelligence. Needs a fast work queue, strong provenance, duplicate control, and file-level portability.

### Global product leader

Needs an understandable view of category position, competitive challenges, varieties, genetics, market activity, and testing or commercial priorities.

### Product, breeding, commercial, and regional teams

Need trustworthy access to competitor performance, variety developments, source evidence, market activity, and category-specific onboarding.

### Future contributor

Submits articles, observations, photos, reports, and facts through a secure hosted intake pathway, without direct access to trusted published data.

## 4. Product principles

- Evidence is the root object.
- Published facts remain traceable to evidence.
- Facts, claims, assessments, signals, and recommendations are visibly distinct.
- AI may suggest structure but cannot publish autonomously.
- JSON files are the authoritative data store.
- The system must run locally and be versionable in Git.
- A read-only web build must be deployable independently.
- Generated indexes, HTML, and caches must be reproducible from trusted records.
- The interface should reveal why an item matters, not merely what happened.
- The data model is multi-berry even when the first operational dataset is blueberry.

## 5. V1 scope

### Included

- local web application;
- evidence intake by form;
- article, note, observation, report, and standalone-fact pathways;
- file-drop and batch-import support;
- review and structuring workspace;
- entity matching and creation;
- optional extraction of facts and relationships;
- reading, testing, commercial-position, and monitoring priorities;
- newsfeed generated from published records;
- company, variety, evidence, source, and strategic-question pages;
- search and filters;
- priority queues;
- read-only static publication build;
- schema validation and rebuild commands;
- Git-compatible audit trail.

### Deferred

- fully collaborative editing;
- automatic web scraping;
- autonomous publishing;
- complex permissions;
- graph database;
- predictive scoring;
- native mobile app;
- real-time alerts;
- company-specific internal integrations.

## 6. Core workflow

1. Capture source material.
2. Preserve the original submission.
3. Create a draft evidence record.
4. Review proposed metadata and entity matches.
5. Create or link entities.
6. Optionally publish linked facts and relationships.
7. Assign priority dimensions and rationale.
8. Link strategic questions.
9. Publish the evidence.
10. Rebuild feed, entity pages, queues, and search.

## 7. Primary modules

### Home / analyst cockpit

Answers: What deserves attention and what work remains?

Must show:

- new evidence;
- items awaiting review;
- unresolved entity matches;
- high-priority items;
- recently updated signals;
- recent published intelligence.

### Newsfeed

Answers: What changed?

Must provide reverse-chronological feed cards with source type, summary, relevant entities, geography, priority dimensions, rationale, and provenance links.

### Intake

Answers: What did we learn and where did it come from?

Input types:

- article or URL;
- note or observation;
- uploaded report;
- standalone fact;
- later: hosted team submission.

### Review and structure

Answers: What knowledge does this evidence create?

Must preserve the original on one side and proposed structured output on the other.

### Entity pages

Answers: Who or what is this, and how is it evolving?

Initial entity types:

- company;
- variety;
- source;
- brand;
- breeding program;
- geography;
- retailer;
- trait.

### Priority queues

Answers: What should be read, tested, commercially reviewed, or monitored?

### Strategic questions

Answers: What enduring business question does this evidence help resolve?

### Signals

Answers: What pattern may be emerging, how strong is it, and what supports it?

## 8. Visual language

The approved mockup establishes the initial design language:

- dark navy navigation and application shell;
- white work surfaces;
- compact cards with generous spacing;
- object-type badges;
- purple for intelligence/navigation emphasis;
- green for supportive or strengthening states;
- orange for commercial attention;
- blue for reading or informational priority;
- clear priority chips rather than generic alerts;
- dense but legible analyst views;
- split-pane review screens;
- linked context visible without leaving the current task.

Canonical card types must be created for evidence, facts, entities, relationships, signals, recommendations, and workspaces.

## 9. Trust and provenance requirements

Every published fact must include:

- at least one evidence ID;
- confidence level;
- reviewer;
- creation time;
- status;
- clear statement.

Every evidence record must preserve:

- original source or submission;
- capture date;
- source type;
- submitter;
- review state;
- original attachment or URL when available.

Competitor claims must be labeled as claims unless independently verified.

## 10. Success criteria

The V1 is successful when:

- the owner can capture and publish a new article without editing JSON directly;
- the same article can create linked entities, facts, and relationships;
- published intelligence automatically appears in the newsfeed and relevant entity pages;
- users can filter by berry, competitor, source, geography, event type, and priority;
- every conclusion can be traced to evidence;
- the complete system can be rebuilt from versioned files;
- a read-only web build can be deployed independently;
- a new product leader can use the platform to understand the global playing field and onboard a team.
