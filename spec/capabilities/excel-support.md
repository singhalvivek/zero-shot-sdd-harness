# Capability: Excel Support (Phase 3)
## What It Does
Accepts `.xlsx` uploads (sheet-aware) alongside CSV, profiling each sheet as a dataframe.
## Inputs
| Input | Type | Source | Required |
| xlsx file | upload | User | yes |
## Outputs
| Output | Type | Destination |
| Dataset record(s) | JSON | `dataset` table |
## External Calls
| System | Operation | On Failure |
| openpyxl / pandas | Read sheets | 400 (unreadable) |
## Business Rules
- A multi-sheet workbook yields one dataframe per sheet (named `<file>_<sheet>`).
- Same privacy guarantee: only columns/dtypes profiled, never cell values.
## Success Criteria
- [ ] Uploading an .xlsx returns dataset records with correct columns per sheet.
- [ ] A question over the Excel data returns a correct answer.
