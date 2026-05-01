"""Tests for composer sample resolution.

The composer used to emit pseudo-tools and placeholder strings
({downloaded_path}) because sample resolution was deferred until "the agent
figures it out". Plans were aspirational, not executable. This resolver
moves resolution to plan time so compose() can drop unresolvable layers
cleanly and emit only real tool calls.

Phase 2C extends the resolver with Splice remote download support. It's
async now because splice_client.download_sample is network I/O.
"""

import asyncio

import pytest

from mcp_server.composer.layer_planner import LayerSpec
from mcp_server.composer.sample_resolver import resolve_sample_for_layer


def _run(coro):
    """Helper: run an async call synchronously for tests."""
    return asyncio.run(coro)


# ── Filesystem path (async wrapper around sync matching) ──────────────

def test_resolve_returns_path_when_filesystem_hit(tmp_path):
    sample = tmp_path / "kick_tight.wav"
    sample.write_bytes(b"RIFF....WAVE")

    layer = LayerSpec(role="kick", search_query="tight kick techno")
    path, source = _run(resolve_sample_for_layer(layer, search_roots=[tmp_path]))

    assert path == str(sample)
    assert source == "filesystem"


def test_resolve_returns_none_when_no_match(tmp_path):
    (tmp_path / "unrelated.wav").write_bytes(b"RIFF....WAVE")

    layer = LayerSpec(role="kick", search_query="nonexistent_xyz_12345")
    path, source = _run(resolve_sample_for_layer(layer, search_roots=[tmp_path]))

    assert path is None
    assert source == "unresolved"


def test_resolve_without_search_roots_returns_unresolved():
    layer = LayerSpec(role="bass", search_query="fat bass")
    path, source = _run(resolve_sample_for_layer(layer, search_roots=[]))
    assert path is None
    assert source == "unresolved"


def test_resolve_matches_on_role_when_query_tokens_too_short(tmp_path):
    (tmp_path / "bass_sample.wav").write_bytes(b"RIFF....WAVE")
    layer = LayerSpec(role="bass", search_query="a b")
    path, source = _run(resolve_sample_for_layer(layer, search_roots=[tmp_path]))
    assert path is not None
    assert source == "filesystem"


def test_resolve_prefers_first_search_root_hit(tmp_path):
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()
    (root_a / "kick_a.wav").write_bytes(b"RIFF")
    (root_b / "kick_b.wav").write_bytes(b"RIFF")

    layer = LayerSpec(role="kick", search_query="kick")
    path, source = _run(resolve_sample_for_layer(layer, search_roots=[root_a, root_b]))
    assert path.endswith("kick_a.wav") or path.endswith("kick_b.wav")
    assert source == "filesystem"


def test_resolve_handles_nonexistent_search_root(tmp_path):
    missing = tmp_path / "does_not_exist"

    layer = LayerSpec(role="kick", search_query="kick")
    path, source = _run(resolve_sample_for_layer(layer, search_roots=[missing]))
    assert path is None
    assert source == "unresolved"


def test_resolve_finds_aif_files(tmp_path):
    (tmp_path / "snare_punch.aif").write_bytes(b"FORM")
    layer = LayerSpec(role="snare", search_query="punch snare")
    path, source = _run(resolve_sample_for_layer(layer, search_roots=[tmp_path]))
    assert path.endswith(".aif")
    assert source == "filesystem"


# ── Splice paths (Phase 2C) ──────────────────────────────────────────

class _FakeSpliceClient:
    """Fake SpliceGRPCClient with controllable local + remote hits."""

    def __init__(self, local_hits=None, remote_hits=None, credits=100, connected=True):
        self.local_hits = local_hits or []     # [{"hash": .., "filename": .., "path": ..}]
        self.remote_hits = remote_hits or []   # [{"hash": .., "filename": .., "downloaded_path": ..}]
        self._credits = credits
        self.connected = connected
        self.download_calls: list[str] = []
        self.search_calls: list[str] = []

    async def search_samples(self, query="", **kwargs):
        from mcp_server.splice_client.models import SpliceSample, SpliceSearchResult
        self.search_calls.append(query)
        samples = []
        for h in self.local_hits:
            samples.append(SpliceSample(
                file_hash=h["hash"], filename=h["filename"], local_path=h["path"],
            ))
        for h in self.remote_hits:
            samples.append(SpliceSample(
                file_hash=h["hash"], filename=h["filename"], local_path="",
            ))
        return SpliceSearchResult(total_hits=len(samples), samples=samples)

    async def download_sample(self, file_hash, timeout=30.0):
        self.download_calls.append(file_hash)
        for h in self.remote_hits:
            if h["hash"] == file_hash:
                return h["downloaded_path"]
        return None

    async def can_afford(self, credits_needed, budget):
        from mcp_server.splice_client.client import CREDIT_HARD_FLOOR
        can = (
            self._credits > CREDIT_HARD_FLOOR
            and credits_needed <= budget
            and credits_needed <= (self._credits - CREDIT_HARD_FLOOR)
        )
        return can, self._credits


def test_resolve_prefers_splice_local_over_remote_without_credit_spend(tmp_path):
    local_path = str(tmp_path / "splice_local.wav")
    (tmp_path / "splice_local.wav").write_bytes(b"RIFF")

    splice = _FakeSpliceClient(
        local_hits=[{"hash": "h1", "filename": "kick.wav", "path": local_path}],
        remote_hits=[{"hash": "h2", "filename": "kick2.wav", "downloaded_path": "/tmp/x.wav"}],
    )

    layer = LayerSpec(role="drums", search_query="techno drums")
    path, source = _run(resolve_sample_for_layer(
        layer, search_roots=[], splice_client=splice,
    ))
    assert path == local_path
    assert source == "splice_local"
    assert splice.download_calls == []  # zero credits spent


def test_resolve_falls_through_to_splice_remote_when_no_local(tmp_path):
    downloaded = str(tmp_path / "downloaded.wav")
    (tmp_path / "downloaded.wav").write_bytes(b"RIFF")

    splice = _FakeSpliceClient(
        local_hits=[],
        # 2026-05-01: filename needs role signal so the new role-fit
        # scorer (BUG-FULL-MODE-10) doesn't reject it as score=0.
        remote_hits=[{"hash": "h1", "filename": "drums_remote.wav", "downloaded_path": downloaded}],
    )

    layer = LayerSpec(role="drums", search_query="techno drums")
    path, source = _run(resolve_sample_for_layer(
        layer, search_roots=[], splice_client=splice,
    ))
    assert path == downloaded
    assert source == "splice_remote"
    assert splice.download_calls == ["h1"]


def test_resolve_skips_splice_remote_when_credits_below_hard_floor():
    splice = _FakeSpliceClient(
        local_hits=[],
        remote_hits=[{"hash": "h1", "filename": "remote.wav", "downloaded_path": "/tmp/x.wav"}],
        credits=3,  # below hard floor of 5
    )

    layer = LayerSpec(role="drums", search_query="techno drums")
    path, source = _run(resolve_sample_for_layer(
        layer, search_roots=[], splice_client=splice,
    ))
    assert path is None
    assert source == "unresolved"
    assert splice.download_calls == []


def test_resolve_skips_splice_when_client_disconnected():
    splice = _FakeSpliceClient(connected=False)
    layer = LayerSpec(role="drums", search_query="techno drums")
    path, source = _run(resolve_sample_for_layer(
        layer, search_roots=[], splice_client=splice,
    ))
    assert path is None
    assert source == "unresolved"
    assert splice.search_calls == []  # no calls on disconnected client


def test_resolve_filesystem_wins_over_splice_local(tmp_path):
    """If a filesystem hit exists, we don't even query Splice — filesystem
    is cheaper and faster."""
    local_sample = tmp_path / "drums_techno.wav"
    local_sample.write_bytes(b"RIFF")

    splice = _FakeSpliceClient(
        local_hits=[{"hash": "h1", "filename": "splice.wav", "path": "/tmp/splice.wav"}],
    )

    layer = LayerSpec(role="drums", search_query="techno drums")
    path, source = _run(resolve_sample_for_layer(
        layer, search_roots=[tmp_path], splice_client=splice,
    ))
    assert path == str(local_sample)
    assert source == "filesystem"
    assert splice.search_calls == []  # never queried


def test_resolve_download_failure_falls_through_to_unresolved():
    class _FailingSplice(_FakeSpliceClient):
        async def download_sample(self, file_hash, timeout=30.0):
            self.download_calls.append(file_hash)
            return None  # simulate download failure

    splice = _FailingSplice(
        # 2026-05-01: role signal required so role-fit scorer accepts it.
        remote_hits=[{"hash": "h1", "filename": "drums_x.wav", "downloaded_path": "/tmp/x.wav"}],
    )

    layer = LayerSpec(role="drums", search_query="techno drums")
    path, source = _run(resolve_sample_for_layer(
        layer, search_roots=[], splice_client=splice,
    ))
    assert path is None
    assert source == "unresolved"
    assert splice.download_calls == ["h1"]


# ── v1.10.3 Truth Release: role-aware ranking, no bad musical matches ──

def test_resolve_lead_does_not_grab_drums_via_shared_genre_token(tmp_path):
    """The naive resolver used to return the first file whose name contained
    any query token. Query 'techno melody Am' would match 'drums_techno.wav'
    because of the shared 'techno' token — giving the lead layer a drum
    sample. Lock out that failure mode.
    """
    (tmp_path / "drums_techno.wav").write_bytes(b"RIFF")
    (tmp_path / "kick_techno_punchy.wav").write_bytes(b"RIFF")

    layer = LayerSpec(role="lead", search_query="techno melody Am")
    path, source = _run(resolve_sample_for_layer(layer, search_roots=[tmp_path]))

    if path is not None:
        name = path.lower()
        assert "drum" not in name and "kick" not in name, \
            f"lead layer resolved to drum material: {path}"
    else:
        assert source == "unresolved"


def test_resolve_bass_prefers_bass_over_generic_genre_match(tmp_path):
    """When both a role-matching and a genre-token-matching file exist,
    role match must win."""
    (tmp_path / "drums_techno_128.wav").write_bytes(b"RIFF")
    (tmp_path / "bass_sub_808.wav").write_bytes(b"RIFF")

    layer = LayerSpec(role="bass", search_query="techno bass 128bpm")
    path, source = _run(resolve_sample_for_layer(layer, search_roots=[tmp_path]))

    assert path is not None
    assert "bass" in path.lower(), f"Expected bass-named file, got: {path}"
    assert source == "filesystem"


def test_resolve_tempo_in_filename_boosts_score(tmp_path):
    """If tempo token appears in the filename AND in the query, prefer that file."""
    (tmp_path / "drums_generic.wav").write_bytes(b"RIFF")
    (tmp_path / "drums_128bpm.wav").write_bytes(b"RIFF")

    layer = LayerSpec(role="drums", search_query="techno drums 128bpm")
    path, source = _run(resolve_sample_for_layer(layer, search_roots=[tmp_path]))
    assert path is not None
    assert "128" in path, f"Expected tempo-matched file preferred, got: {path}"


def test_resolve_role_only_match_still_works(tmp_path):
    """When only a role-matching file exists, return it even if query tokens
    don't overlap at all."""
    (tmp_path / "pad_ambient.wav").write_bytes(b"RIFF")

    layer = LayerSpec(role="pad", search_query="atmospheric texture")
    path, source = _run(resolve_sample_for_layer(layer, search_roots=[tmp_path]))
    assert path is not None
    assert "pad" in path.lower()


def test_resolve_multiple_candidates_picks_best_score(tmp_path):
    """Confirm scoring actually ranks — best candidate wins, not first seen.

    Alphabetical order is set up so first-hit-wins would pick the worst one.
    """
    (tmp_path / "a_unrelated.wav").write_bytes(b"RIFF")
    (tmp_path / "b_random_techno.wav").write_bytes(b"RIFF")
    (tmp_path / "z_drums_perfect_match.wav").write_bytes(b"RIFF")

    layer = LayerSpec(role="drums", search_query="drums perfect")
    path, source = _run(resolve_sample_for_layer(layer, search_roots=[tmp_path]))
    assert path is not None
    assert "z_drums_perfect_match" in path, f"Scoring did not rank best candidate: {path}"


def test_resolve_unrelated_files_return_unresolved(tmp_path):
    """If NO file has any signal (no role, no token), return unresolved,
    not a random arbitrary hit."""
    (tmp_path / "a.wav").write_bytes(b"RIFF")
    (tmp_path / "b.wav").write_bytes(b"RIFF")
    (tmp_path / "c.wav").write_bytes(b"RIFF")

    layer = LayerSpec(role="lead", search_query="arpeggiated melody C")
    path, source = _run(resolve_sample_for_layer(layer, search_roots=[tmp_path]))
    # a/b/c have no signal at all — should be unresolved (not an arbitrary pick)
    assert path is None
    assert source == "unresolved"


# ── 2026-05-01 super-debug fixes (BUG-FULL-MODE-9..11) ────────────


class _RecordingSpliceClient(_FakeSpliceClient):
    """Extends _FakeSpliceClient to record every kwarg passed to
    search_samples. Used to verify filter forwarding."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_search_kwargs: dict = {}

    async def search_samples(self, query="", **kwargs):
        self.last_search_kwargs = dict(kwargs)
        self.last_search_kwargs["query"] = query
        return await super().search_samples(query=query, **kwargs)


def test_splice_resolve_forwards_all_filters_to_search_samples(tmp_path):
    """BUG-FULL-MODE-9: layer.splice_filters (key, chord_type, BPM range,
    genre, sample_type, instrument) MUST be forwarded to the client.
    Pre-fix only `query` and `per_page` were sent."""
    local_path = str(tmp_path / "bass.wav")
    (tmp_path / "bass.wav").write_bytes(b"RIFF")

    splice = _RecordingSpliceClient(
        local_hits=[{"hash": "h1", "filename": "synth_bass_oneshot_Am.wav", "path": local_path}],
    )

    layer = LayerSpec(
        role="bass",
        search_query="electro bass Am oneshot",
        splice_filters={
            "key": "a",
            "chord_type": "minor",
            "bpm_min": 117,
            "bpm_max": 127,
            "genre": "electro",
            "sample_type": "oneshot",
            "instrument": "bass",
        },
    )
    _path, _source = _run(resolve_sample_for_layer(
        layer, search_roots=[], splice_client=splice,
    ))

    kw = splice.last_search_kwargs
    assert kw["key"] == "a", f"key not forwarded, got {kw.get('key')!r}"
    assert kw["chord_type"] == "minor"
    assert kw["bpm_min"] == 117
    assert kw["bpm_max"] == 127
    assert kw["genre"] == "electro"
    assert kw["sample_type"] == "oneshot"
    assert kw["instrument"] == "bass"


def test_splice_resolve_rejects_piano_in_bass_slot(tmp_path):
    """BUG-FULL-MODE-10: even if Splice's server-side filtering misses,
    role-fit scoring must reject a piano oneshot landing in the bass slot.
    The _score_candidate scorer applies -5.0 penalty for primary-role
    mismatch — net negative score = skipped."""
    piano_path = str(tmp_path / "Piano_OneShot_PianoPhrase_Am.wav")
    bass_path = str(tmp_path / "bass_oneshot_Am.wav")
    (tmp_path / "Piano_OneShot_PianoPhrase_Am.wav").write_bytes(b"RIFF")
    (tmp_path / "bass_oneshot_Am.wav").write_bytes(b"RIFF")

    # Splice returns piano FIRST (mimicking server-side ordering bug), bass second.
    # Filename starts with "bass" so _primary_role_of returns "bass" (not "synth"
    # which would mismatch the bass role family and trigger the -5.0 penalty).
    splice = _FakeSpliceClient(
        local_hits=[
            {"hash": "h1", "filename": "Piano_OneShot_PianoPhrase_Am.wav", "path": piano_path},
            {"hash": "h2", "filename": "bass_oneshot_Am.wav", "path": bass_path},
        ],
    )

    layer = LayerSpec(
        role="bass",
        search_query="electro bass Am oneshot",
        splice_filters={"key": "a", "instrument": "bass", "sample_type": "oneshot"},
    )
    path, source = _run(resolve_sample_for_layer(
        layer, search_roots=[], splice_client=splice,
    ))
    # Bass file should win despite Piano being returned first by Splice
    assert path == bass_path, f"Expected bass to win, got {path}"
    assert source == "splice_local"


def test_splice_resolve_returns_unresolved_when_all_candidates_score_negative(tmp_path):
    """BUG-FULL-MODE-10 corollary: if every Splice result is wrong-role
    (all piano files for a bass slot), return unresolved rather than
    picking a bad fit."""
    p1 = str(tmp_path / "Piano_A.wav"); (tmp_path / "Piano_A.wav").write_bytes(b"RIFF")
    p2 = str(tmp_path / "Piano_B.wav"); (tmp_path / "Piano_B.wav").write_bytes(b"RIFF")
    splice = _FakeSpliceClient(
        local_hits=[
            {"hash": "h1", "filename": "Piano_A.wav", "path": p1},
            {"hash": "h2", "filename": "Piano_B.wav", "path": p2},
        ],
    )

    layer = LayerSpec(
        role="bass",
        search_query="electro bass Am oneshot",
        splice_filters={"key": "a", "instrument": "bass"},
    )
    path, source = _run(resolve_sample_for_layer(
        layer, search_roots=[], splice_client=splice,
    ))
    assert path is None
    assert source == "unresolved"


def test_layer_planner_emits_instrument_in_splice_filters():
    """BUG-FULL-MODE-9 — verify _build_splice_filters emits the
    `instrument` field per role from _ROLE_INSTRUMENT."""
    from mcp_server.composer.layer_planner import (
        _build_splice_filters, _ROLE_INSTRUMENT,
    )
    from mcp_server.composer.prompt_parser import CompositionIntent

    intent = CompositionIntent(genre="electro", tempo=122, key="Am")

    # Bass should get instrument=bass
    f_bass = _build_splice_filters(intent, sample_type="oneshot", role="bass")
    assert f_bass.get("instrument") == "bass"

    # Lead should get instrument=synth
    f_lead = _build_splice_filters(intent, sample_type="loop", role="lead")
    assert f_lead.get("instrument") == "synth"

    # Drums should NOT get an instrument filter (any drum sub-category fits)
    f_drums = _build_splice_filters(intent, sample_type="loop", role="drums")
    assert "instrument" not in f_drums

    # Texture / fx — no instrument filter (creative latitude)
    f_tex = _build_splice_filters(intent, sample_type="loop", role="texture")
    assert "instrument" not in f_tex

    # Empty role → no instrument
    f_none = _build_splice_filters(intent, sample_type="loop", role="")
    assert "instrument" not in f_none


def test_drums_layer_gets_no_key_or_chord_type_filter():
    """BUG-FULL-MODE-13 (2026-05-01): Splice's drum samples don't have
    key/chord_type metadata. Applying `chord_type=minor, key=a` to a
    drums search filters EVERY drum out → 0 hits → unresolved. Key /
    chord_type must only apply to tonal roles (bass/lead/pad/vocal/texture).
    """
    from mcp_server.composer.layer_planner import _build_splice_filters
    from mcp_server.composer.prompt_parser import CompositionIntent

    intent = CompositionIntent(genre="electro", tempo=122, key="Am")

    # Drums should NOT get key or chord_type — drum samples in Splice
    # don't have those tags, so the filter excludes everything.
    f_drums = _build_splice_filters(intent, sample_type="loop", role="drums")
    assert "key" not in f_drums, (
        f"Drums shouldn't have key filter; got {f_drums.get('key')!r}"
    )
    assert "chord_type" not in f_drums, (
        f"Drums shouldn't have chord_type filter; got {f_drums.get('chord_type')!r}"
    )
    # But BPM range + sample_type + genre still apply for drums
    assert f_drums.get("bpm_min") == 117
    assert f_drums.get("bpm_max") == 127
    assert f_drums.get("sample_type") == "loop"

    # Percussion same as drums
    f_perc = _build_splice_filters(intent, sample_type="loop", role="percussion")
    assert "key" not in f_perc
    assert "chord_type" not in f_perc

    # FX likewise — riser/sweep/impact samples don't have tonal metadata
    f_fx = _build_splice_filters(intent, sample_type="oneshot", role="fx")
    assert "key" not in f_fx
    assert "chord_type" not in f_fx


def test_tonal_layers_keep_key_and_chord_type_filter():
    """Regression: bass/lead/pad/vocal still get key + chord_type so
    Splice returns key-matched samples for those layers."""
    from mcp_server.composer.layer_planner import _build_splice_filters
    from mcp_server.composer.prompt_parser import CompositionIntent

    intent = CompositionIntent(genre="electro", tempo=122, key="Am")

    for tonal_role in ("bass", "lead", "pad", "vocal"):
        f = _build_splice_filters(intent, sample_type="loop", role=tonal_role)
        assert f.get("key") == "a", f"{tonal_role}: missing key filter"
        assert f.get("chord_type") == "minor", (
            f"{tonal_role}: missing chord_type filter"
        )


def test_texture_keeps_key_filter_for_tonal_textures():
    """Texture is borderline — some textures are tonal (piano/synth pads),
    others aren't (rain/noise). Keep key filter as a soft preference;
    Splice will still return some matches because key is a ranking
    signal, not a hard exclusion when most catalog items are tagged."""
    from mcp_server.composer.layer_planner import _build_splice_filters
    from mcp_server.composer.prompt_parser import CompositionIntent

    intent = CompositionIntent(genre="electro", tempo=122, key="Am")
    f = _build_splice_filters(intent, sample_type="loop", role="texture")
    # Texture keeps key — most "experimental texture" samples have tonal data
    assert f.get("key") == "a"


def test_role_instrument_map_covers_all_tonal_roles():
    """BUG-FULL-MODE-9 sanity sweep: every role that has a clear
    instrument category must be mapped. Drums / texture / fx are
    intentionally NOT mapped (no clean Splice instrument tag)."""
    from mcp_server.composer.layer_planner import _ROLE_INSTRUMENT
    expected_mapped = {"bass", "lead", "pad", "vocal", "percussion"}
    expected_unmapped = {"drums", "texture", "fx"}
    actual_mapped = set(_ROLE_INSTRUMENT.keys())

    missing = expected_mapped - actual_mapped
    assert not missing, f"Tonal roles missing instrument: {missing}"
    overlap = actual_mapped & expected_unmapped
    assert not overlap, f"These roles should be unmapped: {overlap}"


def test_splice_client_search_samples_accepts_instrument_kwarg():
    """BUG-FULL-MODE-9: the Python client signature must accept
    `instrument=` to plumb through to gRPC SearchSampleRequest.Instrument."""
    import inspect
    from mcp_server.splice_client.client import SpliceGRPCClient
    sig = inspect.signature(SpliceGRPCClient.search_samples)
    assert "instrument" in sig.parameters, (
        "search_samples missing instrument parameter"
    )
    # Default should be empty string (don't filter unless explicitly set)
    assert sig.parameters["instrument"].default == ""
