"""Temporary, local OCR for printed recipe uploads.

No upload or rendered page is kept after this function returns.
"""

import io
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_RECIPE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
OCR_TIMEOUT_SECONDS = 30


class InvalidRecipeFile(ValueError):
    """The upload is missing, too large, or not a supported printed page."""


class UnreadableRecipe(ValueError):
    """OCR completed but found no usable text."""


class OCRUnavailable(RuntimeError):
    """A local OCR dependency is missing or failed to finish."""


def _run(command: list[str], timeout: int = OCR_TIMEOUT_SECONDS, *, ocr=False) -> str:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, check=False, timeout=timeout
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise OCRUnavailable("The local OCR service is unavailable.") from exc
    if result.returncode:
        if ocr:
            raise OCRUnavailable("The local OCR service could not process this page.")
        raise InvalidRecipeFile("The uploaded page could not be read.")
    return result.stdout


def _normalize_image(contents: bytes, output: Path, expected: str) -> None:
    try:
        with Image.open(io.BytesIO(contents)) as image:
            if image.format != expected or image.width * image.height > MAX_IMAGE_PIXELS:
                raise InvalidRecipeFile("The image format or dimensions are unsupported.")
            oriented = ImageOps.exif_transpose(image)
            oriented.convert("RGB").save(output, format="PNG")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidRecipeFile("The uploaded image is invalid.") from exc


def _render_pdf(contents: bytes, directory: Path) -> Path:
    if not contents.startswith(b"%PDF-"):
        raise InvalidRecipeFile("The uploaded PDF is invalid.")
    source = directory / "recipe.pdf"
    source.write_bytes(contents)
    info = _run(["pdfinfo", str(source)])
    pages = re.search(r"^Pages:\s*(\d+)\s*$", info, re.MULTILINE)
    if pages is None or int(pages.group(1)) != 1:
        raise InvalidRecipeFile("Upload a single-page PDF.")
    prefix = directory / "page"
    _run(
        [
            "pdftoppm", "-f", "1", "-l", "1", "-singlefile",
            "-scale-to", "2200", "-png", str(source), str(prefix),
        ]
    )
    output = directory / "page.png"
    if not output.is_file():
        raise InvalidRecipeFile("The PDF page could not be rendered.")
    return output


def extract_printed_recipe_text(stream, filename: str) -> str:
    """Return OCR text from a supported file-like upload without storing it."""
    extension = Path(filename or "").suffix.lower()
    if extension not in {".png", ".jpg", ".jpeg", ".pdf"}:
        raise InvalidRecipeFile("Use a PNG, JPEG, or single-page PDF.")
    contents = stream.read(MAX_RECIPE_BYTES + 1)
    if not contents or len(contents) > MAX_RECIPE_BYTES:
        raise InvalidRecipeFile("Upload a nonempty file no larger than 10 MB.")

    with tempfile.TemporaryDirectory(prefix="recipe-lens-") as temporary:
        directory = Path(temporary)
        if extension == ".pdf":
            image_path = _render_pdf(contents, directory)
        else:
            image_path = directory / "page.png"
            _normalize_image(
                contents, image_path, "PNG" if extension == ".png" else "JPEG"
            )
        text = _run(
            ["tesseract", str(image_path), "stdout", "-l", "eng"], ocr=True
        )
        text = text.strip()
        if not text:
            raise UnreadableRecipe("No readable printed text was found.")
        return text
