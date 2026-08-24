"""Programmatic Alembic upgrade entrypoint for container startup."""

from pathlib import Path

from alembic import command
from alembic.config import Config

from companion.config import Settings


def run_migrations(settings: Settings) -> None:
    """Upgrade a configured companion database to the packaged head revision."""

    database_url = settings.sqlalchemy_database_url
    if database_url is None:
        return

    config = Config()
    config.set_main_option("script_location", str(Path(__file__).with_name("migrations")))
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")
