from pathlib import Path

from alembic.script import ScriptDirectory


def test_alembic_migration_graph_has_exactly_one_head() -> None:
    migrations = Path(__file__).parents[1] / "companion" / "migrations"
    script = ScriptDirectory(str(migrations))
    heads = script.get_heads()

    assert len(heads) == 1, f"Expected one Alembic head, found: {heads}"
