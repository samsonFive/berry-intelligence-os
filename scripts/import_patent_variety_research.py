"""Install a hashed research packet as private variety pages, without publishing.

Idempotent immutable batches; no writes to data/, Facts, relationships, analyst
review state or existing profile edits. Run against the explicitly chosen inbox.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import sys
import unicodedata
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.analyst_state_io import atomic_json
from app.services.variety_research import ROOT, SAFE_CAPTURE

CONTACT_IDS = {
 "Fall Creek Farm & Nursery": "company-fall-creek-farm-and-nursery",
 "Oregon Blueberry": "company-oregon-blueberry",
 "Advanced Berry Breeding": "company-advanced-berry-breeding",
 "CIV": "company-civ-italy", "Flevo Berry": "company-flevo-berry",
 "ABZ Seeds": "company-abz-seeds", "TopFruit": "company-topfruit",
 "Florida Foundation Seed Producers (FFSP)": "company-florida-foundation-seed-producers",
 "University of California, Davis Plant Variety Licensing Program": "breeding_program-uc-davis-strawberry",
 "Hortifrut": "company-hortifrut", "Vissers Plant Innovators": "company-vissers-plant-innovators",
 "Plant Sciences Genetics": "company-plant-sciences-genetics", "Plant Sciences Europe": "company-plant-sciences-genetics",
 "California Berry Cultivars": "company-california-berry-cultivars",
 "California Berry Cultivars licensed nursery network": "company-california-berry-cultivars",
 "Cornell University Center for Technology Licensing": "breeding_program-cornell-berry",
}

def fold(text):
    return re.sub('[^A-Z0-9]', '', unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode().upper())

def slug(text):
    return re.sub('[^a-z0-9]+', '-', unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()).strip('-')[:110]

def digest_tree(root):
    h=sha256()
    for path in sorted(Path(root).rglob('*.json')):
        h.update(str(path.relative_to(root)).encode());h.update(path.read_bytes())
    return h.hexdigest()

def install(packet_path, *, data_dir, inbox_dir, source_sheet=None):
    packet_path=Path(packet_path).resolve();data_dir=Path(data_dir).resolve();inbox_dir=Path(inbox_dir).resolve()
    raw=packet_path.read_bytes();payload=json.loads(raw);digest=sha256(raw).hexdigest();batch_id='patents-apr-oct-2026-'+digest[:12]
    batch_dir=inbox_dir/ROOT/'imports'/batch_id;manifest_path=batch_dir/'manifest.json'
    if manifest_path.exists():
        prior=json.loads(manifest_path.read_text(encoding='utf-8'))
        if prior['packet_sha256']!=digest:raise ValueError('Existing import has a different source hash')
        return {'replayed': True, 'batch_id': batch_id, **prior['counts']}
    for group in payload['varieties']:
        links=[s['url'] for s in group['sources']]+[s['source'] for s in group['captures']]
        for party in group.get('commercial_contacts', []) + group.get('commercial_leads', []):
            links.extend(party.get('source_urls', []))
        links.extend(link for photo in group['variety_image_links'] for link in [photo['url'],photo['source']])
        for link in links:
            parsed=urlsplit(link)
            if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Research sources and image references require public HTTP(S) links')
    sheet_payload=None
    if source_sheet is not None:
        sheet_raw=Path(source_sheet).read_bytes();sheet=json.loads(sheet_raw)
        if len(sheet['headers'])!=14 or any(len(row)!=14 for row in sheet['rows']):
            raise ValueError('Original sheet must retain its fourteen columns')
        sheet_groups={}
        for group in payload['varieties']:
            sheet_groups[group['key']]=[]
            for number in group['rows']:
                if type(number) is not int or not 2<=number<=len(sheet['rows'])+1:
                    raise ValueError('Original sheet row is outside the source range')
                sheet_groups[group['key']].append({'row':number,'fields':dict(zip(sheet['headers'],sheet['rows'][number-2])),
                    'review_notes':[str(note[1])+': '+str(note[-1]) for note in sheet.get('review',[]) if note[0]==number]})
        sheet_payload={'source':'Rebuilt April–October 2026 photo spreadsheet','source_sha256':sha256(sheet_raw).hexdigest(),
            'review_state':'Unverified photo transcription; original review flags preserved','groups':sheet_groups}
    before=digest_tree(data_dir)
    entities={}
    for path in (data_dir/'entities').rglob('*.json'):
        entity=json.loads(path.read_text(encoding='utf-8'));entities[entity['id']]=entity
    groups=payload['varieties'];profile_groups=defaultdict(list);profile_entities={};unresolved=[];commercial_entities={};capture_files=set()
    # Registration-resolved blank names join the same literal code and berry,
    # but do not approve a different commercial-name alias.
    for g in groups:
        if not g['resolved_name']:
            unresolved.append({key:g[key] for key in ['key','berry','rows','applications','summary','sources','closeout','commercial_leads'] if key in g});continue
        crop=g['berry'];name=g['resolved_name'];known=[entities[x['id']] for x in g['existing_entities'] if x['id'] in entities]
        current_matches=[entity for entity in entities.values() if entity.get('entity_type')=='variety'
            and 'berry-'+crop.lower() in entity.get('berry_ids',[])
            and fold(name) in {fold(entity['name']),*(fold(a) for a in entity.get('aliases',[])),
                *(fold(entity.get('attributes',{}).get(field,'')) for field in ['denomination','breeder_code','selection_code'])}]
        known=list({entity['id']:entity for entity in [*known,*current_matches]}.values())
        if len(known)>1:raise ValueError('Ambiguous canonical mapping: '+g['key'])
        if known:
            entity=known[0]
            if entity.get('entity_type')!='variety':raise ValueError('Canonical mapping is not a variety: '+g['key'])
            if 'berry-'+crop.lower() not in entity.get('berry_ids',[]):raise ValueError('Crop mismatch: '+g['key'])
            entity_id=entity['id'];kind='existing'
        else:
            entity_id='variety-research-'+slug(crop)+'-'+fold(name).lower();kind='unverified'
            entity={'id':entity_id,'record_type':'entity','entity_type':'variety','name':name,'aliases':[],
                    'status':'unverified','description':'Unverified research profile imported from photographed patent/PBR records. Identity and source claims require review.',
                    'berry_ids':['berry-'+crop.lower()] if crop in {'Blueberry','Strawberry','Raspberry','Blackberry'} else [],
                    'roles':['cultivar_candidate'],'evidence_ids':[],'fact_ids':[],'relationship_ids':[],
                    'attributes':{'package_note':'Research identity pending. Source-reported aliases and company roles below do not change the reviewed catalog.'}}
            profile_entities[entity_id]=entity
        contacts=[]
        parties=g.get('commercial_contacts')
        if parties is None:
            parties=[{'name':x.strip()} for x in g['commercial_entities'].split(';') if x.strip()]
        for party in parties:
            label=party['name'].strip()
            if not label:raise ValueError('Commercial contacts need a name')
            contact_id=CONTACT_IDS.get(label)
            if contact_id not in entities:
                exact=[e for e in entities.values() if e['entity_type'] in {'company','brand','breeding_program'} and fold(label) in {fold(e['name']),*(fold(a) for a in e.get('aliases',[]))}]
                contact_id=exact[0]['id'] if len(exact)==1 else None
            if not contact_id:
                contact_id='company-research-'+slug(label)
                commercial_entities[contact_id]={'id':contact_id,'record_type':'entity','entity_type':'company','name':label,'aliases':[],
                    'status':'unverified','description':'Source-reported commercial contact. Legal identity and cultivar-specific role are unreviewed.',
                    'berry_ids':[],'roles':[],'evidence_ids':[],'fact_ids':[],'relationship_ids':[],'attributes':{}}
            target=entities.get(contact_id) or commercial_entities[contact_id]
            role=party.get('role') or g['role']
            if not party.get('role') and (label=='CIV' or label=='Flevo Berry'):role='Breeder / licensing contact'
            elif not party.get('role') and (label=='Salvi Vivai' or 'Trayplant' in label):role='Commercial nursery supplier'
            elif not party.get('role') and label=='California Berry Cultivars licensed nursery network':role='Licensor contact; actual supplying nursery unnamed'
            if not any((c['entity_id'],c['source_label'],c['role'],c.get('territory',''))==(contact_id,label,role,party.get('territory','')) for c in contacts):
                contacts.append({'entity_id':contact_id,'name':label,'source_label':label,'role':role,
                    'territory':party.get('territory',''),'source_urls':party.get('source_urls',[]),
                    'evidence_status':party.get('evidence_status','Source-supported; awaiting review'),
                    'relationship_note':party.get('relationship_note',''),
                    'href':f"/entities/{target['entity_type']}/{contact_id}",'review_state':'unreviewed'})
        keep=['key','name','resolved_name','berry','rows','applications','aliases','summary','availability','commercial_status','role',
              'patent_assignee_lead','baseline_status','new_information_assessment','issue','sources','variety_image_links']
        dossier={key:g[key] for key in keep};dossier['checked_on']=payload['metadata']['checked_on'];dossier['commercial_contacts']=contacts
        for key in ['closeout','commercial_leads','partnerships','row_holds']:
            if key in g:dossier[key]=g[key]
        dossier['review_state']='unreviewed';dossier['batch_id']=batch_id;dossier['captures']=[]
        dossier['baseline_references']=sorted({*[x['file'] for x in g['existing_entities']],*[x['baseline_file'] for x in g['prior_mentions']],*[x['file'] for x in g['prior_evidence']]})
        for cap in g['captures']:
            filename=Path(cap['path']).name
            if not SAFE_CAPTURE.fullmatch(filename):raise ValueError('Unsafe capture name')
            source=(packet_path.parent/cap['path']).resolve()
            if source.parent!=(packet_path.parent/'captures').resolve():raise ValueError('Capture escapes packet directory')
            if not source.is_file():raise ValueError('Missing capture '+filename)
            capture_files.add(filename)
            dest=batch_dir/'captures'/filename;dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists() and dest.read_bytes()!=source.read_bytes():raise ValueError('Capture collision')
            if not dest.exists():shutil.copyfile(source,dest)
            dossier['captures'].append({**cap,'href':f'/variety-research-captures/{batch_id}/{filename}'})
        profile_groups[entity_id].append(dossier)
    profiles=[]
    for entity_id,dossiers in profile_groups.items():
        target=entities.get(entity_id) or profile_entities[entity_id]
        profile={'entity_id':entity_id,'dossiers':dossiers,'review_state':'unreviewed'}
        atomic_json(batch_dir/'profiles'/(entity_id+'.json'),profile)
        names=sorted({a for d in dossiers for a in d['aliases']});cids=sorted({c['entity_id'] for d in dossiers for c in d['commercial_contacts']})
        profiles.append({'entity_id':entity_id,'name':target['name'],'berries':sorted({d['berry'] for d in dossiers}),
            'href':'/entities/variety/'+entity_id,'aliases':names,'profile_kind':'existing' if entity_id in entities else 'unverified',
            'private_entity':profile_entities.get(entity_id),'commercial_entity_ids':cids,
            'commercial_label':'; '.join(dict.fromkeys(c['name'] for d in dossiers for c in d['commercial_contacts'])),
            'has_issue':any(d['issue'] for d in dossiers),'baseline_statuses':sorted({d['baseline_status'] for d in dossiers}),
            'search_text':' '.join([target['name'],*names,*(str(d.get(k,'')) for d in dossiers for k in ['name','summary','applications','commercial_contacts'])])})
    after=digest_tree(data_dir)
    if before!=after:raise ValueError('Canonical data unexpectedly changed')
    counts={'input_groups':len(groups),'input_rows':sum(len(g['rows']) for g in groups),'named_profiles':len(profiles),
            'existing_profiles_updated':sum(p['profile_kind']=='existing' for p in profiles),
            'new_unverified_profiles':len(profile_entities),'unresolved_applications':len(unresolved),
            'new_private_commercial_entities':len(commercial_entities),'captures':len(capture_files)}
    manifest={'id':batch_id,'kind':'private_variety_research_import','version':1,'packet_sha256':digest,'checked_on':payload['metadata']['checked_on'],'imported_at':datetime.now(UTC).isoformat(),
        'baseline_commit':payload['metadata']['baseline_commit'],'method':payload['metadata']['method'],
        'review_state':'unreviewed','canonical_data_sha256_before':before,'canonical_data_sha256_after':after,
        'profiles':profiles,'unresolved':unresolved,'resolved_keys':[g['key'] for g in groups if g['resolved_name']],
        'commercial_entities':list(commercial_entities.values()),'capture_files':sorted(capture_files),'counts':counts}
    # Manifest is committed last: partial attempts do not become visible pages.
    if sheet_payload is not None:atomic_json(batch_dir/'source_sheet_rows.json',sheet_payload)
    atomic_json(manifest_path,manifest)
    return {'replayed':False,'batch_id':batch_id,**counts}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('packet',type=Path);p.add_argument('--data-dir',type=Path,required=True);p.add_argument('--inbox-dir',type=Path,required=True);p.add_argument('--source-sheet',type=Path)
    a=p.parse_args();print(json.dumps(install(a.packet,data_dir=a.data_dir,inbox_dir=a.inbox_dir,source_sheet=a.source_sheet),indent=2))

if __name__=='__main__':main()
