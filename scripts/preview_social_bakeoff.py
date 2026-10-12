"""Local isolated news-feed pilot preview; no collector/scheduler/production write."""
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ['BIOS_INBOX_DIR']=str(ROOT/'inbox/social-bakeoff/news-combined-2026-10-07/evaluation-inbox')
os.environ['ENABLE_SOURCE_POLLING']='false';os.environ['BIOS_MODE']='authoring'
if __name__=='__main__':
    if not (Path(os.environ['BIOS_INBOX_DIR'])/'social/observations.sqlite3').exists():
        raise SystemExit('Run the authorized free evaluation and local summary first; no placeholder live data is seeded')
    import uvicorn
    uvicorn.run('app.main:app',host='127.0.0.1',port=18344)
