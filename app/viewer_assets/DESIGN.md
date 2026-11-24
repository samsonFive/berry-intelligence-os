# Driscoll’s company intelligence viewer

The viewer uses a spreadsheet workspace rather than a marketing dashboard. Company and variety records are the primary surface: a frozen identity column, row numbers, visible cell boundaries, consistent field labels, restrained color, and a compact toolbar. The newsletter retains a reading layout; panel score records remain distinct rows.

## Brand references

The supplied logo is the public Driscoll’s mark linked by the [official website](https://www.driscolls.com/). It is embedded in standalone releases, not loaded remotely by employees. Source asset: `https://edge.sitecorecloud.io/driscollsin7a07-driscolls1bc6-prod99c8-40a3/media/Project/driscolls/shared/logo.png?h=236&iar=0&w=770`.

The website’s public stylesheet provided the green `#4a773c` and yellow-flat `oklch(89.15% .1773 96.78)` references. The app adds dark green navigation and neutral table surfaces. Typography uses locally available Segoe UI/Arial for business information; no remote fonts are loaded. This is a purpose-built internal interface using those references, not an assertion of compliance with a complete corporate brand manual.

## Directory interactions

- Alphabetical A–Z or Z–A sorting, header sorting, and an All/A–Z/# navigator. Accented Latin names sort into the appropriate letter group.
- Berry, role, and geography filters combine with search and alphabetical selection.
- Geography is a pair: a basis selector (Either, Headquarters, Documented activity) and a place selector. In the variety view, Headquarters is labeled Associated company HQ. That reference never becomes the variety’s activity or growing footprint.
- Frozen name and row-number columns; sticky headers; horizontal and vertical scrolling.
- Keyboard-accessible resizing, column visibility/reorder controls, and standard/compact rows. Layout preferences stay in the browser and do not enter exported research content.
- Every profile labels headquarters and activity separately. Missing geography remains Not recorded.

The optional `activity_geographies` field is explicit input. A company’s location or a variety’s company association does not fill it automatically. The platform exporter uses recorded operating geography and the existing variety observation index, preserving that distinction.

## Packaging

`styles.css` supplies the shared page behavior and `sheet.css` supplies this presentation. Both stylesheets and the logo are embedded in standalone output. Data and script hashes are rebuilt for each generated page. There are no API connections, remote fonts, analytics, or external display assets.
