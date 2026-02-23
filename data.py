"""
data.py — GuildDB
JSON-based guild data persistence.

Design goals:
  • One JSON file per guild  →  data/guilds/{guild_id}.json
  • Per-guild asyncio.Lock   →  concurrent events for different guilds
                                never block each other; same-guild events
                                are serialised safely.
  • Merge-on-load            →  new schema keys are back-filled automatically
                                so you never get a KeyError after adding a
                                new feature.
  • Accessed via bot.db      →  cogs get it from ctx.bot.db, no global state.
"""

import asyncio
import json
import os
from typing import Any

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "guilds")
os.makedirs(DATA_DIR, exist_ok=True)


def _default_guild() -> dict:
    """
    Canonical schema for a fresh guild.
    Add new top-level keys here; they'll be back-filled on next load
    for guilds that were created before the key existed.
    """
    return {
        "warnings": {},       # { "user_id": ["reason", ...] }
        "welcome": {
            "channel_id": None,
            "message": "Welcome {user} to **{server}**! You are member #{count}.",
            "embed": False,
        },
        "auto_role": {
            "member": None,   # role_id  (int | None)
            "bot": None,      # role_id  (int | None)
        },
        "muted_role": None,   # role_id  (int | None)
        "image_muted": {},    # { "user_id": True }
        "logs": {
            "mod":     None,  # moderation events
            "message": None,  # message edits/deletes
            "member":  None,  # join/leave
            "server":  None,  # role/channel changes
            "voice":   None,  # voice activity
        },
    }


class GuildDB:
    """
    Async JSON database, one document per guild.

    Usage (inside a cog):
        data = await ctx.bot.db.load(ctx.guild.id)
        data["warnings"].setdefault(str(member.id), []).append(reason)
        await ctx.bot.db.save(ctx.guild.id, data)

    Or use the convenience helpers:
        value = await ctx.bot.db.get(guild_id, "muted_role")
        await ctx.bot.db.set(guild_id, ["auto_role", "member"], role.id)
    """

    def __init__(self) -> None:
        # Per-guild locks: only one coroutine touches a guild file at a time.
        # Different guilds never block each other.
        self._locks: dict[int, asyncio.Lock] = {}

    def _lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self._locks:
            self._locks[guild_id] = asyncio.Lock()
        return self._locks[guild_id]

    def _path(self, guild_id: int) -> str:
        return os.path.join(DATA_DIR, f"{guild_id}.json")

    # ── Core I/O ───────────────────────────────────────────────────────────

    async def load(self, guild_id: int) -> dict:
        """Return the guild document, back-filling any missing default keys."""
        async with self._lock(guild_id):
            path = self._path(guild_id)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as fh:
                    stored = json.load(fh)
            else:
                stored = {}

            # Merge defaults — shallow for top-level keys only.
            # We do NOT deep-merge so user data inside dicts is never clobbered.
            defaults = _default_guild()
            for key, default_val in defaults.items():
                if key not in stored:
                    stored[key] = default_val

            return stored

    async def save(self, guild_id: int, data: dict) -> None:
        """Persist the guild document."""
        async with self._lock(guild_id):
            with open(self._path(guild_id), "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)

    # ── Convenience helpers ────────────────────────────────────────────────

    async def get(self, guild_id: int, *keys: str, default: Any = None) -> Any:
        """
        Read a nested value by key path without having to load + index manually.
            val = await bot.db.get(guild_id, "auto_role", "member")
        """
        data = await self.load(guild_id)
        obj = data
        for key in keys:
            if not isinstance(obj, dict) or key not in obj:
                return default
            obj = obj[key]
        return obj

    async def set(self, guild_id: int, keys: list[str], value: Any) -> None:
        """
        Write a nested value by key path without touching unrelated keys.
            await bot.db.set(guild_id, ["auto_role", "member"], role.id)
        """
        data = await self.load(guild_id)
        obj = data
        for key in keys[:-1]:
            obj = obj.setdefault(key, {})
        obj[keys[-1]] = value
        await self.save(guild_id, data)

    async def delete_guild(self, guild_id: int) -> None:
        """Remove a guild's data file entirely (e.g. on guild leave)."""
        async with self._lock(guild_id):
            path = self._path(guild_id)
            if os.path.exists(path):
                os.remove(path)