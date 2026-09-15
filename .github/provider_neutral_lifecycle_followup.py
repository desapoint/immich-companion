from pathlib import Path

path = Path("backend/tests/test_duplicate_service.py")
text = path.read_text()
old = '    assert reviews.saved["review_status"] == "manually_configured"\n'
new = '    assert reviews.saved["review_status"] == "reviewed_mixed"\n'
count = text.count(old)
if count != 1:
    raise SystemExit(f"expected one legacy mixed-review assertion, got {count}")
path.write_text(text.replace(old, new, 1))
