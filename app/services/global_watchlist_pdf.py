"""Paginated PDF of the exact protected Global Watchlist projection."""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

from app.services.global_watchlist import real_record, safe_url


def render(model):
    output = BytesIO()
    styles = getSampleStyleSheet()
    green, gray = colors.HexColor('#234e3c'), colors.HexColor('#647267')
    styles.add(ParagraphStyle(name='GWTitle', fontName='Helvetica-Bold', fontSize=30, leading=34, textColor=green, spaceAfter=14))
    styles.add(ParagraphStyle(name='GWHeading', parent=styles['Heading2'], textColor=green, spaceBefore=18, spaceAfter=10, keepWithNext=True))
    styles.add(ParagraphStyle(name='GWBody', fontName='Helvetica', fontSize=9, leading=13, textColor=colors.HexColor('#273d31'), spaceAfter=7, splitLongWords=True))
    styles.add(ParagraphStyle(name='GWMeta', parent=styles['GWBody'], fontSize=7.5, leading=10, textColor=gray))
    styles.add(ParagraphStyle(name='GWCell', parent=styles['GWBody'], fontSize=8, leading=11, spaceAfter=0))

    def clean(value):
        # Core fonts have no full Unicode coverage; use readable punctuation.
        return str(value if value is not None else 'Unknown').replace('\u2014', ' - ').replace('\u2013', '-').replace('\u2011', '-').replace('\u2019', "'").replace('\u201c', '"').replace('\u201d', '"')

    def p(value, style='GWBody'):
        return Paragraph(escape(clean(value)).replace('\n', '<br/>'), styles[style])

    def link(value, label):
        url = safe_url(value)
        return Paragraph('<link href="' + escape(url, {'"': '&quot;'}) + '" color="#234e3c">' + escape(clean(label)) + '</link>', styles['GWMeta']) if url else p(label, 'GWMeta')

    def table(headers, rows, widths):
        cells = [[p(x, 'GWCell') for x in headers]] + [[p(x, 'GWCell') for x in row] for row in rows]
        item = Table(cells, colWidths=widths, repeatRows=1, hAlign='LEFT')
        item.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eaf0e6')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8), ('TOPPADDING', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
            ('LINEBELOW', (0, 0), (-1, -1), .4, colors.HexColor('#dbe3d7')),
        ]))
        return item

    width = A4[0] - 90
    story = [p('BERRY OS / COMPETITIVE INTELLIGENCE', 'GWMeta'), Spacer(1, 12),
             p('Global Watchlist', 'GWTitle'), p('Competitive landscape and captured evidence', 'GWHeading'),
             p('Internal / Confidential - protected workspace export', 'GWMeta'),
             p('Exported ' + model['exported_at'] + '. This is the export time, not the freshness of every source.', 'GWMeta')]
    scope = [(key, value) for key, value in model['params'].items() if value]
    story += [p('Selected scope', 'GWHeading'), p('; '.join(f'{key}: {value}' for key, value in scope) or 'All berries and organizations')]
    if model.get('selected_group'):
        group = model['selected_group']
        story.append(p(f"Workspace group: {group['name']} | {len(group['member_ids'])} saved members. Filters do not change membership."))
    story += [p(model['data_note']), p('Coverage is not performance. Genetic potential and commercial adoption are separate. No combined numerical threat score is defined. Internal sensory data is unavailable; no illustrative sensory values are included.')]
    report = model['tier_report']
    story += [p('Classification provenance', 'GWHeading'),
              p(f"{report['source']} | snapshot {report['snapshot_date']} | {report['review_state']}"),
              p(report['caveat']), p(f"{report['source_row_count']} source rows; {len(report['assignments'])} unique berry assignments; {len(report['unmatched'])} unmatched; {len(report['conflicts'])} conflicts.", 'GWMeta'),
              p('Imported regions describe monitoring scope, not proof of market presence. A tier belongs to its selected berry, never a company-wide performance score.', 'GWMeta')]
    rows = model['focus'] or model['rows']
    story += [p(f'Organizations ({len(rows)})', 'GWHeading')]
    if rows:
        story.append(table(['Organization / roles', 'Tier / scope', 'Footprint / assessed confidence'], [[
            row['name'] + '\n' + ', '.join(row['roles']),
            row['tier'] + '\nImported scope: ' + (', '.join(row['monitoring_regions']) or 'Unassigned'),
            (', '.join(row['regions']) or 'Geographic evidence insufficient') + '\n' + row['confidence']
        ] for row in rows], [width * .36, width * .27, width * .37]))
    else:
        story.append(p('No organizations match the selected filters. Missing records do not imply no market activity.'))
    if model['focus']:
        for row in rows:
            story += [PageBreak(), p(row['name'], 'GWTitle'), p('Connected company evidence', 'GWHeading')]
            story += [p('Captured geographic mentions / presence: ' + (', '.join(g['name'] for g in row['geographies']) or 'Insufficient evidence')),
                      p('Source monitoring: ' + row['monitoring']['state'].replace('_', ' ') + '. ' + row['monitoring']['detail'], 'GWMeta'),
                      p('Canonical dossier: ' + row['profile_href'], 'GWMeta')]
            for assignment in row['tier_details']:
                story.append(p(f"Imported tier: {assignment['berry']} / {assignment['tier']} / {', '.join(assignment['regions']) or 'Region unspecified'} / effective {assignment.get('effective_date') or 'Unspecified'} / end {assignment.get('end_date') or 'Unspecified'} / source scope {assignment.get('scope') or 'Not further specified'}", 'GWMeta'))
            for relationship in row['relationships']:
                subject_name = model['entities'].get(relationship.get('subject_id'), {}).get('name', relationship.get('subject_id'))
                object_name = model['entities'].get(relationship.get('object_id'), {}).get('name', relationship.get('object_id'))
                story.append(p(f"{subject_name} | {relationship.get('predicate', 'Relationship')} | {object_name} | status {relationship.get('status', 'Unknown')} | confidence {relationship.get('confidence', 'Unknown')}"))
                story.append(p('Sources: ' + ', '.join(relationship.get('evidence_ids') or []) + '; date ' + str(relationship.get('effective_date') or relationship.get('start_date') or 'Unknown'), 'GWMeta'))
            if not row['relationships']:
                story.append(p('No sourced relationships captured.'))
            story.append(p('Genetic potential - evidence and limitations', 'GWHeading'))
            story.append(p('No genetic threat score is defined. Registry filings do not establish breeding performance or adoption.'))
            for record in row['genetic_evidence']:
                story.append(p((record.get('title') or record['id']) + ' | ' + record['id'], 'GWMeta'))
            if not row['genetic_evidence']:
                story.append(p('Insufficient captured genetic evidence.', 'GWMeta'))
            story.append(p('Commercial adoption - observed evidence', 'GWHeading'))
            story.append(p('Market mentions, licences and patent filings do not establish sales or acreage. Brand-only records do not establish a variety association.'))
            for record in row['adoption_evidence']:
                story.append(p((record.get('title') or record['id']) + ' | ' + record['id'], 'GWMeta'))
            if not row['adoption_evidence']:
                story.append(p('Insufficient structured adoption observations. No zero adoption or weak capability is inferred.', 'GWMeta'))
            story.append(p('Company assessments and signals', 'GWHeading'))
            for assessment in row['assessments']:
                story += [p(assessment.get('title') or assessment.get('summary') or assessment['id']),
                          p(f"{'AI PROPOSED' if assessment.get('ai_proposed') else 'REVIEWED'} | status {assessment.get('status', 'Unknown')}; confidence {assessment.get('confidence', 'Unknown')}; scope {assessment.get('market_ids') or 'Company-wide / undeclared'}", 'GWMeta'),
                          p('Sources: ' + ', '.join(assessment.get('evidence_ids') or []), 'GWMeta')]
            for signal in row['signals']:
                story += [p(signal.get('title') or signal['id']), p(f"Signal status {signal.get('status', 'Unknown')}; sources: {', '.join(signal.get('evidence_ids') or [])}", 'GWMeta')]
            if not row['assessments'] and not row['signals']:
                story.append(p('No company assessment or signal captured. No zero strength or threat is inferred.'))
        capabilities = model.get('capabilities') or {}
        story.append(p('Scoped capability assessments', 'GWHeading'))
        for assessment in capabilities.get('assessments', []):
            if not real_record(assessment):
                continue
            story += [p(f"{model['entities'].get(assessment['entity_id'], {}).get('name', assessment['entity_id'])} | {assessment['capability_label']} | {assessment['effective_label']}", 'GWHeading'),
                p(f"{assessment['status']} | confidence {assessment['confidence']} | assessed {assessment['assessed_at']}", 'GWMeta'),
                p('Scope: ' + '; '.join(f'{key}: {assessment.get(key, "Unknown")}' for key in ('berry_id','peer_role','destination_scope','origin_scope','program_or_variety','period_start','period_end','use_system','rubric_version')), 'GWMeta'),
                p(assessment.get('rationale') or 'No rationale recorded')]
            for source in assessment.get('sources', []):
                story.append(link(source['fields'].get('original_url'), source['fields'].get('original_url') or source['id']))
        if not capabilities.get('assessments'):
            story.append(p('Insufficient supported capability observations. Ratings are not inferred from coverage counts.'))
        story += [p('People, public activity and hiring history', 'GWHeading'),
                  p('Retained research observations; source inspection is separate from claim review. Captured jobs are not assumed active. No hiring or capability-growth inference is generated.')]
        for person in model.get('people', []):
            person_block = [p(f"{person['company']} | {person['name']} | {person['type']}", 'GWHeading'),
                      p(f"{person['role']} | {person['status']} | {person['location']}"),
                      p(f"{person['date_basis']}: {person['date']} | scope {person['scope']}", 'GWMeta'),
                      p(person['detail']), p(f"Mapping: {person['resolution']} | sources: {person['source_state']}", 'GWMeta')]
            for source in person.get('sources', []):
                person_block.append(link(source['fields'].get('original_url'), source['fields'].get('original_url') or source['id']))
            # Keep a record and its citations together when they fit a page.
            # ReportLab can still split an exceptionally long record.
            story.append(KeepTogether(person_block))
        if not model.get('people'):
            story.append(p('No structured people or job research retained for this selection.', 'GWMeta'))
    story += [PageBreak(), p('News & source register', 'GWTitle'),
              p('Sorted by publication date. Every source in a syndication family remains accessible. Reprints are not independent corroboration. No live connection is implied.')]
    for number, group in enumerate(model['news'], 1):
        lead = group['lead']
        heading = [p(f"{number:02d}. {lead.get('title') or lead['id']}", 'GWHeading'), p(group['independence'], 'GWMeta')]
        for source_index, source in enumerate(group['sources']):
            source_block = [p(f"{source.get('source_name') or 'Publisher unknown'} | {source.get('source_type') or 'Type unknown'} | {source['id']}", 'GWMeta'),
                p(f"Published: {source.get('published_date') or 'Unknown'} | Captured: {source.get('captured_at') or source.get('captured_date') or 'Unknown'}", 'GWMeta'),
                link(source.get('source_url'), source.get('source_url') or 'Original URL unavailable')]
            story.append(KeepTogether((heading if source_index == 0 else []) + source_block))
            if source.get('association_corrections'):
                story.append(p('Workspace association correction applied; canonical source preserved.', 'GWMeta'))
    if not model['news']:
        story.append(p('No captured sources match this scope.'))
    if model['notes']:
        story += [p('Protected workspace notes', 'GWHeading'), p('Analyst capture, unreviewed. These entries are not verified Facts.')]
        for note in model['notes']:
            story += [p(note['classification'] + ' / ' + note['review_state'], 'GWHeading'), p(note['text']),
                      p(f"{note['author']} | observed {note['observed_at']} | entered {note['created_at']} | visibility {note['visibility']}", 'GWMeta')]
            if note['reference']:
                story.append(link(note['reference'], note['reference']))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(green)
        canvas.line(45, A4[1] - 32, A4[0] - 45, A4[1] - 32)
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(gray)
        canvas.drawString(45, 25, 'Berry OS | Internal / Confidential | Captured evidence, not a market ranking')
        canvas.drawRightString(A4[0] - 45, 25, f'Page {doc.page}')
        canvas.restoreState()

    doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=45, rightMargin=45,
                            topMargin=50, bottomMargin=48, title='Global Watchlist - Competitive Landscape', author='Berry OS')
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
