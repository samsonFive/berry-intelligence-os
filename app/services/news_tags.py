"""Private, durable subject tags. Classification never changes source trust.

SQLite transactions arbitrate duplicate creation and manual/background races.
Automatic decisions and overrides are separate rows; neither overwrites the other.
"""
from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import unicodedata
from uuid import uuid4

from app.services.gene_editing import classify as genetics_classify
from app.services.analyst_state_io import serialized_write

VERSION = 'news-tags-1'
SEEDS = {
    'markets': ('Markets', 'Supply, demand, prices, trade flows, market access, production and export outlooks.'),
    'gene-editing': ('Gene Editing', 'Agricultural genome editing, CRISPR, base and prime editing, related policy and IP.'),
    'advanced-breeding': ('Advanced Breeding', 'Genomic selection, marker-assisted, AI-assisted and speed breeding systems.'),
    'agtech': ('AgTech', 'Agricultural robotics, automation, sensors, digital agriculture and growing technology.'),
    'retail': ('Retail', 'Retailers, stores, online channels, assortment, merchandising and shopper activity.'),
    'corporate': ('Corporate', 'Acquisitions, financing, leadership, ownership, partnerships, licensing and company expansion.'),
    'weather': ('Weather', 'Weather events, growing conditions, forecasts and crop or logistics impacts.'),
    'genetics': ('Genetics', 'Breeding programs, germplasm, cultivars, varieties and inherited traits.'),
    'sustainability': ('Sustainability', 'Resource use, emissions, waste, packaging, biodiversity and environmental practices.'),
}
TERMS = {
    'markets': r'export\w*|import\w*|prices?|supply|demand|tariffs?|trade flows?|market access|production outlook|shortage\w*',
    'agtech': r'robots?|robotics|automation|sensors?|digital agriculture|precision agriculture|growing software|automated harvesting',
    'retail': r'retail\w*|supermarkets?|grocery|groceries|merchandising|shopper\w*|store shelves|assortment|online stores?',
    'corporate': r'acqui\w*|merger\w*|financing|funding round|appointed|chief executive|CEO|partnership\w*|licensing|license agreement|company expansion',
    'weather': r'frost\w*|drought\w*|flood\w*|heatwave\w*|heat wave\w*|hail\w*|rainfall|weather|hurricane\w*|growing conditions',
    'genetics': r'breed\w*|germplasm|cultivars?|variet(?:y|ies)|genetic\w*|inherited traits|CRISPR|genome editing',
    'sustainability': r'sustainab\w*|emissions?|carbon footprint|biodiversity|recycl\w*|packaging|water conservation|food waste|environmental resource',
}


def normalized(name):
    return ' '.join(unicodedata.normalize('NFKC', str(name)).casefold().split())


def stamp():
    return datetime.now(UTC).isoformat()


def exists(inbox_dir):
    return (Path(inbox_dir) / 'news_workspace' / 'tags.sqlite3').exists()


@contextmanager
def database(inbox_dir, readonly=False):
    folder = Path(inbox_dir) / 'news_workspace'
    if readonly:
        db = sqlite3.connect((folder / 'tags.sqlite3').resolve().as_uri() + '?mode=ro', uri=True, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            db.close()
        return
    folder.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(folder / 'tags.sqlite3', timeout=30)
    db.row_factory = sqlite3.Row
    try:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS tags(id TEXT PRIMARY KEY, name TEXT, normalized TEXT UNIQUE,
          description TEXT, version INTEGER DEFAULT 1, matcher_name TEXT);
        CREATE TABLE IF NOT EXISTS automatic(article TEXT, tag TEXT, fingerprint TEXT, present INTEGER,
          rationale TEXT, classified_at TEXT, classifier_version TEXT, definition_version INTEGER,
          PRIMARY KEY(article,tag));
        CREATE TABLE IF NOT EXISTS overrides(article TEXT, tag TEXT, present INTEGER, actor TEXT,
          updated_at TEXT, PRIMARY KEY(article,tag));
        CREATE TABLE IF NOT EXISTS audit(article TEXT, tag TEXT, action TEXT, actor TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS preferences(actor TEXT PRIMARY KEY, selection TEXT, mode TEXT);
        CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY CHECK(id=1), status TEXT, processed INTEGER,
          total INTEGER, error TEXT, updated_at TEXT);
        ''')
        if 'matcher_name' not in {row[1] for row in db.execute('PRAGMA table_info(tags)')}:
            db.execute('ALTER TABLE tags ADD COLUMN matcher_name TEXT')
            db.execute('UPDATE tags SET matcher_name=name')
        for key, (name, description) in SEEDS.items():
            db.execute('INSERT OR IGNORE INTO tags(id,name,normalized,description,matcher_name) VALUES(?,?,?,?,?)',
                       (key, name, normalized(name), description, name))
        db.commit()
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def catalog(inbox_dir):
    if not exists(inbox_dir):
        return [dict(id=k, name=v[0], description=v[1], version=1) for k, v in SEEDS.items()]
    with database(inbox_dir, readonly=True) as db:
        return [dict(row) for row in db.execute('SELECT * FROM tags ORDER BY name COLLATE NOCASE')]


def create(inbox_dir, name, description=''):
    name = ' '.join(unicodedata.normalize('NFKC', str(name)).split())
    description = str(description).strip()
    if not name or len(name) > 80 or len(description) > 2000:
        raise ValueError('Use a tag name of 1–80 characters and a description of at most 2000 characters.')
    with database(inbox_dir) as db:
        db.execute('INSERT OR IGNORE INTO tags(id,name,normalized,description,matcher_name) VALUES(?,?,?,?,?)',
                   ('tag-' + uuid4().hex, name, normalized(name), description, name))
        return dict(db.execute('SELECT * FROM tags WHERE normalized=?', (normalized(name),)).fetchone())


def update(inbox_dir, tag_id, name, description):
    name = ' '.join(unicodedata.normalize('NFKC', str(name)).split())
    description = str(description).strip()
    if not name or len(name) > 80 or len(description) > 2000:
        raise ValueError('Use a name of 1–80 characters and a description of at most 2000 characters.')
    with database(inbox_dir) as db:
        old = db.execute('SELECT * FROM tags WHERE id=?', (tag_id,)).fetchone()
        if old is None:
            raise ValueError('Tag is unavailable.')
        duplicate = db.execute('SELECT id FROM tags WHERE normalized=? AND id!=?', (normalized(name), tag_id)).fetchone()
        if duplicate:
            raise ValueError('Use the existing tag with this name.')
        changed = description != old['description']
        db.execute('UPDATE tags SET name=?,normalized=?,description=?,version=version+? WHERE id=?',
                   (name, normalized(name), description, int(changed), tag_id))
        return changed


def text(record):
    from app.services.source_body import article_full_text, clean_reader_text
    article = record.get('article') or {}
    body = ' '.join(str(article.get(k) or '') for k in ('body', 'text', 'content', 'body_text')) if isinstance(article, dict) else str(article)
    return ' '.join(str(record.get(k) or '') for k in ('title', 'summary', 'supporting_excerpt', 'transcript_excerpt')) + ' ' + clean_reader_text(article_full_text(record) or body)


def decision(record, tag):
    content = text(record)
    key = tag['id']
    customized_seed = key in SEEDS and tag.get('description', '') != SEEDS[key][1]
    if customized_seed:
        key = ''  # A revised definition replaces the shipped seed vocabulary.
    if key in {'gene-editing', 'advanced-breeding'}:
        result = genetics_classify({**record, 'supporting_excerpt': content})
        if key in result['topics']:
            return True, result['excerpt'][:700]
        if key == 'advanced-breeding':
            match = re.search(r'\b(?:speed breeding|AI-assisted breeding|AI-driven breeding)\b', content, re.I)
            if match:
                return True, content[max(0, match.start()-100):match.end()+200]
        return False, ''
    pattern = TERMS.get(key)
    if pattern is None:
        # User definitions extend the existing deterministic terminology matcher.
        # Name-only creation works, including ordinary inflections (labor/labour).
        stop = {'about', 'these', 'those', 'their', 'which', 'where', 'articles', 'article', 'related', 'relevant', 'including', 'include', 'coverage', 'developments', 'should', 'would', 'classification'}
        words = [w for w in re.findall(r'[\w-]+', tag['description']) if len(w) > 3 and w.casefold() not in stop]
        matcher_name = tag.get('matcher_name') or tag['name']
        terms = words if customized_seed and words else [matcher_name, *words]
        if normalized(matcher_name) in {'labor', 'labour'}:
            terms += ['labor', 'labour', 'workers', 'workforce', 'wages', 'employment']
        pattern = '|'.join(re.escape(t) + r'\w*' for t in terms)
    match = re.search(r'\b(?:' + pattern + r')\b', content, re.I)
    return (bool(match), content[max(0, match.start()-100):match.end()+200] if match else '')


def effective(record, tags, automatic=None, overrides=None):
    key = str(record.get('id') or '')
    result = []
    legacy = genetics_classify(record)['topics']
    exclusions = {str(t).removeprefix('topic-exclude-') for t in record.get('tags') or [] if str(t).startswith('topic-exclude-')}
    for tag in tags:
        pair = (key, tag['id'])
        original = (tag['id'] in legacy or tag['id'] in (record.get('tags') or [])) and tag['id'] not in exclusions
        present = (automatic or {}).get(pair, original) if automatic is not None else decision(record, tag)[0] or original
        if (overrides or {}).get(pair, present):
            result.append(tag['id'])
    return result


def snapshot(inbox_dir):
    if not exists(inbox_dir):
        return {}, {}
    with database(inbox_dir, readonly=True) as db:
        return ({(r['article'], r['tag']): bool(r['present']) for r in db.execute('SELECT * FROM automatic')},
                {(r['article'], r['tag']): bool(r['present']) for r in db.execute('SELECT * FROM overrides')})


def override(inbox_dir, article, tag, action, actor):
    if action not in {'add', 'remove', 'automatic'}:
        raise ValueError('Choose add, remove or automatic.')
    with database(inbox_dir) as db:
        if not db.execute('SELECT 1 FROM tags WHERE id=?', (tag,)).fetchone():
            raise ValueError('Tag is unavailable.')
        if action == 'automatic':
            db.execute('DELETE FROM overrides WHERE article=? AND tag=?', (article, tag))
        else:
            db.execute('INSERT OR REPLACE INTO overrides VALUES(?,?,?,?,?)', (article, tag, int(action == 'add'), actor, stamp()))
        db.execute('INSERT INTO audit VALUES(?,?,?,?,?)', (article, tag, action, actor, stamp()))


def preferences(inbox_dir, actor, selection=None, mode='all'):
    if selection is None and not exists(inbox_dir):
        return {'tag': '', 'tag_mode': 'all'}
    with database(inbox_dir, readonly=selection is None) as db:
        if selection is not None:
            if mode not in {'all', 'any'}:
                raise ValueError('Choose All or Any.')
            known = {r['id'] for r in db.execute('SELECT id FROM tags')}
            if set(selection) - known:
                raise ValueError('Tag is unavailable.')
            db.execute('INSERT OR REPLACE INTO preferences VALUES(?,?,?)', (actor, json.dumps(selection), mode))
        row = db.execute('SELECT * FROM preferences WHERE actor=?', (actor,)).fetchone()
        return {'tag': ','.join(json.loads(row['selection'])), 'tag_mode': row['mode']} if row else {'tag': '', 'tag_mode': 'all'}


def job_state(inbox_dir):
    if not exists(inbox_dir):
        return {'status': 'pending', 'processed': 0, 'total': 0}
    with database(inbox_dir, readonly=True) as db:
        row = db.execute('SELECT * FROM jobs WHERE id=1').fetchone()
        return dict(row) if row else {'status': 'pending', 'processed': 0, 'total': 0}


def incremental(inbox_dir, records):
    """Use local rules after source persistence; tagging cannot fail ingestion."""
    if exists(inbox_dir):
        try:
            backfill(inbox_dir, records, track_job=False)
        except Exception:
            # backfill records a durable retry/error state and keeps old rows.
            import logging
            logging.getLogger(__name__).warning('News tag update interrupted; retry stored article classification.')


@serialized_write
def backfill(inbox_dir, records, batch_size=100, track_job=True):
    """Resumable bounded transactions; content/version cache avoids repeat work.

    No provider calls. A failed batch retains previous decisions and overrides.
    """
    tags = catalog(inbox_dir)
    rows = list(records.values()) if isinstance(records, dict) else list(records)
    total = len(rows) * len(tags)
    processed = 0
    try:
        for offset in range(0, len(rows), batch_size):
            with database(inbox_dir) as db:
                for record in rows[offset:offset+batch_size]:
                    for tag in tags:
                        fingerprint = hashlib.sha256((VERSION + str(tag['version']) + tag['description'] + text(record) + json.dumps(record.get('classification')) + json.dumps(record.get('tags'))).encode()).hexdigest()
                        old = db.execute('SELECT fingerprint FROM automatic WHERE article=? AND tag=?', (record['id'], tag['id'])).fetchone()
                        if not old or old[0] != fingerprint:
                            present, rationale = decision(record, tag)
                            db.execute('INSERT OR REPLACE INTO automatic VALUES(?,?,?,?,?,?,?,?)',
                                       (record['id'], tag['id'], fingerprint, int(present), rationale, stamp(), VERSION, tag['version']))
                        processed += 1
                if track_job:
                    db.execute('INSERT OR REPLACE INTO jobs VALUES(1,?,?,?,?,?)', ('running', processed, total, '', stamp()))
        if track_job:
            with database(inbox_dir) as db:
                db.execute('INSERT OR REPLACE INTO jobs VALUES(1,?,?,?,?,?)', ('ready', processed, total, '', stamp()))
    except Exception:
        with database(inbox_dir) as db:
            db.execute('INSERT OR REPLACE INTO jobs VALUES(1,?,?,?,?,?)', ('failed', processed, total, 'Classification interrupted. Retry to resume; existing assignments are retained.', stamp()))
        raise
