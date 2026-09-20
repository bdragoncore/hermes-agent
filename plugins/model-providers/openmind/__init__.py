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
_FALLBACK_MODELS = (
    "zen-big-pickle",
    "zen-muse-spark-1.2-contributor-free",
    "zen-muse-spark-1.3-contributor-free",
    "zen-ling-3.0-flash-fin-free",
    "zen-mimo-v2.5-free",
    "zen-nemotron-3-ultra-free",
    "zen-nemotron-3.5-lightning-free",
    "kilo-openrouter/free",
    "kilo-kilo-auto/free",
    "openrouter-openrouter/free",
    "synthetic-syn:large:text",
    "synthetic-syn:small:text",
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