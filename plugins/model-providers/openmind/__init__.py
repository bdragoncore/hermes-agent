"""OpenMind provider profile — the OpenMind proxy on the tailnet.

OpenMind (bdragoncore/openmind) is an OpenAI-compatible Go proxy that routes
prompts through Tor to the OpenCode Zen API. It exposes ``/v1/chat/completions``
and ``/v1/models`` with no API key on the tailnet; the default endpoint is the
pibox magicdns host (``http://pibox:5000/v1``), overridable via
``OPENMIND_BASE_URL``.
"""

from providers import register_provider
from providers.base import ProviderProfile

# Curated free models served by the proxy. The live ``/v1/models`` catalog is the
# source of truth; this list is the picker fallback when the proxy is unreachable.
# ``zen-big-pickle`` leads so it is the silent default for the provider.
# Mirrors the proxy's canonical free catalogs (zen-free-models.json,
# kilo-free-models.json, openrouter-free-models.json) + the synthetic aliases.
_FALLBACK_MODELS = (
    "zen-big-pickle",
    # Zen free tier
    "zen-muse-spark-1.2-contributor-free",
    "zen-muse-spark-1.3-contributor-free",
    "zen-ling-3.0-flash-fin-free",
    "zen-mimo-v2.5-free",
    "zen-mimo-v2.6-flash-free",
    "zen-nemotron-3-ultra-free",
    "zen-nemotron-3.5-lightning-free",
    "zen-longcat-2.5-preview-free",
    "zen-space-bunny-free",
    # Kilo free (per-IP free pool)
    "kilo-kilo-auto/free",
    "kilo-openrouter/free",
    "kilo-nex-agi/nex-n2.5-pro:free",
    "kilo-z-ai/glm-5.2:free",
    "kilo-nvidia/nemotron-3-ultra-550b-a55b:free",
    "kilo-nvidia/nemotron-3-super-120b-a12b:free",
    # OpenRouter free (separate quota pool from kilo)
    "openrouter-openrouter/free",
    "openrouter-deepseek/deepseek-v4-flash-0731:free",
    "openrouter-qwen/qwen3.8-27b:free",
    "openrouter-z-ai/glm-5.2:free",
    # Synthetic (aliases auto-route to the current checkpoint)
    "synthetic-syn:large:text",
    "synthetic-syn:small:text",
    "synthetic-syn:large:vision",
    "synthetic-syn:small:vision",
)

openmind = ProviderProfile(
    name="openmind",
    aliases=("open-mind", "openmind-proxy"),
    display_name="OpenMind",
    description="OpenMind proxy on pibox (Tor → OpenCode Zen)",
    env_vars=("OPENMIND_BASE_URL",),
    base_url="http://pibox:5000/v1",
    default_aux_model="zen-ling-3.0-flash-fin-free",
    fallback_models=_FALLBACK_MODELS,
)

register_provider(openmind)