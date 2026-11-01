# OSP Inventory Data Quality Standards

These standards define what counts as a data-quality exception in the NRI. Exceptions are raised to the inventory team for investigation; analysts flag them but do not correct records directly.

## Reporting date
All aging and as-of calculations use the reporting date **2026-10-31** unless stated otherwise.

## Completeness: manhole coordinates
Every manhole must have both a latitude and a longitude. A manhole with either `lat` or `lon` empty is a completeness exception, because it cannot be located on the map or matched to GIS.

## Uniqueness: duplicate records
Each `cable_id` must appear exactly once in the cables table. Any cable_id that appears more than once is a duplicate record exception, even if the duplicate rows are identical. Report the cable_id once.

## Referential integrity: cables to ducts
Every cable's `duct_id` must exist in the ducts table. A cable pointing to a duct that is not in the inventory is an orphan reference exception.

## Referential integrity: ducts to manholes
Both `from_manhole` and `to_manhole` of a duct must exist in the manholes table. A duct with either end pointing to a missing manhole is an orphan reference exception.

## Status consistency: decommissioned cables
A cable with status Decommissioned must have `used_count` of 0. A decommissioned cable that still shows fibres or pairs in use is a status consistency exception: either the status or the service assignments are wrong.

## Escalation
Exceptions are grouped by category (completeness, uniqueness, referential integrity, capacity, status consistency, reconciliation) and sent to the owning engineering or systems team with the affected record IDs.
