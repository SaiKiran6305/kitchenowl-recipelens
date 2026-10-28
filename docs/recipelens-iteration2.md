# RecipeLens US-02: structured extraction

Related story: #3. The authenticated POST /api/household/<id>/recipe/scan/draft
endpoint converts Sprint 1 OCR text to a versioned draft with title, ingredients,
instructions, servings, prep_time and cook_time. It preserves source_text and
original ingredient quantities/units. Missing metadata uses null; missing core
fields return validation errors and a null recipe_payload for later correction.
The partial KitchenOwl field mapping creates no recipe, item or permanent upload.

The local English parser recognizes Ingredients, Instructions, Directions,
Method and Steps headings plus labelled servings and integer hour/minute times.
Ambiguous values and text outside sections are flagged for review. Unlabelled
layouts and handwriting are not supported by this baseline. Every draft needs
human review. The existing /scan endpoint is unchanged.

Use the same authenticated multipart file request documented for Sprint 1,
but append /draft to /scan. Upload validation and error statuses are preserved.
Run the service and API draft tests with the backend pytest environment.
Tests mock OCR and verify mapping, incomplete drafts, access checks and no writes.

US-03 (#4) follows in a separate dependent PR: strict numeric typing,
malformed provider-output validation and optional provider timeout/fallback.
Flutter review, household item matching and confirmed save remain Sprint 3.

