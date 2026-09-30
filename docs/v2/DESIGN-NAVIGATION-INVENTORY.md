# Navigation preservation inventory

Status: design proposal; no production sections removed. Originally audited the feed-first NAV and V2 sidebar; the section audit adds the stakeholder navigation and other entry points. The complete route registry and disposition recommendations are in `APP-SECTION-AUDIT.md`. No production navigation has been consolidated yet.

Top level: News, Map Explorer, Entities, Learn, More. More contains eight groups in four desktop columns and remains within the viewport. People is a tab within an individual company dossier, not a global directory or News section. Learn is always top level; Statements is under More. Prototype links marked ↗ open the existing app; their layouts have not been redesigned.

| Existing section | Existing route | Proposed access | Prototype status |
| --- | --- | --- | --- |
| News | `/today` | News | Interactive sample; existing route preserved |
| Following | `/following` | More → Read & follow → Following | Link to existing app; redesign pending |
| Saved | `/saved` | News → Personal Digest | Accepted consolidation with Reading Queue and subscribed-list stories; compatibility link retained |
| Entities | `/entities` | Entities | Interactive sample; existing route preserved |
| Variety Database | `/entities/variety` | More → Markets & varieties → Variety Database | Link to existing app; redesign pending |
| People | `/people` | Entities → selected company → People tab | Company-scoped prototype; legacy route remains intact, no global navigation entry |
| Statements | `/statements` | More → Analysis & decisions → Statements | Link to existing app; redesign pending |
| Landscapes | `/landscapes` | Intelligence → Landscape | User-configurable subjects, geography and sections accepted; implementation pending |
| This week | `/week` | More → Read & follow → This week | Link to existing app; redesign pending |
| Learn | `/learn` | Learn; contextual Explain this / Research & add to Learn | Visual lesson and Perplexity deep-research expansion accepted; implementation pending |
| War Room | `/war-room` | More → Reports & Briefings → Meeting Prep | Accepted rename; preserve notes, scope and existing links |
| Watchtower | `/watchtower` | More → Watches & alerts → Watchtower | Link to existing app; redesign pending |
| Research Ops | `/research-ops` | More → Sources & collection → Research Ops | Link to existing app; redesign pending |
| Settings | `/settings` | More → Directory & settings → Settings | Link to existing app; redesign pending |
| How it works | `/guide` | More → Directory & settings → How it works | Link to existing app; redesign pending |
| Morning Brief | `/brief` | More → Read & follow → Morning Brief | Link to existing app; redesign pending |
| Live Intelligence | `/work-queue` | More → Read & follow → Live Intelligence | Link to existing app; redesign pending |
| Review Operations | `/review-ops` | More → Review & quality → Review Operations | Link to existing app; redesign pending |
| Reading Queue | `/queues/reading` | News → Personal Digest | Accepted shared workspace; keep independent saved/read/priority/completed state |
| Pending Review | `/pending` | More → Review & quality → Pending Review | Link to existing app; redesign pending |
| Signal Review | `/signals/review` | More → Review & quality → Signal Review | Link to existing app; redesign pending |
| Assessments | `/assessments` | More → Analysis & decisions → Assessments | Link to existing app; redesign pending |
| Strategic Questions | `/strategic-questions` | More → Analysis & decisions → Strategic Questions | Link to existing app; redesign pending |
| Monitoring queue | `/queues/monitoring` | More → Watches & alerts → Monitoring queue | Link to existing app; redesign pending |
| Alerts | `/queues/monitoring#alerts` | More → Watches & alerts → Alerts | Link to existing app; redesign pending |
| My Watches | `/watches` | More → Watches & alerts → My Watches | Link to existing app; redesign pending |
| Source Health | `/sources` | More → Sources & collection → Source Health | Link to existing app; redesign pending |
| Companies | `/entities/company` | Entities → Companies | Interactive sample; existing route preserved |
| Variety coverage | `/varieties/coverage` | More → Markets & varieties → Variety coverage | Link to existing app; redesign pending |
| Variety identity review | `/varieties/candidates` | More → Directory & settings → Variety identity review | Link to existing app; redesign pending |
| Entity identity integrity | `/entities/identity` | More → Directory & settings → Entity identity integrity | Link to existing app; redesign pending |
| Map Explorer | `/explorer` | Map Explorer | Interactive sample; existing route preserved |
| Geographies | `/geographies` | More → Markets & varieties → Geographies | Link to existing app; redesign pending |
| Landscape | `/entities/berry` | More → Markets & varieties → Landscape | Link to existing app; redesign pending |
| Competitor Landscape | `/competitors` | More → Markets & varieties → Competitor Landscape | Link to existing app; redesign pending |
| Executive Readout | `/readout` | More → Reports & briefs → Executive Readout | Link to existing app; redesign pending |
| Manager Brief Pack | `/brief-pack` | More → Reports & briefs → Manager Brief Pack | Link to existing app; redesign pending |
| Saved Brief Packs | `/brief-packs` | More → Reports & briefs → Saved Brief Packs | Link to existing app; redesign pending |
| AI-Assisted Reports | `/reports` | More → Reports & briefs → AI-Assisted Reports | Link to existing app; redesign pending |
| Intake | `/intake` | More → Sources & collection → Intake | Link to existing app; redesign pending |
| Publications | `/review?kind=publication` | More → Review & quality → Publications | Link to existing app; redesign pending |
| Claims | `/review?kind=atomic` | More → Review & quality → Claims | Link to existing app; redesign pending |
| Source fidelity | `/source-fidelity` | More → Review & quality → Source fidelity | Link to existing app; redesign pending |
| Collection Operations | `/collection-ops` | More → Sources & collection → Collection Operations | Link to existing app; redesign pending |
| Coverage Assurance | `/coverage-assurance` | More → Sources & collection → Coverage Assurance | Link to existing app; redesign pending |
| Claim testing | `/queues/testing` | More → Review & quality → Claim testing | Link to existing app; redesign pending |
| Signal catalog | `/signals` | More → Analysis & decisions → Signal catalog | Link to existing app; redesign pending |
| Newsfeed | `/` | More → Read & follow → Newsfeed | Link to existing app; redesign pending |
| Commercial positions | `/queues/commercial_position` | More → Analysis & decisions → Commercial positions | Link to existing app; redesign pending |
| Recommendations | `/recommendations` | More → Analysis & decisions → Recommendations | Link to existing app; redesign pending |

Before migration sign-off: audit every routed page and detail/action endpoint, preserve bookmarks and permissions, check active section highlighting, empty/error states and keyboard navigation. Static/public builds must keep their existing route and private-data exclusions; this local studio menu is not a public-build navigation manifest. No consolidation or retirement is authorized by omission from a mockup.


## Additional entry points found in the section audit

These were absent from the original 50-entry inventory. They are inventoried here, not newly added to the prototype menu. The audit recommends consolidated destinations before another menu expansion.

| Existing section | Existing route | Recommended home to review | Status |
| --- | --- | --- | --- |
| Front Page | `/news` | News edition/briefing view | Working route; consolidation candidate |
| Industry Pulse | `/industry-pulse` | Operations → Discovery | Operator-only; not abandoned |
| Ask Berry | `/research` | Intelligence, with contextual access | Working question interface |
| Radar | `/radar` | Intelligence → Developments | Working cached-development surface |
| Moves | `/moves` | Intelligence/Companies → Moves | Working derived company lens |
| Whitespace | `/whitespace` | Landscape → Coverage and concentration | Working coverage-sensitive view |
| Search | `/search` | Global search/results | Retain full results and overlay |
| Design System | `/design-system` | Developer-only | Component gallery; not product navigation |

Company/variety comparisons, company portfolio, geographic and entity details, Story Threads, publication-review migration views, report builders/exports and alternate views are also covered in `APP-SECTION-AUDIT.md`. Action/API endpoints are listed in `artifacts/design-sprint/route-audit-inventory.json` and are not counted as independent menu sections.
