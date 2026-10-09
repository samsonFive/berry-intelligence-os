"""Local isolated trial preview; never performs collection or seeds sample data."""
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ['BIOS_INBOX_DIR']=str(ROOT/'inbox/social-bakeoff/sociavault-multiplatform-2026-10-07/evaluation-inbox')
os.environ['ENABLE_SOURCE_POLLING']='false';os.environ['BIOS_MODE']='authoring'
os.environ['BIOS_SOCIAL_TRIAL_PREVIEW']='true'
if __name__=='__main__':
    if not (Path(os.environ['BIOS_INBOX_DIR'])/'social/observations.sqlite3').exists():
        raise SystemExit('Run the authorized trial and offline report first; no invented live records')
    import uvicorn
    uvicorn.run('app.main:app',host='127.0.0.1',port=18345)
