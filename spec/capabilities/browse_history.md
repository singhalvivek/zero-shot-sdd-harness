# Capability: Browse History

## What It Does
Shows a browsable gallery of every part the user has generated, each with a preview thumbnail, and lets the user open a part to see its full version / modification chain and reload any version into the viewer.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| (list) | none | history sidebar/gallery load | yes |
| part_id | string | clicking a part | yes (detail view) |
| thumbnail image | PNG data URL (client-captured from the viewer canvas) | frontend, after a version renders | yes (to populate thumbnails) |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| parts list | `[{part_id, title, latest_version, thumbnail_url, created_at}]` | history gallery |
| part detail | `{part_id, versions: [{version_number, parent_version_id, source, prompt, thumbnail_url, stl_url, step_url, code_url, created_at}]}` | detail view + chain visualization |
| thumbnail_path | string | `versions.thumbnail_path`; served under `/artifacts/previews/...` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite (via SQLAlchemy) | list parts, fetch version chain | 500 on DB error |
| Local filesystem | store the captured PNG thumbnail | log + continue (thumbnail is non-critical; gallery shows a placeholder) |

## Business Rules
- `title` is derived from the originating prompt (first ~60 chars) at part creation.
- Thumbnails are **client-generated** (`canvas.toDataURL()` from the three.js render) and uploaded — avoids a server-side headless-GL dependency (a major Windows install risk). A version with no thumbnail yet shows a placeholder.
- The version chain is reconstructed from `parent_version_id`; version 1 has `parent_version_id = null`.

## Success Criteria
- [ ] After generating N parts, the gallery lists exactly N parts, newest first, each with title, created-at and a thumbnail (or placeholder).
- [ ] Opening a part with a modification chain shows all versions in order with correct parent links.
- [ ] Selecting a past version reloads its STL into the viewer and its code into the code panel.
- [ ] A captured thumbnail is persisted and served back on the next gallery load.
