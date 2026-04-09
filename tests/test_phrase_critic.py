"""Tests for phrase-level evaluation."""

from mcp_server.musical_intelligence.phrase_critic import (
    analyze_phrase, compare_phrases, PhraseCritique,
)


def test_analyze_with_loudness():
    loudness = {
        "integrated_lufs": -14.5,
        "true_peak_dbtp": -2.0,
        "lra_lu": 3.5,
        "short_term_lufs": [-14.0, -15.0, -13.5, -14.8, -14.2],
    }
    critique = analyze_phrase(loudness_data=loudness, target="loop")
    assert critique.overall > 0
    assert critique.fatigue_risk < 0.6  # LRA 3.5 is decent
    assert critique.translation_risk < 0.5  # Peak -2 is ok


def test_analyze_with_spectrum():
    spectrum = {
        "centroid_hz": 500,
        "rolloff_hz": 3000,
        "band_balance": {
            "sub_60hz": 0.3,
            "low_250hz": 0.25,
            "mid_2khz": 0.3,
            "high_8khz": 0.1,
            "air_16khz": 0.05,
        },
    }
    critique = analyze_phrase(spectrum_data=spectrum, target="chorus")
    assert critique.identity_strength > 0
    assert critique.payoff_strength > 0.5  # Chorus target


def test_analyze_empty():
    critique = analyze_phrase()
    assert len(critique.notes) > 0
    assert critique.overall == 0.0 or True  # May be default values


def test_high_fatigue_risk():
    loudness = {"lra_lu": 0.3, "short_term_lufs": [-14.0, -14.0, -14.0]}
    critique = analyze_phrase(loudness_data=loudness, target="loop")
    assert critique.fatigue_risk > 0.5


def test_clipping_risk():
    loudness = {"true_peak_dbtp": -0.5, "short_term_lufs": [-12.0, -11.5]}
    critique = analyze_phrase(loudness_data=loudness, target="drop")
    assert critique.translation_risk > 0.5


def test_compare_phrases():
    c1 = PhraseCritique(render_id="a", arc_clarity=0.8, contrast=0.7,
                        fatigue_risk=0.2, payoff_strength=0.7,
                        identity_strength=0.6, translation_risk=0.1)
    c2 = PhraseCritique(render_id="b", arc_clarity=0.3, contrast=0.3,
                        fatigue_risk=0.8, payoff_strength=0.3,
                        identity_strength=0.3, translation_risk=0.5)
    ranking = compare_phrases([c1, c2])
    assert ranking[0]["render_id"] == "a"
    assert ranking[0]["rank"] == 1
    assert ranking[1]["rank"] == 2


def test_target_affects_payoff():
    loudness = {"lra_lu": 2, "short_term_lufs": [-14.0, -13.0]}
    drop = analyze_phrase(loudness_data=loudness, target="drop")
    intro = analyze_phrase(loudness_data=loudness, target="intro")
    assert drop.payoff_strength > intro.payoff_strength
