"""Tag hierarchy selection identities."""

from uuid import UUID

from companion.immich import ImmichTag
from companion.main import matching_tag_ids, tag_subtree_ids

ROOT = UUID("11111111-1111-4111-8111-111111111111")
CHILD = UUID("22222222-2222-4222-8222-222222222222")
GRANDCHILD = UUID("33333333-3333-4333-8333-333333333333")
SIBLING = UUID("44444444-4444-4444-8444-444444444444")


def test_real_tag_rows_include_self_and_every_descendant() -> None:
    catalog = [
        ImmichTag(id=ROOT, name="Places", value="Places"),
        ImmichTag(id=CHILD, name="City", value="City", parentId=ROOT),
        ImmichTag(id=GRANDCHILD, name="Park", value="Park", parentId=CHILD),
        ImmichTag(id=SIBLING, name="Town", value="Town", parentId=ROOT),
    ]

    identities = tag_subtree_ids(catalog)

    assert identities[ROOT] == [ROOT, CHILD, GRANDCHILD, SIBLING]
    assert identities[CHILD] == [CHILD, GRANDCHILD]
    assert identities[GRANDCHILD] == [GRANDCHILD]

    assert matching_tag_ids(catalog, "Places", False) == [ROOT, CHILD, GRANDCHILD, SIBLING]
    assert matching_tag_ids(catalog, "Places / City", True) == [CHILD, GRANDCHILD]
