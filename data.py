import asyncio
import logging
import os
from typing import Any

import httpx

log = logging.getLogger("corebot")


def _sb_headers(prefer: str = "return=representation") -> dict:
    key = os.environ.get("SUPABASE_KEY", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def _sb_url(path: str = "") -> str:
    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    return f"{base}/rest/v1/{path}"


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

    def _lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self._locks:
            self._locks[guild_id] = asyncio.Lock()
        return self._locks[guild_id]

    async def close(self) -> None:
        pass  # No persistent client to close

    # ── Core I/O ───────────────────────────────────────────────────────────

    async def load(self, guild_id: int) -> dict:
        async with self._lock(guild_id):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    r = await client.get(
                        _sb_url("guild_data"),
                        params={"guild_id": f"eq.{guild_id}", "select": "data"},
                        headers=_sb_headers(),
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
                async with httpx.AsyncClient(timeout=10.0) as client:
                    r = await client.post(
                        _sb_url("guild_data"),
                        json={
                            "guild_id": guild_id,
                            "data": data,
                            "updated_at": "now()",
                        },
                        headers=_sb_headers("resolution=merge-duplicates,return=minimal"),
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
                async with httpx.AsyncClient(timeout=10.0) as client:
                    r = await client.delete(
                        _sb_url("guild_data"),
                        params={"guild_id": f"eq.{guild_id}"},
                        headers=_sb_headers(),
                    )
                    r.raise_for_status()
            except Exception as e:
                log.error(f"Supabase delete failed for guild {guild_id}: {e}")