"""Login page UI."""
import reflex as rx
from ..state import State
from ..styles.constants import ACCENT_PRIMARY, ACCENT_PRIMARY_HOVER


def login_page() -> rx.Component:
    """Login page with form and fallback option."""
    return rx.center(
        rx.vstack(
            # Logo/Title
            rx.vstack(
                rx.text("Zack Stinks", size="8", weight="bold", color=ACCENT_PRIMARY),
                rx.text("Portfolio Dashboard", size="3", color="gray"),
                spacing="1",
                align="center",
                margin_bottom="2em",
            ),
            # Login card
            rx.card(
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
                    # Username field
                    rx.vstack(
                        rx.text("Email", size="2", weight="medium"),
                        rx.input(
                            placeholder="your@email.com",
                            value=State.login_username,
                            on_change=State.set_login_username,
                            width="100%",
                            size="3",
                        ),
                        spacing="1",
                        width="100%",
                        align_items="start",
                    ),
                    # Password field
                    rx.vstack(
                        rx.text("Password", size="2", weight="medium"),
                        rx.input(
                            placeholder="••••••••",
                            type="password",
                            value=State.login_password,
                            on_change=State.set_login_password,
                            width="100%",
                            size="3",
                        ),
                        spacing="1",
                        width="100%",
                        align_items="start",
                    ),
                    # MFA field (conditional)
                    rx.cond(
                        State.show_mfa_input,
                        rx.vstack(
                            rx.text("MFA Code", size="2", weight="medium"),
                            rx.input(
                                placeholder="123456",
                                value=State.mfa_input,
                                on_change=State.set_mfa_input,
                                width="100%",
                                size="3",
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
                    # Login button
                    rx.button(
                        rx.cond(
                            State.is_loading,
                            rx.hstack(rx.spinner(size="1"), rx.text("Signing in...")),
                            rx.text("Sign In"),
                        ),
                        on_click=State.login_with_form,
                        width="100%",
                        size="3",
                        background=ACCENT_PRIMARY,
                        _hover={"background": ACCENT_PRIMARY_HOVER},
                        disabled=State.is_loading,
                    ),
                    rx.divider(margin_y="1em"),
                    # Fallback option
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
                    spacing="4",
                    width="100%",
                    padding="1.5em",
                ),
                width="100%",
                max_width="400px",
            ),
            # Security note
            rx.text(
                "Your credentials are sent directly to Robinhood over HTTPS and are not stored.",
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
