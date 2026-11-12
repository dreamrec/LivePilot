"""Public device control: explicit nested paths and native Wavetable contracts."""
import importlib
import sys
import types
from pathlib import Path
from types import SimpleNamespace as NS

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ATTRS = ('amp_envelope', 'envelope_2', 'envelope_3', 'lfo_1', 'lfo_2',
                'midi_velocity', 'midi_note', 'midi_pitch_bend',
                'midi_channel_pressure', 'midi_mod_wheel', 'midi_random')


class Parameter:
    def __init__(self, name, value=.25):
        self.name, self.value = name, value
        self.min, self.max = 0, 1
        self.is_quantized = False
        self.is_enabled = True
        self.automation_state = 0
        self.state = 0
        self.display_value = 25

    def str_for_value(self, value):
        return f'{value * 100:g}%'


class Wavetable:
    name, class_name, _live_ptr = 'Wavetable', 'InstrumentVector', 333
    is_active, can_have_chains, type = True, False, 1

    def __init__(self):
        self.parameters = [Parameter(name) for name in
                           ('Device On', 'Osc 1 Pos', 'Filter 1 Freq', 'Osc 1 Transp')]
        self.visible_modulation_target_names = ['Filter 1 Freq']
        self.parameter_names = ['Filter 1 Freq']
        self.amounts, self.calls = {}, []

    def is_parameter_modulatable(self, parameter):
        assert isinstance(parameter, Parameter)
        return parameter.name != 'Device On'

    def add_parameter_to_modulation_matrix(self, parameter):
        assert isinstance(parameter, Parameter)
        self.calls.append(('add', parameter.name))
        index = len(self.parameter_names)
        self.parameter_names.append(parameter.name)
        self.visible_modulation_target_names.append(parameter.name.replace('Transp', 'Pitch'))
        return index

    def get_modulation_target_parameter_name(self, target_index):
        assert type(target_index) is int
        return self.parameter_names[target_index]

    def get_modulation_value(self, target_index, source_enum):
        assert type(target_index) is int
        return self.amounts.get((target_index, source_enum), 0)

    def set_modulation_value(self, target_index, source_enum, amount):
        assert type(target_index) is int
        self.calls.append(('set', target_index, source_enum, amount))
        self.amounts[target_index, source_enum] = amount


@pytest.fixture
def setup():
    for name in list(sys.modules):
        if name == 'Live' or name == 'remote_script' or name.startswith('remote_script.'):
            sys.modules.pop(name)
    live = types.ModuleType('Live')
    # Deliberately not 0..10: the implementation must use native enum values.
    enum = NS(**{name: 50 + i * 7 for i, name in enumerate(SOURCE_ATTRS)})
    live.WavetableDevice = NS(ModulationSource=enum)
    app = NS(get_major_version=lambda: 12, get_minor_version=lambda: 4,
             get_bugfix_version=lambda: 16)
    live.Application = NS(get_application=lambda: app)
    sys.modules['Live'] = live
    for name, path in [('remote_script', ROOT / 'remote_script'),
                       ('remote_script.LivePilot', ROOT / 'remote_script/LivePilot')]:
        package = types.ModuleType(name)
        package.__path__ = [str(path)]
        sys.modules[name] = package
    devices = importlib.import_module('remote_script.LivePilot.devices')
    wt = Wavetable()
    mixer = NS(volume=NS(value=.7), panning=NS(value=0))
    inner_chain = NS(name='Inner chain', devices=[wt], mixer_device=mixer, mute=False, solo=False)
    inner = NS(name='Inner rack', class_name='InstrumentGroupDevice', _live_ptr=222,
               can_have_chains=True, chains=[inner_chain], parameters=[])
    outer_chain = NS(name='Outer chain', devices=[inner], mixer_device=mixer, mute=False, solo=False)
    outer = NS(name='Outer rack', class_name='InstrumentGroupDevice', _live_ptr=111,
               can_have_chains=True, chains=[outer_chain], parameters=[])
    song = NS(tracks=[NS(name='Synth', devices=[outer, wt])],
              begin_undo_step=lambda: None, end_undo_step=lambda: None)
    path = [{'chain_index': 0, 'device_index': 0}, {'chain_index': 0, 'device_index': 0}]
    args = {'track_index': 0, 'device_index': 0, 'device_path': path}
    return devices, song, wt, enum, args


def test_nested_discovery_and_parameter_write(setup):
    devices, song, wt, _enum, args = setup
    chains = devices.get_rack_chains(song, {'track_index': 0, 'device_index': 0})
    child = chains['chains'][0]['devices'][0]
    assert child['device_path'] == args['device_path'][:1]
    info = devices.get_device_info(song, args)
    assert info['name'] == 'Wavetable'
    assert info['device_id'] == '333'
    result = devices.set_device_parameter(song, dict(args, parameter_name='Osc 1 Pos',
                                                    value=.75, expected_device_id='333'))
    assert result['value'] == .75
    assert wt.parameters[1].value == .75
    result = devices.get_device_parameters(song, args)
    assert result['parameters'][1]['is_enabled']
    assert result['device_path'] == args['device_path']


def test_stale_target_is_rejected_before_single_or_batch_write(setup):
    devices, song, wt, _enum, args = setup
    for handler, extra in [
        (devices.set_device_parameter, {'parameter_name': 'Osc 1 Pos', 'value': .9}),
        (devices.batch_set_parameters, {'parameters': [{'name_or_index': 'Osc 1 Pos', 'value': .9}]}),
    ]:
        with pytest.raises(RuntimeError, match='identity changed'):
            handler(song, dict(args, expected_device_id='111', **extra))
    assert wt.parameters[1].value == .25


@pytest.mark.parametrize('path', [
    [{'chain_index': -1, 'device_index': 0}],
    [{'chain_index': True, 'device_index': 0}],
    [{'chain_index': 0}],
    [{'chain_index': 0, 'device_index': 0, 'typo': 3}],
    [{'chain_index': 0, 'device_index': 0}] * 9,
])
def test_malformed_paths_fail_before_access(setup, path):
    devices, song, wt, _enum, args = setup
    with pytest.raises(ValueError):
        devices.set_device_parameter(song, dict(args, device_path=path,
                                                parameter_index=1, value=.9))
    assert wt.parameters[1].value == .25


def test_native_wavetable_enums_and_normalized_roundtrip(setup):
    devices, song, wt, enum, args = setup
    sources = devices.get_wavetable_mod_targets(song, args)['sources']
    assert {'name': 'Amp Env', 'index': enum.amp_envelope} in sources
    assert all('Macro' not in item['name'] for item in sources)
    added = devices.add_wavetable_mod_route(song, dict(args, source='MIDI Note', target='Osc 1 Transp'))
    assert added['target_index'] == 1
    assert wt.calls == [('add', 'Osc 1 Transp')]
    result = devices.set_wavetable_mod_amount(song, dict(args, source='LFO 1',
                                                        target='index:1', amount=-.35))
    assert wt.calls[-1] == ('set', 1, enum.lfo_1, -.35)
    assert result['amount'] == -.35
    read = devices.get_wavetable_mod_amount(song, dict(args, source='LFO 1', target='Osc 1 Pitch'))
    assert read['amount'] == -.35
    matrix = devices.get_wavetable_mod_matrix(song, args)
    assert len(matrix['routings']) == 1
    assert matrix['routings'][0]['source_index'] == enum.lfo_1


@pytest.mark.parametrize('amount', [float('nan'), float('inf'), 1.01, -1.01])
def test_invalid_wavetable_amount_cannot_mutate(setup, amount):
    devices, song, wt, _enum, args = setup
    with pytest.raises(ValueError):
        devices.set_wavetable_mod_amount(song, dict(args, source='LFO 1',
                                                  target='Filter 1 Freq', amount=amount))
    assert wt.calls == []


def test_matrix_read_failure_is_not_silent_empty_matrix(setup):
    devices, song, wt, _enum, args = setup
    def fail(*args):
        raise RuntimeError('native matrix unavailable')
    wt.get_modulation_value = fail
    with pytest.raises(RuntimeError, match='native matrix unavailable'):
        devices.get_wavetable_mod_matrix(song, args)


def test_macro_source_rejected_without_creating_target(setup):
    devices, song, wt, _enum, args = setup
    with pytest.raises(ValueError, match='unavailable Wavetable source'):
        devices.add_wavetable_mod_route(song, dict(args, source='Macro 1', target='Osc 1 Transp'))
    assert wt.calls == []


def test_public_wrapper_forwards_nested_address_in_error_readback():
    from mcp_server.tools.devices import set_device_parameter
    calls = []
    path = [{'chain_index': 1, 'device_index': 2}]
    def send(command, params):
        calls.append((command, params))
        if command == 'set_device_parameter':
            raise RuntimeError('out of range')
        return {'parameters': [{'name': 'Frequency', 'index': 1, 'min': 0, 'max': 1}]}
    ctx = NS(lifespan_context={'ableton': NS(send_command=send)})
    with pytest.raises(ValueError, match='Accepts min=0'):
        set_device_parameter(ctx, 0, 0, 12, parameter_name='Frequency',
                             device_path=path, expected_device_id='333')
    assert len(calls) == 2
    assert all(params['device_path'] == path and params['expected_device_id'] == '333'
               for _command, params in calls)
