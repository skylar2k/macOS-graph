import logging
import os
from pathlib import Path
from typing import Final

import msal
from msal_extensions import (
    FilePersistence,
    PersistedTokenCache,
    build_encrypted_persistence,
)

from ..errors import GraphMacosError

log = logging.getLogger(__name__)

CACHE_PATH: Final[Path] = Path.home() / ".cache" / "graph_macos" / "token_cache.bin"
ALLOW_PLAINTEXT_ENV: Final = "GRAPH_MACOS_ALLOW_PLAINTEXT_CACHE"


class AuthError(GraphMacosError):
    pass


def _build_cache() -> PersistedTokenCache:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        persistence = build_encrypted_persistence(str(CACHE_PATH))
    except Exception as e:
        if not os.environ.get(ALLOW_PLAINTEXT_ENV):
            raise AuthError(
                f"encrypted token cache unavailable ({e}); "
                f"set {ALLOW_PLAINTEXT_ENV}=1 to store tokens in a plain file instead"
            ) from e
        log.warning("Encrypted cache unavailable, using plain text file (mode 0600)")
        persistence = FilePersistence(str(CACHE_PATH))
        CACHE_PATH.touch(mode=0o600, exist_ok=True)
    return PersistedTokenCache(persistence)


class GraphAuth:
    """Delegated, interactive sign-in with a persistent token cache.

    Configuration: GRAPH_MACOS_CLIENT_ID, GRAPH_MACOS_TENANT_ID and optionally
    GRAPH_MACOS_UPN (login hint).
    """

    def __init__(self, client_id: str | None = None, tenant_id: str | None = None):
        client_id = client_id or os.environ.get("GRAPH_MACOS_CLIENT_ID")
        tenant_id = tenant_id or os.environ.get("GRAPH_MACOS_TENANT_ID")
        if not client_id or not tenant_id:
            raise AuthError("set GRAPH_MACOS_CLIENT_ID and GRAPH_MACOS_TENANT_ID")
        self.app = msal.PublicClientApplication(
            client_id,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
            token_cache=_build_cache(),
        )

    def get_token(self, scopes: list[str], login_hint: str | None = None) -> str:
        login_hint = login_hint or os.environ.get("GRAPH_MACOS_UPN")
        result = None

        if accounts := self.app.get_accounts(username=login_hint):
            result = self.app.acquire_token_silent(scopes, account=accounts[0])

        if not result:
            result = self.app.acquire_token_interactive(scopes, login_hint=login_hint)

        if "access_token" not in result:
            raise AuthError(
                f"{result.get('error')}: {result.get('error_description')} "
                f"(correlation_id={result.get('correlation_id')})"
            )
        return result["access_token"]
