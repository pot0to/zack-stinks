import reflex as rx

config = rx.Config(
    app_name="zack_stinks",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)