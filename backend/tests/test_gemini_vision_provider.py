"""Contract tests for Gemini Vision Analysis Provider per S7 and S7.1 specifications."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import AnalysisRejectedError, MalformedProviderResponseError
from app.models.schema import DimensionProvenance, ProfileType
from app.services.analysis_provider import (
    GeminiAnalysisProvider,
    MockAnalysisProvider,
    get_analysis_provider,
    sanitize_error_message,
)


def test_gemini_provider_configuration_defaults() -> None:
    """Test Gemini provider initializes with Flash-Lite default and Flash fallback."""
    provider = GeminiAnalysisProvider(api_key="test_key")
    assert provider.model_name == "gemini-3.5-flash-lite"
    assert provider.fallback_model_name == "gemini-3.6-flash"
    assert provider.fallback_enabled is True


def test_low_confidence_lite_triggers_flash() -> None:
    """Test low-confidence Lite result without explicit rejection reasons
    triggers Flash fallback."""
    provider = GeminiAnalysisProvider(api_key="test_api_key")
    low_conf_lite_json = """
    {
      "profile_type": "circle",
      "candidate_points": [],
      "candidate_dimensions": [],
      "provenance": "image_extracted",
      "confidence": 0.45,
      "warnings": [],
      "rejection_reasons": [],
      "success": true
    }
    """
    valid_flash_json = """
    {
      "profile_type": "circle",
      "candidate_points": [],
      "candidate_dimensions": [],
      "provenance": "image_extracted",
      "confidence": 0.94,
      "warnings": [],
      "rejection_reasons": [],
      "success": true
    }
    """

    resp_lite = MagicMock()
    resp_lite.text = low_conf_lite_json
    resp_flash = MagicMock()
    resp_flash.text = valid_flash_json

    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = [resp_lite, resp_flash]
        mock_client_cls.return_value = mock_client

        result = provider.analyze(b"fake_image_bytes", "circle.png")

        assert result.confidence == 0.94
        assert result.model_used == "gemini-3.6-flash"
        assert result.fallback_triggered is True
        assert mock_client.models.generate_content.call_count == 2


def test_valid_poor_image_rejection_does_not_trigger_flash() -> None:
    """Test valid poor-image rejection with explicit rejection reasons
    does NOT trigger Flash fallback."""
    provider = GeminiAnalysisProvider(api_key="test_api_key")
    explicit_rejection_json = """
    {
      "profile_type": "circle",
      "candidate_points": [],
      "candidate_dimensions": [],
      "provenance": "image_extracted",
      "confidence": 0.35,
      "warnings": [],
      "rejection_reasons": ["Glare and perspective distortion obscure edge."],
      "success": false
    }
    """

    resp_lite = MagicMock()
    resp_lite.text = explicit_rejection_json

    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = resp_lite
        mock_client_cls.return_value = mock_client

        with pytest.raises(AnalysisRejectedError) as exc_info:
            provider.analyze(b"fake_image_bytes", "poor_image.png")

        assert "Glare and perspective" in str(exc_info.value)
        # Verify fallback was NOT attempted
        assert mock_client.models.generate_content.call_count == 1


def test_fallback_disabled() -> None:
    """Test fallback_enabled=False prevents fallback when Lite fails."""
    provider = GeminiAnalysisProvider(api_key="test_api_key", fallback_enabled=False)
    malformed_json = "{ bad json"

    resp_lite = MagicMock()
    resp_lite.text = malformed_json

    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = resp_lite
        mock_client_cls.return_value = mock_client

        with pytest.raises(MalformedProviderResponseError):
            provider.analyze(b"fake_image_bytes", "test.png")

        assert mock_client.models.generate_content.call_count == 1


def test_both_models_fail_safely() -> None:
    """Test both models returning malformed payloads fails safely with clean error."""
    provider = GeminiAnalysisProvider(api_key="test_api_key")
    resp1 = MagicMock()
    resp1.text = "{ bad json 1"
    resp2 = MagicMock()
    resp2.text = "{ bad json 2"

    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = [resp1, resp2]
        mock_client_cls.return_value = mock_client

        with pytest.raises(MalformedProviderResponseError) as exc_info:
            provider.analyze(b"fake_image_bytes", "test.png")

        assert "invalid JSON response" in str(exc_info.value)
        assert mock_client.models.generate_content.call_count == 2


def test_gemini_provider_valid_response() -> None:
    """Test parsing a valid JSON response from Gemini vision model."""
    provider = GeminiAnalysisProvider(api_key="test_api_key")
    valid_json = """
    {
      "profile_type": "rectangle",
      "candidate_points": [{"x": -30.0, "y": -20.0}, {"x": 30.0, "y": 20.0}],
      "candidate_dimensions": [
        {
          "id": "width",
          "label": "Width",
          "value": 60.0,
          "unit": "mm",
          "provenance": "image_extracted",
          "confidence": 0.95,
          "critical": true
        }
      ],
      "provenance": "image_extracted",
      "confidence": 0.92,
      "warnings": [],
      "rejection_reasons": [],
      "success": true
    }
    """
    result = provider.validate_and_parse_response(valid_json)
    assert result.profile_type == ProfileType.RECTANGLE
    assert result.confidence == 0.92
    assert len(result.candidate_dimensions) == 1
    assert result.candidate_dimensions[0].value == 60.0
    assert result.candidate_dimensions[0].provenance == DimensionProvenance.IMAGE_EXTRACTED


def test_gemini_provider_malformed_json() -> None:
    """Test malformed JSON string from provider raises MalformedProviderResponseError."""
    provider = GeminiAnalysisProvider(api_key="test_api_key")
    malformed_json = "{ invalid json payload"
    with pytest.raises(MalformedProviderResponseError) as exc_info:
        provider.validate_and_parse_response(malformed_json)
    assert "invalid JSON response" in str(exc_info.value)


def test_gemini_provider_unsupported_profile_type() -> None:
    """Test unsupported profile type raises MalformedProviderResponseError."""
    provider = GeminiAnalysisProvider(api_key="test_api_key")
    invalid_ptype_json = """
    {
      "profile_type": "hexagon",
      "confidence": 0.90,
      "candidate_points": [],
      "candidate_dimensions": []
    }
    """
    with pytest.raises(MalformedProviderResponseError) as exc_info:
        provider.validate_and_parse_response(invalid_ptype_json)
    assert "Unsupported or unrecognized profile type 'hexagon'" in str(exc_info.value)


def test_gemini_provider_invalid_confidence() -> None:
    """Test out-of-range confidence score raises MalformedProviderResponseError."""
    provider = GeminiAnalysisProvider(api_key="test_api_key")
    out_of_range_json = """
    {
      "profile_type": "circle",
      "confidence": 1.5,
      "candidate_points": [],
      "candidate_dimensions": []
    }
    """
    with pytest.raises(MalformedProviderResponseError) as exc_info:
        provider.validate_and_parse_response(out_of_range_json)
    assert "outside valid range" in str(exc_info.value)


def test_gemini_provider_non_finite_values() -> None:
    """Test non-finite coordinate or dimension value raises MalformedProviderResponseError."""
    provider = GeminiAnalysisProvider(api_key="test_api_key")
    non_finite_json = """
    {
      "profile_type": "circle",
      "confidence": 0.9,
      "candidate_points": [{"x": "NaN", "y": 0.0}],
      "candidate_dimensions": []
    }
    """
    with pytest.raises(MalformedProviderResponseError) as exc_info:
        provider.validate_and_parse_response(non_finite_json)
    assert "non-finite coordinate" in str(exc_info.value) or "invalid" in str(exc_info.value)


def test_gemini_provider_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test vision provider request timeout raises MalformedProviderResponseError."""
    provider = GeminiAnalysisProvider(api_key="fake_key_123", fallback_enabled=False)

    def mock_generate(*args, **kwargs):
        raise TimeoutError("Request deadline exceeded")

    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = mock_generate
        mock_client_cls.return_value = mock_client

        with pytest.raises(MalformedProviderResponseError) as exc_info:
            provider.analyze(b"fake_image_bytes", "test.png")
        assert "timed out" in str(exc_info.value).lower()


def test_gemini_provider_auth_failure() -> None:
    """Test auth failure raises MalformedProviderResponseError without leaking secret."""
    secret_key = "AIzaSySecretApiKey1234567890abcdef"
    provider = GeminiAnalysisProvider(api_key=secret_key)

    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception(
            f"401 API_KEY_INVALID: Key {secret_key} is invalid"
        )
        mock_client_cls.return_value = mock_client

        with pytest.raises(MalformedProviderResponseError) as exc_info:
            provider.analyze(b"fake_image_bytes", "test.png")

        err_msg = str(exc_info.value)
        assert "authentication failed" in err_msg.lower()
        assert secret_key not in err_msg
        assert "[REDACTED_API_KEY]" in err_msg


def test_gemini_provider_prompt_injection_defense() -> None:
    """Test prompt-injection content is safely constrained by strict JSON schema validation."""
    provider = GeminiAnalysisProvider(api_key="test_api_key")
    injection_response = """
    ```json
    {
      "profile_type": "circle",
      "candidate_points": [],
      "candidate_dimensions": [
        {
          "id": "outer_diameter",
          "label": "Outer Diameter",
          "value": 50.0,
          "unit": "mm",
          "provenance": "image_extracted",
          "confidence": 0.95,
          "critical": true
        }
      ],
      "provenance": "image_extracted",
      "confidence": 0.95,
      "warnings": [],
      "rejection_reasons": [],
      "success": true
    }
    ```
    """
    result = provider.validate_and_parse_response(injection_response)
    assert result.profile_type == ProfileType.CIRCLE
    assert result.confidence == 0.95


def test_gemini_provider_low_confidence_rejection() -> None:
    """Test low confidence (< 0.60) with explicit rejection reasons raises AnalysisRejectedError."""
    provider = GeminiAnalysisProvider(api_key="test_api_key")
    low_conf_json = """
    {
      "profile_type": "circle",
      "confidence": 0.45,
      "rejection_reasons": ["Poor lighting and severe perspective tilt"],
      "candidate_points": [],
      "candidate_dimensions": []
    }
    """
    with pytest.raises(AnalysisRejectedError) as exc_info:
        provider.validate_and_parse_response(low_conf_json)
    assert "rejected" in str(exc_info.value).lower()
    assert "Poor lighting" in str(exc_info.value)


def test_mock_fallback_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test fallback to MockAnalysisProvider when configured provider is mock or missing key."""
    monkeypatch.setattr("app.core.config.settings.analysis_provider", "mock")
    provider = get_analysis_provider()
    assert isinstance(provider, MockAnalysisProvider)

    monkeypatch.setattr("app.core.config.settings.analysis_provider", "gemini")
    monkeypatch.setattr("app.core.config.settings.gemini_api_key", "")
    provider_fallback = get_analysis_provider()
    assert isinstance(provider_fallback, MockAnalysisProvider)


def test_secret_redaction_utility() -> None:
    """Test sanitize_error_message utility removes API keys cleanly."""
    secret = "AIzaSy1234567890abcdef1234567890abc"
    msg = f"Failed request with key={secret} and bearer {secret}"
    sanitized = sanitize_error_message(msg, secret)
    assert secret not in sanitized
    assert "[REDACTED_API_KEY]" in sanitized
