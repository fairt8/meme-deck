# deskstate.py - small run-to-run counters for the GitHub Actions desk (desk_state.json, kept in the state branch).
import json, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
F = "desk_state.json"
def load() -> dict:
    try: return json.load(open(F))
    except Exception: return {}
def save(d: dict):
    tmp = F + ".tmp"; json.dump(d, open(tmp, "w"), indent=1); os.replace(tmp, F)
