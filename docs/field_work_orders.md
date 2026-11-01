# Field Work Orders and SLA Targets

Work orders come from the Digital Field Force (DFF) system and are raised against cables, ducts or manholes.

## SLA targets by job type
Each job type has a target completion time, counted in calendar days from `opened_date`: Repair 7 days, Re-termination 14 days, Duct Clearing 21 days, Inspection 30 days.

## Aged (overdue) work orders
An open work order is **aged** when the number of days between its `opened_date` and the reporting date is greater than its SLA target. Closed work orders are never aged.

## Aging buckets
Overdue work is reported in buckets of days past SLA: 1–30, 31–60, 61–90 and over 90 days. Management reports show counts per bucket and per job type.
