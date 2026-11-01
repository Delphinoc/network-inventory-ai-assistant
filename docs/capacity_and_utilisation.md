# Capacity and Utilisation Rules

## Cable utilisation
Cable utilisation is `used_count / capacity`, where capacity is the fibre count (fibre cables) or pair count (copper cables).

## Cable over capacity
A cable whose `used_count` is greater than its `capacity` is a capacity exception. It usually means service records were assigned to the wrong cable.

## Sub-duct over capacity
A duct whose `sub_ducts_used` is greater than its `sub_duct_count` is a capacity exception.

## Splitter over capacity
A splitter's port capacity is the second number of its split ratio (1:8 has 8 ports, 1:16 has 16, 1:32 has 32). A splitter with `ports_used` greater than its port capacity is a capacity exception.

## Underutilised cables
For investment planning, a cable is flagged as **underutilised** when all of the following hold: status is In Service, it was installed in or before 2015 (`install_year <= 2015`), and utilisation is below 10%. Underutilised cables are candidates for re-use before new cable is laid. This is an insight flag, not a data error.
