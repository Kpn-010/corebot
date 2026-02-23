import asyncio
import logging
import os
from typing import Any

import httpx

log = logging.getLogger("corebot")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def _default_guild() -> dict:
    return {
        "warnings": {},
        "welcome": {
            "channel_id": None,
            "message": "Welcome {user} to **{server}**! You are member #{count}.",
            "embed": False,
        },
        "auto_role": {
            "member": None,
            "bot": None,
        },
        "muted_role": None,
        "image_muted": {},
        "logs": {
            "mod":     None,
            "message": None,
            "member":  None,
            "server":  None,
            "voice":   None,
        },
        "reaction_roles": {},
    }


class GuildDB:
    """
    Async Supabase-backed guild data store.
    Same interface as the old JSON version — no cog changes needed.

    Table: public.guild_data
        guild_id   bigint  primary key
        data       jsonb
        updated_at timestamptz default now()
    """

    def __init__(self) -> None:
        self._locks: dict[int, asyncio.Lock] = {}
        self._client: httpx.AsyncClient | None = None

    def _lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self._locks:
            self._locks[guild_id] = asyncio.Lock()
        return self._locks[guild_id]

    @property
    def _http(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=f"{SUPABASE_URL}/rest/v1",
                headers=_HEADERS,
                timeout=10.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Core I/O ───────────────────────────────────────────────────────────

    async def load(self, guild_id: int) -> dict:
        async with self._lock(guild_id):
            try:
                r = await self._http.get(
                    "/guild_data",
                    params={"guild_id": f"eq.{guild_id}", "select": "data"},
                )
                r.raise_for_status()
                rows = r.json()
                stored = rows[0]["data"] if rows else {}
            except Exception as e:
                log.error(f"Supabase load failed for guild {guild_id}: {e}")
                stored = {}

            defaults = _default_guild()
            for key, val in defaults.items():
                if key not in stored:
                    stored[key] = val

            return stored

    async def save(self, guild_id: int, data: dict) -> None:
        async with self._lock(guild_id):
            try:
                r = await self._http.post(
                    "/guild_data",
                    json={
                        "guild_id": guild_id,
                        "data": data,
                        "updated_at": "now()",
                    },
                    headers={
                        **_HEADERS,
                        "Prefer": "resolution=merge-duplicates,return=minimal",
                    },
                )
                r.raise_for_status()
            except Exception as e:
                log.error(f"Supabase save failed for guild {guild_id}: {e}")

    # ── Convenience helpers ────────────────────────────────────────────────

    async def get(self, guild_id: int, *keys: str, default: Any = None) -> Any:
        data = await self.load(guild_id)
        obj = data
        for key in keys:
            if not isinstance(obj, dict) or key not in obj:
                return default
            obj = obj[key]
        return obj

    async def set(self, guild_id: int, keys: list[str], value: Any) -> None:
        data = await self.load(guild_id)
        obj = data
        for key in keys[:-1]:
            obj = obj.setdefault(key, {})
        obj[keys[-1]] = value
        await self.save(guild_id, data)

    async def delete_guild(self, guild_id: int) -> None:
        async with self._lock(guild_id):
            try:
                r = await self._http.delete(
                    "/guild_data",
                    params={"guild_id": f"eq.{guild_id}"},
                )
                r.raise_for_status()
            except Exception as e:
                log.error(f"Supabase delete failed for guild {guild_id}: {e}")