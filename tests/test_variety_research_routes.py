from types import SimpleNamespace

from fastapi.testclient import TestClient


def setup(monkeypatch,tmp_path):
    from app import main
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path/'inbox')
    monkeypatch.setattr(main,'DATA_DIR',tmp_path/'data')
    return main,TestClient(main.app)


def test_public_research_get_is_inert_and_post_uses_only_the_entered_query(monkeypatch,tmp_path):
    from app import variety_research_routes as routes
    main,client=setup(monkeypatch,tmp_path)
    calls=[]
    class Search:
        def search(self,query,**kwargs):
            calls.append((query,kwargs))
            return SimpleNamespace(hits=[SimpleNamespace(url='https://breeder.org/sheet',title='Rafiki <script>bad</script>',snippet='Rafiki raspberry Mediterranean hydroponics',published_date=None),SimpleNamespace(url='javascript:bad',title='Unsafe',snippet='no',published_date=None)])
    monkeypatch.setattr(routes,'search_client',lambda:Search())
    assert client.get('/varieties/research?q=Rafiki').status_code==200 and not calls
    response=client.post('/varieties/research',data={'query':'Rafiki raspberry technical sheet'})
    assert response.status_code==200
    assert calls==[('Rafiki raspberry technical sheet',{'max_results':10})]
    assert 'javascript:bad' not in response.text and '<script>bad</script>' not in response.text
    assert 'Send to publication review' in response.text and 'Unreviewed search result' in response.text
    assert not list((tmp_path/'data').rglob('*.json'))
    assert client.post('/varieties/research',data={'query':'Rafiki'},headers={'origin':'https://elsewhere.org'}).status_code==403


def test_public_search_suppresses_name_collisions_and_keeps_native_crop_context():
    from app.variety_research_routes import relevant_hit
    target=dict(name='Rafiki',aliases=[],berry_ids=['berry-raspberry'])
    assert not relevant_hit(SimpleNamespace(title='Rafiki film',snippet='Cinema review',url='https://film.org/rafiki'),query='Rafiki raspberry',target=target)
    assert relevant_hit(SimpleNamespace(title='Rafiki malina',snippet='Nowa odmiana malin',url='https://breeder.org/rafiki'),query='Rafiki raspberry',target=target)
    assert relevant_hit(SimpleNamespace(title='Rafiki',snippet='',url='https://breeder.org/rafiki'),query='Rafiki raspberry',target=target,known_hosts={'breeder.org'})


def test_view_preferences_are_scoped_to_the_authenticated_analyst(monkeypatch,tmp_path):
    main,client=setup(monkeypatch,tmp_path)
    monkeypatch.setattr(main,'session_username',lambda request:request.headers.get('x-test-actor','one'))
    payload=dict(revision=0,widths={'name':320},order=['name','berry'],hidden=['berry'],filters={})
    assert client.post('/api/varieties/view-state/catalog',json=payload).status_code==200
    assert client.get('/api/varieties/view-state/catalog').json()['widths']=={'name':320}
    assert client.get('/api/varieties/view-state/catalog',headers={'x-test-actor':'two'}).json()['revision']==0
    assert client.post('/api/varieties/view-state/catalog',json=payload).status_code==409
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    assert client.get('/api/varieties/view-state/catalog').status_code==403
    assert client.post('/api/varieties/view-state/catalog',json=payload).status_code==403


def test_remove_restore_preserves_the_source_record_and_catalog_metadata(monkeypatch,tmp_path):
    from app.services.variety_catalog_management import canonical_record
    main,client=setup(monkeypatch,tmp_path)
    row=canonical_record(dict(id='candidate-one',candidate_name='Sourceberry',berry_id='berry-blueberry',identity_state='distinct',status='proposed',source_tier='tier_1_breeder_catalog',source_url='https://breeder.org/sourceberry'),varieties=[],actor='analyst',authorization='explicit test action')
    repo=main.get_repositories(main.DATA_DIR,main.SCHEMAS_DIR).entities;repo.create(row)
    assert client.post('/varieties/'+row['id']+'/catalog-status',data={'action':'remove'},follow_redirects=False).status_code==303
    removed=repo.get(row['id']);assert removed['attributes']['catalog_removed'] and removed['attributes']['identity_review']==row['attributes']['identity_review']
    assert not main.living_catalog()
    assert client.post('/varieties/'+row['id']+'/catalog-status',data={'action':'restore'},follow_redirects=False).status_code==303
    assert len(main.living_catalog())==1 and repo.get(row['id'])['status']=='unverified'
