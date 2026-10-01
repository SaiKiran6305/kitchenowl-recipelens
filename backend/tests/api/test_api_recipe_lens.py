import io
from unittest.mock import patch

from app.models import Recipe


def test_scan_requires_login(client):
    response = client.post(
        "/api/household/1/recipe/scan",
        data={"file": (io.BytesIO(b"image"), "page.png")},
    )
    assert response.status_code == 401


def test_scan_returns_text_without_creating_recipe(user_client_with_household, household_id):
    with patch(
        "app.controller.recipe.recipe_controller.extract_printed_recipe_text",
        return_value="Pancakes\n2 eggs",
    ):
        response = user_client_with_household.post(
            f"/api/household/{household_id}/recipe/scan",
            data={"file": (io.BytesIO(b"image"), "page.png")},
        )
    assert response.status_code == 200
    assert response.get_json() == {"text": "Pancakes\n2 eggs"}
    assert Recipe.query.count() == 0


def test_scan_rejects_missing_file(user_client_with_household, household_id):
    response = user_client_with_household.post(
        f"/api/household/{household_id}/recipe/scan", data={}
    )
    assert response.status_code == 400
    assert Recipe.query.count() == 0


def test_scan_rejects_non_member(user_client):
    response = user_client.post(
        "/api/household/1000000000/recipe/scan",
        data={"file": (io.BytesIO(b"image"), "page.png")},
    )
    assert response.status_code == 403
