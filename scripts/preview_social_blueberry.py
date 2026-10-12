"""Local isolated review preview. Polling/collection off; never production deploy."""
import os
from pathlib import Path
import sys
import json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ['BIOS_INBOX_DIR']=str(ROOT/'inbox/social-blueberry-preview')
os.environ['ENABLE_SOURCE_POLLING']='false'
os.environ['BIOS_MODE']='authoring'
from app.services.social_intelligence.store import Store

if __name__=='__main__':
    from scripts.social_intelligence import entities
    rows=json.loads((ROOT/'benchmarks/social-blueberry-fixtures.json').read_text(encoding='utf-8'))['records']
    store=Store(Path(os.environ['BIOS_INBOX_DIR']));ids=store.ingest(rows,entities(),mode='fixture')
    image=(ROOT/'artifacts/social-blueberry/synthetic-package.png').read_bytes()
    for row,key in zip(rows,ids,strict=True):
        for m in row['media']:
            store.attach_media(key,m['id'],image,'image/png')
    import uvicorn
    uvicorn.run('app.main:app',host='127.0.0.1',port=18343)
