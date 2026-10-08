"""Bounded literal proposals, not a qualified Atomic Evidence extractor.

No network, models, actions, configuration writes or registry creation. Rules
retain exact original spans; unsupported language/context stays uncertain.
"""
import re
import hashlib
from functools import lru_cache

VERSION = 'social-literal-4'
OTHER_FOODS = ['banana','bananas','cashew','cashews','yogurt','granola',
               'plátano','plátanos','anacardo','anacardos','iogurte','castanha','castanhas',
               '香蕉','腰果','酸奶','バナナ','カシューナッツ','ヨーグルト']
VOCAB = {
 'berry-blueberry': {'en':['blueberry','blueberries'], 'es':['arándano','arándanos'], 'pt':['mirtilo','mirtilos'], 'zh':['蓝莓','藍莓'], 'ja':['ブルーベリー']},
 'berry-strawberry': {'en':['strawberry','strawberries'], 'es':['fresa','fresas','frutilla','frutillas'], 'pt':['morango','morangos'], 'zh':['草莓'], 'ja':['イチゴ','いちご','苺']},
 'berry-raspberry': {'en':['raspberry','raspberries'], 'es':['frambuesa','frambuesas'], 'pt':['framboesa','framboesas'], 'zh':['树莓','樹莓','覆盆子'], 'ja':['ラズベリー']},
 'berry-blackberry': {'en':['blackberry','blackberries'], 'es':['mora','moras','zarzamora','zarzamoras'], 'pt':['amora','amoras','amora-preta','amoras-pretas'], 'zh':['黑莓'], 'ja':['ブラックベリー']},
}
# Regional vocabulary is reviewable and intentionally small. Five-language QA
# is a pilot, not an assertion of worldwide semantic coverage.
ASPECTS = {
 'flavor': {'positive':['sweet','tasty','dulce','doce','甘い','甜'], 'negative':['bland','sour','insípido','sem sabor','味が薄い','寡淡']},
 'texture': {'positive':['crunchy','firm','crujiente','crocante','カリカリ','脆'], 'negative':['mushy','soft','blando','mole','柔らかすぎ','软']},
 'size': {'positive':['huge','large','grande','大きい','大颗'], 'negative':['tiny','pequeño','pequeno','小さい','小颗']},
 'quality': {'positive':['fresh','fresco','新鮮','新鲜'], 'negative':['mold','mould','moho','bolor','カビ','发霉']},
 'value': {'positive':['good value','barato','お買い得','便宜'], 'negative':['expensive','caro','高い','贵']},
 'packaging': {'positive':['recyclable','reciclable','reciclável','リサイクル','可回收'], 'negative':['leaking','漏れ','漏液']},
 'availability': {'positive':['in stock','disponible','在庫あり','有货'], 'negative':['out of stock','agotado','esgotado','売り切れ','缺货']},
 'usage': {'positive':['snack','merienda','lanche','おやつ','零食'], 'negative':[]},
}
RETAILERS = {'Costco':['costco','コストコ','好市多'], 'Kroger':['kroger'], 'Whole Foods':['whole foods','wholefoods']}
RELATIONS = {
 'wishes-stocked-by':['wish','ojalá','tomara','扱ってほしい','希望'],
 'unavailable-at':['out of stock','no había','esgotado','売り切れ','缺货'],
 'bought-at':['bought','compré','comprei','買った','买了'],
 'found-at':['found','encontré','encontrei','見つけた','发现'],
 'sold-by':['sold by','vendido por','販売','出售'],
 'compared-with':['compared','comparado','比較','相比'],
}

@lru_cache(maxsize=8192)
def term_pattern(term):
    latin = bool(re.fullmatch(r'[\w\s-]+', term) and all(ord(c) < 1000 for c in term))
    pattern = (r'(?<![A-Za-zÀ-Ͽ0-9_])' + re.escape(term) + r'(?![A-Za-zÀ-Ͽ0-9_])') if latin else re.escape(term)
    return re.compile(pattern,re.I)

def spans(text, term):
    return [{'start':m.start(), 'end':m.end(), 'text':m.group()} for m in term_pattern(term).finditer(text)]

def analyze(item, entities):
    from .media_extraction import media_observations
    text = item['text']
    # Technology posts often mention the device several sentences away from
    # "BlackBerry". Match specific product/security context, not generic words
    # like patents, price or technology that also occur in berry-industry posts.
    blackberry_mentions=spans(text,'blackberry')
    tech_context=bool(re.search(r'\b(?:smartphones?|phones?|iphones?|ios|touchscreens?|android|qwerty|keyboards?|bb10|cybersecurity|qnx|blackberry\s+(?:limited|passport|keyone|key2|z10|z30|bold|curve|stock|shares|\d{3,4}))\b|\$BB\b|\bNYSE\s*:\s*BB\b',text,re.I))
    excluded=bool(blackberry_mentions and tech_context)
    # Preserve an explicit plural fruit mention even in a mixed device/food post.
    explicit_blackberries=bool(spans(text,'blackberries') or re.search(r'\bblackberry\s+(?:jam|bush|plant|fruit|cobbler|pie|harvest)\b|\b(?:picked|ate|eating|harvested)\s+(?:a\s+)?blackberry\b',text,re.I))
    nonfruit = bool(re.search(r'raspberry\s+pi\b|perfume that smells|need a perfume|(?:wine|coffee).{0,35}(?:notes of|notes:)', text, re.I))
    berries = sorted(b for b, packs in VOCAB.items() if any(spans(text,t) for terms in packs.values() for t in terms))
    if excluded and not explicit_blackberries:
        berries = [b for b in berries if b != 'berry-blackberry']
    if nonfruit:
        berries = []
    aspects = []
    for aspect, polarities in ASPECTS.items():
        hits = [{'polarity':p, 'span':s, 'basis':'original_text'} for p, terms in polarities.items() for t in terms for s in spans(text,t)]
        if hits:
            for hit in hits:
                s=hit['span'];before=text[max(0,s['start']-12):s['start']];after=text[s['end']:s['end']+15]
                if re.search(r'\b(not|no|não)\s+$|不$',before,re.I) or 'ない' in after:
                    hit['polarity']='uncertain' # Simple negation must not become confident praise.
            signs = {h['polarity'] for h in hits}
            competing_food=False
            for hit in hits:
                start=hit['span']['start'];end=hit['span']['end'];boundaries='.;!?。；！？，,、\n'
                left=max([text.rfind(c,0,start) for c in boundaries])+1
                right=min([i for c in boundaries if (i:=text.find(c,end))>=0] or [len(text)])
                if any(spans(text[left:right],food) for food in OTHER_FOODS):
                    competing_food=True;hit['target_basis']='Other food in descriptor clause; berry attribution requires review'
            aspects.append({'aspect':aspect, 'sentiment':'uncertain' if competing_food or 'uncertain' in signs else 'mixed' if len(signs)>1 else next(iter(signs)), 'target':berries[0] if len(berries)==1 and not competing_food else None, 'evidence':hits})
    retailers = []
    for label, aliases in RETAILERS.items():
        for alias in aliases:
            for s in spans(text,alias):
                # Clause context prevents a wish about Kroger becoming a Costco sighting.
                start = max(text.rfind('.',0,s['start']), text.rfind(';',0,s['start']), text.rfind('!',0,s['start']),text.rfind('。',0,s['start']),text.rfind('；',0,s['start']),text.rfind('！',0,s['start']))+1
                stop = min([i for c in '.;!。；！' if (i:=text.find(c,s['end']))>=0] or [len(text)])
                clause = text[start:stop]
                relation = next((r for r,terms in RELATIONS.items() if any(spans(clause,t) for t in terms)), 'uncertain-mention')
                matches = [e['id'] for e in entities if e.get('name','').casefold() in [a.casefold() for a in aliases]]
                retailers.append({'name':label, 'entity_id':matches[0] if len(matches)==1 else None, 'relation':relation, 'span':s, 'basis':'original_text', 'review':'proposed'})
    links, candidates = [], []
    bases = [('text',text,None)] + [('packaging_label',lit['text'],{'media_id':m['id'],'locator':lit['locator'], 'method':lit['method'], 'confidence':lit['confidence']}) for m in item['media'] if m['state']=='available' for lit in m['literal'] if lit['method'] in ('human_label','ocr')]
    for basis, content, locator in bases:
        by_name = {}
        for e in entities:
            if e.get('entity_type') not in ('company','brand','variety','breeding_program'):
                continue
            names = [e.get('name','')] + [a if isinstance(a,str) else a.get('name','') for a in e.get('aliases',[])]
            for name in names:
                if len(name) >= 4 and spans(content,name):
                    by_name.setdefault(name.casefold(), []).append(e)
        for name, choices in by_name.items():
            ids = {e['id'] for e in choices}
            e = choices[0]
            provisional = e.get('status') in ('unverified','provisional') or e.get('attributes',{}).get('identity_status') in ('provisional','unresolved')
            # Single generic cultivar words are deliberately not auto-linked.
            ambiguous = len(ids)!=1 or provisional or (e.get('entity_type')=='variety' and len(name.split())==1 and len(name)<9)
            hit = {'name':name,'basis':basis,'locator':locator,'span':spans(content,name)[0], 'review':'proposed'}
            if ambiguous or not berries:
                candidates.append({**hit,'candidate_ids':sorted(ids)})
            else:
                links.append({**hit,'entity_id':e['id'],'confidence':0.8})
    # A brand substring inside an explicit cultivar name does not independently
    # establish a brand observation or a brand→cultivar registry relationship.
    links=[link for link in links if not any(link is not other and link['basis']==other['basis'] and link['locator']==other['locator'] and link['span']['start']>=other['span']['start'] and link['span']['end']<=other['span']['end'] and len(link['name'])<len(other['name']) for other in links)]
    concepts = sorted({a['aspect'] for a in aspects})
    return {'version':VERSION,'relevance':'relevant' if berries else 'excluded-phone' if excluded else 'excluded-nonfruit' if nonfruit else 'needs-review',
            'berry_ids':berries,'aspects':aspects,'retailers':retailers,'entity_links':links,'candidates':candidates,'concepts':concepts,
            'media_observations':media_observations(item),
            'content_fingerprint':hashlib.sha256(' '.join(text.casefold().split()).encode()).hexdigest(),
            'limitations':['Literal rules only; negation, irony, homonyms and unnamed targets require review.','Image appearance never establishes cultivar; unavailable video is not analyzed.']}
