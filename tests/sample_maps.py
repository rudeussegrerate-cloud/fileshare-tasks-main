"""Minimal valid maps used by unit tests."""

LINEAR_MAP = """
nb_drones: 2
start_hub: start 0 0
end_hub: end 3 0
hub: a 1 0
hub: b 2 0
connection: start-a
connection: a-b
connection: b-end
"""

RESTRICTED_MAP = """
nb_drones: 1
start_hub: start 0 0
end_hub: end 3 0
hub: lab 1 0 [zone=restricted]
hub: b 2 0
connection: start-lab
connection: lab-b
connection: b-end
"""

PARALLEL_MAP = """
nb_drones: 4
start_hub: start 0 1
end_hub: end 4 1
hub: up 1 0 [max_drones=2]
hub: up2 2 0 [max_drones=2]
hub: up3 3 0 [max_drones=2]
hub: down 1 2 [max_drones=2]
hub: down2 2 2 [max_drones=2]
hub: down3 3 2 [max_drones=2]
connection: start-up
connection: up-up2
connection: up2-up3
connection: up3-end
connection: start-down
connection: down-down2
connection: down2-down3
connection: down3-end
"""
