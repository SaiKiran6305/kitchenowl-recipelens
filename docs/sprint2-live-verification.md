# Sprint 2 live verification

Executed October 28, 2026, approximately 7:06–7:08 PM America/Chicago (October 29 UTC).
Executor: automated API checks operated during project setup; not a team Scrum meeting or classroom demonstration.

## Environment

- Service: https://recipelens-backend-production.up.railway.app/
- Deployed commit: 2228eb513207b72ed824bc84c6c5260ef642510d.
- Main commit checked: 5c5a97fe748d7aadd3f6a5374762f738c7a6d525.
- Both commits have tree 05ce6f17fe6b4d497316b599e6d4e48ccd58a9f9.
- Railway deployment 0f80d854-78d6-4f33-9adf-4e63287a631f reached SUCCESS.
- GitHub Pytesting runs 40790999824 and 40791033462 passed.
- A signed-in administrator created the RecipeLens Demo household through the Flutter client.
- A temporary API token was used for the requests, then revoked. DELETE returned 200; reuse returned 401. No token is included in this evidence.

## Live results

Actual Tesseract and PDF rendering ran on Railway. OCR was not mocked.
Inputs were synthetic English recipes with labelled sections.

| Check | Observed result |
| --- | --- |
| PNG structured draft | 200; title Simple Toast, 2 servings, prep 5 minutes, cook 3 minutes, two ingredients and two instructions |
| Sprint 1 text endpoint | 200; expected source text recognized |
| Missing optional metadata | 200; servings and times null, three missing-field warnings |
| Incomplete recipe | 200; invalid draft, required-field errors, recipe_payload null |
| Unsupported text file | 400 |
| Corrupt PNG | 400 |
| JPEG structured draft | 200; expected fields recognized |
| Single-page PDF draft | 200; expected fields recognized |
| Two-page PDF | 400; single-page requirement enforced |
| No recipe writes | Recipe list remained empty before and after extraction requests |
| Server-admin household bypass | 200 for a nonexistent household ID, consistent with the existing authorize_household administrator bypass |

The initial household-denial expectation was inappropriate for the administrator account.
It is recorded as an administrator-bypass observation, not proof of non-admin denial.
Automated API tests cover non-admin denial; a separate live non-admin test remains outstanding.
Unauthenticated requests to both scan endpoints returned 401 in the preceding deployment audit.

Detailed synthetic responses are in sprint2-live-results.json. Approximate PNG request timings
were 2.3–4.8 seconds in this small run; these are not a performance benchmark.

## Scope and remaining evidence

This verifies the Sprint 2 backend API path: authenticated upload, real OCR, local
parsing, validation and a no-save response. The optional remote provider was disabled;
provider timeout and fallback are covered by mocked automated tests rather than a live paid call.

The existing Flutter client does not contain a RecipeLens upload/review screen.
US-04 review and US-05 ingredient matching/confirmed saving remain Sprint 3 work.
The browser-to-OCR user workflow is therefore not complete.

For the Iteration 2 report, supply actual team task ownership and completion dates,
Scrum attendance/updates, retrospective board photo and action owners, the new Scrum
Master and next meeting schedule. These records were not produced by this verification.
A classroom demonstration and 30–50 sample quality evaluation are not claimed.
