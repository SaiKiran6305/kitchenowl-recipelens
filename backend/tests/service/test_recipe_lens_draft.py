
import pytest
from app.service.recipe_lens_draft import (
    InvalidDraft,
    build_recipe_draft,
    parse_ocr_text,
    validate_draft,
)

RECIPE = """Pancakes
Serves: 4
Prep time: 10 minutes
Cook time: 1 hour 5 minutes
Ingredients:
• 1 1/2 cups flour
- 2 eggs
Instructions:
1. Mix ingredients.
2. Cook in a pan.
"""


@pytest.fixture(autouse=True)
def local_extraction(monkeypatch):
    monkeypatch.delenv("RECIPELENS_MODEL", raising=False)


def test_printed_recipe_preserves_quantities_and_maps_kitchenowl_fields():
    result = build_recipe_draft(RECIPE)
    assert result["source_text"] == RECIPE
    assert result["schema_version"] == 1
    assert result["draft"] == {
        "title": "Pancakes",
        "ingredients": ["1 1/2 cups flour", "2 eggs"],
        "instructions": ["Mix ingredients.", "Cook in a pan."],
        "servings": 4,
        "prep_time": 10,
        "cook_time": 65,
    }
    assert result["validation"] == {"valid": True, "errors": []}
    assert result["warnings"] == []
    assert result["recipe_payload"] == {
        "name": "Pancakes",
        "description": "Mix ingredients.\n\nCook in a pan.",
        "yields": 4,
        "prep_time": 10,
        "cook_time": 65,
    }
    assert result["requires_review"] is True
    assert "items" not in result["recipe_payload"]


def test_missing_optional_fields_are_null_not_invented():
    result = build_recipe_draft("Toast\nIngredients: bread\nMethod: Toast bread.")
    assert result["validation"]["valid"] is True
    assert result["draft"]["servings"] is None
    assert result["draft"]["prep_time"] is None
    assert result["draft"]["cook_time"] is None
    assert {w["field"] for w in result["warnings"]} == {
        "servings",
        "prep_time",
        "cook_time",
    }
    assert "yields" not in result["recipe_payload"]


def test_unlabelled_text_requires_review_instead_of_guessing_ingredients():
    result = build_recipe_draft("Pancakes\n2 eggs\nMix and cook")
    assert result["draft"]["ingredients"] == []
    assert result["validation"]["valid"] is False
    assert result["recipe_payload"] is None
    assert {e["field"] for e in result["validation"]["errors"]} == {
        "ingredients",
        "instructions",
    }
    assert any(w["code"] == "unassigned" for w in result["warnings"])


def test_missing_title_does_not_use_an_ingredient_as_the_title():
    result = build_recipe_draft("Ingredients\n2 eggs\nDirections\nCook eggs.")
    assert result["draft"]["title"] is None
    assert result["validation"]["errors"][0]["field"] == "title"


def test_cooking_words_in_recipe_content_are_not_metadata():
    result = build_recipe_draft(
        "Eggs\nIngredients\ncooking oil\n2 eggs\nMethod\nCook eggs.\nServe warm."
    )
    assert result["draft"]["ingredients"] == ["cooking oil", "2 eggs"]
    assert result["draft"]["instructions"] == ["Cook eggs.", "Serve warm."]
    assert result["validation"]["valid"] is True


def test_repeated_metadata_stays_ambiguous_and_compact_labels_are_supported():
    result = build_recipe_draft(
        "Toast\nServes:4\nServes:8\nServes:2\nPrep:5 min\nIngredients\nbread\nSteps\nToast."
    )
    assert result["draft"]["servings"] is None
    assert result["draft"]["prep_time"] == 5


@pytest.mark.parametrize("text", ["", " \n", None, 5, "x" * 100_001])
def test_bad_source_is_rejected(text):
    with pytest.raises(InvalidDraft):
        parse_ocr_text(text)


@pytest.mark.parametrize("value", [[], None, "recipe"])
def test_non_object_draft_is_rejected(value):
    with pytest.raises(InvalidDraft):
        validate_draft(value)


@pytest.mark.parametrize(
    "line,field",
    [
        ("Serves: 2-4", "servings"),
        ("Serves: 0", "servings"),
        ("Prep time: -5 minutes", "prep_time"),
        ("Cook time: 10-15 minutes", "cook_time"),
        ("Cook time: 1.5 hours", "cook_time"),
        ("Cook time: 200 hours", "cook_time"),
    ],
)
def test_ambiguous_printed_values_are_left_for_review(line, field):
    result = build_recipe_draft(f"Toast\n{line}\nIngredients\nbread\nSteps\nToast.")
    assert result["draft"][field] is None
    assert any(
        w["field"] == field and w["code"] == "unparsed" for w in result["warnings"]
    )


def test_conflicting_metadata_is_not_silently_overwritten():
    result = build_recipe_draft(RECIPE.replace("Serves: 4", "Serves: 4\nServes: 8"))
    assert result["draft"]["servings"] is None
    assert any(w["code"] == "ambiguous" for w in result["warnings"])



