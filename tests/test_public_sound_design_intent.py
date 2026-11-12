"""Topology is evidence about visible control, not musical quality."""
import pytest

from mcp_server.sound_design.models import PatchBlock, PatchModel, SoundDesignState, TimbralGoalVector
from mcp_server.sound_design.critics import run_all_sound_design_critics, run_static_timbre_critic
from mcp_server.sound_design.tools import _timbral_goal


@pytest.mark.parametrize('name', ['Simple Lead', 'Stable Sub', 'Sampled Texture'])
def test_simple_patch_has_no_unrequested_aesthetic_penalty(name):
    patch = PatchModel(device_chain=[name], blocks=[PatchBlock(device_name=name, block_type='oscillator')])
    issues = run_all_sound_design_critics(SoundDesignState(patch=patch))
    unwanted = {'too_few_blocks', 'generic_chain', 'no_modulation_sources', 'no_modulation', 'no_lfo_movement'}
    assert not unwanted.intersection(i.issue_type for i in issues)


def test_movement_request_yields_one_qualified_unmeasured_advisory():
    patch = PatchModel(blocks=[PatchBlock(block_type='oscillator', device_name='Source')])
    issues = run_all_sound_design_critics(SoundDesignState(patch=patch, goal=TimbralGoalVector(movement=.5)))
    modulation = [i for i in issues if i.critic in ('static_timbre', 'modulation_flatness')]
    assert len(modulation) == 1
    assert 'does not establish audible stasis' in modulation[0].evidence
    assert modulation[0].confidence <= .35
    assert modulation[0].to_dict()['measured'] is False


def test_opaque_patch_does_not_imply_audible_stasis():
    patch = PatchModel(blocks=[PatchBlock(block_type='effect')], opaque_blocks=['Opaque instrument'])
    assert run_static_timbre_critic(patch, TimbralGoalVector(movement=.8)) == []


@pytest.mark.parametrize('goal', [{'movement': float('nan')}, {'movement': 2},
                                 {'unknown': .2}, {'movement': True}])
def test_invalid_goal_fails(goal):
    with pytest.raises(ValueError):
        _timbral_goal(goal)


def test_explicit_goal_preserves_negative_direction():
    goal = _timbral_goal({'brightness': -.2, 'movement': .6})
    assert goal.brightness == -.2
    assert goal.movement == .6
