*This project has been created as part of the 42 curriculum by tusandri.*

# Fly-in

Drones are interesting.

## Description

Fly-in routes a fleet of autonomous drones through a network of connected
zones, from one central start hub to one end hub, in the fewest possible
simulation turns.

The network is described by a map file: `nb_drones`, exactly one
`start_hub`, exactly one `end_hub`, regular `hub` zones and bidirectional
`connection` lines. Zones carry optional metadata (`zone=`, `color=`,
`max_drones=`) and connections carry `max_link_capacity=`. Zone types
drive the movement costs:

| Zone type    | Cost to enter | Meaning                            |
|--------------|---------------|------------------------------------|
| `normal`     | 1 turn        | default                            |
| `blocked`    | forbidden     | drones must never enter or cross   |
| `restricted` | 2 turns       | 2-turn transit through a connection |
| `priority`   | 1 turn        | preferred by the pathfinding       |

Everything is written in object-oriented Python 3.10+, fully typed
(`mypy --strict` passes) and `flake8` compliant. No graph library
(`networkx`, `graphlib`, ...) is used: the graph structure is
implemented from scratch in `network.py`. More generally, no
ready-made algorithmic object is used anywhere: `Counter`, `heapq`,
`dataclasses`, `Enum`, `argparse` and regular expressions are all
replaced by hand made equivalents (`datastructures.py`, `gui.py`,
`zone.py`, `main.py`, `parser.py`) built only with plain lists,
dicts, tuples and strings.

## Instructions

### Install (Poetry)

The project is managed with **Poetry** (`pyproject.toml` +
`poetry.lock`):

```sh
make install          # poetry install: pygame + flake8 + mypy + pytest
```

Every `make` rule runs through `poetry run`, inside the dedicated
virtual environment. A plain `pip` fallback exists for environments
without Poetry:

```sh
make pip-install      # python3 -m pip install -r requirements.txt
```

### Run

```sh
make run MAP=maps/easy_1.map        # raw output (one line per turn)
make gui MAP=maps/medium_1.map      # pygame window (implies a solve)
python3 main.py maps/medium_3.map --stats   # raw output + metrics
python3 main.py maps/easy_3.map --visual    # colored turn-by-turn view
python3 main.py maps/easy_3.map --animate   # animated network snapshots
python3 main.py maps/easy_3.map --gui       # pygame window from the CLI
python3 main.py maps/easy_3.map --check     # replay and validate rules
```

The default output follows the subject format exactly: one line per
simulation turn listing every drone movement, space separated:

```text
D1-a D2-b
D1-end D2-c
D2-end
```

`D<ID>-<zone>` is a zone entry; `D<ID>-<connection>` (e.g. `D1-start-lab`)
is a drone still in flight towards a `restricted` zone: it lands on the
very next turn.

### Other Makefile rules

```sh
make lint          # flake8 . && mypy . --warn-return-any --warn-unused-ignores \
                   #   --ignore-missing-imports --disallow-untyped-defs \
                   #   --check-untyped-defs
make lint-strict   # flake8 . && mypy . --strict
make test          # pytest unit tests (parser, pathfinding, simulation, gui)
make debug MAP=maps/easy_1.map   # run inside pdb
make clean         # remove caches, .venv and build artifacts
```

## Architecture and algorithm choices

### Modules

| File              | Responsibility                                        |
|-------------------|-------------------------------------------------------|
| `main.py`         | CLI, error handling, exit codes                       |
| `parser.py`       | full map syntax + semantic validation, line numbers   |
| `instance.py`     | parsed problem + reachability check                   |
| `zone.py`         | `Zone`, `ZoneType`, capacities and entry costs        |
| `connection.py`   | `Connection`, link capacities                         |
| `network.py`      | `Network`: the graph (adjacency, no graph library)    |
| `pathfinding.py`  | Dijkstra + penalty based path diversification         |
| `planner.py`      | drone-to-path assignment minimizing predicted makespan|
| `simulation.py`   | turn engine, conflict repair, waiting, transits       |
| `validator.py`    | independent replay of the rules (used by `--check`)   |
| `visualizer.py`   | colored terminal output, snapshots, metrics           |
| `gui.py`          | pygame window: network map, drones turn by turn       |
| `datastructures.py` | hand made `MinHeap`, `Multiset`, `link_key`, sorts  |
| `drone.py`        | per-drone state (position, path, transit, delivery)   |
| `errors.py`       | `ParseError`, `SimulationError`, integrity errors     |

### Pathfinding

1. **Single pair search** — a Dijkstra run over the zone graph. The edge
   cost is the entry cost of the destination zone (1 for `normal` and
   `priority`, 2 for `restricted`, `blocked` zones are never entered).
   The search key is lexicographic `(total cost, number of non-priority
   zones visited, hops)` so equally long paths automatically prefer
   `priority` zones, as required by the subject.

2. **Path diversification** — up to 8 distinct routes are extracted by
   re-running the search after adding a penalty to every zone and link
   of the paths already found. This produces disjoint or partially
   overlapping corridors which the fleet can flow through in parallel.

3. **Assignment** — each drone is assigned to the route that minimizes
   the predicted makespan, where a route carrying `k` drones is
   estimated to finish at `cost + ceil(k / lanes) - 1` turns and
   `lanes` is the bottleneck capacity of the route (smallest
   `max_drones` / `max_link_capacity` on its internal zones/links).
   This distributes drones across multiple paths instead of pouring
   them into a single queue.

### Scheduling and waiting

The simulation proceeds in discrete turns. For every turn:

* Drones in flight towards a `restricted` zone **must** land (their
  landing was reserved when the transit started, so it never fails).
* Every other drone proposes its next move (or the start of a 2-turn
  transit, with the landing zone reserved on the next turn).
* All proposals are projected into an end-of-turn occupancy map, then
  conflicts are resolved by cancelling the lowest priority move and
  re-projecting, until every zone, link and reserved landing fits.
  Drones leaving a zone free its capacity the same turn, so legal swaps
  are allowed, while a cancelled proposal becomes a strategic wait.
* Link capacity is enforced per turn across both directions of a
  connection (`max_link_capacity` counts traversals, not directions).

As a safety net, a drone blocked for several consecutive turns is
re-routed on a shorter alternative path with a penalty around
current congestion (bounded number of replans to avoid livelocks).

### Complexity

* One Dijkstra is `O((V + E) log V)` with `V` zones and `E`
  connections; diversification runs at most 8 of them, and the planner
  runs once before the simulation (results are cached, never
  recomputed per turn — only the rare anti-deadlock replan triggers a
  new search).
* Per turn, conflict resolution is `O(D²)` in the worst case (`D`
  drones) but is in practice linear: proposals are committed greedily
  and cancels are rare.
* Memory is `O(V + E + D)`: no time-expanded graph is maintained; the
  occupancy is rebuilt from drone positions each turn.

### Visual representation

`--visual` colors every zone with the `color=` declared in the map
(unknown single-word colors fall back to a deterministic palette),
prepending each turn with the moves as `D1->zone`, colored by the
destination zone. `--animate` additionally clears the screen and shows
a snapshot of all zones (`[ ]` normal, `[X]` blocked, `[!]` restricted,
`[*]` priority) with live drone counts, so the flow through corridors
and the effect of capacities are directly visible. A summary at the end
reports the secondary metrics of the subject: total turns, total moves,
average turns per drone and total path cost.

### Graphical simulation (pygame)

`--gui` opens a real `pygame` window replaying the whole simulation:

every zone is drawn as a disk at its map coordinates (colored by
`color=`, otherwise by zone type; `S`/`E` letters for the start and end
hubs, type icons inside), connections are drawn as lines, and drones
are small disks moving from zone to zone at each turn (orange while in
2-turn transit over a connection). Controls: `SPACE` play/pause,
`RIGHT`/`LEFT` step one turn forward/backward, `ESC` quit; the window
also plays automatically from the first turn. pygame is imported
lazily: all other modes and the whole test suite keep working on a
machine without pygame (a clear error message then suggests
`make install` or `--visual`), and the pure `GuiRenderer` behind the
window is unit tested headlessly.

## Performance benchmarks

Measured with the bundled maps and checked by the test suite:

| Map                          | Drones | Target  | Ours |
|------------------------------|--------|---------|------|
| `easy_1.map` (linear)        | 2      | ≤ 6     | **6** |
| `easy_2.map` (simple fork)   | 4      | ≤ 8     | **5** |
| `easy_3.map` (basic capacity)| 4      | ≤ 6     | **6** |
| `medium_1.map` (dead end)    | 5      | ≤ 12    | **8** |
| `medium_2.map` (loop)        | 6      | ≤ 15    | **9** |
| `medium_3.map` (priority)    | 5      | ≤ 12    | **7** |
| `hard_1.map` (maze)          | 8      | ≤ 30    | **17** |
| `hard_2.map` (capacity hell) | 12     | ≤ 35    | **8** |
| `hard_3.map` (ultimate)      | 15     | ≤ 45    | **21** |
| `challenger.map` (dream)     | 25     | < 45    | **43** |

Every target listed in the subject is met or beaten, and the
challenger map is solved below the 45-turn reference record (bonus).
These numbers are asserted by the test suite (`make test`), and the
raw output of each run is replayed by the rule validator
(`--check`) to prove the solution never violates a constraint.

The map files bundled in `maps/` were authored for this project
following the subject descriptions (the map files attached to the
subject were not available in this environment); they reproduce the
described topologies and drone counts.

## Resources

* subject: Fly-in .en.subject.pdf
* Dijkstra (1959), *A note on two problems in connexion with graphs*
* `typing` module documentation — https://docs.python.org/3/library/typing.html
* PEP 257 (docstrings), PEP 8 (style), PEP 484 (type hints)
* flake8 — https://flake8.pycqa.org
* mypy — https://mypy.readthedocs.io

### Use of AI

AI tools were used to explore Dijkstra-based multi-agent scheduling
ideas (reservation based conflict avoidance, path penalization
strategies) and to help structure the validation test matrix. The
engine design, the conflict repair loop, the parser rules and all map
authoring were written, reviewed and tested manually.
