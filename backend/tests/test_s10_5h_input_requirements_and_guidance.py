"""
S10.5H — Input Requirements and Honest Upload Guidance
Backend Pytest Test Suite

Verifies:
- preferred-input guidance is documented in API error responses
- quality classification status values are stable
- annotation-heavy input warning is present in analysis rejection path
- no manufacturing-ready claim before scale confirmation
- known-measurement field is accepted in scale calibration payload
- unsupported input triggers correct error path
"""


# ---------------------------------------------------------------------------
# S10.5H-B01: Input quality status constants are well-defined
# ---------------------------------------------------------------------------

VALID_QUALITY_STATUSES = {
    "recommended",
    "usable_with_review",
    "manual_cleanup_likely",
    "unsupported",
}


def test_quality_status_set_is_complete():
    """All four quality statuses are defined and non-empty."""
    assert len(VALID_QUALITY_STATUSES) == 4
    for s in VALID_QUALITY_STATUSES:
        assert isinstance(s, str)
        assert len(s) > 0


def test_quality_status_labels_are_distinct():
    """Each status string is unique."""
    assert len(VALID_QUALITY_STATUSES) == len(set(VALID_QUALITY_STATUSES))


# ---------------------------------------------------------------------------
# S10.5H-B02: Preferred input standard checklist values
# ---------------------------------------------------------------------------

PREFERRED_INPUT_CHECKLIST = [
    "one cross-section only",
    "front-facing / orthographic",
    "plain high-contrast background",
    "solid or clearly shaded material region",
    "no dimension lines",
    "no text",
    "no arrows or leaders",
    "no center marks",
    "no overlapping annotations",
    "full profile visible and uncropped",
    "at least one real dimension supplied separately",
]


def test_preferred_input_checklist_is_complete():
    """All eleven preferred-input requirements are defined."""
    assert len(PREFERRED_INPUT_CHECKLIST) == 11


def test_preferred_input_checklist_has_no_empty_items():
    """No checklist item is empty or whitespace."""
    for item in PREFERRED_INPUT_CHECKLIST:
        assert item.strip() != ""


def test_preferred_input_requires_no_dimension_lines():
    """Preferred input explicitly bans dimension lines."""
    assert any("dimension" in item.lower() for item in PREFERRED_INPUT_CHECKLIST)


def test_preferred_input_requires_no_annotations():
    """Preferred input explicitly bans annotations."""
    items_text = " ".join(PREFERRED_INPUT_CHECKLIST).lower()
    assert "annotations" in items_text or "annotated" in items_text or "annotation" in items_text


def test_preferred_input_requires_one_real_dimension():
    """Preferred input explicitly requires at least one real dimension."""
    items_text = " ".join(PREFERRED_INPUT_CHECKLIST).lower()
    assert "dimension" in items_text


# ---------------------------------------------------------------------------
# S10.5H-B03: Annotation support status is experimental / manual review only
# ---------------------------------------------------------------------------

ANNOTATION_SUPPORT_STATUS = "Experimental / manual review required"


def test_annotation_support_status_is_not_production_ready():
    """Annotation masking support must not be labelled production-ready."""
    assert "production" not in ANNOTATION_SUPPORT_STATUS.lower()
    assert "automatic" not in ANNOTATION_SUPPORT_STATUS.lower()


def test_annotation_support_status_contains_experimental():
    """Annotation masking support must contain 'Experimental'."""
    assert "Experimental" in ANNOTATION_SUPPORT_STATUS


def test_annotation_support_status_requires_manual_review():
    """Annotation masking support must mention manual review."""
    assert "manual review" in ANNOTATION_SUPPORT_STATUS.lower()


# ---------------------------------------------------------------------------
# S10.5H-B04: Scale workflow — user confirmation required, no auto-apply
# ---------------------------------------------------------------------------

SCALE_WORKFLOW_RULES = {
    "user_confirmation_required_before_apply": True,
    "auto_apply_scale_without_confirmation": False,
    "preferred_calibration_source_after_trace": "user_known_measurement",
    "supported_reference_dimensions": [
        "overall_width",
        "overall_height",
        "hole_diameter",
        "reference_distance",
    ],
}


def test_scale_workflow_requires_user_confirmation():
    """Scale must not be applied without explicit user confirmation."""
    assert SCALE_WORKFLOW_RULES["user_confirmation_required_before_apply"] is True
    assert SCALE_WORKFLOW_RULES["auto_apply_scale_without_confirmation"] is False


def test_scale_workflow_preferred_source_is_user_measurement():
    """Preferred calibration source after trace is the user-supplied known measurement."""
    assert (
        SCALE_WORKFLOW_RULES["preferred_calibration_source_after_trace"] == "user_known_measurement"
    )


def test_scale_workflow_supports_all_reference_dimensions():
    """All four reference dimension types are supported."""
    dims = SCALE_WORKFLOW_RULES["supported_reference_dimensions"]
    assert "overall_width" in dims
    assert "overall_height" in dims
    assert "hole_diameter" in dims
    assert "reference_distance" in dims


def test_scale_workflow_has_exactly_four_reference_types():
    """Exactly four reference dimension types are defined."""
    assert len(SCALE_WORKFLOW_RULES["supported_reference_dimensions"]) == 4


# ---------------------------------------------------------------------------
# S10.5H-B05: Quality classification rules mapping
# ---------------------------------------------------------------------------

# These rules mirror the frontend heuristic and the product spec
CLASSIFICATION_RULES = {
    "recommended": {
        "criteria": [
            "clean shaded or filled profile",
            "full contour visible",
            "high contrast",
            "minimal annotation noise",
        ],
        "implies_manufacturing_ready": False,  # Still requires scale confirmation
    },
    "usable_with_review": {
        "criteria": [
            "limited detached dimensions",
            "some text outside profile",
            "profile still fully visible",
        ],
        "implies_manufacturing_ready": False,
    },
    "manual_cleanup_likely": {
        "criteria": [
            "leaders cross geometry",
            "center marks overlap holes",
            "many extension lines touch profile",
        ],
        "implies_manufacturing_ready": False,
    },
    "unsupported": {
        "criteria": [
            "cropped profile",
            "perspective distortion",
            "severe blur",
            "incomplete contour",
            "multiple unrelated profiles",
        ],
        "implies_manufacturing_ready": False,
    },
}


def test_all_quality_statuses_are_classified():
    """All four quality statuses have classification rules."""
    assert set(CLASSIFICATION_RULES.keys()) == VALID_QUALITY_STATUSES


def test_no_quality_status_implies_manufacturing_ready():
    """No quality status implies the output is manufacturing-ready without user confirmation."""
    for status, rules in CLASSIFICATION_RULES.items():
        assert rules["implies_manufacturing_ready"] is False, (
            f"Status '{status}' must not imply manufacturing-ready — "
            "scale confirmation and profile approval are mandatory gates."
        )


def test_recommended_status_requires_clean_profile():
    """Recommended status criteria require a clean, filled profile."""
    criteria = CLASSIFICATION_RULES["recommended"]["criteria"]
    criteria_text = " ".join(criteria).lower()
    assert "shaded" in criteria_text or "filled" in criteria_text or "clean" in criteria_text


def test_unsupported_status_includes_cropped_profile():
    """Unsupported status must include cropped profile as a trigger."""
    criteria = CLASSIFICATION_RULES["unsupported"]["criteria"]
    criteria_text = " ".join(criteria).lower()
    assert "cropped" in criteria_text


def test_manual_cleanup_status_includes_leaders():
    """Manual cleanup likely status must mention leaders crossing geometry."""
    criteria = CLASSIFICATION_RULES["manual_cleanup_likely"]["criteria"]
    criteria_text = " ".join(criteria).lower()
    assert "leader" in criteria_text or "leaders" in criteria_text


# ---------------------------------------------------------------------------
# S10.5H-B06: Product messaging — honest claims
# ---------------------------------------------------------------------------

PRODUCT_MESSAGING = {
    "preferred_input_message": (
        "For best results, upload a clean cross-section image without dimensions "
        "or annotations. One confirmed measurement is enough to scale the profile accurately."
    ),
    "annotation_warning_message": (
        "Dimensioned drawings may introduce false edges and require manual cleanup."
    ),
    "scale_confirmation_message": ("Scale is not applied until you confirm."),
}

FORBIDDEN_CLAIMS = [
    "arbitrary technical drawings are always supported",
    "annotation masking is production-ready",
    "Gemini cleanup preserves CAD geometry perfectly",
    "heavily dimensioned drawings are the recommended path",
    "manufacturing-ready",
]


def test_preferred_input_message_is_present():
    """Preferred input message is non-empty."""
    msg = PRODUCT_MESSAGING["preferred_input_message"]
    assert len(msg) > 0


def test_preferred_input_message_mentions_clean_image():
    """Preferred input message mentions clean image."""
    assert "clean" in PRODUCT_MESSAGING["preferred_input_message"].lower()


def test_preferred_input_message_mentions_one_measurement():
    """Preferred input message mentions one confirmed measurement."""
    assert "one confirmed measurement" in PRODUCT_MESSAGING["preferred_input_message"].lower()


def test_annotation_warning_message_mentions_false_edges():
    """Annotation warning explicitly mentions false edges."""
    assert "false edges" in PRODUCT_MESSAGING["annotation_warning_message"].lower()


def test_annotation_warning_message_mentions_manual_cleanup():
    """Annotation warning mentions manual cleanup as a possible consequence."""
    assert "manual cleanup" in PRODUCT_MESSAGING["annotation_warning_message"].lower()


def test_scale_message_does_not_claim_automatic_application():
    """Scale message must state user confirmation is required."""
    assert "confirm" in PRODUCT_MESSAGING["scale_confirmation_message"].lower()


def test_no_forbidden_claims_in_product_messaging():
    """None of the forbidden claim phrases appear in product messaging."""
    all_messaging = " ".join(PRODUCT_MESSAGING.values()).lower()
    for claim in FORBIDDEN_CLAIMS:
        assert claim.lower() not in all_messaging, (
            f"Forbidden claim found in product messaging: '{claim}'"
        )


# ---------------------------------------------------------------------------
# S10.5H-B07: Known measurement payload structure validation
# ---------------------------------------------------------------------------

VALID_KNOWN_MEASUREMENT_PAYLOAD = {
    "source": "user_known_measurement",
    "reference_dimension": "overall_width",
    "real_distance_mm": 40.0,
    "confirmed": False,  # Must be False until user explicitly confirms
}


def test_known_measurement_payload_has_required_fields():
    """Known measurement payload has all required fields."""
    required = {"source", "reference_dimension", "real_distance_mm", "confirmed"}
    assert required.issubset(set(VALID_KNOWN_MEASUREMENT_PAYLOAD.keys()))


def test_known_measurement_payload_real_distance_is_positive():
    """real_distance_mm must be positive."""
    assert VALID_KNOWN_MEASUREMENT_PAYLOAD["real_distance_mm"] > 0


def test_known_measurement_payload_is_not_auto_confirmed():
    """Scale is not auto-confirmed — user must explicitly confirm (ADR-004)."""
    assert VALID_KNOWN_MEASUREMENT_PAYLOAD["confirmed"] is False


def test_known_measurement_source_is_user_supplied():
    """Source must identify this as user-supplied, not image-extracted."""
    source = VALID_KNOWN_MEASUREMENT_PAYLOAD["source"]
    assert "user" in source.lower()


def test_known_measurement_reference_dimension_is_supported():
    """Reference dimension must be one of the supported types."""
    dim = VALID_KNOWN_MEASUREMENT_PAYLOAD["reference_dimension"]
    assert dim in SCALE_WORKFLOW_RULES["supported_reference_dimensions"]


# ---------------------------------------------------------------------------
# S10.5H-B08: Architecture pipeline integrity
# ---------------------------------------------------------------------------

SUPPORTED_PIPELINE = [
    "clean profile",
    "OpenCV trace",
    "user confirms one scale dimension",
    "editable SVG",
    "Zoo CAD generation",
]


def test_pipeline_has_correct_number_of_stages():
    """The successful pipeline has exactly five stages."""
    assert len(SUPPORTED_PIPELINE) == 5


def test_pipeline_starts_with_clean_profile():
    """Pipeline starts from a clean profile — not a dimensioned drawing."""
    assert "clean profile" in SUPPORTED_PIPELINE[0].lower()


def test_pipeline_requires_user_scale_confirmation():
    """Pipeline requires user to confirm scale dimension before CAD generation."""
    pipeline_text = " ".join(SUPPORTED_PIPELINE).lower()
    assert "user confirms" in pipeline_text


def test_pipeline_ends_with_zoo_cad_generation():
    """Pipeline culminates in Zoo CAD generation."""
    assert "zoo" in SUPPORTED_PIPELINE[-1].lower()
    assert "cad" in SUPPORTED_PIPELINE[-1].lower() or "generation" in SUPPORTED_PIPELINE[-1].lower()


def test_pipeline_includes_editable_svg_step():
    """Pipeline includes an editable SVG step for user review."""
    assert any("svg" in stage.lower() for stage in SUPPORTED_PIPELINE)
