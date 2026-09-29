"""
TramaMind — configurazione runtime (Pydantic Settings).

Ruoli nodo: standalone (default) | hub (Oracle) | edge (PC).
Variabili: TRAMAMIND_NODE_ROLE, TRAMAMIND_HUB_URL, TRAMAMIND_EDGE_TOKEN.

Le API key dei provider NON passano da qui in chiaro: get_api_key() risolve
a cascata keyring → age → .env → variabile ambiente (router/keystore.py).
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

from router import keystore


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRAMAMIND_")

    node_role: Literal["standalone", "hub", "edge"] = "standalone"
    hub_url: Optional[str] = None        # es. http://100.x.y.z:20128 (IP Tailscale hub)
    edge_token: Optional[str] = None     # token edge → hub (meglio via keystore: provider "edge")

    @property
    def is_hub(self) -> bool:
        return self.node_role == "hub"

    @property
    def is_edge(self) -> bool:
        return self.node_role == "edge"

    def get_api_key(self, provider: str) -> str | None:
        """Cascata: keyring → age → .env plain → variabile ambiente."""
        key, _storage = keystore.get_key(provider)
        return key

    def get_edge_token(self) -> str | None:
        """Il token edge segue la stessa cascata delle API key."""
        if self.edge_token:
            return self.edge_token
        key, _ = keystore.get_key("edge")
        return key


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
