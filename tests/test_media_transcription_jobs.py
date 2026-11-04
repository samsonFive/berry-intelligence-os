import json
import subprocess

from app.services.media_transcription_jobs import run_job, read_status


def test_explicit_caption_job_persists_running_deferred_and_restart_attempts(tmp_path):
    folder = tmp_path / 'discovered_media'
    folder.mkdir()
    key = 'discovered-recording'
    (folder / (key + '.json')).write_text(json.dumps({'id': key, 'media_format': 'video'}))
    def timeout(command, **kwargs):
        assert read_status(tmp_path, key)['state'] == 'running'
        assert kwargs['timeout'] == 1
        raise subprocess.TimeoutExpired(command, 1)
    first = run_job(tmp_path, key, timeout=1, executor=timeout)
    assert first['state'] == 'deferred' and first['attempt'] == 1
    assert first['paid_calls'] == 0 and not first['speech_to_text']
    def worker(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, json.dumps({'status': 'ok', 'segment_count': 4, 'language': 'es', 'partial': True}), '')
    second = run_job(tmp_path, key, executor=worker)
    assert second['state'] == 'partial' and second['attempt'] == 2
    assert read_status(tmp_path, key)['language'] == 'es'
    assert not (folder / '_media').exists()


def test_caption_challenge_is_disclosed_without_token_bearing_error(tmp_path):
    from app.services.media_transcription import transcribe_discovered_item
    def blocked(video_id):
        raise RuntimeError('Sign in to confirm you are not a bot: https://example.org/?token=PRIVATE')
    outcome = transcribe_discovered_item(tmp_path, {'id': 'discovered-video', 'media_format': 'video',
        'raw_metadata': {'yt_video_id': 'abcdefghijk'}}, max_tier=2, caption_info_fetcher=blocked)
    assert outcome.diagnostics['caption_reason'] == 'platform_access_blocked'
    assert 'PRIVATE' not in json.dumps(outcome.diagnostics)
