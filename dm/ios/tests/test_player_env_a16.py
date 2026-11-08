"""The A16 conservative GPU-write fallback must survive player-mode env filtering.

No game assets, Apple SDK, simulator, or iOS build is required.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
HEADER_DIR = ROOT / 'dm/ios/Sources'


class PlayerEnvHazardTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('clang'), 'clang required')
    def test_conservative_ab_allowed_but_unrelated_diagnostics_ignored(self):
        source = r'''
#include "player_env.h"
#include <assert.h>
int main(void) {
    assert(!dm_player_diagnostic_key("DM_NVN_SBW_FINE"));
    assert(!dm_player_diagnostic_key("DM_NVN_ENC_THREAD"));
    assert(dm_player_diagnostic_key("DM_NVN_HELD_SCAN"));
    assert(dm_player_diagnostic_key("DM_NVN_PASSDUMP"));
    assert(dm_player_diagnostic_key("MTL_DEBUG_LAYER"));
    assert(dm_player_diagnostic_key("DM_CTL"));
    assert(!dm_player_diagnostic_key("DM_FPS_TARGET"));
    assert(!dm_player_diagnostic_key("DM_RENDER_SCALE"));
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as td:
            src, exe = Path(td) / 'test.c', Path(td) / 'test'
            src.write_text(source, encoding='utf-8')
            subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-I', str(HEADER_DIR), str(src), '-o', str(exe)],
                           check=True, capture_output=True, text=True)
            subprocess.run([str(exe)], check=True, capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()
