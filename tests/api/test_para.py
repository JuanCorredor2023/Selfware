from fastapi.testclient import TestClient

from selfware.api.app import app

client = TestClient(app)

ITEM_KEYS = {"id", "name", "email_count", "last_activity"}


def test_para_returns_the_four_categories_in_order():
    response = client.get("/para")
    assert response.status_code == 200
    assert [c["key"] for c in response.json()] == [
        "projects",
        "areas",
        "resources",
        "archive",
    ]


def test_every_category_endpoint_matches_the_tree():
    tree = {c["key"]: c["items"] for c in client.get("/para").json()}
    for key, items in tree.items():
        response = client.get(f"/{key}")
        assert response.status_code == 200
        assert response.json() == items


def test_items_have_the_expected_shape():
    for category in client.get("/para").json():
        assert category["items"], f"{category['key']} is empty"
        for item in category["items"]:
            assert ITEM_KEYS <= set(item.keys())
            assert isinstance(item["email_count"], int)
            assert item["last_activity"][:4].isdigit()


def test_only_projects_have_a_status():
    tree = {c["key"]: c["items"] for c in client.get("/para").json()}
    assert all(i["status"] in {"active", "inactive"} for i in tree["projects"])
    for key in ("areas", "resources", "archive"):
        assert all("status" not in i for i in tree[key])


def test_item_ids_are_unique_across_the_tree():
    ids = [i["id"] for c in client.get("/para").json() for i in c["items"]]
    assert len(ids) == len(set(ids))


def test_endpoints_return_copies_not_shared_state():
    first = client.get("/projects").json()
    first[0]["name"] = "changed by the client"
    assert client.get("/projects").json()[0]["name"] != "changed by the client"
