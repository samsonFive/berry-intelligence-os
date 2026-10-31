"""Apply explicit source-grounded anchor checks without changing claim trust."""
import argparse
import json
from pathlib import Path

from app.services import competitive_evaluation as ce
from app.services.living_workspaces import Store


def apply(inbox, selections, entities):
    store = Store(inbox)
    rows = store.rows('competitive_record')
    index = {(r['batch_id'], r['local_id']): r for r in rows}
    caps = {c['capability_id']: c for c in ce.catalogue()['capabilities']}
    result = []
    for selection in selections:
        observation = index[(selection['batch_id'], selection['observation_id'])]
        f = observation['fields']
        scope = {k: f.get(k) or 'Unknown' for k in ce.SCOPE}
        scope.update(berry_id=f['berry_scope'], use_system=f.get('production_system_fresh_processing') or 'Unknown',
                     rubric_version=ce.catalogue()['rubric_version'])
        checks = {}
        for check in selection['anchor_checks']:
            anchor = next(a for a in caps[f['capability_id']]['anchors'] if a['level'] == check['level'])
            checks[str(check['level'])] = {'requirement': anchor['requires'],
                'all_conditions_supported': check['supported'], 'explanation': check['explanation'],
                'source_ids': [index[(selection['batch_id'], sid)]['id'] for sid in check['source_ids']]}
        result.append(ce.apply_anchor(inbox, scope=scope, observation_ids=[observation['id']], checks=checks,
            confidence=selection['confidence'], confidence_details=selection['confidence_details'],
            rationale=selection['rationale'], entities=entities))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('selection_file', type=Path)
    parser.add_argument('--inbox', type=Path, default=ce.ROOT / 'inbox')
    args = parser.parse_args()
    entities = {r['id']: r for p in (ce.ROOT / 'data/entities').rglob('*.json')
                for r in [json.loads(p.read_text(encoding='utf-8'))]}
    result = apply(args.inbox, json.loads(args.selection_file.read_text(encoding='utf-8')), entities)
    print(json.dumps([{'id': r['id'], 'entity_id': r['entity_id'], 'capability_id': r['capability_id'],
                       'rating': r['rating'], 'status': r['status']} for r in result], indent=2))
