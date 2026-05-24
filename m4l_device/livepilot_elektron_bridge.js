// m4l_device/livepilot_elektron_bridge.js
// LivePilot Elektron Bridge — runs inside LivePilot_Elektron.amxd.
//
// Wire model:
//
//   M4L → Python : UDP 9882
//                  Inbound SysEx from physical MIDI [sysexin → sxformat
//                  → prepend sysex] arrives at JS as a "sysex <bytes...>"
//                  message; forwards out outlet 1 (→ [udpsend 9882]).
//
//   Python → M4L : UDP 9883
//                  [udpreceive 9883] outputs bytes as a "list" message
//                  → JS function list() pushes onto sendQueue.
//                  [metro 50 @active 1] drives bang() which drains one
//                  chunk per tick onto outlet 0 (→ [midiout]).
//
// Outlets:
//   0 → [midiout]                  paced chunks to physical MIDI port
//   1 → [udpsend 127.0.0.1 9882]   sysex-from-device upstream to Python
//   2 → "set <text>" → live.text   status display
//   3 → +1 counter → live.numbox   RX message counter
//
// Phase 1 design note: heartbeat is intentionally OUT for v1 of the M4L
// device. The Python bridge uses per-operation timeouts (per design
// spec §7.3) so it does not need M4L liveness polling. Heartbeat / pong
// can be added in a Phase 2 patch to the .maxpat if "is M4L loaded?"
// detection becomes useful — the ping()/pong() functions below are
// kept as reserved stubs for that future wiring.

inlets = 1;
outlets = 4;

var sendQueue = [];
var rxCount = 0;

// Called by [metro 50 @active 1] — drain one queued chunk per tick.
function bang() {
    if (sendQueue.length > 0) {
        var chunk = sendQueue.shift();
        // Spread chunk into outlet args so Max sees it as a list message
        outlet.apply(this, [0].concat(chunk));
    }
}

// Called by [udpreceive 9883] — outputs raw UDP bytes as a list.
// This is the Python → M4L outbound MIDI path. Each datagram is a
// pre-chunked SysEx fragment; we queue and let bang() pace them.
function list() {
    var bytes = [];
    for (var i = 0; i < arguments.length; i++) {
        bytes.push(arguments[i]);
    }
    sendQueue.push(bytes);
}

// Called when [sysexin → sxformat → prepend sysex] delivers a complete
// SysEx as a "sysex <bytes...>" message. We forward to Python and
// bump the RX counter + status.
function sysex() {
    var bytes = [];
    for (var i = 0; i < arguments.length; i++) {
        bytes.push(arguments[i]);
    }
    // Forward to Python via outlet 1 → [udpsend 9882]
    outlet.apply(this, [1].concat(bytes));
    // Bump RX counter via outlet 3
    rxCount += 1;
    outlet(3, rxCount);
    // Update status via outlet 2
    outlet(2, "set", "Online — receiving SysEx");
}

// Phase 2 reserved: heartbeat ping. Wire [metro 1000] → [t ping] → js
// to enable. Not wired in Phase 1 .maxpat.
function ping() {
    outlet(1, 0xF0, 0x7F, 0x7F, 0x00, 0xF7);
}

// Phase 2 reserved: receive pong from Python. Currently unused.
function pong() {
    outlet(2, "set", "Online — pong received");
}
