"""Run only new img2img CPU contract checks. No sockets, GPU or cloud."""
from pathlib import Path
import subprocess
import sys

if __name__ == '__main__':
    raise SystemExit(subprocess.call([sys.executable, '-m', 'unittest', 'discover',
        '-s', str(Path(__file__).resolve().parent), '-p', 'test_img2img.py', '-v']))
