"""Offer the resolution control only when the rewritten build supports it."""
from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'games'))
import settings

class ResolutionSetting(unittest.TestCase):
    def test_verified_rewrite_required(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(settings.nacp,'languages',return_value=['en-US']):
            p=Path(tmp)/'main.fixups.tsv'
            for header,supported in [('# BUILD_ID\t3c10ec35c5ef4c3686b4053afb0e58e7\n',False),
                                     ('# DYNAMIC_RESOLUTION\t1\n',True),('',False)]:
                p.write_text(header)
                rows=settings.build('010056B015FE8000',tmp,'unused')['settings']
                dr=[s for s in rows if s['env']=='DM_DYNAMIC_RESOLUTION']
                self.assertEqual(bool(dr),supported)
                if dr:self.assertEqual((dr[0]['kind'],dr[0]['default']),('toggle','0'))
                fps=next(s for s in rows if s['env']=='DM_FPS_TARGET')
                self.assertEqual(fps['default'],'60')
                self.assertEqual(fps['options'],[['30','30 fps'],['60','60 fps']])

class ExperimentalA16Settings(unittest.TestCase):
    def test_host_only_fast_build_can_opt_in_without_changing_shader_inputs(self):
        import os
        with tempfile.TemporaryDirectory() as tmp, patch.object(settings.nacp,'languages',return_value=['en-US']):
            (Path(tmp)/'main.fixups.tsv').write_text('# RUNTIME_TUNING\\t7\\n')
            with patch.dict(os.environ, {'GFXAPI':'nvn','DM_NVN_SBW_SCOPED':'1'}):
                rows={r['env']:r for r in settings.build('010056B015FE8000',tmp,'unused')['settings']}
            self.assertEqual(rows['DM_NVN_SBW_SCOPED']['default'],'1')
            self.assertEqual(rows['DM_NVN_CPU_READ_NORES']['default'],'1')
            self.assertEqual(rows['DM_NVN_RT_VIEW_UPGRADE']['default'],'0')
            for name in ('DM_NVN_SBW_SCOPED','DM_NVN_CPU_READ_NORES','DM_NVN_RT_VIEW_UPGRADE'):
                self.assertEqual(rows[name]['kind'],'toggle')
                self.assertEqual((rows[name]['on'],rows[name]['off']),('1','0'))
            with patch.dict(os.environ, {'GFXAPI':'nvn'}):
                os.environ.pop('DM_NVN_SBW_SCOPED',None)
                normal={r['env']:r for r in settings.build('010056B015FE8000',tmp,'unused')['settings']}
                self.assertEqual(normal['DM_NVN_SBW_SCOPED']['default'],'0')

if __name__=='__main__':unittest.main()
