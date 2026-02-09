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
    hide_portfolio_values: bool = False
    
    # Global portfolio loading flag - accessible from any page
    # Used to show loading indicators across the app while portfolio data is being fetched
    is_portfolio_loading: bool = False
    
    # Login UI state (non-sensitive fields only)
    # SECURITY: Credentials (username, password, mfa_code) are NOT stored in Reflex state.
    # They are captured only at form submission time via rx.form, transmitted once over
    # TLS, used immediately for authentication, then discarded. This prevents credentials
    # from being synced to server-side state management (Redis) on every keystroke.
    login_error: str = ""
    show_mfa_input: bool = False
    redirect_after_login: str = "/"  # Track where to redirect after successful login

    def toggle_sidebar(self):
        self.sidebar_open = not self.sidebar_open
    
    def toggle_hide_values(self):
        self.hide_portfolio_values = not self.hide_portfolio_values
    
    def clear_login_error(self):
        """Clear login error message when user starts typing."""
        self.login_error = ""
    
    def navigate_to_login(self, from_page: str = "/"):
        """Set the redirect destination and navigate to login page."""
        self.redirect_after_login = from_page
        return rx.redirect("/login")

    async def validate_existing_session(self) -> bool:
        """Check if an existing robin_stocks pickle session is still valid.
        
        Called on page load to restore login state from the pickle file
        without requiring the user to re-enter credentials. Always validates
        against the actual API rather than trusting in-memory state.
        """
        try:
            user_profile = await asyncio.to_thread(rs.account.load_user_profile)
            if user_profile and user_profile.get("first_name"):
                self.account_name = user_profile.get("first_name", "User")
                self.is_logged_in = True
                return True
        except Exception:
            pass
        
        # Session invalid or expired
        self.is_logged_in = False
        self.account_name = "User"
        return False

    async def _perform_login(self, username: str, password: str, mfa_code: str = ""):
        """Common login logic for both form and credentials file methods.
        
        SECURITY: Credentials are passed as function arguments, used immediately,
        and never stored in instance state. They exist only in local scope.
        """
        try:
            login_info = await asyncio.to_thread(
                rs.login,
                username=username,
                password=password,
                mfa_code=mfa_code if mfa_code else None,
                store_session=True
            )
            
            if login_info and "access_token" in login_info:
                user_profile = await asyncio.to_thread(rs.account.load_user_profile)
                self.account_name = user_profile.get("first_name", "User")
                self.is_logged_in = True
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

    async def login_with_form(self, form_data: dict):
        """Login using credentials submitted via form.
        
        SECURITY: Credentials arrive in form_data dict, are used immediately for
        authentication, then go out of scope. They are never stored in Reflex state,
        so they cannot be synced to server-side state management or logged.
        """
        username = form_data.get("username", "").strip()
        password = form_data.get("password", "")
        mfa_code = form_data.get("mfa_code", "").strip()
        
        if not username or not password:
            self.login_error = "Please enter both email and password."
            return
        
        self.is_loading = True
        self.login_error = ""
        yield
        
        success, error = await self._perform_login(username, password, mfa_code)
        # Credentials are now out of scope and eligible for garbage collection
        
        if success:
            redirect_to = self.redirect_after_login or "/"
            self.redirect_after_login = "/"
            from .portfolio import PortfolioState
            yield PortfolioState.fetch_all_portfolio_data
            yield rx.redirect(redirect_to)
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
        
        success, error = await self._perform_login(
            creds.get("username", ""),
            creds.get("password", "")
        )
        
        if success:
            redirect_to = self.redirect_after_login or "/"
            self.redirect_after_login = "/"
            from .portfolio import PortfolioState
            yield PortfolioState.fetch_all_portfolio_data
            yield rx.redirect(redirect_to)
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
        self.show_mfa_input = False
        yield rx.redirect("/")
