"""Prepare a source-only human worksheet; assemble supplied answers offline.

No detector runs during preparation. Bodies stay in the existing private capture
store. This creates neither source decisions nor an approved benchmark marker.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.variety_universe.identity import fold_identity

VERSION = 'variety-name-human-review-v1'
SCOPE = 'Human-supplied literal names/crops/codes from explicit private Article copies. Source acceptance, catalog identity, statement review and extraction qualification remain separate.'
BERRIES = {'berry-blueberry', 'berry-strawberry', 'berry-raspberry', 'berry-blackberry'}
SAFE_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,180}$')


def public_url(value):
    parts = urlsplit(value)
    if parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username or parts.password:
        raise ValueError('Source and review links need HTTP(S) URLs without credentials')
    return value


def private_output(path, *, root=ROOT):
    target = path.resolve()
    if not target.is_relative_to((root / 'inbox').resolve()):
        raise ValueError('Write this private packet under inbox/, never data, benchmarks or public output')
    return target


def capture_digest(artifact):
    payload = artifact.get('artifact')
    if not isinstance(payload, dict) or not isinstance(payload.get('article'), dict):
        raise ValueError('This worksheet supports explicit captured Article inputs only')
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def write_new(target, value, *, folder):
    if target.is_symlink() or not target.resolve().is_relative_to(folder.resolve()):
        raise ValueError('Packet files must stay inside their private output folder')
    # Exclusive creation also rejects an existing or dangling file symlink.
    with target.open('x',encoding='utf-8') as stream:
        stream.write(value)


def original_record(data_dir, identifier):
    if not SAFE_ID.fullmatch(identifier):
        raise ValueError('Invalid source record ID')
    paths = list((data_dir / 'evidence').rglob(identifier + '.json'))
    if len(paths) != 1:
        raise ValueError('Source needs exactly one existing publication record')
    record = json.loads(paths[0].read_text(encoding='utf-8'))
    if record.get('id') != identifier or record.get('status') != 'published':
        raise ValueError('Source record identity or publication state changed')
    return record


def prepare(*, runtime_inbox, data_dir, review_base_url):
    public_url(review_base_url)
    base = urlsplit(review_base_url)
    if base.query or base.fragment:
        raise ValueError('Review base URL cannot contain a query or fragment')
    cases = []
    for path in sorted((runtime_inbox / 'source_fidelity/artifacts').glob('*.json')):
        artifact = json.loads(path.read_text(encoding='utf-8'))
        identifier = artifact['evidence_id']
        if path.stem != identifier:
            raise ValueError('Capture filename and source identity disagree')
        original = original_record(data_dir, identifier)
        if artifact.get('artifact_type') != 'article':
            raise ValueError('Non-Article capture needs a separately scoped worksheet')
        cases.append(dict(id=identifier, title=artifact.get('source_title') or original['title'],
            source_url=public_url(artifact['source_url']),
            saved_copy_url=review_base_url.rstrip('/')+'/source-fidelity/'+identifier+'?name_review=1',
            source_copy_review=(artifact.get('review') or {}).get('status', 'pending'),
            capture_sha256=capture_digest(artifact), body_sha256=artifact.get('body_sha256'),
            published_date=artifact.get('published_date'), language=artifact.get('language') or 'undetermined',
            paragraph_count=len(artifact['artifact']['article'].get('paragraphs') or []),
            expected=None, expected_review_complete=False))
    if not cases:
        raise ValueError('No explicit source copies found; do not create an empty successful worksheet')
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Duplicate source identities')
    fingerprint = hashlib.sha256(json.dumps(cases, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
    return dict(schema_version=VERSION, packet_id='name-review-'+fingerprint[:20], reviewer='',
        scope=SCOPE,
        reviewed=False, cases=cases)


def assemble(*, review, runtime_inbox, data_dir):
    if review.get('schema_version') != VERSION or not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip() or len(review['reviewer']) > 100:
        raise ValueError('Worksheet version and named human reviewer are required')
    cases = review.get('cases')
    if not isinstance(cases, list) or not cases:
        raise ValueError('The worksheet needs its complete source list')
    if any(not isinstance(c,dict) or not isinstance(c.get('id'),str) or not SAFE_ID.fullmatch(c['id']) for c in cases):
        raise ValueError('Each source needs its original safe record ID')
    ids = [c.get('id') for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate source identities')
    actual = sorted(p.stem for p in (runtime_inbox / 'source_fidelity/artifacts').glob('*.json'))
    if sorted(ids) != actual:
        raise ValueError('Source list changed or was shortened; prepare and review the full packet again')
    assembled = []
    for case in cases:
        identifier = case['id']
        original = original_record(data_dir, identifier)
        artifact = json.loads((runtime_inbox/'source_fidelity/artifacts'/f'{identifier}.json').read_text(encoding='utf-8'))
        if artifact.get('evidence_id') != identifier or capture_digest(artifact) != case.get('capture_sha256'):
            raise ValueError('Source copy changed; expected names must be checked against the new copy')
        if artifact.get('source_url') != case.get('source_url'):
            raise ValueError('Source URL changed')
        if artifact.get('artifact_type') != 'article' or (artifact.get('source_title') or original['title']) != case.get('title') or (artifact.get('language') or 'undetermined') != case.get('language'):
            raise ValueError('Source type, captured title or language changed')
        expected = case.get('expected')
        if case.get('expected_review_complete') is not True or not isinstance(expected, list):
            raise ValueError('Every source needs an explicit completed name list, including an intentional empty list')
        seen = set()
        for row in expected:
            if not isinstance(row, dict) or not isinstance(row.get('name'), str) or not row['name'].strip() or row.get('berry_id') not in BERRIES:
                raise ValueError('Expected names need literal spelling and one of the four berry IDs')
            if len(row['name']) > 200 or ('breeder_code' in row and (not isinstance(row['breeder_code'], str) or len(row['breeder_code']) > 100)):
                raise ValueError('Use short literal names and codes')
            key = fold_identity(row['name'])
            if key in seen:
                raise ValueError('Duplicate expected names; separately scope ambiguous crop identities')
            seen.add(key)
            if any(k not in {'name', 'berry_id', 'breeder_code'} for k in row):
                raise ValueError('Expected names must not carry approval or detector-output fields')
        # Explicit offline opt-in only. Never replace or hydrate real app records.
        source_record = {k:deepcopy(original[k]) for k in ('id','record_type','source_type','source_id','source_name') if k in original}
        source_record.update(deepcopy(artifact['artifact']))
        source_record.update(status='in_review',title=artifact.get('source_title') or '',
            source_url=artifact['source_url'],published_date=artifact.get('published_date'))
        assembled.append(dict(id=identifier, format='captured_article', language=case['language'],
            fixture_kind='human_supplied_source_copy_names', reference_urls=[case['source_url']],
            inputs=dict(varieties=[], entities=[], evidence=[], facts=[], candidates=[], source_text_records=[source_record]),
            expected=deepcopy(expected), human_review=dict(reviewer=review['reviewer'],
                capture_sha256=case['capture_sha256'], source_copy_review=(artifact.get('review') or {}).get('status','pending'))))
    return dict(schema_version='variety-name-recall-v1', scope=SCOPE,
        review_status='human_expected_lists_supplied; source acceptance and independent benchmark qualification remain separate',
        qualification_approved=False, cases=assembled)


def render_worksheet(packet):
    template = (ROOT/'scripts/templates/variety_recall_review.html').read_text(encoding='utf-8')
    encoded = json.dumps(packet, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    return template.replace('__PACKET_JSON__', encoded)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-inbox', required=True, type=Path)
    parser.add_argument('--data-dir', default=ROOT/'data', type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--review-base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--review-file', type=Path, help='Assemble manually entered answers; preparation never runs detection')
    args=parser.parse_args()
    output=private_output(args.output_dir)
    if output.is_relative_to(args.runtime_inbox.resolve()):
        raise ValueError('Keep packet outputs outside the active source/review runtime')
    output.mkdir(parents=True,exist_ok=True)
    if args.review_file:
        result=assemble(review=json.loads(args.review_file.read_text(encoding='utf-8')),
            runtime_inbox=args.runtime_inbox,data_dir=args.data_dir)
        target=output/'human-expected-recall-input.json'
        if target.resolve()==args.review_file.resolve():
            raise ValueError('Do not replace the supplied human answers')
        if target.exists():
            raise ValueError('Use a fresh output folder; existing assembled inputs are preserved')
        write_new(target,json.dumps(result,ensure_ascii=False,indent=2)+'\n',folder=output)
        print(json.dumps(dict(cases=len(result['cases']),qualified=False,source_decisions_created=0)))
    else:
        packet=prepare(runtime_inbox=args.runtime_inbox,data_dir=args.data_dir,review_base_url=args.review_base_url)
        if any((output/name).exists() for name in ('worksheet.json','index.html')):
            raise ValueError('Use a fresh packet folder; existing human worksheet files are preserved')
        for name,value in [('worksheet.json',json.dumps(packet,ensure_ascii=False,indent=2)+'\n'),('index.html',render_worksheet(packet))]:
            target=output/name
            if target.exists():
                raise ValueError('Use a fresh packet folder; existing human worksheet files are preserved')
            write_new(target,value,folder=output)
        print(json.dumps(dict(source_copies=len(packet['cases']),expected_names_supplied=False,detector_run=False)))


if __name__=='__main__':
    main()
