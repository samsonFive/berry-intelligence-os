"""Explicit release-time installation of public Argos CPU model assets.

Never called by the app. Saves upstream metadata and archive checksums for
reproducibility; runtime translation has no network or paid-provider dependency.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from urllib.request import urlopen
import zipfile

INDEX = 'https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json'


def provision(output, languages):
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'manifest.json').exists():
        raise ValueError('Choose a fresh model directory')
    with urlopen(INDEX, timeout=30) as response:
        index_bytes = response.read(1_000_000)
    index = json.loads(index_bytes)
    def install(code):
        choices = [row for row in index if row.get('from_code') == code and row.get('to_code') == 'en']
        package = choices[-1]
        upstream_link = next(url for url in package['links'] if url.startswith('https://'))
        # Publisher-operated public model archive; preserve both URLs in receipt.
        link = 'https://data.argosopentech.com/argospm/v1/' + upstream_link.rsplit('/', 1)[-1]
        with tempfile.TemporaryDirectory(dir=output) as temporary:
            archive = Path(temporary) / 'package.zip'
            digest = hashlib.sha256()
            size = 0
            with urlopen(link, timeout=60) as response, archive.open('xb') as stream:
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > 300_000_000:
                        raise ValueError('Model archive exceeds release limit')
                    digest.update(chunk); stream.write(chunk)
            target = output / code
            target.mkdir()
            with zipfile.ZipFile(archive) as packed:
                metadata_path = next(name for name in packed.namelist() if name.endswith('/metadata.json'))
                prefix = str(PurePosixPath(metadata_path).parent) + '/'
                metadata = json.loads(packed.read(metadata_path))
                if metadata.get('from_code') != code or metadata.get('to_code') != 'en':
                    raise ValueError('Model language mismatch')
                for member in packed.infolist():
                    if not member.filename.startswith(prefix) or member.is_dir():
                        continue
                    relative = PurePosixPath(member.filename[len(prefix):])
                    if relative.is_absolute() or '..' in relative.parts:
                        raise ValueError('Unsafe model archive path')
                    if relative.parts[0] not in {'model', 'metadata.json', 'sentencepiece.model', 'bpe.model', 'README', 'README.md', 'LICENSE'}:
                        continue
                    path = target.joinpath(*relative.parts)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with packed.open(member) as source, path.open('xb') as destination:
                        shutil.copyfileobj(source, destination)
            if not any((target / p).is_file() for p in ('sentencepiece.model', 'bpe.model')) or not (target / 'model/model.bin').is_file():
                raise ValueError('Unsupported model/tokenizer package')
            return {'language': code, 'package': package, 'download_url': link,
                    'archive_sha256': digest.hexdigest(), 'bytes': size}
    with ThreadPoolExecutor(max_workers=2) as pool:
        packages = list(pool.map(install, languages))
    manifest = {'index_url': INDEX, 'index_sha256': hashlib.sha256(index_bytes).hexdigest(),
                'packages': packages, 'files': {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(output.rglob('*')) if p.is_file()}}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'languages': languages, 'files': len(manifest['files']),
                      'archive_bytes': sum(p['bytes'] for p in packages)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--languages', nargs='+', default=['pt', 'es', 'fr', 'pl', 'zh', 'ja', 'ar', 'de'])
    args = parser.parse_args()
    provision(args.output, args.languages)
