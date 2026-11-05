#!/usr/bin/env python3
"""Generate Xbox / PlayStation BOTW icons from your own RomFS folder or DMROMFS1 image."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'dm/tools'))
from controller_icons import main

if __name__ == '__main__': main()
