/**
 * LivePilot Pitch Glide — monophonic MIDI pitch-bend helper.
 *
 * This Max for Live MIDI Effect passes incoming MIDI through, but can
 * rewrite a following note so it starts at the prior pitch and bends into
 * the requested pitch over a short glide. It is intentionally monophonic:
 * channel pitch bend affects every sounding note on that channel.
 */

autowatch = 1;
inlets = 2;
outlets = 1;

var enabled = 1;
var glide_ms = 140;
var bend_range = 2;
var curve = 0.25;
var max_interval = 2;
var trigger_window_ms = 700;
var reset_delay_ms = 20;
var steps = 24;

var status_byte = -1;
var data_bytes = [];
var expected_data = 0;

var last_pitch = null;
var last_channel = null;
var last_note_on_ms = 0;
var active_map = {};
var protected_source = {};
var tasks = [];

function bang() {
    reset_all_bends();
}

function msg_int(v) {
    if (inlet === 0) {
        handle_midi_byte(v & 255);
    } else {
        set_param("enabled", v);
    }
}

function msg_float(v) {
    if (inlet === 0) {
        handle_midi_byte(Math.round(v) & 255);
    }
}

function list() {
    var args = arrayfromargs(arguments);
    if (inlet === 0) {
        for (var i = 0; i < args.length; i++) {
            handle_midi_byte(Math.round(args[i]) & 255);
        }
    }
}

function anything() {
    var args = arrayfromargs(arguments);
    set_param(messagename, args.length ? args[0] : 1);
}

function set_param(name, value) {
    var v = Number(value);
    if (isNaN(v)) return;
    if (name === "enabled") enabled = v >= 0.5 ? 1 : 0;
    else if (name === "glide_ms") glide_ms = clamp(v, 1, 2000);
    else if (name === "bend_range") bend_range = clamp(v, 0.25, 96);
    else if (name === "curve") curve = clamp(v, -1, 1);
    else if (name === "max_interval") max_interval = clamp(v, 0.25, 48);
    else if (name === "trigger_window_ms") trigger_window_ms = clamp(v, 1, 5000);
    else if (name === "reset_delay_ms") reset_delay_ms = clamp(v, 0, 500);
}

function handle_midi_byte(byte) {
    if (byte >= 240) {
        // System messages: pass through and clear running channel state.
        emit(byte);
        if (byte === 255 || byte === 240 || byte === 247) {
            status_byte = -1;
            data_bytes = [];
            expected_data = 0;
        }
        return;
    }

    if (byte >= 128) {
        status_byte = byte;
        data_bytes = [];
        expected_data = data_len(status_byte);
        if (expected_data === 0) emit(byte);
        return;
    }

    if (status_byte < 0) {
        emit(byte);
        return;
    }

    data_bytes.push(byte);
    if (data_bytes.length >= expected_data) {
        handle_channel_message(status_byte, data_bytes.slice(0, expected_data));
        data_bytes = [];
    }
}

function data_len(status) {
    var hi = status & 240;
    if (hi === 192 || hi === 208) return 1;
    if (hi >= 128 && hi <= 224) return 2;
    return 0;
}

function handle_channel_message(status, data) {
    var hi = status & 240;
    var ch = status & 15;

    if (hi === 144 && data[1] > 0) {
        note_on(status, ch, data[0], data[1]);
        return;
    }

    if (hi === 128 || (hi === 144 && data[1] === 0)) {
        note_off(status, ch, data[0], data[1]);
        return;
    }

    emit(status);
    for (var i = 0; i < data.length; i++) emit(data[i]);
}

function note_on(status, ch, pitch, velocity) {
    var now = Date.now();
    var interval = last_pitch === null ? 0 : pitch - last_pitch;
    var should_glide =
        enabled &&
        last_pitch !== null &&
        last_channel === ch &&
        Math.abs(interval) > 0 &&
        Math.abs(interval) <= max_interval &&
        (now - last_note_on_ms) <= trigger_window_ms &&
        Math.abs(interval) <= bend_range;

    if (should_glide) {
        var out_pitch = clamp_int(last_pitch, 0, 127);
        clear_tasks();
        // If the source note overlaps the target, release it before retriggering
        // at the glide source pitch. Some instruments ignore duplicate note-ons.
        emit(128 + (ch & 15));
        emit(out_pitch);
        emit(0);
        send_bend(ch, 0);
        emit(status);
        emit(out_pitch);
        emit(velocity);
        active_map[ch + ":" + pitch] = out_pitch;
        protected_source[ch + ":" + out_pitch] = (protected_source[ch + ":" + out_pitch] || 0) + 1;
        schedule_glide(ch, interval);
    } else {
        send_bend(ch, 0);
        emit(status);
        emit(pitch);
        emit(velocity);
    }

    last_pitch = pitch;
    last_channel = ch;
    last_note_on_ms = now;
}

function note_off(status, ch, pitch, velocity) {
    var key = ch + ":" + pitch;
    if (protected_source.hasOwnProperty(key) && protected_source[key] > 0) {
        protected_source[key] -= 1;
        if (protected_source[key] <= 0) delete protected_source[key];
        return;
    }
    var out_pitch = active_map.hasOwnProperty(key) ? active_map[key] : pitch;
    delete active_map[key];
    emit(status);
    emit(out_pitch);
    emit(velocity);
    schedule_reset(ch);
}

function schedule_glide(ch, semitones) {
    var total = Math.max(1, glide_ms);
    var n = Math.max(4, Math.min(64, Math.round(steps)));
    for (var i = 1; i <= n; i++) {
        (function(step) {
            var p = step / n;
            var shaped = shape(p);
            var bend = semitones * shaped;
            var t = new Task(function() {
                send_bend(ch, bend);
            }, this);
            tasks.push(t);
            t.schedule(Math.round(total * p));
        })(i);
    }
}

function schedule_reset(ch) {
    var t = new Task(function() {
        send_bend(ch, 0);
    }, this);
    tasks.push(t);
    t.schedule(Math.round(reset_delay_ms));
}

function shape(p) {
    if (curve === 0) return p;
    var amount = 1 + Math.abs(curve) * 4;
    if (curve > 0) return Math.pow(p, amount);
    return 1 - Math.pow(1 - p, amount);
}

function send_bend(ch, semitones) {
    var ratio = clamp(semitones / Math.max(0.25, bend_range), -1, 1);
    var value = ratio >= 0
        ? Math.round(8192 + ratio * 8191)
        : Math.round(8192 + ratio * 8192);
    value = clamp_int(value, 0, 16383);
    emit(224 + (ch & 15));
    emit(value & 127);
    emit((value >> 7) & 127);
}

function reset_all_bends() {
    clear_tasks();
    for (var ch = 0; ch < 16; ch++) {
        send_bend(ch, 0);
    }
    active_map = {};
    protected_source = {};
    last_pitch = null;
    last_channel = null;
}

function clear_tasks() {
    for (var i = 0; i < tasks.length; i++) {
        try {
            tasks[i].cancel();
        } catch (e) {
        }
    }
    tasks = [];
}

function emit(v) {
    outlet(0, v & 255);
}

function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(hi, v));
}

function clamp_int(v, lo, hi) {
    return Math.max(lo, Math.min(hi, Math.round(v)));
}
