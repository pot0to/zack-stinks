# zack_stinks/utils/auth.py
import json
import os

def get_rh_credentials():
    """Reads credentials from a local JSON or env file."""
    # It's safer to use an Absolute path or an Environment Variable
    creds_path = os.path.join(os.path.dirname(__file__), "../../credentials.json")
    
    try:
        with open(creds_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None