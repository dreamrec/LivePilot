# LivePilot Extension API

**Stable from v1.23.0 forward.** Breaking changes only at major version bumps.

User-local extensions let you add atlas content (and, in future versions, MCP tools and skills) without forking LivePilot. Anything inside `~/.livepilot/` survives npm updates.

## Phase 1 (v1.23.0): Atlas overlays

Drop YAML files at `~/.livepilot/atlas-overlays/<namespace>/<category>/<entry>.yaml` (the category subdirectory is convention only — the loader keys by `entity_type`, not directory).

### Required fields

```yaml
entity_id: <unique_within_namespace>     # NOT 'id' (avoids Python builtin shadow)
entity_type: machine | signature_chain | aesthetic_lineage | technique
```

### Conditional required (when `entity_type: signature_chain`)

```yaml
tags: [list, of, tags]
artists: [list, of, artist_ids]
```

### Optional (recommended)

```yaml
name: "Human-readable name"
description: |
  Multi-line description.
requires_box: <hardware_id>
requires_machines: [list of machine ids]
requires_firmware: { box: minimum_version }   # surfaced by extension_atlas_get
sources: [list of citation strings]
related_chains: [list of chain ids]
related_techniques: [list of technique ids]
# Plus any extension-specific fields — preserved verbatim in the entry's `body`.
```

### Security

- Loader uses `yaml.safe_load` only. Python tags (`!!python/*`) are rejected — including benign ones like `!!python/name:datetime.datetime`. The loader treats all `!!python/*` tags identically (logged + skipped).
- (Phase 2) Symlinks pointing outside `~/.livepilot/` are rejected by the extension Python loader.

### Search semantics

`extension_atlas_search(query)` weights matches:
- Exact `entity_id` (case-insensitive): +1000
- Substring in `name`: +100
- Substring in `tags` or `artists`: +50
- Substring in `description`: +10

### Failure handling

- Missing `~/.livepilot/atlas-overlays/`: silent (empty index).
- Bad YAML: logged WARN, file skipped, others continue.
- Missing required field: logged WARN, entry skipped.
- Duplicate `(namespace, entity_type, entity_id)`: logged WARN, last-loaded wins.

## Phase 2 (future minor): User-local Python extensions

Drop Python packages at `~/.livepilot/extensions/<name>/`. Each package's `__init__.py` exposes a `register(mcp)` function that the loader calls at server boot to register additional `@mcp.tool()`, `@mcp.prompt()`, `@mcp.resource()` declarations.

Tool-name collisions: **first-registered-wins**. Bundled tools always beat extensions. Use a namespaced prefix (e.g., `myhw_set_param` not `set_param`).

Recommended top-level constant: `__livepilot_min_version__ = "1.23"`. Soft-warned by the loader; not enforced in v1.23.

## Status

- v1.23.0: Phase 1 (atlas overlays) — **shipped**.
- Future versions: Phase 2 (Python extensions), starter template repo, per-namespace ACL, async loader.
