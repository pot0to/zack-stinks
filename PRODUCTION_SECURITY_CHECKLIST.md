# Production Security Checklist

Before deploying to production, complete these steps to remove the development-only credentials file fallback.

## Changes Required

### 1. Delete the auth utility file
Remove `stonks_board/utils/auth.py` entirely. This file only exists to read credentials.json.

### 2. Update base state
In `stonks_board/state/base.py`:
- Remove the import: `from ..utils.auth import get_rh_credentials`
- Delete the entire `login_with_credentials_file()` method (approximately lines 119-140)

### 3. Update login page UI
In `stonks_board/pages/login.py`:
- Remove the divider: `rx.divider(margin_y="1em")`
- Remove the fallback section containing "Having trouble?" text and the "Use credentials.json instead" button

### 4. Delete credentials.json
Remove the `credentials.json` file from the project root.

### 5. Update README.md
Remove the "Option 2: credentials.json (Fallback)" section from the Configuration documentation.

## Security Notes

The form-based login that remains is well-designed:
- Credentials are captured only at form submission time via uncontrolled inputs
- Never stored in Reflex state, preventing sync to Redis on every keystroke
- Transmitted once over HTTPS, used immediately, then discarded
- MFA is supported through the same secure flow

The robin_stocks library stores session tokens at `~/.tokens/robinhood.pickle`, which persists login across server restarts. This is library behavior and provides session continuity without re-authentication.
