from app.services.social_intelligence.presentation import player

def row(source='youtube',native='abcdefghijk',url='https://www.youtube.com/watch?v=abcdefghijk'):
 return dict(source=source,native_id=native,canonical_url=url,record_role='original',mode='live',media=[])

def test_player_missing_media_is_not_missing_video_and_no_untrusted_html():
 assert player(row())['url'].startswith('https://www.youtube-nocookie.com/embed/abcdefghijk')
 assert player(row(url='https://youtube.com.evil.org/watch?v=abcdefghijk')) is None
 assert player(row(native='differentID')) is None
 assert player({**row(),'mode':'fixture'}) is None
 assert player({**row(),'record_role':'reply'}) is None
 assert player({**row(),'media':[{'state':'deleted'}]}) is None

def test_linkedin_native_content_identity_and_tiktok_player():
 r=row('linkedin','123','https://www.linkedin.com/posts/example-activity-123-test')
 assert player({**r,'source_embed_urn':'urn:li:ugcPost:456'})['url'].endswith('urn:li:ugcPost:456')
 assert player({**r,'source_embed_urn':'javascript:alert(1)'}) is None
 assert player(row('tiktok','123','https://www.tiktok.com/@example/video/123'))['shape']=='portrait'
 assert player(row('tiktok','456','https://www.tiktok.com/@example/video/123')) is None
