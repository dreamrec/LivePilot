"""Release artwork must not retain stale uppercase counts unnoticed."""
import importlib.util
from pathlib import Path


def _sync():
    path = Path(__file__).resolve().parents[1] / 'scripts/sync_metadata.py'
    spec = importlib.util.spec_from_file_location('banner_metadata_sync', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_uppercase_artwork_counts_are_detected_and_fixed(tmp_path):
    sync = _sync()
    banner = tmp_path / 'banner.svg'
    banner.write_text('<svg><text>467 TOOLS</text><text>56 DOMAINS</text></svg>')
    sync.ROOT = tmp_path
    sync.TOOL_COUNT_FILES = ['banner.svg']
    sync.DOMAIN_COUNT_FILES = ['banner.svg']
    assert sync.check_tool_count(474)
    assert sync.check_domain_count(57)
    sync.fix_tool_count(474)
    sync.fix_domain_count(57)
    assert sync.check_tool_count(474) == []
    assert sync.check_domain_count(57) == []
    assert '474 TOOLS' in banner.read_text()
    assert '57 DOMAINS' in banner.read_text()
