# Perception (Analyzer) Reference

Deep-dive detail for `mcp_server/tools/analyzer.py` tools. The tool
docstrings carry a trimmed operational contract (params, ranges,
gotchas); this file carries the full band tables, classification
thresholds, and historical bug context that motivated each behavior.
Read this before deep spectral/health-check work — the tool docstrings
point back here for the parts that don't change from call to call.

## `listen_capture` / `listen_ab` — offline perception loop

Live in `mcp_server/listening/` (v1.28+, domain `listening`, not
`analyzer`), but complete the perception picture: everything below this
section is *real-time* — bridge-dependent, read while the session plays.
`listen_capture`/`listen_ab` are *offline* — librosa/soundfile analysis of
a WAV/AIFF already on disk (a `capture_audio` output or any absolute
path); only the capture step itself needs the Analyzer on master.

Canonical ground-truth A/B loop for any significant move:
`capture_audio(filename="before")` → apply the move →
`capture_audio(filename="after")` →
`listen_ab("before", "after", bpm=<session tempo>)` → pass its
`before_snapshot`/`after_snapshot` straight into `evaluate_move` for a
numeric keep/undo verdict grounded in rendered audio.

### Optional: learned perceptual distance (`embed=True`)

`listen_capture(embed=True)` and `listen_ab(embed=True)` add a CLAP embedding
on top of the DSP measurements. Off by default; needs the optional
`pip install torch transformers` extra (~2 GB). Without it both tools behave
exactly as before and return an install hint rather than failing.

Why it is worth the extra when you have it: every measurement below is a
*hand-designed* feature — a band level, a LUFS number, a groove deviation. They
tell you **what** changed numerically. None of them answers "do these two
renders sound like different *things*", because that judgement is holistic. The
embedding gives exactly one number for it.

- `listen_ab(embed=True)` → `perceptual_distance.distance`, a cosine distance.
  Calibrated on real capture families (2026-07-31): **<0.05** is
  indistinguishable from re-rendering the same take, **0.05–0.10** a real but
  modest change, **>0.10** clearly a different version.
- `listen_capture(embed=True)` → a 512-dim `embedding.vector`. This is the
  **taste anchor**: persist it next to the kept/undone outcome so a preference
  model can later be trained on what you actually kept.

Two honest limits. A genuinely subtle change can land *at* the noise floor
(~0.045) and read as "indistinguishable" — that is the model saying it cannot
call this one, not that nothing changed; trust the DSP deltas there. And there
is deliberately **no text-query surface**: CLAP is a joint text-audio model, but
its text side was verified unreliable on this material (asked for "white noise
hiss" it ranked an actual white-noise capture 4th of 5), so it is not exposed.
Audio-to-audio only.

### `taste_record_pair` / `taste_train` / `taste_rank` — the learned head

The taste anchor above, turned into a model. Every kept-over-discarded decision
is a pairwise preference; enough of them fit a Bradley-Terry head that scores
future candidates.

```
capture_audio(before) → move → capture_audio(after)
listen_ab(...)                       # did it change, and how
<decide: keep or undo>
taste_record_pair(kept, discarded)   # the decision becomes data
taste_train()                        # once there are enough pairs
taste_rank([candidates...])          # future moves ranked by taste
```

Record at the moment of decision — a pair is cheap, and the model is only as
good as the honesty of the labels. This complements the symbolic taste system
(`get_taste_profile`, dimension weights, anti-preferences): that side explains
*why* in named qualities, this side notices *that* in audio nobody has a word
for. Neither replaces the other.

**Read the verdict, not the accuracy.** What the head does to avoid overstating
itself — every item below was added after it was caught doing exactly that:

- Training accuracy is never reported. With 512 dimensions and tens of pairs a
  linear head separates almost any labelling, so it reads ~100% regardless.
- `significant: false` means the accuracy carries no information *however high
  it looks* — 20 pairs of random labels measured 65% held-out.
- Cross-validation holds out whole **groups**, because several pairs from one
  session make each other trivially predictable. On 7 real capture pairs from 3
  sessions: leave-one-pair-out 100%, leave-one-session-out 57%. Set `group`
  explicitly whenever the capture filenames do not reflect the true grouping.
- Significance counts **sessions, not pairs** — five or more separate sessions,
  or nothing can be certified however good the accuracy looks. Counting pairs
  put the false-positive rate at ~25% against a nominal 5%.
- **Do not A/B every candidate against one fixed baseline.** Pairs sharing a
  capture are one piece of evidence, not several; they are merged before
  scoring, and `groups_merged` in the report says when that happened. Before
  this guard existed, 6 such pairs across 3 labelled sessions reported "a real
  preference signal" in 40 of 40 runs — for a head scoring 50.7% on fresh pairs.

`significant: null` means "could not be tested" (too few sessions, or captures
shared). Treat it exactly as `false`.

Scores are comparable to each other and to nothing else — Bradley-Terry is
shift-invariant, so there is no meaningful threshold on a single value. Rank
candidates; never gate on a score.

What the offline report adds over any live read: stereo width +
correlation + bass-mono check, groove microtiming (~4 ms resolution,
auto grid division — pass `bpm`), transient character, per-band loudness
movement, technical polish (clipping/DC/true-peak headroom). Canonical
dimensions are computed by the evaluation stack's own extractor, so the
numbers ARE what `evaluate_move` scores. Caveats: captures are whole-clip
statistics — never diff one against a single live meter read; capture
start is not beat-quantized, so loop the section and capture the same
musical span on both sides.

## `get_master_spectrum` — 9-band table

Band energies (fffb~ center frequencies shown in parens), values 0.0-1.0:

| Band | Range | Center | Use |
|---|---|---|---|
| sub_low | 20-60 Hz | ~35 Hz | kick fundamentals, deep sub-bass |
| sub | 60-120 Hz | ~85 Hz | 808s, sub-bass body |
| low | 120-250 Hz | ~175 Hz | bass body, warmth |
| low_mid | 250-500 Hz | ~350 Hz | mud zone, male vocal lows |
| mid | 500 Hz-1 kHz | ~700 Hz | vocal presence, snare body |
| high_mid | 1-2 kHz | ~1.4 kHz | consonants, pick attack |
| high | 2-4 kHz | ~2.8 kHz | presence, vocal intelligibility |
| presence | 4-8 kHz | ~5.6 kHz | cymbal definition, air of breath |
| air | 8-20 kHz | ~12 kHz | shimmer, sparkle |

Older `.amxd` builds (pre-v1.16) emit the legacy 8-band layout without
the explicit `sub_low` split — the server auto-detects band count from
the OSC payload and picks the right name set. Re-freeze the Max device
to get the 9-band resolution.

**BUG-2026-04-22#6 fix — windowed averaging.** Kick transients make
single snapshots swing wildly (0.45 → 0.05 → 0.16 within a bar). The
`window_ms` param samples the cache over a time window and mean-pools
instead of returning one instantaneous frame.

**BUG-2026-04-22#15 fix — sub-band resolution.** `sub_detail=True`
derives three finer buckets from the FluCoMa 40-band mel spectrum
(band 0-1 ≈ sub_deep 0-45 Hz — kick fundamental, band 2 ≈ sub_mid
45-60 Hz — 808 body/kick upper, band 3 ≈ sub_high 60-80 Hz — bass
guitar low/sub-bass crossover). Mel band edges are perceptual, not
linear Hz, so these are approximations tight enough for mixing
decisions ("is energy in the 30 Hz or 60 Hz range?"). Requires FluCoMa
active — omitted with `sub_detail_warning` otherwise.

## `verify_device_health` / `verify_all_devices_health`

**BUG-2026-04-22#19 fix.** `parameter_count` alone can't tell you
whether an AU/VST is alive — plenty of "loaded" plugins return N
params and silence. These tools fire a real test MIDI note and read
the track meter across a window (`get_track_meters(samples=N)` to
dodge the BUG-#7 "left=right=0 while level>0" artifact).

Common dead-device causes (surfaced in the `hint` field when
`alive=False`): (1) plugin waiting for preset/bank selection, (2)
algorithm/envelope configured for zero output, (3) wrong MIDI channel
or velocity curve, (4) dead VST (reinstall). Try opening the device UI
and auditioning manually.

`verify_all_devices_health` (BUG-2026-04-26#1 fix): audio-track
detection uses `has_midi_input`/`has_audio_input` from
`get_session_info` (earlier code checked nonexistent `is_audio_track`/
`type` fields, so detection silently always evaluated False).
Empty-track detection requires a `get_track_info` round-trip per track
because `get_session_info` doesn't embed per-track `devices` arrays.

## `classify_simpler_slices` — classification thresholds

Validated on "Break Ghosts 90 bpm" reference material:
- KICK: sub+low >= 45%, high < 40%
- HAT: high >= 70% AND mid < 25% (thin metal disc = no drum body)
- SNARE: mid >= 25% AND high >= 40% AND peak >= 0.6 (broadband loud)
- ghost: peak < 0.35

**Always run this before programming drum patterns on a sliced break.**
Slice content depends on transient detection order in the source
audio — slice 0 is NOT guaranteed to be a kick. Assuming drum-rack
convention produces wrong grooves that take iterations to diagnose.

File-path resolution order: explicit `file_path` param, then Remote
Script TCP (`get_simpler_file_path` via direct LOM read — most
reliable), then M4L bridge UDP fallback (kept registered for
environments where Remote Script is stale/unavailable; call
`reload_handlers` to refresh without a full restart).

## `add_drum_rack_pad`

**BUG-2026-04-22#1 fix** — this tool closes a gap where
`load_browser_item` replaced the existing chain on repeat calls and
`load_sample_to_simpler` couldn't address nested rack paths. It chains
six steps atomically: locate/auto-detect the Drum Rack, insert a chain,
assign the trigger note, insert an empty Simpler into the chain, native
`replace_sample_native` with nested addressing, Snap=0 hygiene.

## `replace_simpler_sample` / `load_sample_to_simpler`

Prefer `load_browser_item(track, uri)` when the file is browser-indexed
— the M4L bridge's replace path can silently keep the bootstrap
placeholder in some conditions (this is why both tools verify by
reading back the device name post-load and error if the replace didn't
actually take effect).

Nested addressing (`chain_index` + `nested_device_index`) is Live
12.4+ only (BUG-#1, 2026-04-22) — resolves at
`track.devices[device_index].chains[chain_index].devices[nested_device_index or 0]`,
which is how Drum Rack pad-by-pad construction works. The M4L bridge
fallback cannot resolve nested paths; only the native 12.4 path honors
`chain_index`.

`load_sample_to_simpler`'s bootstrap flow (used pre-12.4 or when no
Simpler exists yet): loads a dummy sample via the browser to force
Ableton to create a Simpler, replaces it with the target file, then
runs the same post-load hygiene/verification as `replace_simpler_sample`.

## `simpler_set_warp` / `compressor_set_sidechain` — LOM gap tools

**BUG-A2**: Python's Remote Script ControlSurface API can't reach
Simpler's `warping`/`warp_mode` — they live on the sample child object
(`SimplerDevice.sample.*`) that only Max for Live's JavaScript LiveAPI
can step into. Hence the M4L bridge round-trip.

**BUG-A3**: `compressor_set_sidechain`'s routing properties
(`sidechain_input_routing_type`/`_channel`) aren't in Compressor's
automatable parameter list, but Python's Remote Script reaches them
directly as device properties (same LOM pattern as `set_track_routing`)
— no M4L bridge needed here, unlike the warp case above.
