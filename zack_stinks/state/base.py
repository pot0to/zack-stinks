import reflex as rx

class BaseState(rx.State):
    """Global state for variables used across the entire app."""
    is_loading: bool = False
    is_logged_in: bool = False
    account_name: str = "User"
    sidebar_open: bool = False
    mfa_input: str = ""

    def toggle_sidebar(self):
        self.sidebar_open = not self.sidebar_open