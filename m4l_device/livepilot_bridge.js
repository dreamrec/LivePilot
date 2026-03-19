/**
 * LivePilot Analyzer Bridge — Max for Live JavaScript
 *
 * Handles LiveAPI commands from the MCP server via OSC/UDP.
 * Provides deep LOM access: hidden parameters, automation state,
 * nested rack introspection, key detection, and user action monitoring.
 *
 * Communication:
 *   UDP 9881 → this device (incoming commands)
 *   UDP 9880 ← this device (outgoing responses + spectral data)
 *
 * Design constraints (from AbletonBridge research):
 *   - Max 3 LiveAPI cursor objects (reuse via goto())
 *   - Chunk parameter reads: 4 per batch, 50ms delay
 *   - Base64 encode all JSON responses
 *   - Defer all LiveAPI operations via deferlow()
 */

autowatch = 1;
inlets = 1;
outlets = 2; // 0: to udpsend (responses), 1: to status UI

// ── State ──────────────────────────────────────────────────────────────────

var cursor_a = null;  // Primary LiveAPI cursor
var cursor_b = null;  // Secondary cursor for nested walks
var initialized = false;
var pitch_history = []; // Rolling buffer for key detection
var MAX_PITCH_HISTORY = 128;
var detected_key = "";
var detected_scale = "";

// Base64 encoding table
var B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

// ── Initialization ─────────────────────────────────────────────────────────

function bang() {
    // Called by live.thisdevice when device is ready
    if (!initialized) {
        cursor_a = new LiveAPI(null, "live_set");
        cursor_b = new LiveAPI(null, "live_set");
        initialized = true;
        outlet(1, "status", "ready");
        post("LivePilot Bridge: initialized\n");
    }
}

// ── Incoming OSC Message Dispatch ──────────────────────────────────────────

function anything() {
    // OSC messages arrive as messagename — strip leading / if present
    var cmd = messagename;
    if (cmd.charAt(0) === "/") cmd = cmd.substring(1);
    var args = arrayfromargs(arguments);

    // Defer to low-priority thread for LiveAPI safety
    var task = new Task(function() {
        try {
            dispatch(cmd, args);
        } catch(e) {
            send_response({"error": e.message});
        }
    });
    task.schedule(0);
}

function dispatch(cmd, args) {
    switch(cmd) {
        case "ping":
            send_response({"ok": true, "version": "1.6.2"});
            break;
        case "get_params":
            cmd_get_params(args);
            break;
        case "get_hidden_params":
            cmd_get_hidden_params(args);
            break;
        case "get_auto_state":
            cmd_get_auto_state(args);
            break;
        case "walk_rack":
            cmd_walk_rack(args);
            break;
        case "get_chains_deep":
            cmd_get_chains_deep(args);
            break;
        case "get_track_cpu":
            cmd_get_track_cpu(args);
            break;
        case "get_selected":
            cmd_get_selected();
            break;
        case "get_key":
            send_response({"key": detected_key, "scale": detected_scale, "confidence": pitch_history.length});
            break;
        // ── Phase 2: Sample Operations ──
        case "get_clip_file_path":
            cmd_get_clip_file_path(args);
            break;
        case "replace_simpler_sample":
            cmd_replace_simpler_sample(args);
            break;
        case "get_simpler_slices":
            cmd_get_simpler_slices(args);
            break;
        case "crop_simpler":
            cmd_simpler_action(args, "crop");
            break;
        case "reverse_simpler":
            cmd_simpler_action(args, "reverse");
            break;
        case "warp_simpler":
            cmd_simpler_warp(args);
            break;
        // ── Phase 2: Warp Markers ──
        case "get_warp_markers":
            cmd_get_warp_markers(args);
            break;
        case "add_warp_marker":
            cmd_add_warp_marker(args);
            break;
        case "move_warp_marker":
            cmd_move_warp_marker(args);
            break;
        case "remove_warp_marker":
            cmd_remove_warp_marker(args);
            break;
        // ── Phase 2: Clip & Display ──
        case "scrub_clip":
            cmd_scrub_clip(args);
            break;
        case "stop_scrub":
            cmd_stop_scrub(args);
            break;
        case "get_display_values":
            cmd_get_display_values(args);
            break;
        default:
            send_response({"error": "Unknown command: " + cmd});
    }
}

// ── Commands ───────────────────────────────────────────────────────────────

function cmd_get_params(args) {
    // args: [track_index, device_index]
    var track_idx = parseInt(args[0]);
    var device_idx = parseInt(args[1]);
    var path = build_device_path(track_idx, device_idx);

    cursor_a.goto(path);
    var param_count = cursor_a.getcount("parameters");
    var params = [];

    // Chunked reading: 4 params per batch
    var batch_size = 4;
    var current = 0;

    function read_batch() {
        var end = Math.min(current + batch_size, param_count);
        for (var i = current; i < end; i++) {
            cursor_b.goto(path + " parameters " + i);
            var p = {
                index: i,
                name: cursor_b.get("name").toString(),
                value: parseFloat(cursor_b.get("value")),
                min: parseFloat(cursor_b.get("min")),
                max: parseFloat(cursor_b.get("max")),
                is_quantized: parseInt(cursor_b.get("is_quantized")) === 1,
                automation_state: parseInt(cursor_b.get("automation_state")),
                state: parseInt(cursor_b.get("state"))
            };
            // state: 0=enabled, 1=disabled, 2=irrelevant
            // automation_state: 0=none, 1=active, 2=overridden
            params.push(p);
        }
        current = end;

        if (current < param_count) {
            // Schedule next batch in 50ms
            var next_task = new Task(read_batch);
            next_task.schedule(50);
        } else {
            send_response({"track": track_idx, "device": device_idx, "params": params});
        }
    }

    read_batch();
}

function cmd_get_hidden_params(args) {
    // Returns ALL parameters including hidden ones not in ControlSurface API
    // Same as get_params but also includes value_string and whether it's
    // accessible from the standard API
    var track_idx = parseInt(args[0]);
    var device_idx = parseInt(args[1]);
    var path = build_device_path(track_idx, device_idx);

    cursor_a.goto(path);
    var param_count = cursor_a.getcount("parameters");
    var device_name = cursor_a.get("name").toString();
    var params = [];
    var current = 0;
    var batch_size = 4;

    function read_batch() {
        var end = Math.min(current + batch_size, param_count);
        for (var i = current; i < end; i++) {
            cursor_b.goto(path + " parameters " + i);
            params.push({
                index: i,
                name: cursor_b.get("name").toString(),
                value: parseFloat(cursor_b.get("value")),
                min: parseFloat(cursor_b.get("min")),
                max: parseFloat(cursor_b.get("max")),
                default_value: parseFloat(cursor_b.get("default_value")),
                is_quantized: parseInt(cursor_b.get("is_quantized")) === 1,
                value_string: String(cursor_b.call("str_for_value", parseFloat(cursor_b.get("value")))),
                automation_state: parseInt(cursor_b.get("automation_state")),
                state: parseInt(cursor_b.get("state"))
            });
        }
        current = end;

        if (current < param_count) {
            var next_task = new Task(read_batch);
            next_task.schedule(50);
        } else {
            send_response({
                "track": track_idx,
                "device": device_idx,
                "device_name": device_name,
                "total_params": param_count,
                "params": params
            });
        }
    }

    read_batch();
}

function cmd_get_auto_state(args) {
    // args: [track_index, device_index]
    var track_idx = parseInt(args[0]);
    var device_idx = parseInt(args[1]);
    var path = build_device_path(track_idx, device_idx);

    cursor_a.goto(path);
    var param_count = cursor_a.getcount("parameters");
    var results = [];
    var current = 0;
    var batch_size = 4;

    function read_batch() {
        var end = Math.min(current + batch_size, param_count);
        for (var i = current; i < end; i++) {
            cursor_b.goto(path + " parameters " + i);
            var state = parseInt(cursor_b.get("automation_state"));
            // Only include params that HAVE automation (skip state=0)
            if (state > 0) {
                results.push({
                    index: i,
                    name: cursor_b.get("name").toString(),
                    automation_state: state,
                    // 1 = automation active, 2 = automation overridden (user moved knob)
                    state_label: state === 1 ? "active" : "overridden"
                });
            }
        }
        current = end;

        if (current < param_count) {
            var next_task = new Task(read_batch);
            next_task.schedule(50);
        } else {
            send_response({
                "track": track_idx,
                "device": device_idx,
                "total_params": param_count,
                "automated_params": results,
                "automated_count": results.length
            });
        }
    }

    read_batch();
}

function cmd_walk_rack(args) {
    // Recursively walk a device's chain tree (racks, drum pads, nested devices)
    var track_idx = parseInt(args[0]);
    var device_idx = parseInt(args[1]);
    var path = build_device_path(track_idx, device_idx);

    var tree = walk_device(path, 0);
    send_response({"track": track_idx, "device": device_idx, "tree": tree});
}

function walk_device(path, depth) {
    if (depth > 6) return {"error": "max depth reached"};

    // Read all properties from cursor BEFORE recursing — recursion
    // overwrites both cursors, so we must capture everything first.
    cursor_a.goto(path);
    var result = {
        name: cursor_a.get("name").toString(),
        class_name: cursor_a.get("class_name").toString(),
        is_active: parseInt(cursor_a.get("is_active")) === 1,
        can_have_chains: parseInt(cursor_a.get("can_have_chains")) === 1,
        can_have_drum_pads: parseInt(cursor_a.get("can_have_drum_pads")) === 1,
        param_count: cursor_a.getcount("parameters")
    };

    // Capture chain/pad counts BEFORE recursion clobbers cursors
    var chain_count = result.can_have_chains ? cursor_a.getcount("chains") : 0;
    var pad_count = result.can_have_drum_pads ? cursor_a.getcount("drum_pads") : 0;

    if (chain_count > 0) {
        result.chains = [];
        for (var c = 0; c < chain_count; c++) {
            var chain_path = path + " chains " + c;
            // Re-goto cursor_b each iteration (recursion may have moved it)
            cursor_b.goto(chain_path);
            var chain = {
                index: c,
                name: cursor_b.get("name").toString(),
                devices: []
            };
            var dev_count = cursor_b.getcount("devices");
            for (var d = 0; d < dev_count; d++) {
                chain.devices.push(walk_device(chain_path + " devices " + d, depth + 1));
            }
            result.chains.push(chain);
        }
    }

    if (pad_count > 0) {
        result.drum_pads = [];
        for (var p = 0; p < Math.min(pad_count, 128); p++) {
            var pad_path = path + " drum_pads " + p;
            cursor_b.goto(pad_path);
            var chain_count2 = cursor_b.getcount("chains");
            if (chain_count2 > 0) {
                result.drum_pads.push({
                    index: p,
                    note: parseInt(cursor_b.get("note")),
                    name: cursor_b.get("name").toString(),
                    chain_count: chain_count2
                });
            }
        }
    }

    return result;
}

function cmd_get_chains_deep(args) {
    // Get detailed chain info including all devices in each chain
    var track_idx = parseInt(args[0]);
    var device_idx = parseInt(args[1]);
    var path = build_device_path(track_idx, device_idx);

    cursor_a.goto(path);
    var chain_count = cursor_a.getcount("chains");
    var chains = [];

    for (var c = 0; c < chain_count; c++) {
        var chain_path = path + " chains " + c;
        cursor_b.goto(chain_path);
        var chain = {
            index: c,
            name: cursor_b.get("name").toString(),
            volume: parseFloat(cursor_b.get("volume")),
            panning: parseFloat(cursor_b.get("panning")),
            mute: parseInt(cursor_b.get("mute")) === 1,
            solo: parseInt(cursor_b.get("solo")) === 1,
            devices: []
        };

        var dev_count = cursor_b.getcount("devices");
        for (var d = 0; d < dev_count; d++) {
            cursor_a.goto(chain_path + " devices " + d);
            chain.devices.push({
                index: d,
                name: cursor_a.get("name").toString(),
                class_name: cursor_a.get("class_name").toString(),
                is_active: parseInt(cursor_a.get("is_active")) === 1,
                param_count: cursor_a.getcount("parameters")
            });
        }
        chains.push(chain);
    }

    send_response({"track": track_idx, "device": device_idx, "chains": chains});
}

function cmd_get_track_cpu(args) {
    // Get CPU performance impact per track
    var results = [];
    cursor_a.goto("live_set");
    var track_count = cursor_a.getcount("tracks");

    for (var t = 0; t < track_count; t++) {
        cursor_b.goto("live_set tracks " + t);
        results.push({
            index: t,
            name: cursor_b.get("name").toString(),
            // performance_impact is 0.0-1.0 representing CPU load
            cpu: parseFloat(cursor_b.get("performance_impact") || 0)
        });
    }

    send_response({"tracks": results, "count": track_count});
}

function cmd_get_selected() {
    // What the user is currently focused on
    cursor_a.goto("live_set view");

    var result = {
        selected_track: -1,
        selected_track_name: "",
        selected_scene: -1,
        detail_clip: null,
        appointed_device: null
    };

    // Selected track
    try {
        cursor_b.goto("live_set view selected_track");
        result.selected_track_name = cursor_b.get("name").toString();
        // Get track index by walking tracks
        cursor_a.goto("live_set");
        var tc = cursor_a.getcount("tracks");
        for (var i = 0; i < tc; i++) {
            cursor_a.goto("live_set tracks " + i);
            if (cursor_a.get("name").toString() === result.selected_track_name) {
                result.selected_track = i;
                break;
            }
        }
    } catch(e) {}

    // Selected scene
    try {
        cursor_a.goto("live_set view selected_scene");
        result.selected_scene = parseInt(cursor_a.get("scene_index") || -1);
    } catch(e) {}

    // Appointed device (blue hand)
    try {
        cursor_a.goto("live_set appointed_device");
        result.appointed_device = {
            name: cursor_a.get("name").toString(),
            class_name: cursor_a.get("class_name").toString()
        };
    } catch(e) {}

    send_response(result);
}

// ── Key Detection ──────────────────────────────────────────────────────────

function pitch_in(midi_note, amplitude) {
    // Called from sigmund~ via the Max patch
    // midi_note is fractional (e.g., 69.02 for ~440 Hz)
    if (amplitude < 0.01) return; // Skip silence

    var rounded = Math.round(midi_note) % 12; // Pitch class 0-11
    pitch_history.push(rounded);
    if (pitch_history.length > MAX_PITCH_HISTORY) {
        pitch_history.shift();
    }

    // Only analyze when we have enough data
    if (pitch_history.length >= 16) {
        detect_key();
    }
}

function detect_key() {
    // Krumhansl-Schmuckler key-finding algorithm (simplified)
    // Count occurrences of each pitch class
    var counts = [0,0,0,0,0,0,0,0,0,0,0,0];
    for (var i = 0; i < pitch_history.length; i++) {
        counts[pitch_history[i]]++;
    }

    // Major and minor profiles (Krumhansl)
    var major = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88];
    var minor = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17];
    var note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

    var best_corr = -999;
    var best_key = 0;
    var best_scale = "major";

    // Test all 24 keys (12 major + 12 minor)
    for (var k = 0; k < 12; k++) {
        var rotated = [];
        for (var n = 0; n < 12; n++) {
            rotated.push(counts[(n + k) % 12]);
        }

        // Correlate with major profile
        var corr_major = correlate(rotated, major);
        if (corr_major > best_corr) {
            best_corr = corr_major;
            best_key = k;
            best_scale = "major";
        }

        // Correlate with minor profile
        var corr_minor = correlate(rotated, minor);
        if (corr_minor > best_corr) {
            best_corr = corr_minor;
            best_key = k;
            best_scale = "minor";
        }
    }

    detected_key = note_names[best_key];
    detected_scale = best_scale;

    // Send to UI
    outlet(1, "key", detected_key + " " + detected_scale);
}

function correlate(a, b) {
    // Pearson correlation coefficient
    var n = a.length;
    var sum_a = 0, sum_b = 0, sum_ab = 0, sum_a2 = 0, sum_b2 = 0;
    for (var i = 0; i < n; i++) {
        sum_a += a[i];
        sum_b += b[i];
        sum_ab += a[i] * b[i];
        sum_a2 += a[i] * a[i];
        sum_b2 += b[i] * b[i];
    }
    var denom = Math.sqrt((n * sum_a2 - sum_a * sum_a) * (n * sum_b2 - sum_b * sum_b));
    if (denom === 0) return 0;
    return (n * sum_ab - sum_a * sum_b) / denom;
}

// ── Response Encoding ──────────────────────────────────────────────────────

function send_response(obj) {
    var json = JSON.stringify(obj);
    var encoded = base64_encode(json);

    // Check if chunking needed (Max OSC packet limit ~8KB)
    if (encoded.length < 1400) {
        outlet(0, "/response", encoded);
    } else {
        // Split into chunks
        var chunk_size = 1400;
        var total = Math.ceil(encoded.length / chunk_size);
        for (var i = 0; i < total; i++) {
            var piece = encoded.substring(i * chunk_size, (i + 1) * chunk_size);
            outlet(0, "/response_chunk", i, total, piece);
        }
    }
}

function base64_encode(str) {
    var result = "";
    var bytes = [];
    for (var i = 0; i < str.length; i++) {
        bytes.push(str.charCodeAt(i) & 0xFF);
    }

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

// ── Phase 2: Sample Operations ────────────────────────────────────────

function cmd_get_clip_file_path(args) {
    var track_idx = parseInt(args[0]);
    var clip_idx = parseInt(args[1]);
    var path = build_track_path(track_idx) + " clip_slots " + clip_idx + " clip";

    cursor_a.goto(path);
    if (cursor_a.id === 0) {
        send_response({"error": "No clip at track " + track_idx + " slot " + clip_idx});
        return;
    }

    try {
        var sample_path = cursor_a.get("file_path").toString();
        send_response({
            "track": track_idx,
            "clip": clip_idx,
            "file_path": sample_path,
            "length": parseFloat(cursor_a.get("length")),
            "name": cursor_a.get("name").toString()
        });
    } catch(e) {
        send_response({"error": "Clip has no audio file (MIDI clip?): " + e.message});
    }
}

function cmd_replace_simpler_sample(args) {
    var track_idx = parseInt(args[0]);
    var device_idx = parseInt(args[1]);
    // Reconstruct file path — spaces in path split into multiple OSC args
    var parts = [];
    for (var i = 2; i < args.length; i++) parts.push(args[i].toString());
    var file_path = parts.join(" ");
    var path = build_device_path(track_idx, device_idx);

    cursor_a.goto(path);
    var class_name = cursor_a.get("class_name").toString();

    if (class_name !== "OriginalSimpler") {
        send_response({"error": "Device is " + class_name + ", not Simpler"});
        return;
    }

    try {
        cursor_a.call("replace_sample", file_path);
        send_response({
            "track": track_idx,
            "device": device_idx,
            "sample_loaded": file_path,
            "name": cursor_a.get("name").toString()
        });
    } catch(e) {
        send_response({"error": "Failed to load sample: " + e.message + ". Ensure Simpler already has a sample loaded."});
    }
}

function cmd_get_simpler_slices(args) {
    var track_idx = parseInt(args[0]);
    var device_idx = parseInt(args[1]);
    var path = build_device_path(track_idx, device_idx);

    cursor_a.goto(path);
    if (cursor_a.get("class_name").toString() !== "OriginalSimpler") {
        send_response({"error": "Not a Simpler device"});
        return;
    }

    var playback_mode = parseInt(cursor_a.get("playback_mode"));

    // Sample metadata from SimplerDevice.sample child
    var sample_rate = 0;
    var length = 0;
    try {
        cursor_b.goto(path + " sample");
        sample_rate = parseFloat(cursor_b.get("sample_rate"));
        length = parseFloat(cursor_b.get("length"));
    } catch(e) {}

    // Slice points are on the Sample child object, property name is "slices"
    var slices = [];
    try {
        cursor_b.goto(path + " sample");
        var slice_data = cursor_b.get("slices");
        if (slice_data && slice_data.length) {
            for (var i = 0; i < slice_data.length; i++) {
                slices.push({
                    index: i,
                    frame: parseInt(slice_data[i]),
                    seconds: sample_rate > 0 ? parseFloat(slice_data[i]) / sample_rate : 0
                });
            }
        }
    } catch(e) {}

    send_response({
        "track": track_idx,
        "device": device_idx,
        "playback_mode": playback_mode,
        "playback_mode_name": ["Classic", "One-Shot", "Slicing"][playback_mode] || "Unknown",
        "sample_rate": sample_rate,
        "sample_length_frames": length,
        "sample_length_seconds": sample_rate > 0 ? length / sample_rate : 0,
        "slice_count": slices.length,
        "slices": slices
    });
}

function cmd_simpler_action(args, action) {
    var track_idx = parseInt(args[0]);
    var device_idx = parseInt(args[1]);
    var path = build_device_path(track_idx, device_idx);

    cursor_a.goto(path);
    if (cursor_a.get("class_name").toString() !== "OriginalSimpler") {
        send_response({"error": "Not a Simpler device"});
        return;
    }

    try {
        cursor_a.call(action);
        send_response({"track": track_idx, "device": device_idx, "action": action, "ok": true});
    } catch(e) {
        send_response({"error": action + " failed: " + e.message});
    }
}

function cmd_simpler_warp(args) {
    var track_idx = parseInt(args[0]);
    var device_idx = parseInt(args[1]);
    var beats = parseInt(args[2]);
    var path = build_device_path(track_idx, device_idx);

    cursor_a.goto(path);
    if (cursor_a.get("class_name").toString() !== "OriginalSimpler") {
        send_response({"error": "Not a Simpler device"});
        return;
    }

    try {
        cursor_a.call("warp", beats);
        send_response({"track": track_idx, "device": device_idx, "warped_to_beats": beats, "ok": true});
    } catch(e) {
        send_response({"error": "warp failed: " + e.message});
    }
}

// ── Phase 2: Warp Markers ─────────────────────────────────────────────

function cmd_get_warp_markers(args) {
    var track_idx = parseInt(args[0]);
    var clip_idx = parseInt(args[1]);
    var path = build_track_path(track_idx) + " clip_slots " + clip_idx + " clip";

    cursor_a.goto(path);
    if (cursor_a.id === 0) {
        send_response({"error": "No clip at track " + track_idx + " slot " + clip_idx});
        return;
    }

    try {
        // warp_markers is a dict property (not children) — returns JSON string
        var raw = cursor_a.get("warp_markers");
        var parsed;
        try {
            // get() may return string directly or as single-element array
            parsed = JSON.parse(raw);
        } catch(e1) {
            try {
                parsed = JSON.parse(raw[0]);
            } catch(e2) {
                send_response({"error": "Cannot parse warp_markers dict: raw=" + raw});
                return;
            }
        }
        var markers = parsed["warp_markers"] || [];
        var result = [];
        for (var i = 0; i < markers.length; i++) {
            result.push({
                beat_time: markers[i]["beat_time"],
                sample_time: markers[i]["sample_time"]
            });
        }
        send_response({
            "track": track_idx,
            "clip": clip_idx,
            "marker_count": result.length,
            "markers": result
        });
    } catch(e) {
        send_response({"error": "Cannot read warp markers (MIDI clip?): " + e.message});
    }
}

function cmd_add_warp_marker(args) {
    var track_idx = parseInt(args[0]);
    var clip_idx = parseInt(args[1]);
    var beat_time = parseFloat(args[2]);
    var path = build_track_path(track_idx) + " clip_slots " + clip_idx + " clip";

    cursor_a.goto(path);
    if (cursor_a.id === 0) {
        send_response({"error": "No clip"});
        return;
    }

    try {
        cursor_a.call("add_warp_marker", beat_time);
        send_response({"track": track_idx, "clip": clip_idx, "added_at_beat": beat_time, "ok": true});
    } catch(e) {
        send_response({"error": "Failed to add warp marker: " + e.message});
    }
}

function cmd_move_warp_marker(args) {
    var track_idx = parseInt(args[0]);
    var clip_idx = parseInt(args[1]);
    var old_beat = parseFloat(args[2]);
    var new_beat = parseFloat(args[3]);
    var path = build_track_path(track_idx) + " clip_slots " + clip_idx + " clip";

    cursor_a.goto(path);
    if (cursor_a.id === 0) {
        send_response({"error": "No clip"});
        return;
    }

    try {
        cursor_a.call("move_warp_marker", old_beat, new_beat);
        send_response({"track": track_idx, "clip": clip_idx, "moved_from": old_beat, "moved_to": new_beat, "ok": true});
    } catch(e) {
        send_response({"error": "Failed to move warp marker: " + e.message});
    }
}

function cmd_remove_warp_marker(args) {
    var track_idx = parseInt(args[0]);
    var clip_idx = parseInt(args[1]);
    var beat_time = parseFloat(args[2]);
    var path = build_track_path(track_idx) + " clip_slots " + clip_idx + " clip";

    cursor_a.goto(path);
    if (cursor_a.id === 0) {
        send_response({"error": "No clip"});
        return;
    }

    try {
        cursor_a.call("remove_warp_marker", beat_time);
        send_response({"track": track_idx, "clip": clip_idx, "removed_at_beat": beat_time, "ok": true});
    } catch(e) {
        send_response({"error": "Failed to remove warp marker: " + e.message});
    }
}

// ── Phase 2: Clip & Display ───────────────────────────────────────────

function cmd_scrub_clip(args) {
    var track_idx = parseInt(args[0]);
    var clip_idx = parseInt(args[1]);
    var beat_time = parseFloat(args[2]);
    var path = build_track_path(track_idx) + " clip_slots " + clip_idx + " clip";

    cursor_a.goto(path);
    if (cursor_a.id === 0) {
        send_response({"error": "No clip"});
        return;
    }

    try {
        cursor_a.call("scrub", beat_time);
        send_response({"track": track_idx, "clip": clip_idx, "scrubbing_at": beat_time, "ok": true});
    } catch(e) {
        send_response({"error": "Scrub failed: " + e.message});
    }
}

function cmd_stop_scrub(args) {
    var track_idx = parseInt(args[0]);
    var clip_idx = parseInt(args[1]);
    var path = build_track_path(track_idx) + " clip_slots " + clip_idx + " clip";

    cursor_a.goto(path);
    try {
        cursor_a.call("stop_scrub");
        send_response({"ok": true});
    } catch(e) {
        send_response({"error": e.message});
    }
}

function cmd_get_display_values(args) {
    var track_idx = parseInt(args[0]);
    var device_idx = parseInt(args[1]);
    var path = build_device_path(track_idx, device_idx);

    cursor_a.goto(path);
    var param_count = cursor_a.getcount("parameters");
    var device_name = cursor_a.get("name").toString();
    var params = [];
    var current = 0;
    var batch_size = 4;

    function read_batch() {
        var end = Math.min(current + batch_size, param_count);
        for (var i = current; i < end; i++) {
            cursor_b.goto(path + " parameters " + i);
            var state = parseInt(cursor_b.get("state"));
            if (state !== 2) {
                params.push({
                    index: i,
                    name: cursor_b.get("name").toString(),
                    display_value: String(cursor_b.call("str_for_value", parseFloat(cursor_b.get("value")))),
                    value: parseFloat(cursor_b.get("value"))
                });
            }
        }
        current = end;
        if (current < param_count) {
            var next_task = new Task(read_batch);
            next_task.schedule(50);
        } else {
            send_response({
                "track": track_idx,
                "device": device_idx,
                "device_name": device_name,
                "params": params
            });
        }
    }
    read_batch();
}

// ── Helpers ────────────────────────────────────────────────────────────────

function build_track_path(track_idx) {
    if (track_idx === -1000) {
        return "live_set master_track";
    } else if (track_idx < 0) {
        var ri = Math.abs(track_idx) - 1;
        return "live_set return_tracks " + ri;
    } else {
        return "live_set tracks " + track_idx;
    }
}

function build_device_path(track_idx, device_idx) {
    if (track_idx === -1000) {
        return "live_set master_track devices " + device_idx;
    } else if (track_idx < 0) {
        var ri = Math.abs(track_idx) - 1;
        return "live_set return_tracks " + ri + " devices " + device_idx;
    } else {
        return "live_set tracks " + track_idx + " devices " + device_idx;
    }
}
