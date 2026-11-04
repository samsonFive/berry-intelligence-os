"""Verified teaching defaults retain source scope and user-owned lesson media."""
from copy import deepcopy
from html import unescape
from types import SimpleNamespace

import pytest

from app import main
from app.services import learner, learner_visuals


@pytest.mark.parametrize('slug', ['plasticulture', 'spotted-wing-drosophila', 'botrytis'])
def test_source_licensed_photos_render_with_their_own_rights_and_teaching_limits(slug):
    concept = learner.concept_by_slug(slug)
    photo = concept['teaching_figure']
    html = main.templates.env.get_template('learn_workspace_concept.html').render(
        request=SimpleNamespace(url=SimpleNamespace(path='/learn/'+slug)), concept=concept,
        authoring_mode=False, static_build=True, return_to='/learn', related=[],
        related_intelligence={'rows': []}, berry_notes={'has_any': False})
    text = unescape(html)
    assert photo['image_url'] in text and photo['alt'] in text
    assert photo['url'] in text and photo['license_url'] in text
    assert photo['caption'] in text and photo['attribution'] in text
    assert 'loading="lazy"' in html and 'referrerpolicy="no-referrer"' in html
    assert '<iframe' not in html
    assert photo['verified_at'] == '2026-11-04'
    assert 'does not establish' in photo['caption'] or 'cannot diagnose' in photo['caption']
    if slug == 'botrytis':
        assert '/330px-' in photo['image_url'] and photo['license'] == 'CC BY-SA 3.0'
    if slug == 'spotted-wing-drosophila':
        assert photo['license'] == 'CC BY 3.0 DE'
        assert 'Females lack these spots' in photo['caption']
    if slug == 'plasticulture':
        assert photo['license'].startswith('Public domain')
        assert 'production calendar' in photo['caption']


def test_new_photo_defaults_leave_every_saved_field_and_media_item_unchanged():
    for slug in learner_visuals.CURRICULUM_PHOTOS:
        raw = deepcopy(learner.concept_by_slug(slug))
        raw.update(summary='User summary', what_is_it='User explanation',
                   history=[{'by': 'User', 'note': 'Keep this history'}],
                   media=[{'kind': 'photo', 'url': 'https://example.org/my-source',
                           'caption': 'User caption', 'publisher': 'User attribution',
                           'image_url': 'https://example.org/my-photo.jpg'}])
        before = deepcopy(raw)
        shown = learner_visuals.presentation(raw)
        assert raw == before
        assert all(shown[key] == value for key, value in before.items() if key != 'teaching_figure')
        assert learner_visuals.presentation(shown) == shown
        shown['teaching_figure']['caption'] = 'Temporary presentation edit'
        assert learner_visuals.CURRICULUM_PHOTOS[slug]['caption'] != 'Temporary presentation edit'
