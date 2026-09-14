from pathlib import Path

repo_path = Path("backend/companion/composite_duplicate_repository.py")
text = repo_path.read_text()
text = text.replace(
    '    metadata: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)\n',
    '    evidence_metadata: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)\n',
)
text = text.replace('metadata=dict(row.metadata or {}),', 'metadata=dict(row.evidence_metadata or {}),')
text = text.replace('"metadata": dict(item.metadata),', '"evidence_metadata": dict(item.metadata),')
text = text.replace('"metadata": statement.excluded.metadata,', '"evidence_metadata": statement.excluded.evidence_metadata,')
repo_path.write_text(text)

migration_path = Path(
    "backend/companion/migrations/versions/20260914_0044_composite_duplicate_snapshot.py"
)
migration = migration_path.read_text().replace(
    '        sa.Column("metadata", sa.JSON(), nullable=False),\n',
    '        sa.Column("evidence_metadata", sa.JSON(), nullable=False),\n',
)
migration_path.write_text(migration)
