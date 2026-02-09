"""Login page UI.

SECURITY: This form uses rx.form with on_submit to capture credentials only at
submission time. Credentials are NOT bound to Reflex state variables, so they
are never synced to server-side state management (Redis) on every keystroke.
The password and MFA code only leave the browser once, when the form is submitted.
"""
import reflex as rx
from ..state import State
from ..styles.constants import ACCENT_PRIMARY, ACCENT_PRIMARY_HOVER


def login_page() -> rx.Component:
    """Login page with secure form submission."""
    return rx.center(
        rx.vstack(
            # Logo/Title
            rx.vstack(
                rx.text("StonksBoard", size="8", weight="bold", color=ACCENT_PRIMARY),
                rx.text("Portfolio Dashboard", size="3", color="gray"),
                spacing="1",
                align="center",
                margin_bottom="2em",
            ),
            # Login card with secure form
            rx.card(
                rx.form(
                    rx.vstack(
                        rx.text("Sign in to Robinhood", size="5", weight="bold"),
                        rx.text(
                            "Enter your Robinhood credentials to access your portfolio.",
                            size="2",
                            color="gray",
                        ),
                        # Error message
                        rx.cond(
                            State.login_error != "",
                            rx.callout(
                                State.login_error,
                                icon="triangle-alert",
                                color="red",
                                size="1",
                                width="100%",
                            ),
                        ),
                        # Email field (uncontrolled - not bound to state)
                        rx.vstack(
                            rx.text("Email", size="2", weight="medium"),
                            rx.input(
                                placeholder="your@email.com",
                                name="username",
                                type="email",
                                required=True,
                                width="100%",
                                size="3",
                                on_focus=State.clear_login_error,
                            ),
                            spacing="1",
                            width="100%",
                            align_items="start",
                        ),
                        # Password field (uncontrolled - not bound to state)
                        rx.vstack(
                            rx.text("Password", size="2", weight="medium"),
                            rx.input(
                                placeholder="••••••••",
                                name="password",
                                type="password",
                                required=True,
                                auto_complete=True,
                                width="100%",
                                size="3",
                                on_focus=State.clear_login_error,
                            ),
                            spacing="1",
                            width="100%",
                            align_items="start",
                        ),
                        # MFA field (conditional, uncontrolled)
                        rx.cond(
                            State.show_mfa_input,
                            rx.vstack(
                                rx.text("MFA Code", size="2", weight="medium"),
                                rx.input(
                                    placeholder="123456",
                                    name="mfa_code",
                                    type="text",
                                    input_mode="numeric",
                                    pattern="[0-9]*",
                                    auto_complete=False,
                                    width="100%",
                                    size="3",
                                    on_focus=State.clear_login_error,
                                ),
                                rx.text(
                                    "Check your authenticator app or SMS for the code.",
                                    size="1",
                                    color="gray",
                                ),
                                spacing="1",
                                width="100%",
                                align_items="start",
                            ),
                        ),
                        # Login button (submits form)
                        rx.button(
                            rx.cond(
                                State.is_loading,
                                rx.hstack(rx.spinner(size="1"), rx.text("Signing in...")),
                                rx.text("Sign In"),
                            ),
                            type="submit",
                            width="100%",
                            size="3",
                            background=ACCENT_PRIMARY,
                            _hover={"background": ACCENT_PRIMARY_HOVER},
                            disabled=State.is_loading,
                        ),
                        spacing="4",
                        width="100%",
                    ),
                    on_submit=State.login_with_form,
                    reset_on_submit=False,
                ),
                rx.divider(margin_y="1em"),
                # Fallback option (outside form)
                rx.vstack(
                    rx.text("Having trouble?", size="2", color="gray"),
                    rx.button(
                        "Use credentials.json instead",
                        on_click=State.login_with_credentials_file,
                        variant="outline",
                        size="2",
                        width="100%",
                        disabled=State.is_loading,
                    ),
                    spacing="2",
                    width="100%",
                    align="center",
                ),
                width="100%",
                max_width="400px",
                padding="1.5em",
            ),
            # Security note
            rx.text(
                "Your credentials are transmitted securely over HTTPS only when you click Sign In.",
                size="1",
                color="gray",
                text_align="center",
                max_width="400px",
                margin_top="1em",
            ),
            spacing="2",
            align="center",
            padding="2em",
        ),
        min_height="100vh",
        width="100%",
    )
