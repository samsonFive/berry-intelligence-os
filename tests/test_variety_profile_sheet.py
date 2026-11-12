"""Retained cultivar sheets preserve record meaning and their existing controls."""
from copy import deepcopy
from types import SimpleNamespace

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader
from lxml import html
import pytest

from app.services.variety_workspace import ROLE_LABEL, present_observation


def render(**changes):
    # Exercise the real profile/partials with a minimal shell and no runtime stores.
    shell = """<html><head>{% block head_extra %}{% endblock %}</head><body>
      <main class="variety-sheet-shell">{% include '_breadcrumbs.html' %}
      {% block content %}{% endblock %}</main>{% block scripts %}{% endblock %}</body></html>"""
    env = Environment(loader=ChoiceLoader([DictLoader({'glasshouse_base.html': shell}),
                                          FileSystemLoader('app/templates')]), autoescape=True)
    env.filters.update(us_date=str, humanize_label=lambda value: str(value).replace('_', ' '))
    env.globals['learn_href_for_trait'] = lambda key: '/learn/concepts/firmness' if key == 'trait-firmness' else None
    entity = dict(id='variety-fixture', name='Fixture cultivar', entity_type='variety', berry_ids=[],
                  status='unverified', attributes={}, aliases=[], description='Exact cultivar description')
    context = dict(entity=entity, identity=dict(canonical_name=entity['name'], commercial_names=[],
                    denomination='FIX-1', breeder_code='B-7', aliases=['Commercial fixture'], package_note=''),
                   request=SimpleNamespace(url=SimpleNamespace(path='/entities/variety/variety-fixture'), query_params={}),
                   authoring_mode=False, static_build=False, role_labels=ROLE_LABEL, roles={},
                   grouped_relationships=[], growing_regions=[], observations=[], footprint={},
                   variety_intelligence={}, variety_trait_profile=[], countries_observed=[], retailers_observed=[],
                   rights_published=[], rights_drafts=[], recent_cards=[], recent_intelligence=[],
                   intelligence_timeline={}, investigation_return_href='', breadcrumb_items=[])
    context.update(changes)
    before = deepcopy({key: value for key, value in context.items() if key != 'request'})
    rendered = env.get_template('variety_profile.html').render(**context)
    assert {key: value for key, value in context.items() if key != 'request'} == before
    return html.fromstring(rendered), rendered


def at_rest(node):
    """Native closed details expose their summary, not their secondary contents."""
    node = deepcopy(node)
    for detail in node.xpath('.//details[not(@open)]'):
        for child in list(detail):
            if child.tag != 'summary':
                detail.remove(child)
    return node.text_content()


def test_performance_sheet_keeps_exact_class_status_scope_dates_and_reader():
    rows = []
    for index, classification in enumerate(['fact', 'attributed_claim', '']):
        rows.append(dict(id=f'fact-{index}', trait_chips=[{'id': 'trait-firmness', 'name': 'Firmness'}],
                         statement=f'Exact statement {index} <not markup>', classification=classification,
                         fact_status='disputed', confidence='low', conditions='Trial A only; 20 °C',
                         geography=[{'name': 'Chile', 'href': '/geographies/chile'}],
                         does_not_prove=['Not a universal cultivar trait', 'Not a growing footprint'],
                         published_date='2024-05-03', evidence_id=f'ev-{index}',
                         reader_href=f'/intelligence/ev-{index}', evidence_href=f'/evidence/ev-{index}',
                         fact_href=f'/facts/fact-{index}', source_name='Original supplier',
                         source_type_label='Company self-report', additional_source_count=2))
    tree, text = render(variety_intelligence={'has_any': True, 'groups': [{'label': 'Quality', 'rows': rows}]})
    table = tree.xpath('//table[contains(@class,"variety-performance-sheet")]')[0]
    assert len(table.xpath('./tbody/tr')) == 3
    assert all(len(row.xpath('./th|./td')) == 6 for row in table.xpath('./tbody/tr'))
    for index in range(3):
        row = table.xpath(f'./tbody/tr[@id="fact-fact-{index}"]')[0]
        assert row.get('data-item-id') == f'ev-{index}'
        assert row.xpath(f'.//a[@data-open-reader][@href="/intelligence/ev-{index}"]')
        assert row.xpath('.//a[@href="/learn/concepts/firmness"]')
        for value in ['Disputed', 'low', 'Trial A only; 20 °C', 'Chile', '2024-05-03',
                      'Not a universal cultivar trait', 'Not a growing footprint', 'Company self-report', '+2 more sources']:
            assert value in row.text_content()
        visible = at_rest(row)
        for value in ['Disputed', 'Trial A only; 20 °C', 'Not a universal cultivar trait',
                      'Not a growing footprint', '2024-05-03', 'Original supplier', 'View Fact']:
            assert value in visible
        assert 'Confidence' not in visible and 'Company self-report' not in visible
        assert not row.xpath('.//details[@open]')
        # Preserve summary focus when the legacy data-intel-card click handler bubbles.
        assert row.xpath('.//details/@onclick') == ['event.stopPropagation()']
    assert table.xpath('./tbody/tr[1]/td[3]//span')[0].text == 'Fact'
    assert table.xpath('./tbody/tr[2]/td[3]//span')[0].text == 'Attributed claim'
    assert not table.xpath('./tbody/tr[3]/td[3]//span')
    assert 'UNCLASSIFIED' not in text and 'ATTRIBUTED_CLAIM' not in text
    assert '&lt;not markup&gt;' in text and '<not markup>' not in text


def test_roles_show_only_recorded_parties_and_exact_incoming_basis():
    company = dict(id='company-a', entity_type='company', name='Recorded supplier', href='/entities/company/company-a')
    common = dict(other=company, status='historical', confidence='medium', effective_date='2021-02-03',
                  evidence_ids=['ev-role'])
    incoming = dict(common, predicate='markets', direction='incoming', notes='Territory limited to trial area')
    outgoing = dict(common, predicate='owns', direction='outgoing', notes='OUTGOING_NOT_MARKETER_BASIS')
    tree, _ = render(roles={'marketer': [company]}, grouped_relationships=[incoming, outgoing])
    section = tree.get_element_by_id('roles')
    assert len(section.xpath('.//tbody/tr')) == 1
    assert section.xpath('.//tbody/tr/th')[0].text == 'Marketer'
    assert 'historical' in section.text_content() and '2021-02-03' in section.text_content()
    assert 'Territory limited to trial area' in section.text_content()
    assert 'OUTGOING_NOT_MARKETER_BASIS' not in section.text_content()
    assert section.xpath('.//a[@data-open-reader][@href="/intelligence/ev-role"]')
    empty, _ = render()
    assert 'No company roles recorded.' in empty.get_element_by_id('roles').text_content()
    assert not empty.get_element_by_id('roles').xpath('.//table')


def test_performance_groups_share_one_rectangular_sheet_without_hidden_rows():
    groups = [dict(key=key, label=label, rows=[dict(id=key, trait_chips=[], statement=key)])
              for key, label in [('product_sensory', 'Product / sensory'),
                                 ('postharvest_quality', 'Postharvest / quality')]]
    tree, _ = render(variety_intelligence={'has_any': True, 'groups': groups})
    tables = tree.xpath('//table[contains(@class,"variety-performance-sheet")]')
    # One header/body yields one BerrySheet controller and saved-layout revision.
    assert len(tables) == 1 and len(tables[0].xpath('./thead/tr')) == 1
    assert tables[0].xpath('./thead/tr/th[1]/text()') == ['Trait']
    assert tables[0].xpath('./thead/tr/th[1]/@data-column-label') == ['Performance / Trait']
    assert tables[0].xpath('./thead/tr/th[2]/text()') == ['Group']
    rows = tables[0].xpath('./tbody/tr')
    assert len(rows) == 2 and all(len(row.xpath('./th|./td')) == 6 for row in rows)
    assert [row.xpath('./td[1]/text()')[0] for row in rows] == ['Product / sensory', 'Postharvest / quality']
    assert not tables[0].xpath('.//td[@colspan]|.//th[@colspan]|.//tr[@hidden]')


@pytest.mark.parametrize('prefix', ['confidence=high', ' CONFIDENCE=MEDIUM ', 'confidence=low'])
def test_only_leading_confidence_metadata_is_secondary_while_exact_qualifiers_stay_visible(prefix):
    suffix = ' Territory limited to trial block; not a worldwide supply relationship.'
    raw = prefix + ';' + suffix
    company = dict(id='company-a', entity_type='company', name='Supplier', href='/entities/company/company-a')
    edge = dict(other=company, predicate='markets', direction='incoming', notes=raw,
                status='active', evidence_ids=[])
    tree, _ = render(roles={'marketer': [company]}, grouped_relationships=[edge])
    for section in ['roles', 'network']:
        row = tree.get_element_by_id(section).xpath('.//tbody/tr')[0]
        assert suffix in at_rest(row) and prefix not in at_rest(row)
        info = row.xpath('.//details[@class="variety-row-info"]')[0]
        assert 'open' not in info.attrib and raw in info.text_content()
        assert info.get('onclick') == 'event.stopPropagation()'


def test_unrecognized_confidence_like_text_is_not_stripped():
    raw = 'confidence=high in one territory; material qualifier remains intact'
    company = dict(id='company-a', entity_type='company', name='Supplier', href='/entities/company/company-a')
    edge = dict(other=company, predicate='markets', direction='incoming', notes=raw,
                status='active', evidence_ids=[])
    tree, _ = render(roles={'marketer': [company]}, grouped_relationships=[edge])
    assert raw in at_rest(tree.get_element_by_id('roles').xpath('.//tbody/tr')[0])


def test_empty_sections_and_catalog_identity_explanation_are_secondary():
    entity = dict(id='variety-fixture', name='Fixture cultivar', entity_type='variety', berry_ids=[],
                  status='unverified', aliases=[], description='',
                  attributes={'identity_review': {'source_url': 'https://example.test/catalog', 'source_label': 'Catalog'}})
    tree, _ = render(entity=entity)
    visible = at_rest(tree)
    for phrase in ['No growing locations recorded', 'Add a sourced location', 'No recent intelligence linked',
                   'No company roles recorded', 'Source-backed catalog admission', 'Missing records describe coverage gaps']:
        assert phrase in tree.text_content() and phrase not in visible
    assert not tree.get_element_by_id('roles').xpath('./details[@open]')
    assert tree.xpath('//details[not(@open)]/a[@href="https://example.test/catalog"]')
    assert 'unverified' in visible


def test_observation_sheet_preserves_listing_limits_named_identity_and_pending_state():
    entities = {'variety-fixture': dict(id='variety-fixture', name='Fixture cultivar', entity_type='variety'),
                'company-a': dict(id='company-a', name='Marketer A', entity_type='company'),
                'geo-a': dict(id='geo-a', name='Origin A', entity_type='geography')}
    record = dict(id='ev-listing', title='One shop listing', status='draft', review_state='in_review',
                  source_name='Retail page', source_authority='retailer', verification_state='unverified',
                  does_not_prove='Does not establish market share or growing location',
                  commercial_observation=dict(variety_entity_id='variety-fixture', brand='Pack brand',
                    marketer_entity_id='company-a', origin_geography_id='geo-a', retailer_name='One shop',
                    channel='online', market_country='Market A', observed_at='2023-01-02', price='2.50',
                    currency='GBP', pack_size='400g', promotion='Weekly offer', claims=['Sweet listing claim']))
    pending = present_observation(record, entities=entities, trust='draft (pending review)')
    unknown = present_observation(dict(record, id='ev-unknown', commercial_observation={}), entities=entities, trust='published')
    tree, _ = render(observations=[pending, unknown])
    table = tree.xpath('//table[contains(@class,"variety-observation-sheet")]')[0]
    assert len(table.xpath('./tbody/tr')) == 2
    row = table.xpath('./tbody/tr[@id="obs-ev-listing"]')[0]
    for value in ['Pending review', 'Commercial observation', 'in review', 'Fixture cultivar', 'Pack brand',
                  'Marketer A', 'Origin A', 'Market A', '2023-01-02', 'GBP 2.50', '400g', 'Weekly offer',
                  'Sweet listing claim', 'not trusted Facts', 'Retail page', 'retailer', 'unverified',
                  'Does not establish market share or growing location']:
        assert value in row.text_content()
    assert row.xpath('.//a[@data-open-reader][@href="/intelligence/ev-listing"]')
    assert 'Authority' not in at_rest(row) and 'Verification' not in at_rest(row)
    assert 'Does not establish market share or growing location' in at_rest(row)
    unknown_row = table.xpath('./tbody/tr[2]')[0]
    assert 'Cultivar not named' in at_rest(unknown_row)
    assert 'does not mean the variety is unknown globally' not in at_rest(unknown_row)
    assert 'does not mean the variety is unknown globally' in unknown_row.text_content()
    assert 'No pack/price/origin' not in unknown_row.text_content()
    assert not table.xpath('.//details[@open]')
    assert all(value == 'event.stopPropagation()' for value in table.xpath('.//details/@onclick'))
    static, _ = render(observations=[unknown], static_build=True)
    assert static.xpath('//tr[@id="obs-ev-unknown"]//a[@href="/evidence/ev-unknown"]')
    assert not static.xpath('//tr[@id="obs-ev-unknown"]//*[@data-open-reader]')


def test_profile_keeps_tabs_return_governed_controls_and_existing_trait_columns():
    tree, text = render(authoring_mode=True, is_watched=True,
        investigation_return_href='/app/landscape?ctx_v=1&focus=variety-fixture',
        growing_regions=[dict(country='Chile', locality='Trial block 2', activity='Trial', status='unreviewed',
                            basis='User annotation', observed_on='2023-06-01',
                            scope_note='Single trial only', source_url='https://example.test/trial')],
        variety_trait_profile=[dict(trait_name='firmness', value='Firm', conditions='Owner trial only',
                                   evidence_ids=['ev-trait'], is_claim=True, asserted_by='Owner A')])
    styles = tree.xpath('//link[@rel="stylesheet"]/@href')
    assert styles.index('/static/variety_workspace.css?v=16') < styles.index('/static/variety_profile_sheet.css?v=1')
    assert tree.xpath('//div[contains(@class,"variety-profile-sheet-page")]')
    assert tree.xpath('//a[@href="/app/landscape?ctx_v=1&focus=variety-fixture"]')
    assert tree.xpath('//form[@action="/watches/toggle"]//input[@name="action"][@value="remove"]')
    assert tree.xpath('//a[@href="/varieties/catalog/variety-fixture/edit"]')
    assert tree.xpath('//a[@href="/entities/variety/compare?ids=variety-fixture"]')
    for target in ['roles', 'recent-intelligence', 'growing-regions', 'rights', 'variety-intelligence',
                   'commercial-footprint', 'intelligence-timeline']:
        assert tree.xpath(f'//nav[@aria-label="Variety sections"]/a[@href="#{target}"]')
        assert tree.get_element_by_id(target) is not None
    growing = tree.get_element_by_id('growing-regions')
    for value in ['Trial block 2', 'Unreviewed', 'User annotation', '2023-06-01', 'Single trial only',
                  'Retail markets and rights territories do not establish where this variety grows']:
        assert value in growing.text_content()
    assert growing.xpath('.//a[@href="https://example.test/trial"]')
    # These exact existing headings determine the saved trait-table layout key.
    assert tree.xpath('//table[@class="trait-table"]/thead/tr/th/text()') == ['Trait', 'Reported value', 'Source of claim', 'Asserted by']
    assert 'Owner/marketer claim' in text and 'Owner trial only' in text
    assert text.count('/static/variety_workspace.js?v=13') == 1
