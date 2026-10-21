"""Materialize the reviewed-for-source-fidelity mission import, not trusted Facts.

Only the curated, original-source-checked claims below become program rows.
Perplexity synthesis is discovery material and is never bulk imported as truth.
"""
import hashlib
import json
from pathlib import Path
import re
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.services.gene_editing import classify

BASE=ROOT/'data/imports/gene-editing-2026-10-20'
CAPTURES=ROOT/'inbox/gene-editing-captures'

# slug, canonical id, display label, official domain, headquarters, identity notes
COMPANIES=[
 ('simplot','company-j-r-simplot','J.R. Simplot Company','https://www.simplot.com','Boise, Idaho, United States','Simplot Plant Sciences is the operating unit named in APHIS correspondence. It is not Plant Sciences, Inc.; no PSI ownership is asserted.'),
 ('plant-sciences','company-plant-sciences-genetics','Plant Sciences, Inc.','https://www.plantsciencesgenetics.com','Watsonville, California, United States','Reuse the existing PSI roster ID. The registry currently combines the PSI label with PSG aliases. Research distinguishes PSI, the 2020/2021 contracting company, from the later PSG genetics organization. Legal split/alias correction awaits analyst review; no additional PSI duplicate or automatic alias merge is made.'),
 ('ohalo','company-ohalo','Ohalo','https://www.ohalo.com',None,'Ohalo Genetics / Ohalo; Boosted Breeding is a branded reproductive breeding system, not a synonym for CRISPR.'),
 ('pairwise','company-pairwise','Pairwise','https://www.pairwise.com','Durham, North Carolina, United States','Pairwise Plants is a monitored alias. Exact LLC/Services Inc. equity chain remains unresolved; investors are not treated as parents.'),
 ('hudson-river','company-hudson-river-biotechnology','Hudson River Biotechnology','https://www.hudsonriver.bio','Wageningen, Netherlands','Hudson River Biotechnology B.V.; HRB short-name hits require a plant-biotechnology context.'),
 ('plantik','company-plantik-biosciences','Plantik Biosciences','https://www.plantik.bio','France','Plantik identity supported by its official site and named HRB announcement; exact current registered office/parent remains unresolved.'),
 ('fall-creek','company-fall-creek-farm-and-nursery','Fall Creek Farm & Nursery','https://www.fallcreeknursery.com',None,'Retain the existing Fall Creek dossier and relationships; nursery propagation and genomic research do not themselves establish editing.'),
 ('planasa','company-planasa','Planasa','https://planasa.com',None,'Retain existing Planasa dossier and ownership relationships. This pass does not reinterpret existing parent-company history.'),
 ('heritable','company-heritable-agriculture','Heritable Agriculture','https://heritable.ag',None,'Born at Alphabet X according to its own release; this does not establish present Alphabet ownership. Public product-page text could not be recovered.'),
 ('qi-biodesign','company-qi-biodesign','Qi Biodesign','http://www.qi-biodesign.com','Beijing, China','齐禾生科; Beijing Qi Biodesign is named in the 2026 partner release; Suzhou Qi Biodesign appears in other records. The exact Beijing/Suzhou legal chain is unresolved; aliases are not merged into one legal entity claim.'),
 ('shunfeng','company-shandong-shunfeng-biotechnology','Shandong Shunfeng Biotechnology','http://bellagen.cn',None,'山东舜丰生物科技有限公司 / 舜丰生物. KWS identifies Shandong Shunfeng Biotechnology. BellaGen domain is a research lead; its original site timed out, so the English-site legal equivalence remains unverified in this pass.'),
]
IDS={slug:eid for slug,eid,*_ in COMPANIES}

# key: (source summary, excerpt anchor, date override, linked seed slugs, berry ids, program geography ids)
SPECS={
 'simplot-alliance':('Simplot announced a strawberry gene-editing alliance with PSI, pairing its CRISPR-Cas9 technology with PSI germplasm and commercialization expertise. Shelf-life and waste improvements were targets, not a reported launch.','entered a strategic alliance', '2021-10-28',['simplot','plant-sciences'],['strawberry'],[]),
 'simplot-license':('Simplot announced agricultural research and commercial CRISPR-Cas9 licensing from Corteva and the Broad Institute. This IP agreement does not establish a marketed berry product.','licensing agreement','2018-08-06',['simplot'],[],[]),
 'ohalo-boosted':('Ohalo announced Boosted Breeding, a proprietary plant breeding system intended to transmit complete parental genomes. The company describes applications across potato, corn and berries; its performance statements are company claims.','Ohalo’s Boosted Breeding system','2024-05-23',['ohalo'],[],[]),
 'ohalo-launch':('Ohalo announced a strawberry consortium using its proprietary hybrid plant breeding system and uniform true seed. Field trials were expected in 2026; the announcement does not demonstrate that those trials or commercial sales occurred.','Leading Industry Partners Include','2025-03-10',['ohalo'],['strawberry'],[]),
 'ohalo-strawberry':('Ohalo describes its strawberry true-seed hybrid breeding consortium and intended flavor, propagation and sustainability benefits. Commercial availability and trial outcomes are not established by this undated program page.','Ohalo has partnered',None,['ohalo'],['strawberry'],[]),
 'pairwise-psi':('Pairwise and PSI announced gene-editing collaboration on black and red raspberries and blackberries. Pairwise supplies editing, while PSI contributes germplasm and nursery expertise. Proposed traits include taste, convenience, shelf life and off-season availability.','Teams will focus','2020-04-15',['pairwise','plant-sciences'],['raspberry','blackberry'],['geography-united-states']),
 'pairwise-2026':('Pairwise reports genome-edited compact blackberry outdoor trials in the US and Colombia and consumer sales in Colombia. Seedless blackberries are described separately as a greenhouse pipeline. Volumes, named retailers and independent field results are not disclosed.','first commercial sale of edited blackberries','2026-01-20',['pairwise','plant-sciences'],['blackberry'],['geography-united-states','geography-colombia']),
 'pairwise-fontana':('Pairwise introduced Fontana, a compact fresh-market blackberry built on a PSG variety. The release makes company performance claims and describes thornless and seedless blackberries as future pipeline products, rather than as demonstrated Fontana traits.','Fontana is built on','2026-10-14',['pairwise','plant-sciences'],['blackberry'],[]),
 'pairwise-seedless':('Pairwise announced a seedless blackberry using CRISPR plant editing and described separate compact and thornless edits. The company defines seedless as soft small seeds rather than an absence of seeds. Future field testing and market availability were anticipated.','Created using the company','2024-06-04',['pairwise'],['blackberry'],[]),
 'pairwise-hrb':('Pairwise and Hudson River Biotechnology announced a Fulcrum plant gene-editing license for incorporation into HRB editing services, including vegetables and soft fruit. The license does not identify a newly launched berry variety.','signed a licensing agreement','2026-05-26',['pairwise','hudson-river'],[],[]),
 'hrb-plantik':('HRB and Plantik announced a strawberry heat-tolerance genome-editing collaboration combining Plantik targets with HRB transgene-free editing and BioMaas. The source says validation trials are underway; tomato demonstrations do not establish strawberry field performance.','Validation trials are already underway','2026-09-28',['hudson-river','plantik'],['strawberry'],[]),
 'hrb-regeneration':('HRB reports regeneration of strawberries from gene-edited single cells using its TiGER CRISPR workflow. This is an enabling-method demonstration, not evidence of a named commercial edited strawberry.','first successful regeneration','2024-02-06',['hudson-river'],['strawberry'],[]),
 'plantik-tech':('Plantik describes ATLANTIS target discovery in non-coding regulatory DNA and PROEDIT delivery of CRISPR machinery for plant genome editing. Its platform targets complex traits including heat tolerance; platform claims are not product approvals.','ATLANTIS™ is built',None,['plantik'],[],[]),
 'plantik-trade':('AgFunderNews reports the Plantik-HRB strawberry heat-tolerance partnership and distinguishes tomato validation from strawberry development. This provides reporting context, not independent replication of company performance claims.','heat', '2026-09-28',['plantik','hudson-river'],['strawberry'],[]),
 'plantik-hortidaily':('HortiDaily covers the Plantik-HRB strawberry heat-tolerance partnership. Coverage derives from the same announced collaboration and is not counted as independent confirmation.','strawberr','2026-10-20',['plantik','hudson-river'],['strawberry'],[]),
 'fall-creek-collection':('Fall Creek describes its commercial blueberry genetics and grower-support Collection platform and access to applied research trials. Gene editing is not established by this source.','value-added blueberry genetics platform',None,['fall-creek'],['blueberry'],[]),
 'planasa-about':('Planasa describes berry breeding using traditional breeding methods and modern technology, supported by nursery operations. The page does not establish gene editing in a named Planasa program.','traditional breeding methods',None,['planasa'],['strawberry','blueberry','raspberry','blackberry'],[]),
 'heritable-strawberry':('Heritable, CIV and Paul J. Mastronardi announced an AI-driven predictive breeding collaboration for greenhouse and tabletop strawberries, targeting taste, disease resistance and yield. The release does not establish CRISPR use in this strawberry program.','AI-driven predictive breeding technology',None,['heritable'],['strawberry'],[]),
 'qi-funding':('Qi Biodesign reports $75 million total financing and its SEEDIT plant genome-editing platform, including nucleases, base editors, prime editors and PrimeRoot. The release reports high-oleic soybean and disease-resistant wheat milestones; those regulatory assertions remain attributed to the company.','proprietary SEEDIT','2024-12-06',['qi-biodesign'],[],[]),
 'qi-license':('Vilmorin & Cie announced a global license to Qi Biodesign genome-editing technologies for field and vegetable crops, including access to a CRISPR nuclease. No berry-specific product is named.','portfolio of genome editing technologies','2026-07-31',['qi-biodesign'],[],[]),
 'qi-lab':('A Beijing government science portal reports approval of a Qi Biodesign agricultural genome-editing laboratory and reports five safety certificates across soybean, wheat and rice. This article is not the original product-specific regulatory certificate.','农业农村部基因编辑育种技术开发应用企业重点实验室','2026-01-21',['qi-biodesign'],[],['geography-china']),
 'shunfeng-kws':('KWS reports a worldwide plant-breeding gene-editing license from Shunfeng Bio covering Cas-SF01 and Cas-SF02 enzymes and all crop types. A global IP license is not global product approval or proof of a berry program.','CRISPR Cas-SF01','2025-09-10',['shunfeng'],[],[]),
 'shunfeng-kws-de':('German-language KWS coverage of the same Shunfeng genome-editing license. This is another language edition of the same publisher announcement and is not independent corroboration.','Shunfeng','2025-09-10',['shunfeng'],[],[]),
 'uk-simplot':('Defra published a marketing notice for Simplot S4A-210 strawberry and related lines, describing Tfl1 CRISPR/Cas9 edits and planned 2026 line-selection trials in England. The notice does not prove completed trials, retail sale or authorization in all jurisdictions.','S4A-210 precision bred line','2026-08-21',['simplot'],['strawberry'],['geography-united-kingdom']),
 'us-simplot':('An APHIS response dated August 6, 2020 concludes that the described Simplot remontant genome-edited strawberries are not regulated under the cited 7 CFR part 340 framework, based on representations and conditions in the inquiry. Other authorities may apply.','USDA does not consider','2020-08-06',['simplot'],['strawberry'],['geography-united-states']),
 'us-qi':('This APHIS-hosted document is Qi Biodesign’s high-oleic soybean regulatory-status-review request, revised May 23, 2024, describing FAD2 edits. It is an applicant submission, not itself an APHIS approval or determination letter.','higholeicacidsoybean','2024-05-23',['qi-biodesign'],[],['geography-united-states']),
}

def main():
    if (BASE/'manual-primary-checks.json').exists():
        raise SystemExit('Manual supplement exists; preserve the reviewed snapshot. Do not regenerate the initial seed over it.')
    checks=json.loads((BASE/'source-checks.json').read_text(encoding='utf-8'))
    health={r['key']:r for r in checks}
    evidence=[]
    for key,(summary,anchor,published,slugs,berries,geographies) in SPECS.items():
        source=health[key]
        original_title={'hrb-plantik':'Hudson River and Plantik Partner to Enhance Heat Tolerance in Strawberries',
                        'hrb-regeneration':'HRB achieves major CRISPR breakthrough: first-ever regeneration of strawberries from gene-edited single cells',
                        'heritable-strawberry':'Precision breeding for indoor strawberry: The AI revolution with Heritable, CIV, and Paul J. Mastronardi',
                        'qi-license':'Vilmorin & Cie and Qi Biodesign: worldwide licensing agreement for genome editing technologies',
                        'us-qi':'Response for the Regulatory Status Review of high oleic acid soybean line (24-116-02rsr)',
                        'us-simplot':'Confirmation of the regulatory status of genome edited strawberries with remontancy'}.get(key,source['title'])
        if source['status']!='readable':
            continue
        text=re.sub(r'\s+',' ',(CAPTURES/f'{key}.txt').read_text(encoding='utf-8')).strip()
        index=text.casefold().find(anchor.casefold())
        if index<0:
            # No acceptance of a discovery snippet without original-source text.
            raise ValueError(f'{key}: supporting anchor not found in original capture: {anchor}')
        excerpt=' '.join(text[index:].split()[:23])
        row={'id':'ev-gene-'+key,'record_type':'evidence','status':'in_review','review_state':'in_review',
             'evidence_role':'publication_artifact','source_type':'research_program_publication' if key in {'us-simplot','us-qi','uk-simplot','qi-lab'} else 'company_press_release',
             'title':original_title if original_title!=key else key.replace('-',' ').title(),
             'source_name':source['publisher'],'source_url':source['url'],'published_date':published,
             'captured_date':source['accessed_at'][:10],'summary':summary,'supporting_excerpt':excerpt,
             'original_text_excerpt':excerpt,'original_title':original_title,'source_language':source['language'],
             'attribution':source['publisher']+' reports; original source checked; claim not independently verified',
             'verification_state':'single_source','submitted_by':'gene-editing-mission/2026-10-20',
             'berry_ids':['berry-'+b for b in berries],'entity_ids':[IDS[s] for s in slugs],
             'geography_ids':geographies,'tags':['gene-editing-research','historical-backfill' if published and published<'2026-09-01' else 'research-current'],
             'priority':{key:{'level':'none','rationale':'Research import awaiting publication review.'} for key in ('reading','testing','commercial_position','monitoring')},
             'does_not_prove':['A reported target or platform is not a marketed product.','Regulatory status applies only to the stated product, jurisdiction and date.'],
             'source_fidelity':{'method':source['method']+(' / current article-content DOM; related articles excluded' if key.startswith('pairwise-') else ''),
                'sha256':hashlib.sha256((CAPTURES/f'{key}.txt').read_bytes()).hexdigest(),
                'status':'original_text_checked','capture_key':key},
             'article':{'status':'excerpt_only','full_text':excerpt}}
        row['classification']=classify(row)
        row['tags']+=row['classification']['topics']
        evidence.append(row)
    by_key={r['id'].removeprefix('ev-gene-'):r for r in evidence}
    programs=[]
    def program(slug,name,companies,technology,crop,trait,partner,geography,stage,date,milestone,keys,gaps,role='editing platform',berries=None):
        programs.append({'id':'program-gene-'+slug,'name':name,'company_ids':[IDS[s] for s in companies],
            'technology':technology,'crop':crop,'trait':trait,'partner':partner,'geography':geography,'role':role,
            'stage':stage,'milestone_date':date,'milestone':milestone,'evidence_ids':['ev-gene-'+key for key in keys],
            'berry_ids':['berry-'+b for b in (berries or [])], 'verification':'single_source / awaiting analyst review','last_reviewed':None,'gaps':gaps})
    program('simplot-psi','Simplot–PSI strawberry editing',['simplot','plant-sciences'],'CRISPR-Cas9','Strawberry','Shelf life; reduced waste; horticultural performance','Simplot / PSI',None,'Alliance announced','2021-10-28','Technology and germplasm alliance announced; launch expectation remains historical.',['simplot-alliance'],'No named alliance product, completed launch or current commercial terms verified.',role='editing platform; breeder/germplasm owner; commercialization partner',berries=['strawberry'])
    program('simplot-s4a','S4A-210 remontant strawberry',['simplot'],'CRISPR-Cas9 / Tfl1 knockout','Strawberry','Longer harvest season / altered flowering',None,'England (planned selection trials)','Regulatory notice / trials planned','2026-08-21','Defra published PBM/26/FRAN/008; notice describes intended line-selection trials.',['uk-simplot','us-simplot'],'No proof of completed England trials or retail sale. US 2020 scope is not universal approval; no automatic lineage equivalence to every PSI alliance line.',berries=['strawberry'])
    program('simplot-ip','Foundational CRISPR agricultural license',['simplot'],'CRISPR-Cas9','Crop-unassigned','Enabling plant editing','Corteva; Broad Institute','Worldwide IP scope','License announced','2018-08-06','Agricultural research/commercial license announced.',['simplot-license'],'IP scope is not product approval or commercial availability.')
    program('ohalo-boosted','Boosted Breeding platform',['ohalo'],'Boosted Breeding (distinct from CRISPR)','Potato; corn; berries','Whole-genome parental inheritance; true-seed production',None,None,'Company platform announcement','2024-05-23','Ohalo describes a proprietary reproductive breeding system.',['ohalo-boosted'],'Independent yield data, crop-specific launch and mechanistic equivalence to any particular editor not established.')
    programs[-1]['role']='advanced breeding platform'
    program('ohalo-strawberry','Ohalo Strawberry Consortium',['ohalo'],'Proprietary hybrid breeding / uniform true seed','Strawberry','Flavor; uniform true seed; propagation efficiency','BlazerWilkinsonGee; California Giant; Central West Produce; Crown Nursery; Naturipe Berry Growers; Wish Farms','Global intended access; trial locations undisclosed','Consortium announced / trials anticipated','2025-03-10','Announcement anticipated 2026 field trials and later commercialization.',['ohalo-launch','ohalo-strawberry'],'No confirmation of completed 2026 trials, named released varieties or sales. Boosted Breeding is not automatically CRISPR.',role='breeder/germplasm owner; commercialization partner',berries=['strawberry'])
    program('pairwise-psi','Pairwise–PSI caneberry collaboration',['pairwise','plant-sciences'],'Gene editing / Fulcrum','Blackberry; red and black raspberry','Taste; convenience; shelf life; seasonal availability','Pairwise / PSI','United States (announced target market)','Collaboration announced','2020-04-15','Editing plus germplasm and nursery collaboration announced.',['pairwise-psi'],'Historical launch expectation is not a named commercial raspberry launch.',role='editing platform; breeder/germplasm owner; nursery/propagation',berries=['blackberry','raspberry'])
    program('pairwise-seedless','Seedless blackberry pipeline',['pairwise'],'Fulcrum CRISPR / multiplex editing','Blackberry','Soft small seeds; separate thornless and compact edits',None,None,'Company demonstration / pipeline','2024-06-04','Company announced soft-seed and additional edited traits. January 2026 update still describes seedless greenhouse material.',['pairwise-seedless','pairwise-2026'],'Not literally seed-free. Compact sales do not establish commercial seedless or thornless blackberries.',berries=['blackberry'])
    program('pairwise-compact','Compact blackberry Colombia market validation',['pairwise'],'Fulcrum plant gene editing','Blackberry','Compact architecture / higher-density production','Unnamed production partner and retailers','United States and Colombia (trials); Colombia (reported consumer sales)','Field trials / limited sales reported','2026-01-20','Pairwise reports outdoor trials and edited-blackberry sales to Colombian consumers.',['pairwise-2026'],'Exact sale date, volumes, named retailers, genotype and independent performance not established; not a broad seedless launch.',berries=['blackberry'])
    program('pairwise-fontana','Fontana',['pairwise','plant-sciences'],'Fulcrum-enabled compact architecture','Blackberry','Compact architecture; concentrated fruiting','Plant Sciences Genetics (PSG)',None,'Named product introduced','2026-10-14','Pairwise introduced Fontana, built on a PSG variety.',['pairwise-fontana'],'No broad availability by country verified. Thornless and seedless are separate pipeline traits; underlying cultivar identity not fully disclosed.',berries=['blackberry'])
    program('pairwise-hrb','Fulcrum–BioMaas service license',['pairwise','hudson-river'],'Fulcrum plant gene editing / BioMaas','Vegetables; soft fruit; other species','Editing and regeneration services','Pairwise / Hudson River',None,'License announced','2026-05-26','HRB licensed Fulcrum for its editing services.',['pairwise-hrb'],'No named resulting berry variety or product launch. Soft-fruit scope is not a named berry crop.')
    program('hrb-regeneration','TiGER strawberry single-cell regeneration',['hudson-river'],'TiGER CRISPR workflow','Strawberry','Regeneration from edited single cells',None,None,'Company demonstration','2024-02-06','HRB announced strawberry regeneration from edited single cells.',['hrb-regeneration'],'Original page body dates the announcement February 6, 2024; automated metadata incorrectly suggests September 25, 2026. No marketed cultivar established.',berries=['strawberry'])
    program('heat-strawberry','HRB–Plantik heat-tolerant strawberry',['hudson-river','plantik'],'ATLANTIS target discovery + BioMaas transgene-free editing','Strawberry','Heat tolerance','Hudson River / Plantik',None,'Validation trials underway (company report)','2026-09-28','Partnership combines tomato-validated targets with strawberry editing; source reports ongoing validation.',['hrb-plantik','plantik-trade','plantik-hortidaily'],'No named cultivar, completed strawberry field results or commercial product. Syndicated coverage is not independent trial evidence.',role='trait discovery; editing platform',berries=['strawberry'])
    program('plantik-platform','ATLANTIS / PROEDIT',['plantik'],'Regulatory-DNA target discovery / CRISPR delivery','Crop-unassigned','Complex quantitative traits / heat tolerance',None,None,'Platform described',None,'Official technology page describes discovery and genome-editing workflow.',['plantik-tech'],'Specific target sequence, independent outcomes and crop-specific commercial products not disclosed.',role='trait discovery; editing platform')
    program('plantik-tomato','Tomato heat-tolerance validation',['plantik'],'ATLANTIS target engineering','Tomato','Heat tolerance',None,'United States and Europe (reported demonstrations)','Field demonstrations reported','2026-09-28','HRB partnership release describes tomato demonstrations across genetic backgrounds and locations.',['hrb-plantik'],'Tomato demonstrations cannot establish strawberry heat tolerance; locations, protocols and independent results undisclosed.',role='trait discovery')
    program('fall-creek','Fall Creek Collection',['fall-creek'],'Conventional breeding / selection and applied research','Blueberry','Adaptation across chill levels; grower support',None,'US; Mexico; Spain; Netherlands (offered trial-site access)','Commercial genetics platform described',None,'Company page offers Collection genetics, trial-site access and grower support.',['fall-creek-collection'],'Gene-editing involvement not established in this research pass. No edited blueberry line is asserted.',role='breeder/germplasm owner; nursery/propagation',berries=['blueberry'])
    program('planasa','Planasa berry breeding',['planasa'],'Traditional breeding plus unspecified modern technology','Strawberry; blueberry; raspberry; blackberry',None,None,None,'Breeding / nursery business described',None,'Official company page describes traditional breeding with modern technology.',['planasa-about'],'Gene-editing involvement not established in this research pass; modern technology does not establish CRISPR.',role='breeder/germplasm owner; nursery/propagation',berries=['strawberry','blueberry','raspberry','blackberry'])
    program('heritable-strawberry','Indoor strawberry predictive breeding',['heritable'],'AI-driven predictive breeding (editing not established for this program)','Strawberry','Taste; disease resistance; yield','CIV; Paul J. Mastronardi',None,'Partnership announced; publication date unavailable',None,'Company release describes an AI-driven greenhouse/tabletop breeding program.',['heritable-strawberry'],'No named commercial variety, trial location, publication date or CRISPR use in this program established. Product-page genome-edit design claims remain unverified.',role='trait discovery; breeder support',berries=['strawberry'])
    program('qi-seedit','SEEDIT editing platform',['qi-biodesign'],'RNA-guided nucleases; base editing; prime editing; PrimeRoot','Crop-unassigned','Multiplex editing; trait discovery',None,None,'Company platform claim','2024-12-06','Company financing release describes SEEDIT and reports $75 million total financing.',['qi-funding'],'Not independent platform benchmarking or evidence of a berry product; primary company domain unavailable.')
    program('qi-soybean','High-oleic soybean / FAD2',['qi-biodesign'],'Genome editing / FAD2 target','Soybean','High oleic acid',None,'United States regulatory submission; China reported milestone','Regulatory submission; clearance claimed separately','2024-12-06','Funding release reports US exemption and Chinese safety certificate; APHIS-hosted May 2024 document is an applicant RSR request.',['us-qi','qi-funding'],'Original decision letter/certificate not verified in this pass; do not present applicant request as approval. Commercial sales not established.')
    program('qi-wheat','Powdery-mildew-resistant wheat',['qi-biodesign'],'Genome editing','Wheat','Powdery mildew resistance',None,'China (company-reported regulatory milestone)','Biosafety certificate reported by company','2024-12-06','Company release reports a Chinese safety certificate for edited wheat.',['qi-funding','qi-lab'],'Original event-specific certificate, event ID, commercial availability and field outcomes not verified.')
    program('qi-license','Qi–Vilmorin genome-editing license',['qi-biodesign'],'Portfolio of genome-editing tools / CRISPR nuclease','Field and vegetable crops','Enabling editing','Vilmorin & Cie / Limagrain','Worldwide IP scope','License announced','2026-07-31','Partner release describes global access to Qi editing technologies.',['qi-license'],'Exact nuclease identity, crop-by-crop products, berry application and commercial availability not disclosed.')
    program('qi-lab','Agricultural editing laboratory',['qi-biodesign'],'SEEDIT / TranC / QBEmax / PrimeRoot','Soybean; wheat; rice','Agricultural editing research',None,'Beijing, China','Laboratory approval reported','2026-01-21','Beijing science portal reports laboratory approval and five crop safety certificates.',['qi-lab'],'Chinese official article is not a product-specific approval certificate. A small-berry facility lead in Perplexity remains unverified at original source.')
    program('shunfeng','Cas-SF01 / Cas-SF02 KWS license',['shunfeng'],'CRISPR Cas-SF01 / Cas-SF02','All crop types (license scope)','Enabling plant genome editing','KWS','Worldwide IP scope; Europe breeding context','Global license announced','2025-09-10','KWS confirms licensing Shunfeng editing technologies.',['shunfeng-kws','shunfeng-kws-de'],'Berry program, licensed edited product, commercial sales and original company/news endpoints not established. Language editions are one source.')
    profiles=[]
    entities=[]
    aliases={'simplot':['Simplot','Simplot Plant Sciences'],'plant-sciences':['PSI','Plant Sciences Inc'],'ohalo':['Ohalo Genetics','oHalo'],
             'pairwise':['Pairwise Plants'],'hudson-river':['Hudson River Biotechnology B.V.'],'plantik':['Plantik'],'fall-creek':['Fall Creek','Fall Creek Nursery'],
             'planasa':['Planasa Group'],'heritable':['heritable.ag'],'qi-biodesign':['Qi-Biodesign','齐禾生科'],
             'shunfeng':['Shunfeng Bio','ShunFeng Bio','Shunfeng BioTech','山东舜丰生物科技有限公司','舜丰生物']}
    for slug,eid,name,domain,hq,identity in COMPANIES:
        research=json.loads((BASE/'research'/f'{slug}.json').read_text(encoding='utf-8'))
        linked=[row['id'] for row in evidence if eid in row['entity_ids']]
        gaps=('Gene-editing involvement not established in this research pass. ' if slug in {'fall-creek','planasa'} else '')
        gaps+='Independent trial outcomes, current availability and exact legal/control relationships remain incomplete; see program-specific gaps.'
        if slug in {'heritable','plant-sciences'}:
            gaps+=' Original dynamic product/research pages yielded no readable text.'
        summary=' '.join(dict.fromkeys(p['name'] for p in programs if eid in p['company_ids']))+'. Source claims remain awaiting analyst review.'
        profiles.append({'entity_id':eid,'official_domain':domain,'summary':summary,'headquarters':hq,'identity_notes':identity,
            'editing_status':'not established in this research pass' if slug in {'fall-creek','planasa','heritable'} else
                             'advanced breeding documented; do not automatically label CRISPR' if slug=='ohalo' else 'editing capability/program source claims documented',
            'gaps':gaps,'evidence_ids':linked,
            'coverage':research['capability']+'; '+str(len(research['passes']))+' focused follow-up searches; official sources checked; historical and 2025–2026 coverage. '+('Dedicated Deep Research incomplete after rate limits and exhausted quota.' if not research.get('deep_research') else 'Partial Deep Research response saved (output limit reached); follow-up required; unverified leads withheld.')})
        entities.append({'id':eid,'record_type':'entity','entity_type':'company','name':name,'aliases':aliases[slug],
            'status':'unverified','description':'Gene Editing & Advanced Breeding monitoring seed. Inclusion is not proof of editing activity or commercialization.',
            'berry_ids':[],'evidence_ids':linked,'attributes':{'official_domain':domain,'gene_editing_research_ref':'data/imports/gene-editing-2026-10-20/snapshot.json'}})
        if slug in {'hudson-river','heritable'}:
            entities[-1]['attributes'].update(alias_resolution_candidates=['HRB','Hudson River'] if slug=='hudson-river' else ['Heritable'],
                alias_resolution_note='Require explicit company context; ambiguous short names/adjectives are not global aliases.')
    relationships=[]
    def edge(slug,left,right,label,date,keys,programs):
        relationships.append({'id':'rel-gene-'+slug,'subject_id':IDS[left],'object_id':IDS[right],'predicate':'partners_with',
            'label':label,'date':date,'verification':'source claim / awaiting relationship review',
            'evidence_ids':['ev-gene-'+key for key in keys],'program_ids':['program-gene-'+p for p in programs]})
    edge('simplot-psi','simplot','plant-sciences','Strawberry editing alliance','2021-10-28',['simplot-alliance'],['simplot-psi'])
    edge('pairwise-psi','pairwise','plant-sciences','Caneberry editing and germplasm collaboration','2020-04-15',['pairwise-psi'],['pairwise-psi','pairwise-fontana','pairwise-compact'])
    edge('hrb-plantik','hudson-river','plantik','Strawberry heat-tolerance partnership','2026-09-28',['hrb-plantik'],['heat-strawberry'])
    edge('pairwise-hrb','pairwise','hudson-river','Fulcrum–BioMaas license','2026-05-26',['pairwise-hrb'],['pairwise-hrb'])
    program_entities=[{'id':p['id'],'record_type':'entity','entity_type':'breeding_program','name':p['name'],
        'status':'unverified','description':'Research program identity; source claims await analyst review.',
        'berry_ids':p['berry_ids'],'evidence_ids':p['evidence_ids'],
        'attributes':{'gene_editing':p}} for p in programs]
    sources=[]
    for source in checks:
        # Only actual verified article references, never guessed feed endpoints.
        sources.append({'id':'source-gene-'+source['key'],'type':'reference','label':source['publisher']+' · '+source['key'],
            'value':source['url'],'url':source['url'],'canonical_url':source.get('canonical_url') or source['url'],
            'publisher':source['publisher'],'language':source['language'],'source_type':'official_or_partner_page' if source['publisher'] not in {'AgFunderNews','HortiDaily'} else 'trade_press',
            'acquisition_method':'manual_public_page_check','topic_scope':['gene-editing','advanced-breeding'],
            'linked_competitor_ids':by_key.get(source['key'],{}).get('entity_ids',[]),'enabled':False,
            'last_checked_at':source['accessed_at'],'last_successful_check':source['accessed_at'] if source['status']=='readable' else None,
            'last_status':source['status'],'status':source['status'],'feed_status':'RSS/Atom not verified; no feed invented',
            'monitoring_priority':'medium','created_at':'2026-10-21'})
    monitor_path=BASE/'monitor-checks.json'
    if monitor_path.exists():
        for monitor in json.loads(monitor_path.read_text(encoding='utf-8')):
            sources.append({'id':'source-gene-monitor-'+monitor['slug'],'type':'rss',
                'label':'Company monitoring · '+next(c[2] for c in COMPANIES if c[0]==monitor['slug']),
                'publisher':'Google News search / original publishers','language':'en / original publisher language',
                'value':monitor['feed_url'],'url':monitor['feed_url'],'source_type':'news_search',
                'acquisition_method':'existing news_search_rss adapter; original article requires acquisition/review',
                'discovery':{'adapter':'news_search_rss','feed_url':monitor['feed_url'],'item_limit':10,
                             'feed_url_verified_at':monitor['checked_at'][:10],
                             'notes':'Company monitoring independent of topic classification. Broad company/crop query; no automatic Gene Editing tag.'},
                'entity_types':['company'],'berry_ids':[],'region_coverage':['global'],
                'topic_scope':['company-monitoring'],'linked_competitor_ids':[IDS[monitor['slug']]],
                'enabled':monitor['status']=='verified','status':monitor['status'],
                'last_checked_at':monitor['checked_at'],'last_successful_check':monitor['checked_at'] if monitor['status']=='verified' else None,
                'last_status':'ok' if monitor['status']=='verified' else monitor['status'],
                'monitoring_priority':'medium','update_cadence':'weekly','created_at':'2026-10-21'})
    snapshot={'version':'gene-editing-2026-10-20-v1','research_date':'2026-10-20','access_date':'2026-10-21',
        'research_status':'All 11 companies have Perplexity discovery coverage. Dedicated research and cross-company follow-ups remain incomplete; see coverage and evidence gaps below.',
        'companies':profiles,'entities':entities,'programs':programs,'program_entities':program_entities,
        'relationships':relationships,'evidence':evidence,'sources':sources,
        'conflicts':[
            'PSI/PSG registry identity combines names; retain canonical ID and existing dossier pending analyst resolution.',
            'Some Deep Research reports state no Simplot regulator record was found, while the original Defra S4A-210 notice was verified. Original dated notice takes precedence for that specific line; sales remain unverified.',
            'Generic Pairwise text extraction selected related Fontana content on older pages. Evidence excerpts were re-read from the current article-content DOM; the 2020 and January 2026 dates are preserved.',
            'HRB metadata gives 2026-09-25 for older pages; visible article text dates regeneration 2024-02-06 and the Plantik partnership 2026-09-28.',
            'HortiDaily discovery date 2026-10-19 differs from original page publication metadata 2026-10-20; retain original page date.',
            'APHIS-hosted Qi 24-116-02rsr.pdf is an applicant request, not a decision letter. Company claims of exemption remain separately attributed.',
            'Qi small-berry facility and PSG restructuring leads remain in discovery reports, but original JavaScript pages were unreadable. No unsupported blueberry program or legal merger was imported.',
        ]}
    (BASE/'snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print({key:len(snapshot[key]) for key in ('companies','programs','relationships','evidence','sources')})

if __name__=='__main__':
    main()
