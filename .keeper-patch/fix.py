from pathlib import Path

path = Path('backend/companion/duplicate_keeper_rules.py')
text = path.read_text()
old = '''class DuplicateKeeperChoice:\n    keeper_asset_id: UUID | None\n    reason: str\n'''
new = '''class DuplicateKeeperChoice:\n    keeper_asset_id: UUID | None\n    reason: str\n    used_reference_tiebreaker: bool = False\n'''
if old not in text:
    raise SystemExit('missing DuplicateKeeperChoice anchor')
text = text.replace(old, new, 1)
old_return = 'return DuplicateKeeperChoice(reference_id, "reference_tiebreaker")'
new_return = 'return DuplicateKeeperChoice(reference_id, "reference_tiebreaker", True)'
if old_return not in text:
    raise SystemExit('missing reference tiebreaker anchor')
path.write_text(text.replace(old_return, new_return, 1))

schema = Path('backend/companion/duplicate_schema.py')
text = schema.read_text()
old = '        if self.operator not in {"highest", "lowest", "is_true", "is_false"} and not self.value.strip():\n'
new = (
    '        if (\n'
    '            self.operator not in {"highest", "lowest", "is_true", "is_false"}\n'
    '            and not self.value.strip()\n'
    '        ):\n'
)
if old not in text:
    raise SystemExit('missing keeper rule validation lint anchor')
schema.write_text(text.replace(old, new, 1))

modal = Path('frontend/src/v2/components/V2DuplicateKeeperModal.svelte')
text = modal.read_text()
replacements = {
    "let scope=$state<'current_page'|'all_matching'>(initialScope);": "let scope=$state<'current_page'|'all_matching'>('current_page');\n  $effect(()=>{ scope=initialScope; });",
    "next.operator=operators[0]?.value??'is';": "next.operator=(operators[0]?.value??'is') as DuplicateKeeperUiRule['operator'];",
    "options={operators}": "options={[...operators]}",
    "{#if definition.kind==='boolean'}\n                {:else if definition.kind==='media'}": "{#if definition.kind==='media'}",
}
for before, after in replacements.items():
    if before not in text:
        raise SystemExit(f'missing modal anchor: {before}')
    text = text.replace(before, after, 1)
modal.write_text(text)

demo = Path('frontend/src/v2/data/demo/demoLibraryDataSource.svelte.ts')
text = demo.read_text()
needle = "  duplicates:{\n"
if needle not in text:
    raise SystemExit('missing demo duplicates anchor')
text = text.replace(
    needle,
    "  duplicates:{\n    async previewKeeperRules(){await delay();return {} as any},\n    async applyKeeperRules(){await delay();return {} as any},\n",
    1,
)
text = text.replace(
    "reviewFilters:['All groups','Needs review','Auto-ready','Blocked','Actionable','Needs decisions']",
    "reviewFilters:['All groups','Actionable','Needs review','Needs decisions','Blocked']",
)
demo.write_text(text)

tests = Path('frontend/src/v2/state/duplicateKeeperRules.test.ts')
text = tests.read_text()
text = text.replace(
    "expect(keeperRuleFields.some((field) => field.value === 'newest')).toBe(false);",
    "expect(keeperRuleFields.map((field) => String(field.value))).not.toContain('newest');",
)
text = text.replace(
    "expect(keeperRuleFields.some((field) => field.value === 'oldest')).toBe(false);",
    "expect(keeperRuleFields.map((field) => String(field.value))).not.toContain('oldest');",
)
text = text.replace(
    "for (const field of ['library', 'folder', 'filename', 'mime_type', 'file_size', 'resolution', 'favorite', 'edited', 'tag', 'album', 'reference', 'similarity', 'metadata_richness', 'format_quality']) {",
    "for (const field of ['library', 'folder', 'filename', 'mime_type', 'file_size', 'resolution', 'favorite', 'edited', 'tag', 'album', 'reference', 'similarity', 'metadata_richness', 'format_quality'] as const) {",
)
text = text.replace("keeperOperatorOptions(definition, 'require')", "keeperOperatorOptions(definition.value, 'require')")
text = text.replace("keeperOperatorOptions(definition, 'prefer')", "keeperOperatorOptions(definition.value, 'prefer')")
tests.write_text(text)
