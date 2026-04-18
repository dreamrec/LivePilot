/**
 * LivePilot MIDI Tool Bridge — Max for Live JavaScript
 *
 * Runs inside LivePilot_MIDITool.amxd (a Max MIDI Effect packaged as a
 * Live 12 MIDI Tool — Transformation or Generator). Bridges note lists
 * between live.miditool.in/out and the LivePilot MCP server over OSC/UDP.
 *
 * Wiring (see MIDITOOL_BUILD_GUIDE.md):
 *   Inlets:
 *     0: OSC commands from server via [udpreceive 9881]
 *     1: context dict from live.miditool.in (right outlet)
 *     2: notes list  from live.miditool.in (left outlet)
 *
 *   Outlets:
 *     0: to [udpsend 127.0.0.1 9880] — forwards requests to the server
 *     1: to live.miditool.out left inlet — writes transformed notes into the clip
 *
 * OSC convention:
 *   OUTGOING (this file → server): use WITH leading slash, e.g.
 *     outlet(0, "/miditool/request", encoded). Max's [udpsend] sends
 *     the literal as the OSC address.
 *   INCOMING (server → this file): the Python side sends addresses
 *     WITHOUT a leading slash because Max's [udpreceive] routes by
 *     selector. So dispatch() normalizes by stripping any leading "/".
 *
 * Request correlation:
 *   When a MIDI Tool fire triggers this device, we cache the context +
 *   notes and bundle them with a fresh request_id before shipping the
 *   packet. The server replies with /miditool/response carrying the
 *   same request_id plus transformed notes. If the id doesn't match a
 *   pending request, we drop the reply (stale).
 *
 * Pass-through:
 *   If no target is configured on the server (or the server is down),
 *   we time out after PENDING_TIMEOUT_MS and fall back to the cached
 *   original notes so Live never waits on us forever.
 */

autowatch = 1;
inlets = 3;
outlets = 2;

// ── State ──────────────────────────────────────────────────────────────────

var initialized = false;
var latest_context = {};          // last context from live.miditool.in right outlet
var latest_notes = [];            // last notes from live.miditool.in left outlet
var target_tool = "";             // configured generator name
var target_params = {};           // configured generator params

var pending_request_id = null;    // request_id we're waiting on
var pending_original_notes = [];  // fallback payload for timeout
var pending_timer = null;
var request_counter = 0;

var PENDING_TIMEOUT_MS = 1500;    // 1.5s fallback: Live should never stall

// Base64 encoding table (same as livepilot_bridge.js for wire compat)
var B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

// ── Initialization ─────────────────────────────────────────────────────────

function bang() {
    if (!initialized) {
        initialized = true;
        // Announce ourselves so the server's MidiToolCache flips to connected.
        outlet(0, "/miditool/ready", "1.11.0");
        post("LivePilot MIDI Tool Bridge: initialized\n");
    }
}

// ── Incoming Message Dispatch ──────────────────────────────────────────────

function anything() {
    // Messages can arrive on any of the 3 inlets:
    //   inlet 0 → OSC from server
    //   inlet 1 → context dict from live.miditool.in right outlet
    //   inlet 2 → notes list from live.miditool.in left outlet
    //
    // We dispatch based on `inlet` (provided by Max JS runtime).
    var args = arrayfromargs(arguments);
    if (inlet === 0) {
        _handle_server_message(messagename, args);
    } else if (inlet === 1) {
        _handle_context(messagename, args);
    } else if (inlet === 2) {
        _handle_notes(messagename, args);
    }
}

function list() {
    // Max sometimes routes raw lists without a messagename. Treat per-inlet.
    var args = arrayfromargs(arguments);
    if (inlet === 2) {
        _handle_notes("list", args);
    } else if (inlet === 1) {
        _handle_context("list", args);
    }
}

function dictionary(name) {
    // live.miditool.in emits context as a dictionary. Max JS receives the
    // dictionary name here; we resolve to an actual JS object via Dict.
    if (inlet === 1) {
        try {
            var d = new Dict(name);
            var obj = JSON.parse(d.stringify());
            _apply_context(obj);
        } catch (e) {
            post("LivePilot MIDI Tool Bridge: context dict parse error: " + e + "\n");
        }
    }
}

// ── Server → bridge dispatch ───────────────────────────────────────────────

function _handle_server_message(cmd, args) {
    if (!cmd) return;
    if (cmd.charAt && cmd.charAt(0) === "/") cmd = cmd.substring(1);

    switch (cmd) {
        case "ping":
            outlet(0, "/miditool/pong", "1.11.0");
            break;
        case "miditool/config":
            _handle_config(args);
            break;
        case "miditool/response":
            _handle_response(args);
            break;
        default:
            // Ignore unrelated commands — the analyzer bridge owns
            // everything else on this UDP port.
            break;
    }
}

function _handle_config(args) {
    // Payload: b64(JSON({tool_name, params}))
    var raw = _decode_b64_arg(args[0]);
    if (!raw) return;
    try {
        var obj = JSON.parse(raw);
        target_tool = String(obj.tool_name || "");
        target_params = obj.params || {};
        outlet(0, "/miditool/pong", "config_ack");
    } catch (e) {
        post("LivePilot MIDI Tool Bridge: bad config: " + e + "\n");
    }
}

function _handle_response(args) {
    // Payload: b64(JSON({request_id, notes}))
    var raw = _decode_b64_arg(args[0]);
    if (!raw) return;
    try {
        var obj = JSON.parse(raw);
        var id = String(obj.request_id || "");
        if (!pending_request_id || id !== pending_request_id) {
            // Stale or unexpected reply; drop silently.
            return;
        }
        _cancel_pending_timer();
        pending_request_id = null;
        _emit_notes(obj.notes || []);
    } catch (e) {
        post("LivePilot MIDI Tool Bridge: bad response: " + e + "\n");
    }
}

// ── live.miditool.in context + notes ───────────────────────────────────────

function _handle_context(name, args) {
    // The right outlet emits a dictionary-shaped message. Some Max versions
    // fire the raw key-value pairs; we accept both. _apply_context() is the
    // single place that normalizes onto `latest_context`.
    if (!name) return;
    if (name === "grid" || name === "selection" || name === "scale" ||
        name === "seed" || name === "tuning") {
        latest_context[name] = (args.length === 1) ? args[0] : args.slice();
    }
}

function _apply_context(obj) {
    if (obj && typeof obj === "object") {
        latest_context = obj;
    }
}

function _handle_notes(name, args) {
    // live.miditool.in emits notes as a list of dictionaries. Each dict
    // has {pitch, start_time, duration, velocity, mute, probability,
    // velocity_deviation, release_velocity, note_id}.
    //
    // IMPORTANT: Live's MIDI Tool protocol is SYNCHRONOUS. We must emit
    // transformed notes via live.miditool.out (outlet 1) within this same
    // scheduler dispatch — an async UDP round trip to the server would
    // arrive too late and trigger "Did not receive a Note dictionary in
    // time" in Live.
    //
    // So the generators are implemented here in JS. The server's role is
    // just config dispatch: set_miditool_target pushes {target_tool,
    // target_params} to us via /miditool/config, and we use that to pick
    // which generator runs on each fire.
    if (!args || args.length === 0) {
        latest_notes = [];
    } else {
        latest_notes = _normalize_notes(args);
    }

    // Run the configured generator SYNCHRONOUSLY and emit immediately.
    var out_notes;
    try {
        if (target_tool && _GENERATORS[target_tool]) {
            out_notes = _GENERATORS[target_tool](latest_notes, latest_context, target_params);
        } else {
            // No target configured — identity passthrough.
            out_notes = latest_notes.slice();
        }
    } catch (e) {
        post("LivePilot MIDI Tool Bridge: generator '" + target_tool + "' failed: " + e + "\n");
        out_notes = latest_notes.slice();
    }
    _emit_notes(out_notes);

    // Also send a best-effort async ping to the server for logging/learning
    // (the server's response is no longer load-bearing but we keep the wire
    // for introspection via get_miditool_context()).
    _send_request_async(out_notes);
}


// ── Synchronous generators (JS) ────────────────────────────────────────────
//
// Live 12 MIDI Tools must respond synchronously, so we can't delegate to
// the Python server. Each generator below is a pure function:
//   fn(notes_in: [dict], context: dict, params: dict) -> notes_out: [dict]
//
// Notes have Live's clip-note shape:
//   {pitch, start_time, duration, velocity, mute, probability,
//    velocity_deviation, release_velocity, note_id}

function _gen_euclidean_rhythm(notes_in, context, params) {
    // Bjorklund pattern over the selection. Ignores input notes (Generator).
    var steps = Math.max(1, Math.round(params.steps || 16));
    var pulses = Math.max(0, Math.min(steps, Math.round(params.pulses || 5)));
    var rotation = Math.round(params.rotation || 0);
    var note_pitch = Math.round(params.note !== undefined ? params.note : 36);
    var velocity = (params.velocity !== undefined) ? params.velocity : 0.9;

    // Selection length in beats (fallback to 4 beats if missing)
    var sel = context.selection || {};
    var sel_start = (typeof sel.start === "number") ? sel.start : 0.0;
    var sel_end = (typeof sel.end === "number") ? sel.end : 4.0;
    var sel_len = Math.max(0.01, sel_end - sel_start);
    var step_dur = sel_len / steps;

    // Compute Bjorklund pattern iteratively (euclidean distribution)
    var pattern = _bjorklund(steps, pulses);

    // Rotate
    if (rotation !== 0) {
        rotation = ((rotation % steps) + steps) % steps;
        pattern = pattern.slice(rotation).concat(pattern.slice(0, rotation));
    }

    var out = [];
    for (var i = 0; i < steps; i++) {
        if (pattern[i] === 1) {
            out.push({
                pitch: note_pitch,
                start_time: sel_start + i * step_dur,
                duration: step_dur * 0.9,
                velocity: velocity,
                mute: 0,
                probability: 1.0,
                velocity_deviation: 0.0,
                release_velocity: 0.5,
                note_id: -1
            });
        }
    }
    return out;
}

function _bjorklund(steps, pulses) {
    // Classic Bjorklund / Euclidean rhythm algorithm.
    // Distributes `pulses` hits as evenly as possible across `steps`.
    if (pulses <= 0) {
        var zeros = [];
        for (var i = 0; i < steps; i++) zeros.push(0);
        return zeros;
    }
    if (pulses >= steps) {
        var ones = [];
        for (var i = 0; i < steps; i++) ones.push(1);
        return ones;
    }
    var pattern = [];
    var counts = [];
    var remainders = [pulses];
    var divisor = steps - pulses;
    var level = 0;
    while (true) {
        counts.push(Math.floor(divisor / remainders[level]));
        remainders.push(divisor % remainders[level]);
        divisor = remainders[level];
        level += 1;
        if (remainders[level] <= 1) break;
    }
    counts.push(divisor);

    function build(lev) {
        if (lev === -1) return [0];
        if (lev === -2) return [1];
        var out = [];
        for (var k = 0; k < counts[lev]; k++) {
            out = out.concat(build(lev - 1));
        }
        if (remainders[lev] !== 0) {
            out = out.concat(build(lev - 2));
        }
        return out;
    }
    pattern = build(level);
    while (pattern.length < steps) pattern.push(0);
    return pattern.slice(0, steps);
}

function _gen_humanize(notes_in, context, params) {
    // Perturb timing + velocity of input notes. Deterministic with seed.
    var timing_spread = (params.timing_spread !== undefined) ? params.timing_spread : 0.05;
    var velocity_spread = (params.velocity_spread !== undefined) ? params.velocity_spread : 0.1;
    var seed = (context.seed !== undefined && context.seed !== null)
        ? parseInt(context.seed, 10)
        : 42;
    var rng = _make_rng(seed);

    var out = [];
    for (var i = 0; i < notes_in.length; i++) {
        var src = notes_in[i];
        var dt = (rng() * 2 - 1) * timing_spread;
        var dv = (rng() * 2 - 1) * velocity_spread;
        var copy = {};
        for (var k in src) if (src.hasOwnProperty(k)) copy[k] = src[k];
        copy.start_time = Math.max(0.0, (copy.start_time || 0) + dt);
        copy.velocity = Math.max(0.0, Math.min(1.0, (copy.velocity || 0.8) + dv));
        out.push(copy);
    }
    return out;
}

function _gen_tintinnabuli(notes_in, context, params) {
    // Add a companion voice drawn from a triad. For each input note,
    // add a note at the nearest triad member above (default) or below.
    var triad = params.t_voice_triad || [0, 4, 7];
    var direction = params.direction || "above";

    var out = [];
    for (var i = 0; i < notes_in.length; i++) {
        out.push(notes_in[i]);
    }
    for (var j = 0; j < notes_in.length; j++) {
        var src = notes_in[j];
        var p = src.pitch || 60;
        var companion_pitch;
        if (direction === "above") {
            // Smallest strictly-positive offset such that (p + offset) mod 12 is in triad
            companion_pitch = p + 12;
            for (var off = 1; off <= 12; off++) {
                if (triad.indexOf((p + off) % 12) >= 0) {
                    companion_pitch = p + off;
                    break;
                }
            }
        } else if (direction === "below") {
            companion_pitch = p - 12;
            for (var off2 = 1; off2 <= 12; off2++) {
                if (triad.indexOf(((p - off2) % 12 + 12) % 12) >= 0) {
                    companion_pitch = p - off2;
                    break;
                }
            }
        } else {
            // alternate
            companion_pitch = p + ((triad[j % triad.length] - (p % 12) + 12) % 12);
            if (companion_pitch === p) companion_pitch += 12;
        }
        var comp = {};
        for (var k in src) if (src.hasOwnProperty(k)) comp[k] = src[k];
        comp.pitch = Math.max(0, Math.min(127, companion_pitch));
        comp.note_id = -1;
        out.push(comp);
    }
    return out;
}

function _make_rng(seed) {
    // Simple mulberry32 PRNG — deterministic, good distribution.
    var a = seed >>> 0;
    return function() {
        a = (a + 0x6D2B79F5) >>> 0;
        var t = a;
        t = (t ^ (t >>> 15)) * (t | 1);
        t ^= t + ((t ^ (t >>> 7)) * (t | 61));
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

var _GENERATORS = {
    euclidean_rhythm: _gen_euclidean_rhythm,
    humanize: _gen_humanize,
    tintinnabuli: _gen_tintinnabuli
};


function _send_request_async(out_notes) {
    // Fire-and-forget ping to the server so get_miditool_context() on the
    // MCP side sees connected:true and a recent context. Not load-bearing.
    request_counter += 1;
    var req_id = String(Date.now()) + "_" + String(request_counter);
    var payload = {
        request_id: req_id,
        context: latest_context,
        notes: latest_notes,
        emitted: out_notes,
        target_tool: target_tool,
        target_params: target_params
    };
    try {
        var encoded = base64_encode(JSON.stringify(payload));
        outlet(0, "/miditool/request", encoded);
    } catch (e) {
        // Silent — this is best-effort
    }
}

function _normalize_notes(args) {
    var out = [];
    for (var i = 0; i < args.length; i++) {
        var n = args[i];
        if (n && typeof n === "object" && !(n instanceof Array)) {
            // Already a dict — keep as-is.
            out.push(n);
        } else if (typeof n === "string") {
            // Named dictionary handle; resolve via Dict().
            try {
                var d = new Dict(n);
                out.push(JSON.parse(d.stringify()));
            } catch (e) {
                // Skip unparseable entries rather than poison the whole list.
            }
        }
    }
    return out;
}

// ── Outbound: request to server ────────────────────────────────────────────

function _send_request() {
    request_counter += 1;
    var req_id = String(Date.now()) + "_" + String(request_counter);
    pending_request_id = req_id;
    pending_original_notes = latest_notes.slice();

    var payload = {
        request_id: req_id,
        context: latest_context,
        notes: latest_notes
    };
    var encoded = base64_encode(JSON.stringify(payload));
    outlet(0, "/miditool/request", encoded);

    _arm_pending_timer();
}

function _arm_pending_timer() {
    _cancel_pending_timer();
    pending_timer = new Task(function() {
        if (!pending_request_id) return;
        // Timed out — fall back to the original notes so the clip isn't
        // left empty if the server is down or no target is configured.
        pending_request_id = null;
        _emit_notes(pending_original_notes);
    });
    pending_timer.schedule(PENDING_TIMEOUT_MS);
}

function _cancel_pending_timer() {
    if (pending_timer) {
        try { pending_timer.cancel(); } catch (e) { /* ignore */ }
        pending_timer = null;
    }
}

// ── Outbound: notes back into Live ─────────────────────────────────────────

function _emit_notes(notes) {
    // live.miditool.out accepts notes one at a time as dictionary messages.
    // The "done" bang tells Live we're finished writing this batch.
    if (!notes || notes.length === 0) {
        outlet(1, "done");
        return;
    }
    for (var i = 0; i < notes.length; i++) {
        var n = notes[i];
        if (n && typeof n === "object") {
            var d = new Dict();
            for (var k in n) {
                if (n.hasOwnProperty(k)) {
                    d.replace(k, n[k]);
                }
            }
            outlet(1, "dictionary", d.name);
        }
    }
    outlet(1, "done");
}

// ── Base64 helpers (shared shape with livepilot_bridge.js) ─────────────────

function base64_encode(str) {
    var bytes = _utf8_encode(str);
    var result = "";
    for (var i = 0; i < bytes.length; i += 3) {
        var b0 = bytes[i];
        var b1 = (i + 1 < bytes.length) ? bytes[i + 1] : 0;
        var b2 = (i + 2 < bytes.length) ? bytes[i + 2] : 0;

        result += B64.charAt(b0 >> 2);
        result += B64.charAt(((b0 & 3) << 4) | (b1 >> 4));
        if (i + 1 < bytes.length) {
            result += B64.charAt(((b1 & 15) << 2) | (b2 >> 6));
        }
        if (i + 2 < bytes.length) {
            result += B64.charAt(b2 & 63);
        }
    }
    return result;
}

function _utf8_encode(str) {
    var bytes = [];
    for (var i = 0; i < str.length; i++) {
        var c = str.charCodeAt(i);
        if (c < 0x80) {
            bytes.push(c);
        } else if (c < 0x800) {
            bytes.push(0xC0 | (c >> 6));
            bytes.push(0x80 | (c & 0x3F));
        } else {
            bytes.push(0xE0 | (c >> 12));
            bytes.push(0x80 | ((c >> 6) & 0x3F));
            bytes.push(0x80 | (c & 0x3F));
        }
    }
    return bytes;
}

function base64_decode(str) {
    var clean = String(str || "").replace(/=/g, "");
    var bytes = [];
    for (var i = 0; i < clean.length; i += 4) {
        var c0 = B64.indexOf(clean.charAt(i));
        var c1 = B64.indexOf(clean.charAt(i + 1));
        var c2 = (i + 2 < clean.length) ? B64.indexOf(clean.charAt(i + 2)) : -1;
        var c3 = (i + 3 < clean.length) ? B64.indexOf(clean.charAt(i + 3)) : -1;
        if (c0 < 0 || c1 < 0) break;
        bytes.push(((c0 << 2) | (c1 >> 4)) & 0xFF);
        if (c2 !== -1) bytes.push((((c1 & 15) << 4) | (c2 >> 2)) & 0xFF);
        if (c3 !== -1) bytes.push((((c2 & 3) << 6) | c3) & 0xFF);
    }
    return bytes;
}

function _utf8_decode(bytes) {
    var result = "";
    for (var i = 0; i < bytes.length;) {
        var b0 = bytes[i];
        if (b0 < 0x80) {
            result += String.fromCharCode(b0);
            i += 1;
        } else if ((b0 & 0xE0) === 0xC0 && i + 1 < bytes.length) {
            var b1 = bytes[i + 1];
            result += String.fromCharCode(((b0 & 0x1F) << 6) | (b1 & 0x3F));
            i += 2;
        } else if ((b0 & 0xF0) === 0xE0 && i + 2 < bytes.length) {
            var b1_3 = bytes[i + 1];
            var b2_3 = bytes[i + 2];
            result += String.fromCharCode(
                ((b0 & 0x0F) << 12) | ((b1_3 & 0x3F) << 6) | (b2_3 & 0x3F)
            );
            i += 3;
        } else {
            i += 1;
        }
    }
    return result;
}

function _decode_b64_arg(arg) {
    if (arg === null || arg === undefined) return null;
    var text = String(arg);
    if (text.indexOf("b64:") === 0) {
        try {
            return _utf8_decode(base64_decode(text.substring(4)));
        } catch (e) {
            return null;
        }
    }
    // No prefix — server sent a raw string (rare).
    return text;
}
