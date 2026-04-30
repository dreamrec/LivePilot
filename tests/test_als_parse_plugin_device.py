"""PluginDevice metadata extraction — synthetic-XML fixture tests.

The factory pack corpus contains zero PluginDevice instances (Ableton's
factory content can't depend on user-installed plugins), so this is the
ONLY place where the parser's PluginDevice path is exercised. Without
these tests the code rots silently.

Schema notes (Live 12 .als format):
  - <PluginDevice> wraps <PluginDesc> + <ParameterList> + <Buffer>
  - <PluginDesc> holds ONE of {VstPluginInfo, Vst3PluginInfo, AuPluginInfo,
    AaxPluginInfo} depending on plugin format.
  - Parameter VALUES live in <Buffer Value="..."/> — opaque per-plugin
    binary, NOT readable via XML. We capture identity metadata only.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from scripts.als_deep_parse import _extract_plugin_metadata, extract_device_summary


def _parse(xml: str):
    return ET.fromstring(xml)


def test_vst_plugin_metadata_extraction():
    elem = _parse("""
    <PluginDevice>
      <PluginDesc>
        <VstPluginInfo Id="0">
          <PlugName Value="Serum"/>
          <Manufacturer Value="Xfer Records"/>
          <FileName Value="Serum.vst"/>
          <UniqueId Value="1397772120"/>
        </VstPluginInfo>
      </PluginDesc>
      <ParameterList>
        <ParameterId.0/>
        <ParameterId.1/>
        <ParameterId.2/>
      </ParameterList>
      <Buffer Value="opaque-binary-blob"/>
    </PluginDevice>
    """)
    meta = _extract_plugin_metadata(elem)
    assert meta["format"] == "VST"
    assert meta["name"] == "Serum"
    assert meta["manufacturer"] == "Xfer Records"
    assert meta["file_name"] == "Serum.vst"
    assert meta["unique_id"] == "1397772120"
    assert meta["exposed_param_count"] == 3


def test_vst3_plugin_metadata():
    elem = _parse("""
    <PluginDevice>
      <PluginDesc>
        <Vst3PluginInfo Id="0">
          <Name Value="Diva"/>
          <ManufacturerName Value="u-he"/>
          <FileName Value="Diva.vst3"/>
        </Vst3PluginInfo>
      </PluginDesc>
    </PluginDevice>
    """)
    meta = _extract_plugin_metadata(elem)
    assert meta["format"] == "VST3"
    assert meta["name"] == "Diva"
    assert meta["manufacturer"] == "u-he"
    assert meta["file_name"] == "Diva.vst3"


def test_au_plugin_metadata():
    elem = _parse("""
    <PluginDevice>
      <PluginDesc>
        <AuPluginInfo Id="0">
          <PlugName Value="Massive X"/>
          <Manufacturer Value="Native Instruments"/>
          <ProductId Value="MASSX"/>
        </AuPluginInfo>
      </PluginDesc>
    </PluginDevice>
    """)
    meta = _extract_plugin_metadata(elem)
    assert meta["format"] == "AU"
    assert meta["name"] == "Massive X"
    assert meta["manufacturer"] == "Native Instruments"
    assert meta["unique_id"] == "MASSX"


def test_unknown_format_returns_defaults():
    elem = _parse("""
    <PluginDevice>
      <PluginDesc>
      </PluginDesc>
    </PluginDevice>
    """)
    meta = _extract_plugin_metadata(elem)
    assert meta["format"] == "unknown"
    assert meta["name"] is None
    assert meta["manufacturer"] is None


def test_no_plugin_desc_returns_defaults():
    elem = _parse("<PluginDevice></PluginDevice>")
    meta = _extract_plugin_metadata(elem)
    assert meta["format"] == "unknown"
    assert meta["exposed_param_count"] == 0


def test_extract_device_summary_includes_plugin_field_for_plugindevice():
    """Top-level integration: extract_device_summary surfaces plugin metadata."""
    elem = _parse("""
    <PluginDevice>
      <UserName Value="My Reverb Send"/>
      <PluginDesc>
        <VstPluginInfo Id="0">
          <PlugName Value="Valhalla VintageVerb"/>
          <Manufacturer Value="Valhalla DSP"/>
        </VstPluginInfo>
      </PluginDesc>
    </PluginDevice>
    """)
    result = extract_device_summary(elem)
    assert result["class"] == "PluginDevice"
    assert result["user_name"] == "My Reverb Send"
    assert "plugin" in result
    assert result["plugin"]["format"] == "VST"
    assert result["plugin"]["name"] == "Valhalla VintageVerb"
    assert result["plugin"]["manufacturer"] == "Valhalla DSP"


def test_extract_device_summary_omits_plugin_for_native_devices():
    """Non-PluginDevice classes don't get a 'plugin' key."""
    elem = _parse("""
    <Reverb>
      <DecayTime><Manual Value="1500"/></DecayTime>
    </Reverb>
    """)
    result = extract_device_summary(elem)
    assert "plugin" not in result


def test_param_values_remain_opaque():
    """Sanity check: <Buffer> contents are NOT in the extracted metadata."""
    elem = _parse("""
    <PluginDevice>
      <PluginDesc>
        <VstPluginInfo Id="0"><PlugName Value="Serum"/></VstPluginInfo>
      </PluginDesc>
      <Buffer Value="MIIBIjANBgkqhkiG9w0BAQEFA-pretend-this-is-binary"/>
    </PluginDevice>
    """)
    meta = _extract_plugin_metadata(elem)
    # The opaque buffer must NOT leak into any field
    for v in meta.values():
        assert "MIIBIjANBgkqhkiG" not in str(v), (
            f"Opaque <Buffer> contents leaked into {v}"
        )
