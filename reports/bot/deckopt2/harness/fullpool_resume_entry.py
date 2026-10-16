"""Verify the original game pin plus the reviewed recovery orchestration."""
import runpy
from pathlib import Path
import fullpool_resume
if __name__=='__main__':
    fullpool_resume.install()
    runpy.run_path(str(Path(__file__).with_name('fullpool_entry.py')),run_name='__main__')
