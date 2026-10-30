"""Reviewed focused defaults, each owned by one discovery workflow."""
ROWS = (
 ('variety-awards','Variety awards and recognition','all','global','week',
  '(cultivar OR variety OR breeder) AND (award OR medal OR winner OR "Superior Taste Award" OR "Innovation Award")','en-US','US','US:en'),
 ('variety-news','Variety launches, trials and licensing','all','global','week',
  '(cultivar OR variety OR varieties OR breeder) AND (launch OR released OR trial OR licensing OR commercial)','en-US','US','US:en'),
 ('variety-patent-news','Variety patents and plant rights','all','global','week',
  '(cultivar OR variety OR breeder) AND (patent OR PBR OR CPVO OR PVPO OR "plant variety protection" OR "plant breeders rights")','en-US','US','US:en'),
 ('floricane-blackberry','Floricane developments','blackberry','global','today_google',
  '(floricane OR "second-year canes") AND (cultivar OR variety OR breeding OR trial OR licensing OR release)','en-US','US','US:en'),
 ('primocane-blackberry','Primocane developments','blackberry','global','today_google',
  '(primocane OR "first-year canes" OR "double cropping") AND (cultivar OR breeding OR trial OR licensing OR release)','en-US','US','US:en'),
 ('primocane-raspberry','Primocane and autumn-fruiting developments','raspberry','global','today_google',
  '(primocane OR "autumn fruiting" OR "fall bearing" OR remontant) AND (cultivar OR breeding OR trial OR licensing)','en-US','US','US:en'),
 ('strawberry-resistance','Disease-resistant varieties','strawberry','global','today_google',
  '(Neopestalotiopsis OR Phytophthora OR Botrytis OR "disease resistance") AND (cultivar OR breeding OR resistance OR trial)','en-US','US','US:en'),
 ('strawberry-flowering','Flowering habit and production season','strawberry','global','week',
  '("day neutral" OR day-neutral OR "short day" OR everbearing OR remontant) AND (cultivar OR breeding OR trial OR commercial)','en-US','US','US:en'),
 ('blueberry-warm-climate','Warm-climate adaptation','blueberry','global','week',
  '("low chill" OR low-chill OR "zero chill" OR evergreen OR "heat tolerance") AND (cultivar OR breeding OR trial OR commercial)','en-US','US','US:en'),
 ('postharvest','Postharvest traits','all','global','week',
  '(firmness OR "shelf life" OR postharvest OR "fruit reversion") AND (cultivar OR genetics OR trial OR breeder)','en-US','US','US:en'),
 ('propagation','Propagation and plant supply','all','global','week',
  '("tissue culture" OR "clean plants" OR "virus indexed" OR "nursery capacity" OR "plant shortage") AND (trial OR production OR nursery OR commercial)','en-US','US','US:en'),
 ('raspberry-polish','Polish raspberry breeding','raspberry','europe','week',
  '(malina OR maliny OR malin) AND (odmiana OR odmiany OR odmian OR hodowla OR licencja)','pl-PL','PL','PL:pl'),
 ('berries-portuguese','Brazilian berry developments','all','americas','week',
  '(morango OR mirtilo OR framboesa OR "amora-preta") AND (cultivar OR variedade OR melhoramento OR licenciamento)','pt-BR','BR','BR:pt'),
)


def metadata(key):
    for slug,label,berry,region,group,topic,hl,gl,ceid in ROWS:
        if key.removesuffix(':30d') == 'monitor:' + slug:
            from app.services.collection_settings import compile_custom_query
            return dict(compile_custom_query(query_input=topic,input_mode='advanced',scope_berry=berry,scope_region=region,search_language=hl),
                        label=label, group=group, hl=hl,gl=gl,ceid=ceid,search_language=hl)
    return None


def queries(group):
    from app.services.industry_pulse.matrix import PulseQuery
    result=[]
    for slug,*_ in ROWS:
        row=metadata('monitor:'+slug)
        if row['group'] == group:
            query=PulseQuery(id='monitor:'+slug,text=row['text'],berry=row['berry'],geography=row['geography'],
                topic='focused_monitor',kind='scoped_monitor',hl=row['hl'],gl=row['gl'],ceid=row['ceid'])
            result.append(query.with_window('30d') if group=='today_google' else query)
    return result
