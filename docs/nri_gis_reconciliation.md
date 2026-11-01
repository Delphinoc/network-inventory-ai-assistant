# NRI and GIS Reconciliation Procedure

NRI is the system of record for cable attributes; GIS holds the drawn route of each cable. The two must agree.

## Scope
Cables with status **Planned** are not yet drawn in GIS and are excluded from reconciliation. In Service and Decommissioned cables are in scope.

## Missing in GIS
An in-scope NRI cable with no matching `cable_id` in gis_cables is a "missing in GIS" exception.

## Missing in NRI
A cable_id in gis_cables that does not exist in the NRI cables table is a "missing in NRI" exception (a ghost route).

## Duct mismatch
When a cable exists in both systems, the `duct_id` recorded in NRI must equal the `duct_id` in GIS. A difference is a duct mismatch exception.

## Route length tolerance
For cables that exist in both systems with the same duct, the GIS `route_length_m` is compared with the NRI duct section `length_m`. A difference greater than **10%** of the NRI duct length (absolute difference divided by duct length > 0.10) is a length mismatch exception. Differences within 10% are accepted as drawing tolerance.
