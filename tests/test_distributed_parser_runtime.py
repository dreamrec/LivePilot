"""Runtime helpers must work from extracted releases, without checkout scripts."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('kind', ['npm', 'mcpb'])
def test_distributed_scanners_parse_without_checkout(kind, tmp_path):
    if kind == 'npm':
        npm = shutil.which('npm')
        if not npm:
            pytest.skip('npm unavailable')
        packed = subprocess.run([npm, 'pack', '--ignore-scripts', '--pack-destination', str(tmp_path), '--json'],
                                cwd=ROOT, text=True, capture_output=True, timeout=90)
        assert packed.returncode == 0, packed.stderr
        archive = tmp_path / json.loads(packed.stdout)[0]['filename']
        with tarfile.open(archive) as tar:
            tar.extractall(tmp_path / 'extracted', filter='data')
        extracted = tmp_path / 'extracted/package'
    else:
        if sys.platform == 'win32' or not shutil.which('bash'):
            pytest.skip('MCPB shell build covered by dedicated Ubuntu job')
        archive = tmp_path / 'release.mcpb'
        built = subprocess.run(['bash', 'scripts/build_mcpb.sh', '--output', str(archive)],
                               cwd=ROOT, text=True, capture_output=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        extracted = tmp_path / 'extracted'
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(extracted)
    assert (extracted / 'scripts/als_deep_parse.py').is_file()
    code = r'''
import gzip
from pathlib import Path
from mcp_server.user_corpus.scanners.als import AlsScanner
from mcp_server.user_corpus.scanners.adg import AdgScanner
fixtures = {
 '.als': b'<Ableton><LiveSet><Tracks /></LiveSet></Ableton>',
 '.adg': b'<Ableton><GroupDevicePreset><Device><InstrumentGroupDevice /></Device></GroupDevicePreset></Ableton>',
 '.adv': b'<Ableton><GroupDevicePreset><Device><InstrumentGroupDevice /></Device></GroupDevicePreset></Ableton>',
}
for extension, xml in fixtures.items():
 path = Path('synthetic' + extension)
 with gzip.open(path, 'wb') as output:
  output.write(xml)
 result = (AlsScanner() if extension == '.als' else AdgScanner()).scan_one(path)
 assert result['name'] == 'synthetic'
 if extension != '.als':
  assert result['rack_class'] == 'InstrumentGroupDevice'
print('ALS ADG ADV passed')
'''
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    result = subprocess.run([sys.executable, '-c', code], cwd=extracted, env=env,
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == 'ALS ADG ADV passed'
