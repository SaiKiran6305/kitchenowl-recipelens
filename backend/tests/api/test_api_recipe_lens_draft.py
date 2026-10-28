import io
from unittest.mock import patch

import pytest
from app.models import Item, Recipe
from app.service.recipe_lens_draft import InvalidDraft
from app.service.recipe_lens_ocr import (
    InvalidRecipeFile,
    OCRUnavailable,
    UnreadableRecipe,
)

SOURCE = "Toast\nIngredients\n1 slice bread\nInstructions\nToast bread."
OCR_PATH = "app.controller.recipe.recipe_controller.extract_printed_recipe_text"


@pytest.fixture(autouse=True)
def disable_model(monkeypatch):
    monkeypatch.delenv("RECIPELENS_MODEL", raising=False)


def upload(client, household_id):
    return client.post(
        f"/api/household/{household_id}/recipe/scan/draft",
        data={"file": (io.BytesIO(b"mocked OCR input"), "recipe.png")},
    )


def test_draft_requires_login_before_extraction(client):
    with patch(OCR_PATH) as extract:
        response = upload(client, 1)
    assert response.status_code == 401
    extract.assert_not_called()


def test_draft_requires_household_access_before_extraction(user_client):
    with patch(OCR_PATH) as extract:
        response = upload(user_client, 1000000000)
    assert response.status_code == 403
    extract.assert_not_called()


def test_draft_returns_review_contract_without_writes(
    user_client_with_household, household_id
):
    before = (Recipe.query.count(), Item.query.count())
    with patch(OCR_PATH, return_value=SOURCE):
        response = upload(user_client_with_household, household_id)
    assert response.status_code == 200
    result = response.get_json()
    assert result["source_text"] == SOURCE
    assert result["draft"]["ingredients"] == ["1 slice bread"]
    assert result["validation"]["valid"] is True
    assert result["requires_review"] is True
    assert result["recipe_payload"]["name"] == "Toast"
    assert (Recipe.query.count(), Item.query.count()) == before


def test_incomplete_draft_is_editable_but_has_no_payload(
    user_client_with_household, household_id
):
    with patch(OCR_PATH, return_value="Toast"):
        response = upload(user_client_with_household, household_id)
    assert response.status_code == 200
    assert response.get_json()["validation"]["valid"] is False
    assert response.get_json()["recipe_payload"] is None
    assert Recipe.query.count() == 0


@pytest.mark.parametrize(
    "error,status",
    [
        (InvalidRecipeFile("Invalid upload."), 400),
        (UnreadableRecipe("No text."), 422),
        (OCRUnavailable("Unavailable."), 503),
    ],
)
def test_ocr_errors_do_not_save(
    user_client_with_household, household_id, error, status
):
    with patch(OCR_PATH, side_effect=error):
        response = upload(user_client_with_household, household_id)
    assert response.status_code == status
    assert Recipe.query.count() == 0


def test_invalid_extraction_has_controlled_response(
    user_client_with_household, household_id
):
    with (
        patch(OCR_PATH, return_value=SOURCE),
        patch(
            "app.controller.recipe.recipe_controller.build_recipe_draft",
            side_effect=InvalidDraft("Extraction returned invalid recipe fields."),
        ),
    ):
        response = upload(user_client_with_household, household_id)
    assert response.status_code == 422
    assert Recipe.query.count() == 0


def test_missing_file_is_rejected(user_client_with_household, household_id):
    response = user_client_with_household.post(
        f"/api/household/{household_id}/recipe/scan/draft",
        data={},
    )
    assert response.status_code == 400
    assert Recipe.query.count() == 0


def test_provider_timeout_returns_local_draft_without_writes(
    user_client_with_household,
    household_id,
    monkeypatch,
):
    monkeypatch.setenv("RECIPELENS_MODEL", "test/model")
    with (
        patch(OCR_PATH, return_value=SOURCE),
        patch(
            "app.service.recipe_lens_draft.ModelDraftProvider.extract",
            side_effect=TimeoutError(),
        ),
    ):
        response = upload(user_client_with_household, household_id)
    assert response.status_code == 200
    assert response.get_json()["extraction_method"] == "local"
    assert any(w["code"] == "fallback" for w in response.get_json()["warnings"])
    assert Recipe.query.count() == 0
