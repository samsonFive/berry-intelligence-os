"""Named reference choices for existing authoring forms, never a trust layer."""
from typing import Any


def reference_catalog(*, evidence, facts, signals, assessments, entities, questions) -> dict[str, list[dict[str, Any]]]:
    def choices(rows, kind):
        result = []
        for row in rows:
            if not row.get('id'):
                continue
            label = row.get('title') or row.get('name') or row.get('statement') or 'Untitled record'
            detail = row.get('classification') or row.get('entity_type') or kind
            if kind == 'Source':
                detail = ' · '.join(str(value) for value in (row.get('source_name'), row.get('published_date')) if value) or 'Published source'
            result.append({'id': row['id'], 'label': label, 'detail': str(detail).replace('_', ' ').title() if kind != 'Source' else detail})
        return sorted(result, key=lambda item: (item['label'].casefold(), item['id']))

    source_choices = choices(evidence, 'Source')
    fact_choices = choices(facts, 'Statement')
    return {
        'evidence_ids': source_choices,
        'fact_ids': fact_choices,
        'signal_ids': choices(signals, 'Signal'),
        'assessment_ids': choices(assessments, 'Assessment'),
        'entity_ids': choices(entities, 'Subject'),
        'strategic_question_ids': choices(questions, 'Question'),
        'counterevidence_ids': sorted(source_choices + fact_choices, key=lambda item: (item['label'].casefold(), item['id'])),
    }
