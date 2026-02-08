"""Base state shared across all pages."""
import reflex as rx
import asyncio
import robin_stocks.robinhood as rs
from ..utils.auth import get_rh_credentials


class BaseState(rx.State):
    """Global state for variables used across the entire app."""
    # App state
    is_loading: bool = False
    is_logged_in: bool = False
    account_name: str = "User"
    sidebar_open: bool = False
    
    # Login form state
    login_username: str = ""
    login_password: str = ""
    mfa_input: str = ""
    login_error: str = ""
    show_mfa_input: bool = False

    def toggle_sidebar(self):
        self.sidebar_open = not self.sidebar_open
    
    def set_login_username(self, value: str):
        self.login_username = value
        self.login_error = ""
    
    def set_login_password(self, value: str):
        self.login_password = value
        self.login_error = ""
    
    def set_mfa_input(self, value: str):
        self.mfa_input = value
        self.login_error = ""

    async def _perform_login(self, username: str, password: str):
        """Common login logic for both form and credentials file methods."""
        try:
            login_info = await asyncio.to_thread(
                rs.login,
                username=username,
                password=password,
                mfa_code=self.mfa_input if self.mfa_input else None,
                store_session=True
            )
            
            if login_info and "access_token" in login_info:
                user_profile = await asyncio.to_thread(rs.account.load_user_profile)
                self.account_name = user_profile.get("first_name", "User")
                self.is_logged_in = True
                self.mfa_input = ""
                self.show_mfa_input = False
                return True, None
            else:
                return False, "Login failed. Please check your credentials."
        except Exception as e:
            error_msg = str(e).lower()
            if "mfa" in error_msg or "challenge" in error_msg:
                self.show_mfa_input = True
                return False, "MFA code required. Check your authenticator app or SMS."
            else:
                return False, f"Login error: {str(e)}"

    async def login_with_form(self):
        """Login using credentials from the UI form."""
        if not self.login_username or not self.login_password:
            self.login_error = "Please enter both username and password."
            return
        
        self.is_loading = True
        self.login_error = ""
        yield
        
        success, error = await self._perform_login(self.login_username, self.login_password)
        
        # Always clear password from memory after attempt
        self.login_password = ""
        
        if success:
            self.login_username = ""
            yield rx.redirect("/")
        else:
            self.login_error = error or "Login failed."
        
        self.is_loading = False

    async def login_with_credentials_file(self):
        """Fallback login using credentials.json file."""
        self.is_loading = True
        self.login_error = ""
        yield
        
        creds = get_rh_credentials()
        if not creds:
            self.login_error = "credentials.json not found. Please create it in the project root."
            self.is_loading = False
            return
        
        success, error = await self._perform_login(creds["username"], creds["password"])
        
        if success:
            yield rx.redirect("/")
        else:
            self.login_error = error or "Login failed using credentials.json."
        
        self.is_loading = False

    async def logout(self):
        """Log out and clear session."""
        try:
            await asyncio.to_thread(rs.logout)
        except Exception:
            pass
        self.is_logged_in = False
        self.account_name = "User"
        self.login_username = ""
        self.login_password = ""
        self.mfa_input = ""
        self.show_mfa_input = False
        yield rx.redirect("/login")
