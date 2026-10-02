# Navigation preservation inventory

Status: historical proposal baseline plus delivery notes below; no production sections removed. Originally audited the feed-first NAV and V2 sidebar; the section audit adds the stakeholder navigation and other entry points. The complete route registry and disposition recommendations are in `APP-SECTION-AUDIT.md`. The original table records the September 30 prototype disposition; current implementation evidence is recorded below and in the requirements checklist.

Current prototype navigation: News, Map Explorer, Companies, Learn and More. More now has **eight consolidated entries across four groups**: Personal Digest, Landscape, Varieties, Intelligence, Monitor, Reports & Briefings, Operations and Help. Each opens an in-preview workspace with nested views. Existing tools are accessible inside a collapsed disclosure within their new home; the old 44-link menu has been removed. `workspace-navigation.js` defines this review-only navigation. Production routes, permissions and state are unchanged.

Personal Digest contains Reading, Subscriptions and News briefings. Monitor contains Watches and Alerts. Reports & Briefings contains Briefs (builder + library + executive view), Reports, Market snapshots and Meeting Prep. Operations contains Collection & sources, Review and Data quality. Landscape has one home with a coverage lens. People stays inside company profiles; Learn stays top-level. Varieties remains under More until its final top-level placement is decided. These are navigation/organization previews; their integrated workflows are not implemented merely by opening a tab.

| Existing section | Existing route | Proposed access | Prototype status |
| --- | --- | --- | --- |
| News | `/today` | News | Interactive sample; existing route preserved |
| Following | `/following` | Monitor → Watches | Existing route preserved; combined workflow integration pending |
| Saved | `/saved` | Personal Digest → Reading | Existing route preserved; combined workflow integration pending |
| Entities | `/entities` | Entities | Interactive sample; existing route preserved |
| Variety Database | `/entities/variety` | Varieties → Directory & comparison | Existing route preserved; combined workflow integration pending |
| People | `/people` | Entities → selected company → People tab | Company-scoped prototype; legacy route remains intact, no global navigation entry |
| Statements | `/statements` | Intelligence → Evidence & judgments | Existing route preserved; combined workflow integration pending |
| Landscapes | `/landscapes` | Landscape → Overview | Existing route preserved; combined workflow integration pending |
| This week | `/week` | Personal Digest → Briefings (News views) | Existing route preserved; combined workflow integration pending |
| Learn | `/learn` | Learn; contextual Explain this / Research & add to Learn | Visual lesson and Perplexity deep-research expansion accepted; implementation pending |
| War Room | `/war-room` | Reports & Briefings → Meeting Prep | Existing route preserved; combined workflow integration pending |
| Watchtower | `/watchtower` | Monitor → Alerts | Existing route preserved; combined workflow integration pending |
| Research Ops | `/research-ops` | Operations → Collection & sources | Existing route preserved; combined workflow integration pending |
| Settings | `/settings` | Help → Using Berry Intelligence | Existing route preserved; combined workflow integration pending |
| How it works | `/guide` | Help → Using Berry Intelligence | Existing route preserved; combined workflow integration pending |
| Morning Brief | `/brief` | Personal Digest → Briefings (News views) | Existing route preserved; combined workflow integration pending |
| Live Intelligence | `/work-queue` | Personal Digest → Briefings (News views) | Existing route preserved; combined workflow integration pending |
| Review Operations | `/review-ops` | Operations → Review | Existing route preserved; combined workflow integration pending |
| Reading Queue | `/queues/reading` | Personal Digest → Reading | Existing route preserved; combined workflow integration pending |
| Pending Review | `/pending` | Operations → Review | Existing route preserved; combined workflow integration pending |
| Signal Review | `/signals/review` | Operations → Review | Existing route preserved; combined workflow integration pending |
| Assessments | `/assessments` | Intelligence → Evidence & judgments | Existing route preserved; combined workflow integration pending |
| Strategic Questions | `/strategic-questions` | Intelligence → Research questions | Existing route preserved; combined workflow integration pending |
| Monitoring queue | `/queues/monitoring` | Monitor → Alerts | Existing route preserved; combined workflow integration pending |
| Alerts | `/queues/monitoring#alerts` | Monitor → Alerts | Existing route preserved; combined workflow integration pending |
| My Watches | `/watches` | Monitor → Watches | Existing route preserved; combined workflow integration pending |
| Source Health | `/sources` | Operations → Collection & sources | Existing route preserved; combined workflow integration pending |
| Companies | `/entities/company` | Entities → Companies | Interactive sample; existing route preserved |
| Variety coverage | `/varieties/coverage` | Varieties → Coverage | Existing route preserved; combined workflow integration pending |
| Variety identity review | `/varieties/candidates` | Operations → Data quality | Existing route preserved; combined workflow integration pending |
| Entity identity integrity | `/entities/identity` | Operations → Data quality | Existing route preserved; combined workflow integration pending |
| Map Explorer | `/explorer` | Map Explorer | Interactive sample; existing route preserved |
| Geographies | `/geographies` | Map Explorer → geographic context | Existing route preserved; combined workflow integration pending |
| Landscape | `/entities/berry` | Landscape → Coverage & concentration | Existing route preserved; combined workflow integration pending |
| Competitor Landscape | `/competitors` | Landscape → Overview | Existing route preserved; combined workflow integration pending |
| Executive Readout | `/readout` | Reports & Briefings → Briefs | Existing route preserved; combined workflow integration pending |
| Manager Brief Pack | `/brief-pack` | Reports & Briefings → Briefs | Existing route preserved; combined workflow integration pending |
| Saved Brief Packs | `/brief-packs` | Reports & Briefings → Briefs | Existing route preserved; combined workflow integration pending |
| AI-Assisted Reports | `/reports` | Reports & Briefings → Reports | Existing route preserved; combined workflow integration pending |
| Intake | `/intake` | Operations → Collection & sources | Existing route preserved; combined workflow integration pending |
| Publications | `/review?kind=publication` | Operations → Review | Existing route preserved; combined workflow integration pending |
| Claims | `/review?kind=atomic` | Operations → Review | Existing route preserved; combined workflow integration pending |
| Source fidelity | `/source-fidelity` | Operations → Review | Existing route preserved; combined workflow integration pending |
| Collection Operations | `/collection-ops` | Operations → Collection & sources | Existing route preserved; combined workflow integration pending |
| Coverage Assurance | `/coverage-assurance` | Operations → Collection & sources | Existing route preserved; combined workflow integration pending |
| Claim testing | `/queues/testing` | Operations → Review | Existing route preserved; combined workflow integration pending |
| Signal catalog | `/signals` | Intelligence → Evidence & judgments | Existing route preserved; combined workflow integration pending |
| Newsfeed | `/` | Personal Digest → Briefings (News views) | Existing route preserved; combined workflow integration pending |
| Commercial positions | `/queues/commercial_position` | Intelligence → Developments | Existing route preserved; combined workflow integration pending |
| Recommendations | `/recommendations` | Intelligence → Evidence & judgments | Existing route preserved; combined workflow integration pending |

Before migration sign-off: audit every routed page and detail/action endpoint, preserve bookmarks and permissions, check active section highlighting, empty/error states and keyboard navigation. Static/public builds must keep their existing route and private-data exclusions; this local studio menu is not a public-build navigation manifest. No consolidation or retirement is authorized by omission from a mockup.


## Additional entry points found in the section audit

These were absent from the original 50-entry inventory. They are mapped into the consolidated workspaces below; global Search and developer-only fixtures retain their separate roles.

| Existing section | Existing route | Recommended home to review | Status |
| --- | --- | --- | --- |
| Front Page | `/news` | Personal Digest → Briefings (News views) | Existing route preserved; combined workflow integration pending |
| Industry Pulse | `/industry-pulse` | Operations → Collection & sources | Existing route preserved; combined workflow integration pending |
| Ask Berry | `/research` | Intelligence → Research questions | Existing route preserved; combined workflow integration pending |
| Radar | `/radar` | Intelligence → Developments | Existing route preserved; combined workflow integration pending |
| Moves | `/moves` | Intelligence → Developments | Existing route preserved; combined workflow integration pending |
| Whitespace | `/whitespace` | Landscape → Coverage & concentration | Existing route preserved; combined workflow integration pending |
| Search | `/search` | Global search/results | Retain full results and overlay |
| Design System | `/design-system` | Developer-only | Component gallery; not product navigation |

Company/variety comparisons, company portfolio, geographic and entity details, Story Threads, publication-review migration views, report builders/exports and alternate views are also covered in `APP-SECTION-AUDIT.md`. Action/API endpoints are listed in `artifacts/design-sprint/route-audit-inventory.json` and are not counted as independent menu sections.

## October 2 delivery map — draft branch, not deployed

| Family | Delivered entry and mechanism | Remaining work |
| --- | --- | --- |
| News and Reader | `/today` is newest-first scoped News; shared right-side Article/Brief Reader and personal icons | Actual article-body/image coverage, final integration and retained alternate lenses |
| Personal Digest | `/digest` combines user saves, reading state and subscribed company lists | Account isolation and migration/integrated acceptance |
| Companies and Varieties | Shared marks, profiles, region annotations, directory/candidate review; People only inside Companies | Source-assisted enrichment, photo human decisions and specialist competition/coverage lenses |
| Landscape | `/landscapes` supports what/where/dates/sections and saved selector views | Broader source/maturity gaps, release and retained concentration lens |
| Learn | `/learn` is top-level; real detailed lesson/media slice and explicit cited private research lifecycle | Broader verified visuals, static consistency and account/multi-worker release |
| Monitor | `/monitor` has Watches, Alerts and Monitoring plans; shared marks/list/multi-berry scope | Deep interpretation layouts and event notification grouping; existing Following remains distinct |
| Operations | `/operations` organizes Collect, Review, Data quality, Coverage & health; three core tools share its shell | Deep specialist tools, real capture/retry/provider acceptance |
| Reports & Briefings | `/briefings` groups briefs, working reports, market snapshots and Meeting Prep | Provider/print/integrated release acceptance |
| Help/Intelligence | Existing `/guide`, Radar/Moves/Statements/Signals/Assessments/Questions/Research remain available | Mission 11 presentation and visual explainer work; original review semantics stay |

Shared More navigation exposes consolidated family homes. Its All existing tools disclosure preserves specialist access while parity is checked. These draft implementations do not authorize removing unreplaced routes or merging/deploying. See REDESIGN-REQUIREMENTS-CHECKLIST.md for exact-head verification and remaining requirements.
