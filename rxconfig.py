import reflex as rx

config = rx.Config(
    app_name="stonks_board",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)