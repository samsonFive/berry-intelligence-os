"""Offline closeout from inspected originals; never publishes source claims.

Creates a new dated snapshot. Native changes use an exact prior-payload guard;
existing analyst changes always win. Run import_gene_editing.py separately.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.services.gene_editing import classify
from app.services.pipeline_lock import pipeline_lock
from app.services.analyst_state_io import atomic_json
from audit_gene_editing_closeout import BASE,CAPTURES,NEW,normalize

OLD=ROOT/'data/imports/gene-editing-2026-10-20/snapshot.json'
SPECS={
 'fda-meetings':('FDA inventory defines the limited scope of voluntary premarket meetings',None,['simplot','pairwise'],[],
  'FDA lists voluntary premarket meetings for genome-edited Simplot remontant strawberry and Pairwise blackberry traits. FDA explicitly distinguishes a meeting from its evaluation in a completed voluntary premarket consultation. Neither a meeting nor an inventory row proves sales.',
  'not intended to represent an FDA evaluation'),
 'fda-simplot':('FDA VPM 0002: Simplot remontant strawberry',None,['simplot'],['strawberry'],
  'FDA records a December 4, 2024 meeting for genome-edited strawberry altered flowering and loss-of-function edits in confidential Gn1. The inventory identifies Simplot. This closes the missing FDA-record search, not food approval, commercial availability or an independent Gn1-to-TFL1 identity determination.',
  'Altered flowering for remontancy'),
 'fda-pairwise':('FDA VPM 0011: Pairwise blackberry trait tracks',None,['pairwise'],['blackberry'],
  'FDA records a July 9, 2026 genome-edited blackberry meeting concerning compact architecture, reduced prickles and reduced seed lignification. The record does not identify Fontana, a sold cultivar, or a fully stacked commercial product. A VPM is not an FDA food-safety evaluation.',
  'reduced seed lignification'),
 'canada-s4a':('Health Canada non-novel listing: S4A remontant strawberry','2024-10-24',['simplot'],['strawberry'],
  'The voluntary non-novel list names Simplot S4A, CRISPR/Cas9, longer harvest season and anticipated marketing in 2025. Anticipated marketing is not an actual sale or a novel-food approval. The row alone does not map each English S4A subline.',
  'S4A'),
 'uk-confirmation':('Defra PBM/26/FRAN/008 precision-bred confirmation','2026-07-17',['simplot'],['strawberry'],
  'The July 17, 2026 confirmation covers eight PBM/26/FRAN/008 identifiers; the government notice maps them to eight S4A lines. This is precision-bred status, separate from food authorization, completed England trials or sales.',
  'CONFIRMATION OF PRECISION BRED STATUS'),
 'mara-soybean':('MARA gene-edited soybean certificates: Shunfeng 25T93-1 and Qi Suzhou P16',None,['qi-biodesign','shunfeng'],[],
  'MARA lists certificate 350 for Shandong Shunfeng GmELF3a soybean 25T93-1 and certificate 351 for Suzhou Qi GmFAD2-1A/GmFAD2-1B soybean P16. Both are nationwide production/application certificates valid January 2, 2024 through January 1, 2029. The list does not prove sales, berry authorization, or the Beijing/Suzhou ownership chain.',
  '25T93-1'),
 'psg-history':('PSG official history distinguishes its PSI roots and reports Simplot investment',None,['plant-sciences','simplot'],[],
  'PSG describes its roots in PSI and a consolidation under the PSG name in 2024, while the 2023 issuer release announced restructuring. Its history reports Simplot investment in PSG. Neither source discloses ownership percentages, control, executed assignments or contract novation; announcement and implementation dates remain distinct.',
  'Simplot investing in PSG'),
 'psg-research':('PSG describes current Pairwise and Simplot editing collaborations',None,['plant-sciences','pairwise','simplot'],['strawberry','raspberry','blackberry'],
  'PSG currently describes implementing gene editing with Pairwise across caneberry breeding programs and with Simplot in strawberry programs. This provides current partner-side corroboration of the historical alliances. It does not identify which specific S4A line derives from PSG germplasm or prove a commercial launch.',
  'we are implementing gene editing in our strawberry breeding programs'),
 'heritable-products':('Heritable product page explicitly offers genome-edit design',None,['heritable'],[],
  'Heritable explicitly markets plant genome-edit design for CRISPR or targeted mutagenesis, off-target prediction and multi-gene optimization. These are company platform claims; the page does not establish use in its CIV/Mastronardi strawberry program, completed field validation, or a released edited strawberry.',
  'Designs for CRISPR or targeted mutagenesis'),
 'planasa-rd':('Planasa R&D specifies molecular markers, phenotyping and crossing',None,['planasa'],[],
  'Planasa describes biomolecular markers, molecular analysis, breeder phenotyping and crossing selected individuals. This supports marker-assisted breeding. No editing method or edited-berry launch is established by this page.',
  'biomolecular markers'),
 'uf-ohalo-report':('UF/FSREF reports DNA-free gene-edited strawberry resistance lines',None,['ohalo'],['strawberry'],
  'The UF 2024-25 report names Ohalo as a collaborator in a DNA-free genome-editing system for strawberry. It reports 138 regenerated lines across four varieties and 20 selected for 2025-26 field testing after growth-room assays. Methods name five cultivars while results enumerate four; no fifth result cohort is inferred. Field completion and commercial launch are not reported.',
  'Ohalo Genetics'),
 'fall-creek-affiliation':('Strawberry CRISPR paper records a Fall Creek author affiliation','2025-10-15',['fall-creek'],['strawberry'],
  'PubMed PMID 41635864 indexes a strawberry MYB10-1B CRISPR paper and lists Fall Creek as an author affiliation. Publication was October 15, 2025 with January 2026 collection. Affiliation alone does not establish a Fall Creek corporate editing program, a blueberry editor, ownership of results or an edited commercial product.',
  'Fall Creek Farm and Nursery, Inc.'),
 'shunfeng-recruitment':('University-hosted Shunfeng recruitment links the bellagen.cn domain',None,['shunfeng'],[],
  'Company recruitment material hosted by China Agricultural University names Shandong Shunfeng Biotechnology and a bellagen.cn recruitment email. This establishes a domain association, not a separately incorporated BellaGen company or a legal renaming instrument.',
  'bellagen.cn'),
 'hrb-financing':('HRB financing announcement names investors','2024-04-09',['hudson-river'],[],
  'HRB names Oost NL and Eurogenetic in a financing announcement, with Bridford Group and Elaine Groenestein as existing investors. Visible body date 04.09.2024 controls over shared site metadata. Investment amount and controlling ownership are not disclosed.',
  'Oost NL'),
 'planasa-owner':('Planasa issuer release identifies EW Group subsidiary status','2026-05-12',['planasa'],[],
  'Planasa identifies itself as part of EW Group in the IFSI issuer announcement. Its page is dated May 12, 2026 and the body announcement May 6; those dates remain distinct. This closes the parent-identification source gap, without establishing berry gene editing.',
  'part of the German family holding EW Group'),
 'simplot-case-study':('Simplot SCRA strawberry case study identifies S4A and Gn1',None,['simplot'],['strawberry'],
  'A Simplot presentation hosted by SCRA describes S4A as CRISPR/Cas9 edited and uses the confidential target label Gn1. Its composition and environmental statements remain company assessments; the presentation is not an agency decision or proof of a specific retail SKU.',
  'Remontant Strawberry S4A'),
}
ORIGINAL_TITLES={
 'fda-meetings':'Premarket Meetings Regarding Food from Genome Edited Plants',
 'fda-simplot':'Strawberry (Fragaria x ananassa)',
 'fda-pairwise':'Blackberry (Rubus subgenus Rubus)',
 'canada-s4a':'List of non-novel products of plant breeding for food use',
 'uk-confirmation':'Confirmation of precision bred status reference PBM/26/FRAN/008',
 'mara-soybean':'2023 年农业基因编辑生物安全证书（生产应用）批准清单',
 'psg-history':'Our Vision / Our Story',
 'psg-research':'Cultivar Development / Research and Consulting / Technology Partners',
 'heritable-products':'Meet Heritable Your Partner for AI-Powered Agriculture',
 'planasa-rd':'R&D',
 'uf-ohalo-report':'Developing Molecular Breeding Tools and Resources for Neopestalotiopsis Resistance',
 'fall-creek-affiliation':'Whitening fruit by CRISPR/Cas9-mediated homoeolog-specific gene editing of MYB10-1B in strawberry (F. × ananassa)',
 'shunfeng-recruitment':'山东舜丰生物科技有限公司招聘简章',
 'hrb-financing':'Hudson River raises new financing for novel breeding techniques',
 'planasa-owner':'EW GROUP Subsidiary PLANASA Acquires Sweet Corn Breeder Illinois Foundation Seeds',
 'simplot-case-study':'Simplot Genome Edited Strawberry S4A',
}


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    snapshot=json.loads(OLD.read_text(encoding='utf-8'))
    originals={p['id']:copy.deepcopy(p) for p in snapshot['programs']}
    checks=json.loads((BASE/'source-audit.json').read_text(encoding='utf-8'))
    check_by_key={r['key']:r for r in checks}
    ids=dict(simplot='company-j-r-simplot',pairwise='company-pairwise',**{'plant-sciences':'company-plant-sciences-genetics','qi-biodesign':'company-qi-biodesign','shunfeng':'company-shandong-shunfeng-biotechnology','heritable':'company-heritable-agriculture','planasa':'company-planasa','ohalo':'company-ohalo','hudson-river':'company-hudson-river-biotechnology','fall-creek':'company-fall-creek-farm-and-nursery'})
    # The HTTP transport was blocked, but the original PubMed record was opened
    # and its title, publication date and affiliation recovered by the web tool.
    web_excerpt='Whitening fruit by CRISPR/Cas9-mediated homoeolog-specific gene editing of MYB10-1B in strawberry (F. × ananassa)\n2025 Oct 15;13(1):uhaf272.\nFall Creek Farm and Nursery, Inc., 39318 Jasper-Lowell Road, Lowell, OR 97452, USA.'
    (CAPTURES/'fall-creek-affiliation.txt').write_text(web_excerpt,encoding='utf-8')
    check_by_key['fall-creek-affiliation'].update(alternative_access='web tool opened original PubMed record; selected bibliographic text recovered',recovery_scope='retained bibliography/affiliation excerpt; HTTP remains blocked')
    for key,publisher,url in NEW:
        title,date,companies,berries,summary,anchor=SPECS[key]
        check=check_by_key[key]
        assert check['status']=='readable' or key=='fall-creek-affiliation',(key,check['status'])
        text=(CAPTURES/(key+'.txt')).read_text(encoding='utf-8')
        if normalize(anchor) not in normalize(text):
            raise ValueError('Reinspect source anchor: '+key)
        # Quotes are short, exact anchors; the synopsis above is a paraphrase.
        row=copy.deepcopy(snapshot['evidence'][0])
        jurisdiction={'fda-meetings':'united-states','fda-simplot':'united-states','fda-pairwise':'united-states','canada-s4a':'canada','uk-confirmation':'united-kingdom','mara-soybean':'china'}.get(key)
        row.update(id='ev-gene-closeout-'+key,title=title,original_title=ORIGINAL_TITLES[key],source_name=publisher,source_url=url,
                   published_date=date,captured_date='2026-10-28',summary=summary,supporting_excerpt=anchor,
                   original_text_excerpt=anchor,entity_ids=[ids[c] for c in companies],berry_ids=['berry-'+b for b in berries],
                   geography_ids=['geography-'+jurisdiction] if jurisdiction else [],
                   geography_provenance='Regulatory jurisdiction; England uses its UK country container. Not a cultivation or trial footprint.' if jurisdiction else 'Program geography not assigned from headquarters.',
                   source_language='zh' if key in {'mara-soybean','shunfeng-recruitment'} else 'en',
                   source_type='research_program_publication' if key in {'mara-soybean','fda-meetings','fda-simplot','fda-pairwise','canada-s4a','uk-confirmation','uf-ohalo-report','fall-creek-affiliation'} else 'company_press_release',
                   attribution=publisher+' original source inspected; limited to the stated claim and jurisdiction',
                   submitted_by='gene-editing-closeout/2026-10-28',tags=['gene-editing-research','source-audit-completed'],
                   article={'status':'excerpt_only','full_text':anchor},
                   source_fidelity={'method':check.get('alternative_access') or check['method'],'sha256':hashlib.sha256(text.encode()).hexdigest(),'status':'original_text_checked','hash_scope':'retained bibliographic excerpt' if key=='fall-creek-affiliation' else 'private captured text'},
                   research_review={'reviewer':'Codex source audit','date':'2026-10-28','outcome':'source_checked','publication_decision':'not_made','scope':'source authenticity, attribution and claim bounds; not a human approval'})
        row['classification']=classify(row);row['tags']+=row['classification']['topics']
        snapshot['evidence'].append(row)
        source=copy.deepcopy(snapshot['sources'][0])
        source.update(id='source-gene-closeout-'+key,label=publisher+' · '+key,value=url,url=url,canonical_url=url,
                      publisher=publisher,language=row['source_language'],linked_competitor_ids=row['entity_ids'],enabled=False,
                      last_checked_at='2026-10-28',last_successful_check='2026-10-28',last_status='readable',status='readable')
        snapshot['sources'].append(source)
        for profile in snapshot['companies']:
            if profile['entity_id'] in row['entity_ids']:profile['evidence_ids'].append(row['id'])

    programs={p['id']:p for p in snapshot['programs']}
    def enrich(key,keys,**values):
        p=programs['program-gene-'+key];p.update(values)
        p['evidence_ids']+=['ev-gene-closeout-'+k for k in keys]
        p['research_reviewed_at']='2026-10-28'
    enrich('simplot-s4a',['canada-s4a','fda-meetings','fda-simplot','uk-confirmation','simplot-case-study'],
           stage='Precision-bred status confirmed; food meeting/listing separately documented',
           milestone='Defra July 17 confirmation covers eight identifiers; August 21 notice maps the S4A lines and describes planned England selection trials.',
           regulatory_records={'England':{'reference':'PBM/26/FRAN/008','decision_date':'2026-07-17','notice_date':'2026-08-21','scope':'precision-bred status'},'Canada':{'identifier':'S4A','listing_date':'2024-10-24','scope':'voluntary non-novel list; marketing year anticipated'},'FDA':{'reference':'VPM 0002','meeting_date':'2024-12-04','scope':'voluntary meeting; not safety evaluation'}},
           line_identifiers=['S4A-115','S4A-210','S4A-293','S4A-334','S4A-336','S4A-444','S4A-448','S4A-480'],
           gaps='Completed England trials, food authorization and named commercial SKU not recovered. FDA Gn1 is confidential; Simplot presentation supplies the S4A/Gn1 association. No blanket PSI/PSG ancestry asserted.')
    enrich('simplot-psi',['psg-research'],gaps='Current PSG partner account supports ongoing strawberry editing collaboration; exact contracting novation and S4A cultivar ancestry remain undisclosed.')
    enrich('pairwise-psi',['psg-research'],gaps='Current PSG partner account supports caneberry collaboration; named commercial raspberry varieties and line-level IP allocation not disclosed.')
    for key in ('pairwise-seedless','pairwise-compact','pairwise-fontana'):
        enrich(key,['fda-meetings','fda-pairwise'])
        programs['program-gene-'+key]['gaps']+=' FDA VPM 0011 covers trait tracks, not a named sold cultivar, approval or proof of a commercial trait stack.'
    enrich('ohalo-florida',['uf-ohalo-report'],technology='DNA-free protoplast genome editing; exact nuclease unspecified',
           stage='Edited lines generated; growth-room resistance assays reported; field testing selected',
           milestone='UF/FSREF 2024-25 report names Ohalo collaboration, 138 regenerated lines and 20 selections for 2025-26 field trials.',
           gaps='Field completion, released variety identity and sales not recovered. Methods mention five cultivars while results enumerate four. Distinct from Boosted Breeding and true-seed consortium.')
    enrich('qi-soybean',['mara-soybean'],crop='Soybean (P16 in China; APHIS-described FAD2 soybean separately scoped)',
           milestone='APHIS May 29, 2024 response is verified; MARA certificate 351 names Suzhou applicant and P16, valid 2024-01-02 to 2029-01-01 nationwide.',
           gaps='Beijing/Suzhou equity chain and explicit line-for-line mapping of P16 to APHIS event not recovered. Certificates do not prove sales or berry authorization.')
    enrich('planasa',['planasa-rd'],technology='Marker-assisted pre-breeding; phenotyping; conventional crossing',
           milestone='Original R&D page specifies molecular markers, breeder phenotyping and crossing; editing involvement remains not established.',
           gaps='No original editing license, edited-berry line or commercial edited product recovered; marker-assisted selection is not CRISPR.')
    enrich('heritable-strawberry',['heritable-products'],gaps='Heritable explicitly offers edit design at platform level. Its CIV/Mastronardi strawberry program does not thereby become an edited program; released cultivars and field outcomes remain undisclosed.')

    def add(slug,name,company,technology,crop,trait,role,stage,date,milestone,keys,gaps,berries):
        p=dict(id='program-gene-'+slug,name=name,company_ids=[ids[company]],technology=technology,crop=crop,trait=trait,
               role=role,partner=None,geography=None,stage=stage,milestone_date=date,milestone=milestone,
               evidence_ids=['ev-gene-closeout-'+k for k in keys],berry_ids=['berry-'+b for b in berries],
               verification='single_source / awaiting analyst review',last_reviewed=None,research_reviewed_at='2026-10-28',gaps=gaps)
        snapshot['programs'].append(p)
    add('heritable-edit-design','Heritable genome-edit design capability','heritable','AI-guided CRISPR / targeted-mutagenesis design','Crop-unassigned','Target discovery; off-target prediction; multi-gene optimization','trait discovery; editing design platform','Company platform claim',None,'Rendered company product page explicitly offers genome-edit design.',['heritable-products'],'Not independent benchmarking, a crop-specific edit demonstration or proof of editing in the strawberry partnership.',[])
    add('shunfeng-25t93','Long-juvenile soybean 25T93-1','shunfeng','GmELF3a genome editing','Soybean','Altered developmental timing','editing platform','Chinese production/application safety certificate','2024-01-02','MARA certificate 350 names Shandong Shunfeng; nationwide validity through January 1, 2029.',['mara-soybean'],'Not a berry program, actual sale or a certificate for every Shunfeng product.',[])
    add('fall-creek-paper-affiliation','Strawberry MYB10-1B paper: Fall Creek author affiliation','fall-creek','CRISPR/Cas9 in published strawberry research','Strawberry','Fruit coloration (paper); company program not established','research affiliation only','Published research affiliation; corporate program unestablished','2025-10-15','PubMed records a Fall Creek affiliation in the strawberry paper.',['fall-creek-affiliation'],'Author affiliation does not establish corporate sponsorship, ownership, a blueberry program or commercial edited fruit. Full publisher text was not recovered in this pass.',['strawberry'])

    profiles={p['entity_id']:p for p in snapshot['companies']}
    profiles[ids['plant-sciences']]['identity_notes']='Existing dossier ID retained as a historical PSI/PSG monitoring lineage, not one merged legal person. The 2023 release separates PSG portfolio/IP holding and PSI contracted services. PSG current history describes 2024 implementation; its current research page confirms Simplot strawberry and Pairwise caneberry collaborations. Company-reported Simplot investment does not establish a parent or control percentage. Executed novation and ownership percentages are not public in recovered records.'
    profiles[ids['qi-biodesign']]['identity_notes']='Beijing Qi Biodesign is the Vilmorin counterparty; MARA certificate 351 names 苏州齐禾生科生物科技有限公司 for soybean P16. Brand linkage is retained for monitoring; no Beijing/Suzhou parent, subsidiary or IP ownership edge is inferred.'
    profiles[ids['shunfeng']]['identity_notes']='KWS and MARA name 山东舜丰生物科技有限公司. University-hosted company recruitment corroborates bellagen.cn association. BellaGen is a domain/branding lead; a separate incorporated company or formal renaming is not established.'
    profiles[ids['heritable']]['editing_status']='Company explicitly offers genome-edit design; use in strawberry partnership unestablished'
    profiles[ids['fall-creek']]['editing_status']='Published strawberry-paper author affiliation; corporate editing program not established'
    for profile in snapshot['companies']:
        profile['coverage']='Prior dedicated Perplexity/search discovery plus manual report; October 28 original-source audit and targeted public follow-ups. No paid research calls in closeout.'
        profile['gaps']='Only product-specific public claims are asserted. Undisclosed ownership, commercial terms and unreported trial outcomes remain unknown, not false.'
        profile['research_closeout']='Public-source investigation completed; publication/Atomic Evidence human gates remain separate.'
    for edge in snapshot['relationships']:
        if edge['id'] in {'rel-gene-simplot-psi','rel-gene-pairwise-psi'}:
            edge['evidence_ids'].append('ev-gene-closeout-psg-research')
    for record in snapshot['evidence'][:30]:
        key=record['id'].removeprefix('ev-gene-');check=check_by_key[key]
        assert check['status']=='readable' and check['retained_excerpt_match'],key
        record['research_review']={'reviewer':'Codex source audit','date':'2026-10-28','outcome':'source_and_excerpt_rechecked','publication_decision':'not_made','scope':'not a human approval; not independent claim validation'}
    snapshot['program_entities']=[dict(id=p['id'],record_type='entity',entity_type='breeding_program',name=p['name'],status='unverified',description='Research identity; source audit is separate from publication and claim approval.',berry_ids=p['berry_ids'],evidence_ids=p['evidence_ids'],attributes={'gene_editing':p}) for p in snapshot['programs']]
    snapshot.update(version='gene-editing-2026-10-28-closeout-v3',research_date='2026-10-28',access_date='2026-10-28',
                    research_status='Original-source closeout completed for the eleven-company slice. Publicly unrecoverable facts remain explicit unknowns. Source audits are complete; mandatory human publication/Atomic Evidence approval has not been fabricated.')
    snapshot['conflicts'].extend([
      'October 28: original FDA VPM inventory and details recovered. A premarket meeting is not an FDA safety evaluation or a commercial sale.',
      'October 28: MARA certificate list recovers Suzhou Qi legal name and P16 certificate, plus Shunfeng 25T93-1. Cross-jurisdiction event equivalence and corporate equity chains are not inferred.',
      'October 28: PSG browser history and current partner page recovered. Its history dates consolidation to 2024; the issuer announcement was August 2023. Implementation versus announcement remains distinct.',
      'October 28: Heritable edit-design product claims recovered from rendered browser page. Do not project this platform claim onto CIV/Mastronardi strawberry breeding.',
      'October 28: UF report upgrades Ohalo Florida evidence to regenerated lines and growth-room assays, with 20 selections for field testing; completed field trials and sales remain unestablished.',
      'October 28: Fall Creek affiliation recovered from original PubMed record; it does not establish corporate research sponsorship or an edited-blueberry product.'
    ])
    save(BASE/'snapshot.json',snapshot);save(BASE/'source-audit.json',checks)
    decisions=[{'evidence_id':r['id'],'source_url':r['source_url'],'source_checked_at':'2026-10-28','research_outcome':r['research_review']['outcome'],'recommended_next_action':'human_publication_review_if_not_already_reviewed','publication_decision':'not_made','claim_boundary':r['summary'],'import_candidate_status':r['status'],'runtime_decisions_authoritative':True} for r in snapshot['evidence']]
    save(BASE/'source-review-packet.json',decisions)
    coverage=json.loads((OLD.parent/'coverage.json').read_text(encoding='utf-8'))
    coverage.update(cutoff='2026-10-28',access_date='2026-10-28',research_closeout='Public-source follow-ups and audit completed under the user-approved manual research fallback; unavailable private facts are explicitly unasserted.',
                    imported_unique_programs=len(snapshot['programs']),versioned_evidence=len(snapshot['evidence']),
                    source_audit={'attempted':len(checks),'http_or_browser_readable':sum(c['status']=='readable' for c in checks),'http_blocked_but_original_web_excerpt_recovered':1,'original_30_excerpts_matched':30},
                    mandatory_human_gate='Publication and Atomic Evidence decisions remain human-owned; source review packet is prepared, not approved.',paid_calls_in_closeout=0)
    for row in coverage['companies']:
        row['programs']=sum(row['company'] in p['company_ids'] for p in snapshot['programs'])
        row['evidence']=sum(row['company'] in e['entity_ids'] for e in snapshot['evidence'])
        row['gaps']=profiles[row['company']]['gaps']
        row['closeout']='Source audit complete; product and legal scopes bounded; no false negative or commercial approval inferred.'
    save(BASE/'coverage.json',coverage)
    updates=[]
    with pipeline_lock(ROOT/'inbox','gene-editing-closeout-native-reconciliation'):
        for p in snapshot['programs']:
            native=ROOT/'data/entities/breeding_programs'/(p['id']+'.json')
            if not native.exists() or p['id'] not in originals:continue
            record=json.loads(native.read_text(encoding='utf-8'))
            if record.get('attributes',{}).get('gene_editing')==originals[p['id']]:
                record['attributes']['gene_editing']=p;record['evidence_ids']=p['evidence_ids'];atomic_json(native,record);updates.append(p['id'])
    save(BASE/'reconciliation.json',{'native_programs_updated_under_exact_prior_guard':updates,'analyst_decisions_overwritten':0,'human_approvals_created':0,'paid_calls':0})
    print(json.dumps({k:len(snapshot[k]) for k in ('companies','programs','evidence','sources','relationships')}))


if __name__=='__main__':main()
