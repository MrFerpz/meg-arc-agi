"""Download ARC-AGI-3 games into environment_files/ so the MEG PC can run OFFLINE.

Run once on a PC with internet, then copy environment_files/ to the stimulus PC:
    uv run python scripts/fetch_games.py            # all games the key can see
    uv run python scripts/fetch_games.py ls20 ft09  # only these
"""

import sys

from arc_agi import Arcade, OperationMode

arc = Arcade(operation_mode=OperationMode.NORMAL, environments_dir="environment_files")
wanted = sys.argv[1:] or [e.game_id for e in arc.available_environments]
for game_id in wanted:
    env = arc.make(game_id)
    print(("OK   " if env else "FAIL ") + game_id)
