"""Guarded research-metadata reconciliation; never changes publication trust.

Dry-run by default. Production must first have a verified runtime backup.
Native program analyst edits win over both dated snapshots.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.services.analyst_state_io import atomic_json
from app.services.pipeline_lock import pipeline_lock
from app.services.gene_editing_import import canonical_url


def replace_source_rows(raw,replacements):
    """Keep unrelated hand-formatted registry rows byte-for-byte unchanged."""
    decoder=json.JSONDecoder();index=raw.index('[')+1;edits=[]
    while index<len(raw):
        while index<len(raw) and raw[index] in ' \t\r\n,':index+=1
        if raw[index]==']':break
        row,end=decoder.raw_decode(raw,index)
        if row['id'] in replacements:
            value=json.dumps(replacements[row['id']],ensure_ascii=False,indent=2).replace('\n','\n  ')
            edits.append((index,end,value))
        index=end
    for start,end,value in reversed(edits):raw=raw[:start]+value+raw[end:]
    return raw


def reconcile(data_dir,inbox_dir,*,apply=False,verified_backup=None):
    data_dir,inbox_dir=Path(data_dir),Path(inbox_dir)
    if apply and os.environ.get('BIOS_REMOTE_INTERACTIVE','').lower() in {'true','1'}:
        if verified_backup is None:raise ValueError('Production reconciliation requires --verified-backup')
        from app.services.runtime_backup import verify_backup
        verify_backup(Path(verified_backup))
    old=json.loads((data_dir/'imports/gene-editing-2026-10-20/snapshot.json').read_text(encoding='utf-8'))
    new=json.loads((data_dir/'imports/gene-editing-2026-10-28/snapshot.json').read_text(encoding='utf-8'))
    prior={p['id']:p for p in old['programs']}
    changes=[];preserved=[]
    with pipeline_lock(inbox_dir,'gene-editing-closeout-reconciliation'):
        for p in new['programs']:
            if p['id'] not in prior:continue
            path=data_dir/'entities/breeding_programs'/(p['id']+'.json')
            if not path.exists():continue
            record=json.loads(path.read_text(encoding='utf-8'))
            current=record.get('attributes',{}).get('gene_editing')
            if current==p:continue
            if current!=prior[p['id']] or record.get('status')!='unverified' or record.get('name')!=prior[p['id']]['name']:
                preserved.append(p['id']);continue
            changes.append(p['id'])
            if apply:
                record['attributes']['gene_editing']=p
                record['evidence_ids']=p['evidence_ids']
                atomic_json(path,record)
        identities={
          'company-plant-sciences-genetics':{'scope':'Historical PSI / current PSG monitoring lineage; not one merged legal person','legal_counterparties':['Plant Sciences, Inc.','Plant Sciences Genetics, Inc.'],'sources':['https://www.newswire.com/news/plant-sciences-inc-unveils-restructuring-broadening-north-american-22096147','https://www.plantsciencesgenetics.com/about-us','https://www.plantsciencesgenetics.com/research'],'unasserted':['ownership percentages','control','executed agreement novation'],'brand_history':'PSG describes 2024 consolidation; issuer announcement was August 2023','simplot_investment':'reported by PSG; not a parent/control determination'},
          'company-qi-biodesign':{'scope':'Qi brand monitoring; legal counterparties kept distinct','legal_counterparties':['Beijing Qi Biodesign Biotechnology Co., Ltd.','苏州齐禾生科生物科技有限公司'],'sources':['https://api.vilmorincie.com/uploads/202607_Press_release_VCO_NGT_EN_229637ccd2.pdf','https://www.moa.gov.cn/ztzl/zjyqwgz/spxx/202401/P020240118484537271708.pdf'],'unasserted':['Beijing/Suzhou parent or subsidiary relationship','IP ownership chain']},
          'company-shandong-shunfeng-biotechnology':{'scope':'Shandong Shunfeng legal identity; bellagen.cn domain associated by company recruitment material','legal_counterparties':['山东舜丰生物科技有限公司'],'sources':['https://www.kws.com/corp/en/media-press/news-2025/kws-and-shunfeng-bio-sign-worldwide-licensing-agreement/','https://cbs.cau.edu.cn/module/download/downfile.jsp?classid=0&filename=7c00cfc203104491929b69f13b894b22.pdf'],'unasserted':['separate BellaGen incorporation','formal legal rebranding']},
        }
        identity_changes=[]
        for eid,review in identities.items():
            path=data_dir/'entities/companies'/(eid+'.json')
            record=json.loads(path.read_text(encoding='utf-8'))
            value={'reviewed_at':'2026-10-28','kind':'source_scope_audit_not_trust_decision',**review}
            attrs=record.setdefault('attributes',{})
            if 'gene_editing_identity_closeout' in attrs:continue
            identity_changes.append(eid)
            if apply:
                attrs['gene_editing_identity_closeout']=value;atomic_json(path,record)
        # Refresh only unchanged mission-owned manual-source health metadata.
        # No enabled/discovery setting or existing analyst source decision moves.
        path=data_dir/'configuration/sources.json'
        raw=path.read_text(encoding='utf-8');sources=json.loads(raw)
        old_sources={s['id']:s for s in old['sources']}
        by_url={canonical_url(s['url']):s for s in new['sources'] if s['id'].startswith('source-gene-closeout-')}
        source_changes=[]
        for s in sources:
            base=old_sources.get(s['id']);ref=by_url.get(canonical_url(s.get('url') or s.get('value') or ''))
            if not base or s!=base or not ref:continue
            source_changes.append(s['id'])
            if apply:
                for key in ('last_checked_at','last_successful_check','last_status','status'):
                    s[key]=ref[key]
        if apply and source_changes:
            updated={s['id']:s for s in sources if s['id'] in source_changes}
            fd,name=tempfile.mkstemp(dir=path.parent,prefix=path.name+'.',suffix='.tmp')
            try:
                with os.fdopen(fd,'w',encoding='utf-8') as stream:
                    stream.write(replace_source_rows(raw,updated));stream.flush();os.fsync(stream.fileno())
                os.replace(name,path)
            finally:
                if Path(name).exists():Path(name).unlink()
    return {'applied':apply,'program_updates':changes,'analyst_programs_preserved':preserved,'identity_notes_added':identity_changes,'source_health_updates':source_changes,'publication_decisions':0,'facts_created':0}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data-dir',type=Path,default=ROOT/'data');p.add_argument('--inbox-dir',type=Path,default=ROOT/'inbox');p.add_argument('--apply',action='store_true');p.add_argument('--verified-backup',type=Path);a=p.parse_args()
    print(json.dumps(reconcile(a.data_dir,a.inbox_dir,apply=a.apply,verified_backup=a.verified_backup),ensure_ascii=False,indent=2))
