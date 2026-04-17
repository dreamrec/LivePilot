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
 *
 * OSC address convention:
 *   - OUTGOING (this file → server via udpsend): use WITH leading slash,
 *       e.g. outlet(0, "/response", encoded). The slash is part of the
 *       OSC address that udpsend packs into the packet.
 *   - INCOMING (server → this file via udpreceive): Max's udpreceive
 *       routes on the selector, so the server's address string must be
 *       "response"/"cmd" WITHOUT a leading slash (Max would otherwise
 *       treat the slash as a literal selector character). See
 *       mcp_server/m4l_bridge.py for the sending side and `_parse_osc`
 *       for the tolerant normalization.
 */

autowatch = 1;
inlets = 2;  // 0: OSC commands, 1: dspstate~ (sample rate)
outlets = 2; // 0: to udpsend (responses), 1: to buffer~/status

// ── State ──────────────────────────────────────────────────────────────────

var cursor_a = null;  // Primary LiveAPI cursor
var cursor_b = null;  // Secondary cursor for nested walks
var initialized = false;
var pitch_history = []; // Rolling buffer for key detection
var MAX_PITCH_HISTORY = 128;
var detected_key = "";
var detected_scale = "";

// Capture state
var capture_active = false;
var capture_timer = null;
var capture_filename = "";
var capture_file_path = "";
var current_sample_rate = 44100; // Updated by dspstate~ via inlet 1

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

// ── DSP State (inlet 1: dspstate~ sample rate) ─────────────────────────────

function msg_int(v) {
    // dspstate~ sends the sample rate as an int on inlet 1
    if (inlet === 1) {
        current_sample_rate = v > 0 ? v : 44100;
    }
}

// ── Incoming OSC Message Dispatch ──────────────────────────────────────────

function anything() {
    // OSC messages arrive as messagename — strip leading / if present
    var cmd = messagename;
    if (cmd.charAt(0) === "/") cmd = cmd.substring(1);
    var args = _decode_arg_strings(arrayfromargs(arguments));

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
            send_response({"ok": true, "version": "1.10.6"});
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
        // ── Phase 3: Capture ──
        case "capture_audio":
            cmd_capture_audio(args);
            break;
        case "capture_stop":
            cmd_capture_stop();
            break;
        case "check_flucoma":
            cmd_check_flucoma();
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
        // ── Plugin Parameters ──
        case "get_plugin_params":
            cmd_get_plugin_params(args);
            break;
        case "map_plugin_param":
            cmd_map_plugin_param(args);
            break;
        case "get_plugin_presets":
            cmd_get_plugin_presets(args);
            break;
        // ── BUG-A2 / A3: deep-LOM properties not on the automatable surface ──
        case "simpler_set_warp":
            cmd_simpler_set_warp(args);
            break;
        case "compressor_set_sidechain":
            cmd_compressor_set_sidechain(args);
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

    var batch_size = 8;
    var current = 0;

    function read_batch() {
        try {
            var end = Math.min(current + batch_size, param_count);
            for (var i = current; i < end; i++) {
                cursor_b.goto(path + " parameters " + i);
                params.push({
                    index: i,
                    name: cursor_b.get("name").toString(),
                    value: parseFloat(cursor_b.get("value")),
                    min: parseFloat(cursor_b.get("min")),
                    max: parseFloat(cursor_b.get("max")),
                    is_quantized: parseInt(cursor_b.get("is_quantized")) === 1,
                    automation_state: parseInt(cursor_b.get("automation_state")),
                    state: parseInt(cursor_b.get("state"))
                });
            }
            current = end;

            if (current < param_count) {
                var next_task = new Task(read_batch);
                next_task.schedule(20);
            } else {
                send_response({"track": track_idx, "device": device_idx, "params": params});
            }
        } catch (e) {
            send_response({
                "error": "Failed reading parameter " + current + ": " + String(e),
                "track": track_idx,
                "device": device_idx,
                "partial_params": params
            });
        }
    }

    read_batch();
}

function cmd_get_hidden_params(args) {
    // Returns ALL parameters including hidden ones not in ControlSurface API
    // Includes value_string (human-readable) via str_for_value where safe
    var track_idx = parseInt(args[0]);
    var device_idx = parseInt(args[1]);
    var path = build_device_path(track_idx, device_idx);

    cursor_a.goto(path);
    var param_count = cursor_a.getcount("parameters");
    var device_name = cursor_a.get("name").toString();
    var device_class = cursor_a.get("class_name").toString();
    var params = [];
    var current = 0;
    var batch_size = 8;

    function read_batch() {
        try {
            var end = Math.min(current + batch_size, param_count);
            for (var i = current; i < end; i++) {
                cursor_b.goto(path + " parameters " + i);
                var val = parseFloat(cursor_b.get("value"));
                params.push({
                    index: i,
                    name: cursor_b.get("name").toString(),
                    value: val,
                    value_string: _safe_display_string(cursor_b, val, device_class),
                    min: parseFloat(cursor_b.get("min")),
                    max: parseFloat(cursor_b.get("max")),
                    default_value: parseFloat(cursor_b.get("default_value")),
                    is_quantized: parseInt(cursor_b.get("is_quantized")) === 1,
                    automation_state: parseInt(cursor_b.get("automation_state")),
                    state: parseInt(cursor_b.get("state"))
                });
            }
            current = end;

            if (current < param_count) {
                var next_task = new Task(read_batch);
                next_task.schedule(20);
            } else {
                send_response({
                    "track": track_idx,
                    "device": device_idx,
                    "device_name": device_name,
                    "total_params": param_count,
                    "params": params
                });
            }
        } catch (e) {
            send_response({
                "error": "Failed reading parameter " + current + ": " + String(e),
                "track": track_idx,
                "device": device_idx,
                "device_name": device_name,
                "partial_params": params
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
    var batch_size = 8;

    function read_batch() {
        try {
            var end = Math.min(current + batch_size, param_count);
            for (var i = current; i < end; i++) {
                cursor_b.goto(path + " parameters " + i);
                var state = parseInt(cursor_b.get("automation_state"));
                if (state > 0) {
                    results.push({
                        index: i,
                        name: cursor_b.get("name").toString(),
                        automation_state: state,
                        state_label: state === 1 ? "active" : "overridden"
                    });
                }
            }
            current = end;

            if (current < param_count) {
                var next_task = new Task(read_batch);
                next_task.schedule(20);
            } else {
                send_response({
                    "track": track_idx,
                    "device": device_idx,
                    "total_params": param_count,
                    "automated_params": results,
                    "automated_count": results.length
                });
            }
        } catch (e) {
            send_response({
                "error": "Failed reading automation state at param " + current + ": " + String(e),
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
    var track_idx = parseInt(args[0]);
    var device_idx = parseInt(args[1]);
    var path = build_device_path(track_idx, device_idx);

    try {
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
    } catch (e) {
        send_response({"error": "Failed reading chains: " + String(e), "track": track_idx, "device": device_idx});
    }
}

function cmd_check_flucoma() {
    // Check if FluCoMa externals are installed.
    // Max JS cannot reliably probe the object search path at runtime,
    // so we check if the FluCoMa package folder exists on disk.
    try {
        var pkg_path = max.appsupportpath + "/Packages/FluidCorpusManipulation";
        var f = new Folder(pkg_path);
        var available = !f.end;  // end === true means folder not found
        f.close();
        send_response({"flucoma_available": available});
    } catch (e) {
        // Can't probe — report unknown rather than lying
        send_response({"flucoma_available": false, "probe_error": String(e)});
    }
}

function cmd_get_track_cpu(args) {
    try {
        var results = [];
        cursor_a.goto("live_set");
        var track_count = cursor_a.getcount("tracks");

        for (var t = 0; t < track_count; t++) {
            cursor_b.goto("live_set tracks " + t);
            var cpu = 0;
            try {
                cpu = parseFloat(cursor_b.get("performance_impact") || 0);
            } catch (e) {
                cpu = -1;
            }
            results.push({
                index: t,
                name: cursor_b.get("name").toString(),
                cpu: cpu
            });
        }

        send_response({"tracks": results, "count": track_count});
    } catch (e) {
        send_response({"error": "Failed reading track CPU: " + String(e)});
    }
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

    // Selected track — match by object ID (not name, which can be duplicated)
    try {
        cursor_b.goto("live_set view selected_track");
        result.selected_track_name = cursor_b.get("name").toString();
        var selected_id = cursor_b.id;
        // Get track index by walking tracks and comparing IDs
        cursor_a.goto("live_set");
        var tc = cursor_a.getcount("tracks");
        for (var i = 0; i < tc; i++) {
            cursor_a.goto("live_set tracks " + i);
            if (cursor_a.id === selected_id) {
                result.selected_track = i;
                break;
            }
        }
        // Check return tracks if not found in main tracks
        if (result.selected_track === -1) {
            cursor_a.goto("live_set");
            var rtc = cursor_a.getcount("return_tracks");
            for (var j = 0; j < rtc; j++) {
                cursor_a.goto("live_set return_tracks " + j);
                if (cursor_a.id === selected_id) {
                    result.selected_track = -(j + 1);  // -1, -2, ... convention
                    break;
                }
            }
        }
        // Check master track if still not found
        if (result.selected_track === -1) {
            cursor_a.goto("live_set master_track");
            if (cursor_a.id === selected_id) {
                result.selected_track = -1000;  // master convention
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
    // UTF-8 encode first, then base64 encode the byte sequence.
    // This preserves non-ASCII characters (accented names, CJK, emoji)
    // that would otherwise be truncated by charCodeAt & 0xFF.
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
    // Convert a JavaScript string to a UTF-8 byte array.
    // Handles codepoints U+0000..U+FFFF (BMP) which covers all
    // characters Max JS can produce from LiveAPI get() calls.
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

        if (c0 < 0 || c1 < 0 || (c2 < 0 && i + 2 < clean.length) || (c3 < 0 && i + 3 < clean.length)) {
            throw new Error("Invalid base64 input");
        }

        bytes.push(((c0 << 2) | (c1 >> 4)) & 0xFF);
        if (c2 !== -1) {
            bytes.push((((c1 & 15) << 4) | (c2 >> 2)) & 0xFF);
        }
        if (c3 !== -1) {
            bytes.push((((c2 & 3) << 6) | c3) & 0xFF);
        }
    }

    return bytes;
}

function _utf8_decode(bytes) {
    // Convert a UTF-8 byte array back to a JavaScript string.
    // Handles BMP codepoints and 4-byte sequences (emoji/supplementary planes).
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
            // 3-byte sequence (U+0800..U+FFFF)
            var b1_3 = bytes[i + 1];
            var b2_3 = bytes[i + 2];
            result += String.fromCharCode(
                ((b0 & 0x0F) << 12) |
                ((b1_3 & 0x3F) << 6) |
                (b2_3 & 0x3F)
            );
            i += 3;
        } else if ((b0 & 0xF8) === 0xF0 && i + 3 < bytes.length) {
            // 4-byte sequence (U+10000..U+10FFFF) — emoji and supplementary planes
            var cp = ((b0 & 0x07) << 18) |
                     ((bytes[i + 1] & 0x3F) << 12) |
                     ((bytes[i + 2] & 0x3F) << 6) |
                     (bytes[i + 3] & 0x3F);
            // Encode as UTF-16 surrogate pair
            cp -= 0x10000;
            result += String.fromCharCode(0xD800 + (cp >> 10));
            result += String.fromCharCode(0xDC00 + (cp & 0x3FF));
            i += 4;
        } else {
            // Skip invalid byte
            i += 1;
        }
    }
    return result;
}

function _decode_b64_arg(arg) {
    if (arg === null || arg === undefined) {
        return arg;
    }
    var text = String(arg);
    if (text.indexOf("b64:") !== 0) {
        return arg;
    }
    try {
        return _utf8_decode(base64_decode(text.substring(4)));
    } catch (e) {
        return arg;
    }
}

function _decode_arg_strings(args) {
    var decoded = [];
    for (var i = 0; i < args.length; i++) {
        decoded.push(_decode_b64_arg(args[i]));
    }
    return decoded;
}

function _to_posix_path(path) {
    if (!path || path.length < 2) return path;

    // Keep Windows-style drive paths unchanged.
    if (path.length >= 3 && path.charAt(1) === ":" &&
        (path.charAt(2) === "/" || path.charAt(2) === "\\")) {
        return path;
    }

    var colon = path.indexOf(":");
    var slash = path.indexOf("/");
    if (colon <= 0 || (slash !== -1 && colon > slash)) {
        return path;
    }

    var rest = path.substring(colon + 1);
    if (rest.indexOf(":") !== -1) {
        rest = rest.replace(/:/g, "/");
    }
    if (rest.charAt(0) !== "/") {
        rest = "/" + rest.replace(/^[/\\]+/, "");
    }
    return rest;
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
            "file_path": _to_posix_path(sample_path),
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
    // Keep the join for backward compatibility with older clients.
    // Current clients send file paths as a single decoded b64: arg.
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

// ── BUG-A2: Simpler warping property + warp_mode ─────────────────────
//
// Python's Remote Script ControlSurface API only exposes automatable
// parameters. Simpler's `warping` and `warp_mode` live on the sample
// child object (SimplerDevice.sample.*) — unreachable from the Python
// side. Max JS LiveAPI can step INTO the sample child, so we do the
// property write here and surface the result to the MCP server.
//
// args: [track_index, device_index, warp_on (0/1), warp_mode (-1 = leave alone, 0..6)]
//   warp_mode: 0=Beats, 1=Tones, 2=Texture, 3=Re-Pitch, 4=Complex, 6=Complex Pro
//
// Returns: {ok, warping, warp_mode} on success, {error} otherwise.
function cmd_simpler_set_warp(args) {
    var track_idx = parseInt(args[0]);
    var device_idx = parseInt(args[1]);
    var warp_on = parseInt(args[2]);
    var warp_mode = args.length > 3 ? parseInt(args[3]) : -1;

    var device_path = build_device_path(track_idx, device_idx);
    cursor_a.goto(device_path);
    if (cursor_a.id === 0) {
        send_response({"error": "Device not found at track " + track_idx + ", device " + device_idx});
        return;
    }
    if (cursor_a.get("class_name").toString() !== "OriginalSimpler") {
        send_response({"error": "Not a Simpler device (class is " + cursor_a.get("class_name") + ")"});
        return;
    }

    // Step into the sample child — warping + warp_mode live there, not on
    // the device itself.
    try {
        cursor_a.goto(device_path + " sample");
        if (cursor_a.id === 0) {
            send_response({"error": "Simpler has no sample loaded (warping not applicable)"});
            return;
        }
        cursor_a.set("warping", warp_on ? 1 : 0);
        if (warp_on && warp_mode >= 0) {
            cursor_a.set("warp_mode", warp_mode);
        }
        // Read back so the caller can confirm the write landed
        var read_warping = parseInt(cursor_a.get("warping"));
        var read_warp_mode = parseInt(cursor_a.get("warp_mode"));
        send_response({
            "ok": true,
            "track_index": track_idx,
            "device_index": device_idx,
            "warping": read_warping,
            "warp_mode": read_warp_mode,
        });
    } catch(e) {
        send_response({"error": "simpler_set_warp failed: " + e.message});
    }
}

// ── BUG-A3: Compressor sidechain input routing ───────────────────────
//
// Sidechain INPUT ROUTING is exposed as LiveAPI properties on the
// Compressor device in Live 11+: sidechain_input_routing_type and
// sidechain_input_routing_channel. They don't appear in the automatable
// parameter list so the Python Remote Script can't reach them; Max JS
// LiveAPI can.
//
// args: [track_index, device_index, routing_type, routing_channel]
//   routing_type: string — e.g. "1-Audio From" / track name / "Ext. In"
//   routing_channel: string — "Post FX" / "Pre FX" / "Post Mixer" / ...
//
// Returns: {ok, sidechain: {type, channel}} on success.
// Older Live versions without these properties return a clean error.
function cmd_compressor_set_sidechain(args) {
    var track_idx = parseInt(args[0]);
    var device_idx = parseInt(args[1]);
    var routing_type = String(args[2] || "");
    var routing_channel = String(args[3] || "");

    var path = build_device_path(track_idx, device_idx);
    cursor_a.goto(path);
    if (cursor_a.id === 0) {
        send_response({"error": "Device not found at track " + track_idx + ", device " + device_idx});
        return;
    }
    var class_name = String(cursor_a.get("class_name"));
    if (class_name !== "Compressor2" && class_name !== "Compressor") {
        send_response({"error": "Not a Compressor device (class is " + class_name + ")"});
        return;
    }

    // Helper: read a LiveAPI property that returns a JSON-serialized dict
    // or list. Max's `get()` wraps results in a single-element array,
    // and complex properties come back as JSON strings.
    function read_json_prop(name) {
        try {
            var raw = cursor_a.get(name);
            if (raw === null || raw === undefined) return null;
            if (Object.prototype.toString.call(raw) === "[object Array]" && raw.length === 1) {
                raw = raw[0];
            }
            if (typeof raw === "string") {
                try { return JSON.parse(raw); } catch(e) { return raw; }
            }
            return raw;
        } catch(e) {
            return null;
        }
    }

    function find_by_name(list, name) {
        if (!list || !list.length || !name) return null;
        for (var i = 0; i < list.length; i++) {
            var entry = list[i];
            if (!entry) continue;
            var n = entry.display_name || entry.name;
            if (n === name) return entry;
        }
        return null;
    }

    try {
        // Enable sidechain first — Live rejects routing writes on a
        // compressor with the sidechain disabled. Property is available
        // on Live 10+. Try/catch for legacy builds.
        try { cursor_a.set("sidechain_enabled", 1); } catch(e) {}

        var debug = {};

        // --- Routing TYPE (the source: "1-DRUMS", "Ext. In", "No Input", …)
        if (routing_type) {
            var types = read_json_prop("available_sidechain_input_routing_types");
            debug.requested_type = routing_type;
            debug.type_count = types && types.length ? types.length : 0;
            var t_match = find_by_name(types, routing_type);
            if (t_match && t_match.identifier !== undefined) {
                // LOM expects a RoutingType object; Max JS accepts a
                // JSON-encoded {identifier: N} for the `set`.
                cursor_a.set(
                    "sidechain_input_routing_type",
                    JSON.stringify({identifier: t_match.identifier})
                );
                debug.set_type = "ok (identifier=" + t_match.identifier + ")";
            } else {
                debug.set_type = "FAIL: no matching type";
                if (types) {
                    debug.available_types = [];
                    for (var i = 0; i < types.length; i++) {
                        debug.available_types.push(types[i].display_name || types[i].name || "?");
                    }
                }
            }
        }

        // --- Routing CHANNEL (the tap point: "Post FX", "Pre FX", …)
        if (routing_channel) {
            var channels = read_json_prop("available_sidechain_input_routing_channels");
            debug.requested_channel = routing_channel;
            debug.channel_count = channels && channels.length ? channels.length : 0;
            var c_match = find_by_name(channels, routing_channel);
            if (c_match && c_match.identifier !== undefined) {
                cursor_a.set(
                    "sidechain_input_routing_channel",
                    JSON.stringify({identifier: c_match.identifier})
                );
                debug.set_channel = "ok (identifier=" + c_match.identifier + ")";
            } else {
                debug.set_channel = "FAIL: no matching channel";
                if (channels) {
                    debug.available_channels = [];
                    for (var j = 0; j < channels.length; j++) {
                        debug.available_channels.push(channels[j].display_name || channels[j].name || "?");
                    }
                }
            }
        }

        // Read back canonical display_name for confirmation
        var cur_type = read_json_prop("sidechain_input_routing_type");
        var cur_channel = read_json_prop("sidechain_input_routing_channel");
        var read_type_name = (cur_type && cur_type.display_name) || "";
        var read_channel_name = (cur_channel && cur_channel.display_name) || "";

        send_response({
            "ok": true,
            "track_index": track_idx,
            "device_index": device_idx,
            "sidechain": {
                "type": read_type_name,
                "channel": read_channel_name,
                "enabled": 1
            },
            "debug": debug
        });
    } catch(e) {
        send_response({
            "error": "compressor_set_sidechain failed: " + e.message
                     + " (this Live build may not expose sidechain_input_routing_* —"
                     + " user must set routing manually)"
        });
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
    if (cursor_a.id === 0) {
        send_response({"error": "No clip at track " + track_idx + " slot " + clip_idx});
        return;
    }
    try {
        cursor_a.call("stop_scrub");
        send_response({"ok": true});
    } catch(e) {
        send_response({"error": e.message});
    }
}

// Device classes where str_for_value freezes Max JS (uncatchable hang).
// Auto Filter is the confirmed case; others may exist.
var STR_FOR_VALUE_BLACKLIST = ["AutoFilter"];

function _safe_display_string(cursor, val, device_class) {
    // Return the human-readable UI string for a parameter value.
    // Falls back to raw value string for blacklisted device classes
    // where str_for_value hangs Max's JS engine.
    if (STR_FOR_VALUE_BLACKLIST.indexOf(device_class) !== -1) {
        return String(val);
    }
    try {
        var result = cursor.call("str_for_value", val);
        if (result !== undefined && result !== null && String(result) !== "") {
            return String(result);
        }
    } catch(e) {
        // str_for_value not available on this parameter
    }
    return String(val);
}

function cmd_get_display_values(args) {
    var track_idx = parseInt(args[0]);
    var device_idx = parseInt(args[1]);
    var path = build_device_path(track_idx, device_idx);

    cursor_a.goto(path);
    var param_count = cursor_a.getcount("parameters");
    var device_name = cursor_a.get("name").toString();
    var device_class = cursor_a.get("class_name").toString();
    var params = [];
    var current = 0;
    var batch_size = 8;

    function read_batch() {
        try {
            var end = Math.min(current + batch_size, param_count);
            for (var i = current; i < end; i++) {
                cursor_b.goto(path + " parameters " + i);
                var state = parseInt(cursor_b.get("state"));
                if (state !== 2) {
                    var val = parseFloat(cursor_b.get("value"));
                    params.push({
                        index: i,
                        name: cursor_b.get("name").toString(),
                        display_value: _safe_display_string(cursor_b, val, device_class),
                        value: val
                    });
                }
            }
            current = end;
            if (current < param_count) {
                var next_task = new Task(read_batch);
                next_task.schedule(20);
            } else {
                send_response({
                    "track": track_idx,
                    "device": device_idx,
                    "device_name": device_name,
                    "params": params
                });
            }
        } catch (e) {
            send_response({
                "error": "Failed reading parameter " + current + ": " + String(e),
                "track": track_idx,
                "device": device_idx,
                "device_name": device_name,
                "partial_params": params
            });
        }
    }
    read_batch();
}

// ── Phase 3: Audio Capture ────────────────────────────────────────────

function cmd_capture_audio(args) {
    // args: [duration_ms, filename]
    // duration_ms is the requested record length in milliseconds.
    // filename is the desired output name (empty = auto-generate).
    if (capture_active) {
        send_response({"error": "Capture already in progress. Call capture_stop first."});
        return;
    }

    var duration_ms = parseInt(args[0]) || 10000;
    var requested_name = args[1] ? args[1].toString().trim() : "";

    // Sanitize filename — strip any directory components (defense-in-depth)
    if (requested_name.length > 0) {
        requested_name = _safe_filename(requested_name);
        if (!requested_name || requested_name.length === 0) {
            send_response({"error": "Invalid capture filename (path traversal blocked)"});
            return;
        }
    }

    // Generate a timestamped filename if none provided
    var d = new Date();
    var ts = d.getFullYear() + "_"
        + pad2(d.getMonth() + 1) + "_"
        + pad2(d.getDate()) + "_"
        + pad2(d.getHours()) + pad2(d.getMinutes()) + pad2(d.getSeconds());
    capture_filename = requested_name.length > 0 ? requested_name : ("capture_" + ts + ".wav");
    capture_file_path = _join_path(_get_captures_dir(), capture_filename);

    // Calculate sample count from duration and current sample rate
    var num_samples = Math.ceil((duration_ms / 1000.0) * current_sample_rate);

    capture_active = true;

    // Tell the Max patch to start recording the incoming stereo signal.
    // Message: "capture_start <absolute_path> <num_samples>"
    outlet(1, "capture_start", capture_file_path, num_samples);

    // Set a timer to call cmd_capture_write_done after duration_ms.
    // If the buffer~ fires its bang first (via a connected message), that
    // call will also land here — the guard flag prevents double-response.
    capture_timer = new Task(function() {
        cmd_capture_write_done();
    });
    capture_timer.schedule(duration_ms);
}

function cmd_capture_write_done() {
    // Called when buffer~ finishes writing (bang from record~), or by the
    // timer. Guards against double invocation.
    if (!capture_active) return;
    capture_active = false;
    if (capture_timer) {
        capture_timer.cancel();
        capture_timer = null;
    }

    var written = capture_filename;
    var written_path = capture_file_path;
    capture_filename = "";
    capture_file_path = "";

    // Stop the recorder before reporting completion so the file is flushed.
    outlet(1, "capture_stop");

    // Send /capture_complete back to the MCP server via outlet 0.
    var encoded = base64_encode(JSON.stringify({
        "ok": true,
        "file": written,
        "file_path": _to_posix_path(written_path),
        "sample_rate": current_sample_rate
    }));
    outlet(0, "/capture_complete", encoded);
}

function cmd_capture_stop() {
    if (!capture_active) {
        send_response({"ok": true, "stopped": false, "message": "No capture was active"});
        return;
    }

    // Cancel the countdown timer so cmd_capture_write_done isn't called twice
    if (capture_timer) {
        capture_timer.cancel();
        capture_timer = null;
    }

    // Signal the Max patch to stop recording early
    outlet(1, "capture_stop");

    capture_active = false;
    var written = capture_filename;
    var written_path = capture_file_path;
    capture_filename = "";
    capture_file_path = "";

    send_response({"ok": true, "stopped": true, "file": written, "file_path": _to_posix_path(written_path)});
}

function pad2(n) {
    return n < 10 ? "0" + n : "" + n;
}

// ── Plugin Parameters ──────────────────────────────────────────────────────

function cmd_get_plugin_params(args) {
    // Returns all parameters for a VST/AU plugin device
    var track_idx = parseInt(args[0]);
    var device_idx = parseInt(args[1]);
    var path = build_device_path(track_idx, device_idx);

    cursor_a.goto(path);
    var class_name = cursor_a.get("class_name").toString();

    // Check if this is a plugin device
    var is_plugin = (class_name === "PluginDevice" || class_name === "AuPluginDevice");
    if (!is_plugin) {
        send_response({
            "error": "Device is " + class_name + ", not a plugin (PluginDevice/AuPluginDevice). " +
                "This tool only works on AU/VST plugins. Use get_device_parameters for native Ableton devices. " +
                "Check get_device_info().is_plugin to verify before calling."
        });
        return;
    }

    var device_name = cursor_a.get("name").toString();
    var param_count = cursor_a.getcount("parameters");
    var params = [];
    var current = 0;
    var batch_size = 8;

    function read_batch() {
        try {
            var end = Math.min(current + batch_size, param_count);
            for (var i = current; i < end; i++) {
                cursor_b.goto(path + " parameters " + i);
                var val = parseFloat(cursor_b.get("value"));
                params.push({
                    index: i,
                    name: cursor_b.get("name").toString(),
                    value: val,
                    min: parseFloat(cursor_b.get("min")),
                    max: parseFloat(cursor_b.get("max")),
                    default_value: parseFloat(cursor_b.get("default_value")),
                    is_quantized: parseInt(cursor_b.get("is_quantized")) === 1,
                    value_string: String(val)
                });
            }
            current = end;

            if (current < param_count) {
                var next_task = new Task(read_batch);
                next_task.schedule(20);
            } else {
                send_response({
                    "track": track_idx,
                    "device": device_idx,
                    "name": device_name,
                    "class_name": class_name,
                    "is_plugin": true,
                    "parameter_count": param_count,
                    "parameters": params
                });
            }
        } catch (e) {
            send_response({
                "error": "Failed reading plugin param " + current + ": " + String(e),
                "track": track_idx,
                "device": device_idx,
                "name": device_name,
                "partial_params": params
            });
        }
    }

    if (param_count > 0) {
        read_batch();
    } else {
        send_response({
            "track": track_idx,
            "device": device_idx,
            "name": device_name,
            "class_name": class_name,
            "is_plugin": true,
            "parameter_count": 0,
            "parameters": []
        });
    }
}

function cmd_map_plugin_param(args) {
    // Add a plugin parameter to Ableton's Configure list
    var track_idx = parseInt(args[0]);
    var device_idx = parseInt(args[1]);
    var param_idx = parseInt(args[2]);
    var path = build_device_path(track_idx, device_idx);

    cursor_a.goto(path);
    var param_count = cursor_a.getcount("parameters");
    if (param_idx < 0 || param_idx >= param_count) {
        send_response({"error": "Parameter index " + param_idx + " out of range (0.." + (param_count - 1) + ")"});
        return;
    }

    try {
        cursor_b.goto(path + " parameters " + param_idx);
        var param_name = cursor_b.get("name").toString();

        cursor_a.set("selected_parameter", param_idx);
        cursor_a.call("store_chosen_bank");
        send_response({
            "mapped": true,
            "parameter_index": param_idx,
            "parameter_name": param_name
        });
    } catch(e) {
        send_response({
            "error": "Failed to map parameter: " + String(e),
            "parameter_index": param_idx
        });
    }
}

function cmd_get_plugin_presets(args) {
    // List plugin's internal presets
    var track_idx = parseInt(args[0]);
    var device_idx = parseInt(args[1]);
    var path = build_device_path(track_idx, device_idx);

    cursor_a.goto(path);
    var class_name = cursor_a.get("class_name").toString();
    var device_name = cursor_a.get("name").toString();

    var is_plugin = (class_name === "PluginDevice" || class_name === "AuPluginDevice");
    if (!is_plugin) {
        send_response({
            "error": "Device is " + class_name + ", not a plugin. " +
                "This tool only works on AU/VST plugins. Check get_device_info().is_plugin first."
        });
        return;
    }

    // Read presets — the presets property returns an array of preset names
    var presets = [];
    try {
        var preset_count = cursor_a.getcount("presets");
        for (var i = 0; i < preset_count; i++) {
            cursor_b.goto(path + " presets " + i);
            presets.push({
                index: i,
                name: cursor_b.get("name").toString()
            });
        }
    } catch(e) {
        // Some plugins don't expose presets via LOM
    }

    // Try to get selected preset index
    var selected = -1;
    try {
        selected = parseInt(cursor_a.get("selected_preset_index"));
    } catch(e) {}

    send_response({
        "track": track_idx,
        "device": device_idx,
        "name": device_name,
        "presets": presets,
        "selected_preset": selected
    });
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

function _get_captures_dir() {
    // Stable captures directory: ~/Documents/LivePilot/captures/
    // max.appsupportpath = "/Users/<name>/Library/Application Support/Cycling '74"
    // Walk up to get home directory
    try {
        var support = max.appsupportpath;
        var parts = support.split("/");
        // /Users/<name>/Library/... → first 3 parts = /Users/<name>
        var home = parts.slice(0, 3).join("/");
        return home + "/Documents/LivePilot/captures/";
    } catch (e) {
        // Fallback to patcher directory if home detection fails
        return _get_patcher_dir();
    }
}

function _get_patcher_dir() {
    try {
        var filepath = this.patcher && this.patcher.filepath ? this.patcher.filepath.toString() : "";
        if (!filepath) return "";
        var slash = Math.max(filepath.lastIndexOf("/"), filepath.lastIndexOf("\\"));
        if (slash < 0) return "";
        return filepath.substring(0, slash + 1);
    } catch (e) {
        return "";
    }
}

function _safe_filename(name) {
    // Strip directory components and reject traversal attempts.
    // This is defense-in-depth — Python should sanitize first.
    if (!name || name.length === 0) return name;
    var slash = Math.max(name.lastIndexOf("/"), name.lastIndexOf("\\"));
    if (slash >= 0) name = name.substring(slash + 1);
    if (name === "." || name === ".." || name.length === 0) return "";
    return name;
}

function _join_path(dir, file) {
    if (!dir) return file;
    var last = dir.charAt(dir.length - 1);
    if (last !== "/" && last !== "\\") dir += "/";
    return dir + file;
}
