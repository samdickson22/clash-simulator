"""Hold the admitted recovery allocation until the reviewed local amendment arrives."""
from pathlib import Path
import runpy,time
J=Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2')
if __name__=='__main__':
    while not (J/'fullpool/resume-manifest.json').exists():time.sleep(5)
    runpy.run_path(str(J/'fullpool_resume_entry.py'),run_name='__main__')
