# Landscape and Workspace cohesion — local review

Landscape follows the established authored Workspace: compact overview, Grid/Cards
controls, full cell gridlines, green table headers, account layout controls and
the existing visual News cards and Reader. Shared presentation rules now live in
`app/static/workspace_foundations.css`, loaded by both interfaces.

The compact Landscape overview keeps its first complete finding and citations
visible; Expand overview reveals the remaining findings. Restored/saved layout
feedback appears only when that state actually exists. The default layout does
not add instructional status prose. Developments visibility survives navigation
and reload within the tab, separately from investigation selectors and evidence.

Authored Workspaces put the validated return link inside their quick navigation.
The original breadcrumb remains available without JavaScript. Sidebar, navigation
and document offsets use the same geometry in both views. Workspaces remains the
authored research destination; Save / export remains a separate investigation tool.

Local validation: TypeScript checking, production client build, 173 frontend tests,
29 focused Workspace/navigation tests and independent source review passed. Browser
checks exercise ten distinct canonical watched companies, Grid/Cards, cited overview
expansion, retained News/shared Reader and the exact Landscape → Workspace → Landscape
return. Desktop and narrow News layouts are inspected in the local review artifacts.

The preview uses copied canonical data and an isolated research page containing
catalog summaries labeled as analyst notes. It does not represent current production
news, publication approval or new collection. No provider call, production sign-in,
deployment or production data change is part of this UI review.
