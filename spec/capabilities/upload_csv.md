# Capability: Upload CSV

## What It Does
Accepts a CSV upload, stores the raw file locally, profiles its schema (columns + dtypes + row count, no cell values), and binds it to a session.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| file | multipart CSV | `POST /datasets` | yes |
| df_name | str | request (optional; default derived from filename) | no |
| session_id | str (uuid) | request (optional; created if absent) | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| dataset record | `{dataset_id, df_name, row_count, columns, session_id}` | HTTP response (`ok` envelope) |
| raw file | file on disk | `data/uploads/` |
| Dataset row | DB row | SQLite `Dataset` + `SessionDataset` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Local filesystem | write raw file under `data/uploads/` | 500 `internal_error` |
| pandas | read CSV, profile schema | 400 (unreadable/empty table) |
| SQLite | insert Dataset + SessionDataset | 500 |

## Business Rules
- Phase 1 accepts CSV only (xlsx is a Phase-3 stub).
- `schema_json` stores column names + dtypes + row count ONLY — never cell values (privacy bar, see [data.md](../data.md#sensitive-data)).
- The raw file stays on local disk; it is never sent to the LLM.

## Success Criteria
- [ ] Uploading a valid CSV returns a `dataset_id`, correct `row_count`, and one column entry per column with its dtype.
- [ ] After upload the raw file exists under `data/uploads/` and a `Dataset` row + `SessionDataset` link exist.
- [ ] Uploading a non-CSV / empty / unparseable file returns HTTP 400 with a clear message and writes no Dataset row.
- [ ] The stored `schema_json` contains no data cell values (verifiable by inspecting the row).
