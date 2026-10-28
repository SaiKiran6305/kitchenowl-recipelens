"""Build reviewable recipe drafts without accessing persistent storage."""

import re

from marshmallow import RAISE, Schema, ValidationError, fields, validate

MAX_SOURCE_CHARS = 100_000
MAX_MINUTES = 10_080  # One week; longer durations require manual correction.
MAX_SERVINGS = 1_000


class InvalidDraft(ValueError):
    """Extraction returned an unsupported structure or unsafe field values."""


class StrictString(fields.String):
    def _deserialize(self, value, attr, data, **kwargs):
        if not isinstance(value, str):
            raise ValidationError("Use a string.")
        return super()._deserialize(value, attr, data, **kwargs).strip()


class RecipeDraftSchema(Schema):
    class Meta:
        unknown = RAISE

    title = StrictString(
        allow_none=True, load_default=None, validate=validate.Length(max=128)
    )
    ingredients = fields.List(
        StrictString(validate=validate.Length(min=1, max=1_000)),
        load_default=list,
        validate=validate.Length(max=500),
    )
    instructions = fields.List(
        StrictString(validate=validate.Length(min=1, max=4_000)),
        load_default=list,
        validate=validate.Length(max=500),
    )
    servings = fields.Integer(
        allow_none=True,
        load_default=None,
        validate=validate.Range(min=1, max=MAX_SERVINGS),
    )
    prep_time = fields.Integer(
        allow_none=True,
        load_default=None,
        validate=validate.Range(min=0, max=MAX_MINUTES),
    )
    cook_time = fields.Integer(
        allow_none=True,
        load_default=None,
        validate=validate.Range(min=0, max=MAX_MINUTES),
    )


def validate_draft(candidate):
    """Validate shape/ranges separately from missing fields a person can supply."""
    if not isinstance(candidate, dict):
        raise InvalidDraft("Extraction must return a recipe object.")
    try:
        draft = RecipeDraftSchema().load(candidate)
    except ValidationError as exc:
        raise InvalidDraft("Extraction returned invalid recipe fields.") from exc
    if draft["title"] == "":
        draft["title"] = None
    errors = [
        {"field": field, "code": "required", "message": message}
        for field, message in (
            ("title", "A recipe title is required."),
            ("ingredients", "At least one ingredient is required."),
            ("instructions", "At least one instruction is required."),
        )
        if not draft[field]
    ]
    warnings = errors + [
        {"field": field, "code": "missing", "message": f"{label} was not found."}
        for field, label in (
            ("servings", "Servings"),
            ("prep_time", "Preparation time"),
            ("cook_time", "Cooking time"),
        )
        if draft[field] is None
    ]
    return draft, errors, warnings


HEADINGS = {
    "ingredients": "ingredients",
    "ingredient": "ingredients",
    "instructions": "instructions",
    "directions": "instructions",
    "method": "instructions",
    "steps": "instructions",
}
METADATA = re.compile(
    r"^(servings?|serves|yields?|prep(?:aration)?(?:\s+time)?|cook(?:ing)?(?:\s+time)?)"
    r"(?:\s*:\s*|\s+)(.+)$",
    re.IGNORECASE,
)
TIME_PART = re.compile(r"(\d+)\s*(hours?|hrs?|h|minutes?|mins?|m)\b", re.IGNORECASE)


def _minutes(value):
    parts = list(TIME_PART.finditer(value))
    remainder = TIME_PART.sub("", value).strip()
    if not parts or remainder:
        return None
    total = sum(
        int(part[1]) * (60 if part[2].lower().startswith("h") else 1) for part in parts
    )
    return total if total <= MAX_MINUTES else None


def parse_ocr_text(text):
    """Conservative parser for English printed recipes with section headings.

    Unlabelled sections are left for review instead of guessing which lines are
    ingredients. Original ingredient quantities and units are retained.
    """
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_SOURCE_CHARS:
        raise InvalidDraft("Supply nonempty OCR text of at most 100,000 characters.")
    draft = {
        "title": None,
        "ingredients": [],
        "instructions": [],
        "servings": None,
        "prep_time": None,
        "cook_time": None,
    }
    warnings = []
    seen_metadata = set()
    section = None
    for original in text.splitlines():
        line = original.strip()
        if not line:
            continue
        heading, colon, rest = line.partition(":")
        key = heading.lower().strip()
        if key in HEADINGS:
            section = HEADINGS[key]
            if colon and rest.strip():
                draft[section].append(rest.strip())
            continue
        metadata = METADATA.fullmatch(line)
        # "Cook eggs" is an instruction and "cooking oil" an ingredient,
        # not time metadata. Bare time labels need an explicit colon.
        if (
            metadata
            and metadata[1].lower().startswith(("prep", "cook"))
            and ":" not in line
            and "time" not in metadata[1].lower()
        ):
            metadata = None
        if metadata:
            label, value = metadata.groups()
            label = label.lower()
            if label.startswith(("serv", "yield")):
                field = "servings"
                match = re.fullmatch(
                    r"(\d+)(?:\s+(?:servings?|people|portions?))?", value, re.IGNORECASE
                )
                parsed = int(match[1]) if match else None
                if parsed is not None and not 1 <= parsed <= MAX_SERVINGS:
                    parsed = None
            else:
                field = "prep_time" if label.startswith("prep") else "cook_time"
                parsed = _minutes(value)
            if field in seen_metadata:
                parsed = None
                warnings.append(
                    {
                        "field": field,
                        "code": "ambiguous",
                        "message": "Multiple values need review.",
                    }
                )
            elif parsed is None:
                warnings.append(
                    {
                        "field": field,
                        "code": "unparsed",
                        "message": "The printed value needs manual review.",
                    }
                )
            draft[field] = parsed
            seen_metadata.add(field)
            continue
        if section:
            cleaned = re.sub(r"^(?:[-*•]\s+|\d+[.)]\s+)", "", line).strip()
            if cleaned:
                draft[section].append(cleaned)
        elif draft["title"] is None:
            draft["title"] = line
        else:
            warnings.append(
                {
                    "field": "source_text",
                    "code": "unassigned",
                    "message": "Text outside recognized sections needs review.",
                }
            )
    # Avoid repeating the same warning for each unassigned source line.
    warnings = [
        dict(entries) for entries in dict.fromkeys(tuple(w.items()) for w in warnings)
    ]
    return draft, warnings


def to_recipe_payload(draft):
    """Map reviewed fields to KitchenOwl names without creating/matching items.

    This is not a complete save request: ingredient mapping and explicit save
    confirmation are the responsibility of the later review workflow.
    """
    draft, errors, _ = validate_draft(draft)
    if errors:
        return None
    payload = {
        "name": draft["title"],
        "description": "\n\n".join(draft["instructions"]),
    }
    for source, target in (
        ("servings", "yields"),
        ("prep_time", "prep_time"),
        ("cook_time", "cook_time"),
    ):
        if draft[source] is not None:
            payload[target] = draft[source]
    return payload


def build_recipe_draft(text):
    local, parser_warnings = parse_ocr_text(text)
    draft, errors, warnings = validate_draft(local)
    return {
        "schema_version": 1,
        "source_text": text,
        "extraction_method": "local",
        "draft": draft,
        "validation": {"valid": not errors, "errors": errors},
        "warnings": warnings + parser_warnings,
        "recipe_payload": to_recipe_payload(draft),
        "requires_review": True,
    }

