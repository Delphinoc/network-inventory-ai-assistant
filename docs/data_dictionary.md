# OSP Inventory Data Dictionary

All tables are synthetic and modelled loosely on an Outside Plant (OSP) inventory split across three systems: Network Resource Inventory (NRI), Geographic Information System (GIS) and Digital Field Force (DFF).

## manholes (NRI)
One row per manhole or jointing chamber. Columns: `manhole_id` (primary key, format MH-#####), `exchange` (serving exchange name), `region`, `lat` and `lon` (WGS84 decimal degrees), `status` (In Service or Abandoned), `install_year`.

## ducts (NRI)
One row per duct section between two manholes. Columns: `duct_id` (primary key, DU-#####), `from_manhole` and `to_manhole` (foreign keys to manholes.manhole_id), `length_m` (recorded section length in metres), `sub_duct_count` (number of sub-ducts installed), `sub_ducts_used` (sub-ducts occupied by cables), `status` (In Service or Blocked).

## cables (NRI)
One row per cable. Columns: `cable_id` (primary key, CB-######), `cable_type` (Fibre or Copper), `duct_id` (foreign key to ducts.duct_id), `capacity` (fibre count for fibre cables, pair count for copper cables), `used_count` (fibres or pairs assigned to services), `install_year`, `status` (In Service, Planned or Decommissioned).

## splitters (NRI)
One row per passive optical splitter. Columns: `splitter_id` (primary key, SP-####), `manhole_id` (where the splitter is housed), `split_ratio` (1:8, 1:16 or 1:32; the second number is the number of output ports), `ports_used`, `status`.

## gis_cables (GIS)
One row per cable route drawn in GIS. Columns: `cable_id` (should match cables.cable_id), `duct_id` (duct the route is drawn through), `route_length_m` (length measured from the GIS drawing in metres).

## work_orders (DFF)
One row per field work order. Columns: `work_order_id` (WO-#####), `asset_id` (cable, duct or manhole ID), `job_type` (Inspection, Repair, Re-termination, Duct Clearing), `opened_date`, `closed_date` (empty while open), `status` (Open or Closed).
