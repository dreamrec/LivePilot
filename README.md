```
██╗     ██╗██╗   ██╗███████╗██████╗ ██╗██╗      ██████╗ ████████╗
██║     ██║██║   ██║██╔════╝██╔══██╗██║██║     ██╔═══██╗╚══██╔══╝
██║     ██║██║   ██║█████╗  ██████╔╝██║██║     ██║   ██║   ██║
██║     ██║╚██╗ ██╔╝██╔══╝  ██╔═══╝ ██║██║     ██║   ██║   ██║
███████╗██║ ╚████╔╝ ███████╗██║     ██║███████╗╚██████╔╝   ██║
╚══════╝╚═╝  ╚═══╝  ╚══════╝╚═╝     ╚═╝╚══════╝ ╚═════╝    ╚═╝
```

<p align="center">
  <a href="https://github.com/dreamrec/LivePilot/actions"><img src="https://img.shields.io/github/actions/workflow/status/dreamrec/LivePilot/ci.yml?style=flat-square&amp;label=CI" alt="CI"></a>
  <a href="https://www.npmjs.com/package/livepilot"><img src="https://img.shields.io/npm/v/livepilot?style=flat-square" alt="npm version"></a>
  <a href="https://github.com/dreamrec/LivePilot/releases"><img src="https://img.shields.io/github/v/release/dreamrec/LivePilot?style=flat-square" alt="Latest release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-BSL--1.1-blue?style=flat-square" alt="License"></a>
</p>

**Hi**

LivePilot connects an MCP-compatible AI client to Ableton Live 12. Edit notes,
arrangements, instruments, effects, and routing; inspect what Live exposes;
and compare captured audio before deciding what to keep.

**474 tools across 57 domains. macOS and Windows.** The default catalog presents
a focused set of entry points; the full tool surface remains searchable.

[Install](#install) · [What's new](#whats-new-in-v1310) · [Manual](docs/manual/index.md) · [Tool catalog](docs/manual/tool-catalog.md) · [Changelog](CHANGELOG.md)

## Install

### Setup wizard

Install [Node.js 18+](https://nodejs.org/) and Python 3.12+, then run:

```bash
npx livepilot --setup
```

The wizard installs the Remote Script, prepares the Python environment, and
checks the connection. LivePilot requires Ableton Live 12. The optional Analyzer
requires Max for Live; core control works without it.

### Claude Desktop extension

Download `livepilot-<version>.mcpb` from the
[latest release](https://github.com/dreamrec/LivePilot/releases/latest) and open it
in Claude Desktop. The extension still needs Python 3.12+ and the Remote Script
installed in Live. Follow the [installation guide](docs/manual/getting-started.md).

### Other MCP clients

LivePilot works with Codex, Claude Code, Cursor, VS Code, Windsurf, and other MCP
clients. A typical stdio configuration is:

```json
{
  "mcpServers": {
    "LivePilot": {
      "command": "npx",
      "args": ["-y", "livepilot"]
    }
  }
}
```

See [client setup](docs/manual/getting-started.md) for platform paths and options.
The Remote Script accepts one TCP client at a time. Use a shared HTTP server
when connecting several MCP clients to the same Live instance.

## What's New in v1.31.0

This release deepens existing controls while keeping the same tool count.

- **Reach inside racks.** Discover child devices, inspect parameters, and make
  single or batch edits through explicit nested chain/device paths. Optional
  device identity guards reject stale targets after reordering.
- **Use Wavetable's native modulation matrix.** Discover real sources and
  addable parameters, insert target rows, set normalized amounts, and read back
  the result. Matrix display names and parameter names are reported separately.
- **Give sound design a direction.** Supply an explicit timbral goal such as
  more movement or less brightness. A simple patch or missing LFO receives no
  unsolicited quality penalty. Structural findings are labeled as heuristics.
- **Keep analysis responsive.** Offline DSP runs in bounded workers; cancellation
  stops the worker while preserving the MCP session. Doctor and transport fixes
  are included.
- **Handle newer clip-scale APIs.** Scale setters resolve available names
  defensively on builds that expose per-clip scale properties; older builds
  report the supported song-scale alternative.

The [validation record](docs/validation/v1.31.0.md) documents the live control
checks, API provenance, and their limits. Full changes are in the
[changelog](CHANGELOG.md).

## Workflows

Start with an idea. Get precise when the detail matters.

> “Turn this pad into a brittle, unstable texture. Keep the chord voicing.”
>
> “Make three variations of this rhythm. Protect the kick; let the hats drift.”
>
> “Inside this rack, map LFO 2 to Wavetable's oscillator position at 0.23.
> Read it back before changing anything else.”

| Goal | Workflow |
| --- | --- |
| Shape an instrument inside a rack | Discover children with `get_rack_chains`, inspect a child's parameters, then edit through its returned `device_path`. |
| Add motion to Wavetable | Read supported sources and targets, add a missing matrix row, set an amount, and verify the actual target and value. |
| Develop a musical idea | Plan clips, notes, sections, and automation while preserving the motif and constraints that matter to the user. |
| Compare a sound change | Capture the same passage before and after, then use `listen_ab` for measurements alongside listening. |
| Find a useful starting point | Search the atlas and Live's current browser before loading a device or preset. |
| Explore an unfamiliar mix | Inspect levels and routing, read available spectral data, and separate measurements from role-based suggestions. |

Creative suggestions are options to audition. A larger device chain, more
modulation, or a higher heuristic score does not establish better music.

## How it works

```text
                         YOUR IDEA
                             |
                      [ AI / MCP CLIENT ]
                             |
     +------------------ LIVEPILOT ------------------+
     |                                               |
     |   ATLAS          CONTROL          LISTENING   |
     |   find it        shape it         compare it  |
     |                                               |
     |   474 tools / 57 domains / technique memory   |
     +-----------------------+-----------------------+
                             |
                     [ REMOTE SCRIPT ]
                             |
                    +-----------------+
                    | ABLETON LIVE 12 |
                    +--------+--------+
                             |
                 [ OPTIONAL M4L ANALYZER ]
                     live spectral data
```

- **Remote Script:** executes Live Object Model operations on Ableton's main
  thread through a queued local TCP connection.
- **MCP server:** validates requests, routes commands, runs offline analysis,
  and exposes the tools to the client.
- **Optional Analyzer:** provides live spectral data and additional Max for Live
  operations over the local UDP/OSC bridge. It belongs last on the master chain.
- **Knowledge and memory:** support device discovery, technique retrieval,
  composition plans, and recorded preferences.

The bundled atlas is a snapshot of **5264 browser entries**, including devices,
presets, samples, and clips, with **120 enrichment profiles**. It is not a count
of distinct synth/effect types or proof that an item is installed on the current
machine. Resolve results against Live before loading them.

## Evidence and limits

LivePilot distinguishes measured audio, visible state, structural heuristics,
and artistic preference. `analyze_sound_design` inspects topology; it does not
measure spectral flux or decide whether a sound is good.

`capture_audio` creates recordings. `listen_capture` and `listen_ab` analyze
files. Spectral sampling during a preview is not an exported audio file.
Broad preview plans still have restoration limits; the validation record does
not claim transaction-safe rollback for every backend or workflow.

LivePilot uses the local control connection and does not upload captured audio
by default. The MCP client may send tool arguments and results to its model
provider. Splice integration and optional model downloads use network services.
Review the client configuration for the data policy that applies to your setup.

Different Live editions, devices, plug-ins, and builds expose different controls.
Unknown or unavailable capabilities should be reported explicitly. Pin the
LivePilot version for a repeatable studio or performance setup.

Version detection enables four capability tiers as initial routing labels:
Core (12.0+), Enhanced Arrangement (12.1.10+), Full Intelligence (12.3+), and
Collaborative (12.4+). Individual operations, including `replace_sample_native`,
still probe the actual object and backend. A tier label does not prove that
every control is exposed by a particular edition or build.

## Updating and diagnostics

```bash
npx livepilot@latest --install
npx livepilot@latest --doctor
```

After this release's Remote Script update, restart Live at a convenient time and
restart the MCP client so both sides use the new code. Handler-only development
changes can use `reload_handlers`; changes to the running TCP server require a
Live restart. See [troubleshooting](docs/manual/troubleshooting.md).

## Documentation

| Guide | Contents |
| --- | --- |
| [Getting started](docs/manual/getting-started.md) | Installation and client setup |
| [Device control](docs/manual/sound-design.md) | Instruments, effects, racks, and sound design |
| [Workflow guide](docs/manual/workflows.md) | Examples across common production tasks |
| [Composition](docs/manual/composition.md) | Notes, harmony, scenes, and arrangement |
| [Mixing](docs/manual/mixing.md) | Levels, routing, automation, and analysis |
| [Samples](docs/manual/samples.md) | Sampling and source discovery |
| [Device Atlas](docs/manual/device-atlas.md) | Discovery, provenance, and inventory limits |
| [Tool catalog](docs/manual/tool-catalog.md) | All 474 tools across 57 domains |
| [API reference](docs/manual/tool-reference.md) | Detailed tool contracts |
| [Development](docs/manual/dev-install.md) | Run a local checkout without overwriting edits |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, tests, and pull requests.
Changes to live control should include a focused regression and, when possible,
a disposable-Set smoke test. Keep public examples generic and preserve user files.

Report reproducible problems in [GitHub issues](https://github.com/dreamrec/LivePilot/issues).
The project is distributed under [BSL 1.1](LICENSE).
