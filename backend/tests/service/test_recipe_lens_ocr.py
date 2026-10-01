import io
from unittest.mock import patch

import pytest
from PIL import Image

from app.service.recipe_lens_ocr import (
    InvalidRecipeFile,
    UnreadableRecipe,
    extract_printed_recipe_text,
)


def image_bytes(format="PNG"):
    output = io.BytesIO()
    Image.new("RGB", (100, 50), "white").save(output, format=format)
    return output.getvalue()


def test_png_returns_ocr_text_without_persisting_upload():
    with patch("app.service.recipe_lens_ocr._run", return_value="  Pancakes\n2 eggs\n") as run:
        assert extract_printed_recipe_text(io.BytesIO(image_bytes()), "scan.png") == (
            "Pancakes\n2 eggs"
        )
        assert run.call_args.args[0][0] == "tesseract"


@pytest.mark.parametrize(
    "contents,filename",
    [
        (b"", "scan.png"),
        (b"not an image", "scan.png"),
        (image_bytes("PNG"), "scan.jpg"),
        (image_bytes("PNG"), "scan.gif"),
        (b"x" * (10 * 1024 * 1024 + 1), "scan.png"),
    ],
)
def test_bad_uploads_are_rejected(contents, filename):
    with pytest.raises(InvalidRecipeFile):
        extract_printed_recipe_text(io.BytesIO(contents), filename)


def test_multi_page_pdf_is_rejected_before_rendering():
    with patch("app.service.recipe_lens_ocr._run", return_value="Pages: 2\n") as run:
        with pytest.raises(InvalidRecipeFile, match="single-page"):
            extract_printed_recipe_text(io.BytesIO(b"%PDF-1.7\ntest"), "scan.pdf")
        assert run.call_count == 1
        assert run.call_args.args[0][0] == "pdfinfo"


def test_blank_ocr_result_is_distinct_from_invalid_file():
    with patch("app.service.recipe_lens_ocr._run", return_value="  \n"):
        with pytest.raises(UnreadableRecipe):
            extract_printed_recipe_text(io.BytesIO(image_bytes()), "scan.png")
