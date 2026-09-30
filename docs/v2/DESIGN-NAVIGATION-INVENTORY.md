# Navigation preservation inventory

Status: design proposal; no production sections removed. Audited the feed-first NAV and V2 sidebar. This is the visible navigation inventory, not yet an exhaustive application route audit.

Top level: News, Map Explorer, Entities, Learn, More. More contains eight groups in four desktop columns and remains within the viewport. People is a tab within an individual company dossier, not a global directory or News section. Learn is always top level; Statements is under More. Prototype links marked ↗ open the existing app; their layouts have not been redesigned.

| Existing section | Existing route | Proposed access | Prototype status |
| --- | --- | --- | --- |
| News | `/today` | News | Interactive sample; existing route preserved |
| Following | `/following` | More → Read & follow → Following | Link to existing app; redesign pending |
| Saved | `/saved` | More → Read & follow → Saved | Link to existing app; redesign pending |
| Entities | `/entities` | Entities | Interactive sample; existing route preserved |
| Variety Database | `/entities/variety` | More → Markets & varieties → Variety Database | Link to existing app; redesign pending |
| People | `/people` | Entities → selected company → People tab | Company-scoped prototype; legacy route remains intact, no global navigation entry |
| Statements | `/statements` | More → Analysis & decisions → Statements | Link to existing app; redesign pending |
| Landscapes | `/landscapes` | More → Markets & varieties → Landscapes | Link to existing app; redesign pending |
| This week | `/week` | More → Read & follow → This week | Link to existing app; redesign pending |
| Learn | `/learn` | Learn | Link to existing app; redesign pending |
| War Room | `/war-room` | More → Watches & alerts → War Room | Link to existing app; redesign pending |
| Watchtower | `/watchtower` | More → Watches & alerts → Watchtower | Link to existing app; redesign pending |
| Research Ops | `/research-ops` | More → Sources & collection → Research Ops | Link to existing app; redesign pending |
| Settings | `/settings` | More → Directory & settings → Settings | Link to existing app; redesign pending |
| How it works | `/guide` | More → Directory & settings → How it works | Link to existing app; redesign pending |
| Morning Brief | `/brief` | More → Read & follow → Morning Brief | Link to existing app; redesign pending |
| Live Intelligence | `/work-queue` | More → Read & follow → Live Intelligence | Link to existing app; redesign pending |
| Review Operations | `/review-ops` | More → Review & quality → Review Operations | Link to existing app; redesign pending |
| Reading Queue | `/queues/reading` | More → Read & follow → Reading Queue | Link to existing app; redesign pending |
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
