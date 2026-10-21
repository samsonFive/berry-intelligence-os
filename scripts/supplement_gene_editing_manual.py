"""Materialize four original-source checks from the user's manual research.

Offline, add-only publication intake; no API calls or publication decisions.
Existing program changes require an exact match to the prior import payload.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.analyst_state_io import atomic_json
from app.services.gene_editing import classify
from app.services.gene_editing_import import import_snapshot
from prepare_gene_editing_seed import IDS

BASE = ROOT / 'data/imports/gene-editing-2026-10-20'
CHECKS = [
    ('qi-rsr-response', 'USDA APHIS', 'https://www.aphis.usda.gov/sites/default/files/24-116-02rsr-response.pdf', '2024-05-29', 'qi-biodesign',
     'APHIS regulatory status review 24-116-02rsr: Qi high-oleic soybean',
     'APHIS determined that the specified high-oleic soybean with loss of seed-specific FAD2 function is not subject to 7 CFR part 340. This is a plant-pest regulatory determination, not an FDA decision, berry authorization or proof of sales.',
     'Accordingly, your soybean is not subject to the regulations under 7 CFR part 340.'),
    ('psi-restructure', 'Plant Sciences, Inc. / Newswire', 'https://www.newswire.com/news/plant-sciences-inc-unveils-restructuring-broadening-north-american-22096147', '2023-08-01', 'plant-sciences',
     'PSI announces PSG restructuring and contracted services',
     'The issuer announced PSG would hold berry breeding populations and related IP, while PSI would supply research and propagation under contract. Fifteen populations were described: eight strawberry, three blueberry, two raspberry, one blackberry and one black raspberry. Executed assignments, capitalization and Simplot agreement novation remain unresolved.',
     'PSI will serve PSG, under contract, providing research and propagation services to the new entity.'),
    ('ohalo-florida', 'Ohalo', 'https://www.ohalo.com/news/ohalo-x-university-of-florida-disease-resistant-strawberry-neopestalotiopsis', '2024-12-20', 'ohalo',
     'Ohalo and Florida partners announce Neopestalotiopsis strawberry agreement',
     'Ohalo announced a development and commercialization agreement with UF/IFAS, Florida Foundation Seed Producers and FSGA. It reports integrating a resistance trait into existing Florida strawberry varieties using proprietary advanced breeding. Non-commercial experimental trials were forecast for 2025; their completion, named releases and sales are not established.',
     'These new, resistant varieties will enter non-commercial, experimental trials in 2025.'),
    ('qi-confitop', 'Confitop Capital / 百联挚高资本', 'https://www.confitopcapital.cn/82.html', None, 'qi-biodesign',
     'Qi investor describes Nanjing small-berry editing initiative',
     'The investor describes a small-berry gene-editing innovation center and industrialization initiative in Nanjing, linked to the Lishui blueberry industry and Joyvio-related growing, sales and processing. It dates an A+ investment exceeding RMB 100 million to May 2026 in its body text; the page publication date is unknown. No named edited-blueberry cultivar, completed trial or sale is established.',
     '小浆果基因编辑创新中心'),
]


def main():
    path = BASE / 'snapshot.json'
    snapshot = json.loads(path.read_text(encoding='utf-8'))
    originals = {p['id']: copy.deepcopy(p) for p in snapshot['programs']}
    companies = IDS
    evidence_ids = {r['id'] for r in snapshot['evidence']}
    checked = []
    for key, publisher, url, date, slug, title, summary, excerpt in CHECKS:
        eid = 'ev-gene-' + key
        checked.append({'key': key, 'url': url, 'publisher': publisher,
                        'access_date': '2026-10-21', 'status': 'opened_primary',
                        'method': 'web tool substantive original text recovered; excerpt retained',
                        'supporting_excerpt': excerpt, 'published_date': date})
        if eid in evidence_ids:
            continue
        row = copy.deepcopy(snapshot['evidence'][0])
        row.update(id=eid, title=title, original_title=title, source_name=publisher,
                   source_url=url, published_date=date, captured_date='2026-10-21',
                   summary=summary, supporting_excerpt=excerpt, original_text_excerpt=excerpt,
                   source_language='zh' if key == 'qi-confitop' else 'en',
                   source_type='research_program_publication' if key == 'qi-rsr-response' else 'company_press_release',
                   entity_ids=[companies[slug]], geography_ids=[],
                   berry_ids=['berry-strawberry'] if key == 'ohalo-florida' else [],
                   attribution=publisher + ' original text checked; publication review remains pending',
                   submitted_by='user-manual-research/2026-10-21',
                   source_fidelity={'method': checked[-1]['method'], 'status': 'original_text_checked',
                                    'sha256': hashlib.sha256(excerpt.encode()).hexdigest(),
                                    'hash_scope': 'retained excerpt, not full source document'},
                   article={'status': 'excerpt_only', 'full_text': excerpt},
                   tags=['gene-editing-research', 'manual-research-supplement'])
        row['classification'] = classify(row)
        row['tags'] += row['classification']['topics']
        snapshot['evidence'].append(row)
        source = copy.deepcopy(snapshot['sources'][0])
        source.update(id='source-gene-' + key, label=publisher + ' · ' + key,
                      value=url, url=url, canonical_url=url, publisher=publisher,
                      language=row['source_language'], linked_competitor_ids=[companies[slug]],
                      last_checked_at='2026-10-21', last_successful_check='2026-10-21',
                      last_status='readable', status='readable')
        snapshot['sources'].append(source)
        profile = next(c for c in snapshot['companies'] if c['entity_id'] == companies[slug])
        if eid not in profile['evidence_ids']:
            profile['evidence_ids'].append(eid)
        if key == 'psi-restructure':
            profile['identity_notes'] += ' Opened August 1, 2023 issuer release distinguishes PSG portfolio/IP holding from PSI contracted research and propagation; executed assignments and ownership percentages remain unverified.'

    def add_program(key, name, slug, technology, crop, trait, partners, geography, stage, date, milestone, sources, gaps, berries):
        pid = 'program-gene-' + key
        if pid in originals:
            return
        program = dict(id=pid, name=name, company_ids=[companies[slug]], technology=technology,
                       crop=crop, trait=trait, partner=partners, geography=geography,
                       role='advanced breeding platform' if slug == 'ohalo' else 'editing platform',
                       stage=stage, milestone_date=date, milestone=milestone,
                       evidence_ids=['ev-gene-' + s for s in sources], berry_ids=berries,
                       verification='single_source / awaiting analyst review', last_reviewed=None, gaps=gaps)
        snapshot['programs'].append(program)
        snapshot['program_entities'].append(dict(id=pid, record_type='entity', entity_type='breeding_program',
                                                name=name, status='unverified',
                                                description='Research identity; source claims await analyst review.',
                                                berry_ids=berries, evidence_ids=program['evidence_ids'],
                                                attributes={'gene_editing': program}))

    add_program('ohalo-florida', 'Florida Neopestalotiopsis-resistant strawberry', 'ohalo',
                'Proprietary advanced breeding; exact editor unspecified', 'Strawberry', 'Neopestalotiopsis resistance',
                'UF/IFAS; Florida Foundation Seed Producers; Florida Strawberry Growers Association', 'Florida, United States',
                'Agreement announced / experimental trials forecast', '2024-12-20',
                'Company reports trait integration; forecast non-commercial experimental trials in 2025.', ['ohalo-florida'],
                'Trial completion, named cultivar, sales and CRISPR mechanism not established. Separate from the true-seed consortium.', ['berry-strawberry'])
    add_program('qi-small-berry', 'Nanjing small-berry editing innovation center initiative', 'qi-biodesign',
                'Gene editing; crop-specific editor unspecified', 'Small berries / blueberry industry context',
                'Targets unspecified', 'Nanjing agricultural high-tech zone; Joyvio-related industry participants', 'Nanjing / Lishui, China',
                'Initiative described by investor', None, 'Investor describes small-berry editing center and industry-chain initiative.', ['qi-confitop'],
                'Not a named edited-blueberry product; facility completion, operating entity, trials and sales unverified.', ['berry-blueberry'])

    soybean = next(p for p in snapshot['programs'] if p['id'] == 'program-gene-qi-soybean')
    if 'ev-gene-qi-rsr-response' not in soybean['evidence_ids']:
        soybean['evidence_ids'].append('ev-gene-qi-rsr-response')
        soybean.update(stage='APHIS regulatory status determination', milestone_date='2024-05-29',
                       milestone='APHIS response 24-116-02rsr determines the specified soybean is not subject to 7 CFR part 340.',
                       gaps='US plant-pest scope only; FDA status, Chinese original certificate and commercial sales not established.')
    for entity in snapshot['program_entities']:
        if entity['id'] == soybean['id']:
            entity['attributes']['gene_editing'] = copy.deepcopy(soybean)
            entity['evidence_ids'] = list(soybean['evidence_ids'])
    # Never overwrite analyst modifications to an existing native program.
    native = ROOT / 'data/entities/breeding_programs' / (soybean['id'] + '.json')
    if native.exists():
        record = json.loads(native.read_text(encoding='utf-8'))
        if record.get('attributes', {}).get('gene_editing') == originals[soybean['id']]:
            record['attributes']['gene_editing'] = copy.deepcopy(soybean)
            record['evidence_ids'] = list(soybean['evidence_ids'])
            atomic_json(native, record)
    snapshot['conflicts'] += [
        note for note in [
            'Manual research supplement: Qi APHIS response dated May 29, 2024 was opened, distinct from the applicant request. Earlier missing-decision notes are superseded for this specific soybean.',
            'PSI restructuring issuer release was opened: PSG portfolio/IP holding and PSI contracted services are separate roles. No automatic legal entity merge, executed assignment or Simplot agreement novation inferred.',
            'Confitop investor text supports a small-berry editing initiative, not a released edited-blueberry variety. Earlier unreadable-facility-source gap is partly closed by this separate original investor account.'
        ] if note not in snapshot['conflicts']]
    atomic_json(BASE / 'manual-primary-checks.json', checked)
    snapshot['research_status'] = 'User-supplied manual Perplexity report covers all 11 companies; four new originals checked. Paid API research remains quota-blocked; unresolved primary-record, trial and commercialization gaps remain explicit.'
    for profile in snapshot['companies']:
        profile['manual_research_received'] = '2026-10-21'
    coverage_path = BASE / 'coverage.json'
    coverage = json.loads(coverage_path.read_text(encoding='utf-8'))
    coverage.update(manual_research_received='2026-10-21', manual_research_company_count=11,
                    manual_primary_checks=len(checked), imported_unique_programs=len(snapshot['programs']),
                    versioned_evidence=len(snapshot['evidence']), original_source_candidates=46)
    coverage['source_checks']['readable'] = 37
    for row in coverage['companies']:
        row['manual_research_received'] = '2026-10-21'
        row['programs'] = sum(row['company'] in p['company_ids'] for p in snapshot['programs'])
        row['evidence'] = sum(row['company'] in e['entity_ids'] for e in snapshot['evidence'])
    coverage_path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    snapshot['version'] = 'gene-editing-2026-10-21-manual-supplement-v2'
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(import_snapshot(snapshot, ROOT / 'data', ROOT / 'inbox'), indent=2))


if __name__ == '__main__':
    main()
