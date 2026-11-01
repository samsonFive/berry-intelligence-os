# Reviewed statement destinations

Existing variety dossiers, timelines and commercial positions link to
`/facts/{id}`, but the application had no destination. The fresh section audit
reproduced a 404 for the existing Agrovision scale claim. This repairs that
outstanding navigation item rather than adding a new statement workflow.

The read-only page leads with the exact statement and its claim/fact and
active/disputed labels. It separates event, source publication and recorded
dates, links every eligible supporting source to the shared Reader and original
publisher, and folds secondary record metadata. Existing entity links return
to their canonical profiles. It uses the agricultural Glasshouse Library shell,
with wrapping source cards on phones. Publication review does not turn a claim
into a fact or make two publications independent corroboration.

The route reads the existing eligible Fact population and only its selected
source references. Missing, unpublished, unvalidated and excluded sources do
not disclose titles, URLs or bodies. Existing active statements remain readable
when a reference is unavailable, with an explicit notice. Superseded/withdrawn
records are history only in authoring mode; readonly/static excludes them.
Remote login protection is unchanged. There are no edit/trust actions, domain
schema changes, new canonical records or inbox reads for draft extraction.

Static output creates the same public destination with relocatable links to
published source pages. It excludes private reviewers, draft text and history.
The focused regressions cover literal escaping, malicious URLs, selected-source
reads, source visibility, all citations, history, authentication and static links.
Native desktop/412px review verifies both cited source Reader handoffs, return
to origin, publisher routes and collapsed secondary metadata without overflow.
All 72 affected tests pass with one existing ReportLab warning. The full private
static build creates 1,983 pages, including 186 existing statement destinations;
all 820 statement links from queue, geography and entity pages resolve. Native
412px review measures 397px client/scroll width, both source cards and their
Reader/publisher routes, with record details closed initially. No real account
was used. Current-head CI and final preservation remain required before release.

This repair does not add article bodies where none are available, change source
independence, confirm catalog identities, settle current rights or approve photo
reuse. It does not close broader performance or worldwide catalog completeness.
