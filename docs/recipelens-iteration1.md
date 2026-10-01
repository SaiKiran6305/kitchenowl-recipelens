# RecipeLens: upload and OCR slice

This first increment lets an authenticated KitchenOwl household member submit a
printed recipe page and receive its recognized text. It does not save a recipe.
The user will review and correct a structured draft in a later increment before
explicitly saving it.

## Request and response

`POST /api/household/<household_id>/recipe/scan` accepts `multipart/form-data`
with a `file` field and a bearer token. The file may be PNG, JPEG, or a
single-page PDF, up to 10 MB. The server checks the household membership before
processing the file. Example:

```sh
curl -X POST \
  -H "Authorization: Bearer $KITCHENOWL_ACCESS_TOKEN" \
  -F "file=@printed-recipe.png" \
  "http://localhost:5000/api/household/1/recipe/scan"
```

A successful response is `{"text":"Pancakes\n2 eggs..."}`. Invalid or
unsupported uploads return HTTP 400; a page with no recognized text returns
422; unavailable OCR tools return 503. Login and household access use the
existing KitchenOwl authentication rules.

The backend container includes Tesseract English OCR and Poppler for PDF page
checks and rendering. Local development needs `tesseract`, `pdfinfo`, and
`pdftoppm` on `PATH`. The request is read with a 10 MB cap; normalized images
and PDF pages live in a temporary directory removed after processing. The
existing permanent `/api/upload` endpoint is deliberately not used.

## Demonstration and checks

1. Sign in to KitchenOwl and obtain an access token and household ID.
2. Upload a clear printed recipe using the request above; point out the text
   in the response and verify that the recipe list has not changed.
3. Upload an unsupported file or two-page PDF to show a controlled error.

The tests in `backend/tests/service/test_recipe_lens_ocr.py` cover format,
size, PDF page count, blank OCR, and returned text. The API tests in
`backend/tests/api/test_api_recipe_lens.py` cover authentication, membership,
the response, and the absence of a saved recipe. Run them with the backend's
usual pytest environment. OCR output quality depends on the scan; handwriting
and multi-page PDFs are outside this increment.
