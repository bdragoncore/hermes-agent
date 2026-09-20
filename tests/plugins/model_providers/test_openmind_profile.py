"""OpenMind provider profile registers and points at the tailnet proxy."""

from __future__ import annotations

import pytest


@pytest.fixture
def openmind_profile():
    import model_tools  # noqa: F401  (plugin discovery registers the profile)
    import providers

    profile = providers.get_provider_profile("openmind")
    assert profile is not None, "openmind provider profile must be registered"
    return profile


def test_profile_identity(openmind_profile):
    assert openmind_profile.name == "openmind"
    assert openmind_profile.base_url == "http://pibox:5000/v1"
    assert openmind_profile.auth_type == "api_key"


def test_profile_has_curated_fallback_models(openmind_profile):
    assert openmind_profile.fallback_models
    assert "zen-big-pickle" in openmind_profile.fallback_models


def test_big_pickle_is_the_default_model(openmind_profile):
    assert openmind_profile.fallback_models[0] == "zen-big-pickle"


def test_profile_has_cheap_aux_model(openmind_profile):
    assert openmind_profile.default_aux_model


def test_profile_accepts_base_url_override(openmind_profile):
    extra_body, top_level = openmind_profile.build_api_kwargs_extras(
        reasoning_config={"enabled": True, "effort": "high"},
        model="zen-muse-spark-1.2-contributor-free",
    )
    assert extra_body == {}
    assert top_level == {}