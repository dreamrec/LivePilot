# Lane C: Persistence and Meaning

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make "across sessions" and "return to a project" actually true — persist taste graph inputs, session continuity state, and project context so they survive server restart.

**Architecture:** Follow the TechniqueStore pattern (atomic JSON write, lazy init, corruption recovery, threading.Lock). Create a `persistence/` package with a base store class and two concrete stores: taste and project state. Define four memory layers explicitly.

**Tech Stack:** Python 3.10+, JSON files at `~/.livepilot/`, threading.Lock, atomic tmp+rename.

**Depends on:** PR1 (capability contract — persistence state feeds into capability reporting).
**Blocks:** Lane E (docs must not claim persistence until it exists).

**PR sequence in this plan:** PR6 (after PR1), PR7 (after PR6).

---

## PR6: Persistent Taste State

**Goal:** Taste learning survives restart. Move outcomes, novelty preference, device affinity, and anti-preferences are persisted.

**Depends on:** PR1 (capability contract).

**Files:**
- Create: `mcp_server/persistence/__init__.py`
- Create: `mcp_server/persistence/base_store.py` — atomic JSON store base class
- Create: `mcp_server/persistence/taste_store.py` — persistent taste state
- Modify: `mcp_server/memory/taste_graph.py` — `build_taste_graph` reads from persistent store; mutations write back
- Modify: `mcp_server/memory/taste_memory.py` — wire `update_from_outcome` to persistent backing
- Modify: `mcp_server/memory/anti_memory.py` — wire `record_dislike` to persistent backing
- Modify: `mcp_server/memory/tools.py:194` — fix `record_positive_preference` (if not done in PR4)
- Modify: `mcp_server/preview_studio/tools.py:272-293` — commit writes to persistent taste, not throwaway graph
- Modify: `mcp_server/wonder_mode/tools.py:259-271` — discard writes to persistent taste
- Create: `tests/test_persistent_base.py` — base store tests
- Create: `tests/test_taste_persistence.py` — taste survives restart

**Acceptance criteria:**
- [ ] `PersistentJsonStore` base class: atomic write (tmp+rename+fsync), lazy init, corruption recovery (.corrupt rename), threading.Lock
- [ ] `PersistentTasteStore` stores: move outcomes (per move_id: family, kept_count, undone_count), novelty_band, device affinities, anti-preferences, dimension weights, evidence_count
- [ ] Storage location: `~/.livepilot/taste.json`
- [ ] `build_taste_graph()` accepts optional `persistent_store` and hydrates graph from it
- [ ] `TasteGraph.record_move_outcome()` writes through to persistent store
- [ ] Preview commit path writes to persistent store (not throwaway graph)
- [ ] Wonder discard path writes to persistent store
- [ ] New store instance reads same file → data survives
- [ ] Corrupt file → renamed to `.corrupt`, fresh store started
- [ ] Tests: write+restart round trip, novelty persistence, device affinity persistence, anti-preference persistence, corruption recovery
- [ ] All existing tests pass

**Implementation notes:**
- Follow `technique_store.py` pattern exactly: `_flush()` with `os.fsync` + `os.replace`
- The key change: `build_taste_graph` currently creates a new `TasteGraph()` and copies data one-way from stores. After this PR, it also loads `move_family_scores` and `device_affinities` from the persistent file.
- `TasteGraph.record_move_outcome()` currently mutates the in-memory object only. After this PR, it also calls `persistent_store.record_move_outcome()` which flushes to disk.
- The `ctx.lifespan_context` stores (`taste_memory`, `anti_memory`) remain as fast in-session caches. The persistent store is the durable backing.

---

## PR7: Project and Session Continuity Persistence

**Goal:** "Return to this project" restores open threads, prior exploration, and unresolved creative context.

**Depends on:** PR6 (persistent store base class).

**Files:**
- Create: `mcp_server/persistence/project_store.py` — per-project state
- Create: `mcp_server/runtime/project_identity.py` — project fingerprinting from session info
- Modify: `mcp_server/session_continuity/tracker.py` — flush threads/turns to project store on write
- Modify: `mcp_server/session_continuity/models.py` — add `from_dict` class methods for deserialization
- Modify: `mcp_server/wonder_mode/session.py` — optionally persist WonderSession outcomes per project
- Modify: `mcp_server/memory/session_memory.py` — project-scoped persistence option
- Create: `tests/test_project_identity.py`
- Create: `tests/test_continuity_persistence.py`
- Create: `tests/test_wonder_persistence.py`

**Acceptance criteria:**
- [ ] `ProjectIdentity` from session info: uses set file path hash if available, falls back to `(tempo, track_count, track_names_hash)` fingerprint
- [ ] `PersistentProjectStore` stores per-project: open threads, recent turns (last 50), wonder session outcomes (last 10), session memory entries
- [ ] Storage location: `~/.livepilot/projects/<project_hash>/state.json`
- [ ] `tracker.py`: `record_turn_resolution` and `open_thread` flush to project store
- [ ] `tracker.py`: on init, loads existing project state if project hash matches
- [ ] `CreativeThread.from_dict()` and `TurnResolution.from_dict()` for deserialization
- [ ] WonderSession outcomes (committed/rejected with variant info) persisted per project
- [ ] Session memory entries with `expires_with_session: False` persisted per project
- [ ] Tests: thread persistence across restart, turn persistence, project identity stability, different projects get different stores
- [ ] All existing tests pass

**Implementation notes:**
- Project identity is tricky without Ableton connection. Use a two-phase approach:
  1. At server start (no Ableton yet): use empty/default project hash
  2. On first `get_session_info` call: compute real project hash, load matching state
- Session continuity `tracker.py` currently uses module-level globals. This PR should migrate them to a class instance scoped to the project, with the persistent store as backing.
- Keep the module-level interface (`open_thread`, `record_turn_resolution`) working — they delegate to the class instance internally.
- Only persist the last 50 turns and last 10 Wonder outcomes per project to prevent unbounded growth.

---

## Memory Layer Architecture (Reference)

After PR6 and PR7, the four memory layers are:

| Layer | Scope | Storage | Survives restart? | What it stores |
|-------|-------|---------|-------------------|----------------|
| **Session** | Current MCP process | `ctx.lifespan_context` | No | Fast caches, capability state, current kernel |
| **Project** | Per Ableton set | `~/.livepilot/projects/<hash>/state.json` | Yes | Open threads, turn history, Wonder outcomes, session memory |
| **Global Taste** | Cross-session | `~/.livepilot/taste.json` | Yes | Move outcomes, novelty band, device affinity, anti-preferences |
| **Techniques** | Reusable knowledge | `~/.livepilot/memory/techniques.json` | Yes | Beat patterns, device chains, mix templates (already works) |

---

## Dependency Map

```
PR1 (Capability) ──► PR6 (Persistent Taste) ──► PR7 (Project Continuity)
```

PR6 can start as soon as PR1 is merged. PR7 depends on PR6 (reuses the base store).
