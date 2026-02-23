import asyncio
import logging
import os
import sys

import httpx

import discord
from discord.ext import commands

log = logging.getLogger("corebot")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

_SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

STATUS_TYPES = {
    "watching":  discord.ActivityType.watching,
    "playing":   discord.ActivityType.playing,
    "listening": discord.ActivityType.listening,
    "competing": discord.ActivityType.competing,
}


def _load_env_owner_ids() -> set[int]:
    ids: set[int] = set()
    raw = os.environ.get("OWNER_IDS", "")
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


# Env-based owners loaded at startup — Supabase owners loaded async in setup()
OWNER_IDS: set[int] = _load_env_owner_ids()


async def _fetch_owner_ids() -> set[int]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{SUPABASE_URL}/rest/v1/owner_ids",
                params={"select": "user_id"},
                headers=_SB_HEADERS,
            )
            r.raise_for_status()
            return {row["user_id"] for row in r.json()}
    except Exception as e:
        log.error(f"Failed to fetch owner IDs from Supabase: {e}")
        return set()


async def _add_owner_db(user_id: int, added_by: int) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(
            f"{SUPABASE_URL}/rest/v1/owner_ids",
            json={"user_id": user_id, "added_by": added_by},
            headers={**_SB_HEADERS, "Prefer": "resolution=ignore-duplicates,return=minimal"},
        )
        r.raise_for_status()


async def _remove_owner_db(user_id: int) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.delete(
            f"{SUPABASE_URL}/rest/v1/owner_ids",
            params={"user_id": f"eq.{user_id}"},
            headers=_SB_HEADERS,
        )
        r.raise_for_status()


def is_owner():
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.author.id in OWNER_IDS or await ctx.bot.is_owner(ctx.author):
            return True
        await ctx.send("✕ Owner only.")
        return False
    return commands.check(predicate)


def _resolve_ext(name: str) -> str:
    name = name.strip()
    if not name.startswith("cogs."):
        name = f"cogs.{name}"
    return name


OWNER_PAGES = [
    {
        "title": "Reload",
        "description": "Reload one or all cogs.",
        "syntax": "cc reload [cogs.name]",
        "example": "cc reload cogs.mod",
        "aliases": "None",
    },
    {
        "title": "Load",
        "description": "Load a new extension without restarting.",
        "syntax": "cc load <cogs.name>",
        "example": "cc load cogs.newcog",
        "aliases": "None",
    },
    {
        "title": "Unload",
        "description": "Unload an extension. The owner cog cannot be unloaded.",
        "syntax": "cc unload <cogs.name>",
        "example": "cc unload cogs.mod",
        "aliases": "None",
    },
    {
        "title": "Extensions",
        "description": "List all currently loaded extensions.",
        "syntax": "cc extensions",
        "example": "cc extensions",
        "aliases": "exts",
    },
    {
        "title": "Status",
        "description": "Change the bot's activity text.\nTypes: `watching` `playing` `listening` `competing`",
        "syntax": "cc status <type> <text>",
        "example": "cc status watching the servers",
        "aliases": "None",
    },
    {
        "title": "Presence",
        "description": "Change the bot's online status dot.",
        "syntax": "cc setonline | cc setidle | cc setdnd | cc setinvisible",
        "example": "cc setidle",
        "aliases": "None",
    },
    {
        "title": "Restart",
        "description": "Cleanly close the bot. Render restarts the process automatically.",
        "syntax": "cc restart",
        "example": "cc restart",
        "aliases": "None",
    },
    {
        "title": "Shutdown",
        "description": "Close the bot. Same as restart on Render unless you stop the service.",
        "syntax": "cc shutdown",
        "example": "cc shutdown",
        "aliases": "None",
    },
    {
        "title": "Add Owner",
        "description": "Grant a user owner access. Persisted to file — survives restarts.",
        "syntax": "cc addowner <@user|ID>",
        "example": "cc addowner @friend",
        "aliases": "None",
    },
    {
        "title": "Remove Owner",
        "description": "Revoke a user's owner access. Cannot remove the last owner.",
        "syntax": "cc removeowner <@user|ID>",
        "example": "cc removeowner @friend",
        "aliases": "None",
    },
    {
        "title": "Owners",
        "description": "List all current owners (env var + file-persisted).",
        "syntax": "cc owners",
        "example": "cc owners",
        "aliases": "None",
    },
    {
        "title": "Bot Stats",
        "description": "Show internal stats: guilds, users, latency, extensions, versions.",
        "syntax": "cc botstats",
        "example": "cc botstats",
        "aliases": "None",
    },
]


def _make_owner_embed(
    bot: commands.Bot,
    page: int,
    invoker: discord.User | discord.Member,
) -> discord.Embed:
    cmd = OWNER_PAGES[page]
    embed = discord.Embed(
        title=f"Group: Owner ‣ Module {page + 1}",
        description=(
            f"> {cmd['description']}\n"
            f"```\n"
            f"Syntax:  {cmd['syntax']}\n"
            f"Example: {cmd['example']}\n"
            f"```\n"
            f"**Permissions:**\nOwner only"
        ),
        color=discord.Color.blurple(),
    )
    embed.set_author(
        name="Corebot Help",
        icon_url=bot.user.display_avatar.url if bot.user else None,
    )
    embed.set_footer(
        text=f"Aliases: {cmd['aliases']}  ⌁  Page {page + 1} of {len(OWNER_PAGES)}",
        icon_url=invoker.display_avatar.url,
    )
    return embed


class OwnerHelpView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        invoker: discord.User | discord.Member,
        page: int = 0,
    ):
        super().__init__(timeout=120)
        self.bot = bot
        self.invoker = invoker
        self.page = page
        self._sync()

    def _sync(self):
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page == len(OWNER_PAGES) - 1

    async def _edit(self, interaction: discord.Interaction):
        self._sync()
        await interaction.response.edit_message(
            embed=_make_owner_embed(self.bot, self.page, self.invoker),
            view=self,
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.invoker.id:
            await interaction.response.send_message(
                "✕ This menu belongs to someone else.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except Exception:
            pass

    @discord.ui.button(label="←", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        await self._edit(interaction)

    @discord.ui.button(label="✕", style=discord.ButtonStyle.danger)
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

    @discord.ui.button(label="→", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        await self._edit(interaction)


class Owner(commands.Cog, name="Owner"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self) -> None:
        db_ids = await _fetch_owner_ids()
        OWNER_IDS.update(db_ids)
        log.info(f"Loaded {len(db_ids)} owner(s) from Supabase.")

    @commands.command(name="reload")
    @is_owner()
    async def reload(self, ctx: commands.Context, *, ext: str = None):
        if ext:
            ext = _resolve_ext(ext)
            try:
                await self.bot.reload_extension(ext)
                await ctx.send(f"↻ Reloaded `{ext}`")
                log.info(f"Reloaded extension: {ext}")
            except commands.ExtensionNotLoaded:
                await ctx.send(f"✕ `{ext}` is not loaded.")
            except commands.ExtensionNotFound:
                await ctx.send(f"✕ `{ext}` not found.")
            except Exception as e:
                await ctx.send(f"✕ Failed: `{e}`")
                log.error(f"Reload failed [{ext}]: {e}", exc_info=e)
        else:
            results = []
            for extension in list(self.bot.extensions):
                try:
                    await self.bot.reload_extension(extension)
                    results.append(f"✓ `{extension}`")
                except Exception as e:
                    results.append(f"✕ `{extension}` — {e}")
                    log.error(f"Reload failed [{extension}]: {e}", exc_info=e)
            await ctx.send("↻ **Reload all:**\n" + "\n".join(results))

    @commands.command(name="load")
    @is_owner()
    async def load(self, ctx: commands.Context, *, ext: str):
        ext = _resolve_ext(ext)
        try:
            await self.bot.load_extension(ext)
            await ctx.send(f"✓ Loaded `{ext}`")
            log.info(f"Loaded extension: {ext}")
        except commands.ExtensionAlreadyLoaded:
            await ctx.send(f"✕ `{ext}` is already loaded.")
        except commands.ExtensionNotFound:
            await ctx.send(f"✕ `{ext}` not found.")
        except Exception as e:
            await ctx.send(f"✕ Failed: `{e}`")
            log.error(f"Load failed [{ext}]: {e}", exc_info=e)

    @commands.command(name="unload")
    @is_owner()
    async def unload(self, ctx: commands.Context, *, ext: str):
        ext = _resolve_ext(ext)
        if ext == "cogs.owner":
            return await ctx.send("✕ Cannot unload the owner cog.")
        try:
            await self.bot.unload_extension(ext)
            await ctx.send(f"✓ Unloaded `{ext}`")
            log.info(f"Unloaded extension: {ext}")
        except commands.ExtensionNotLoaded:
            await ctx.send(f"✕ `{ext}` is not loaded.")
        except Exception as e:
            await ctx.send(f"✕ Failed: `{e}`")

    @commands.command(name="extensions", aliases=["exts"])
    @is_owner()
    async def extensions(self, ctx: commands.Context):
        exts = "\n".join(f"✓ `{e}`" for e in sorted(self.bot.extensions))
        await ctx.send(f"**Loaded extensions:**\n{exts}")

    @commands.command(name="status")
    @is_owner()
    async def status(self, ctx: commands.Context, kind: str, *, text: str):
        kind = kind.lower()
        if kind not in STATUS_TYPES:
            types = ", ".join(STATUS_TYPES)
            return await ctx.send(f"✕ Unknown type. Use: {types}")
        await self.bot.change_presence(
            activity=discord.Activity(type=STATUS_TYPES[kind], name=text)
        )
        await ctx.send(f"✓ Status set to **{kind}** `{text}`")

    @commands.command(name="setonline")
    @is_owner()
    async def setonline(self, ctx: commands.Context):
        await self.bot.change_presence(status=discord.Status.online)
        await ctx.send("✓ Status set to Online.")

    @commands.command(name="setidle")
    @is_owner()
    async def setidle(self, ctx: commands.Context):
        await self.bot.change_presence(status=discord.Status.idle)
        await ctx.send("✓ Status set to Idle.")

    @commands.command(name="setdnd")
    @is_owner()
    async def setdnd(self, ctx: commands.Context):
        await self.bot.change_presence(status=discord.Status.do_not_disturb)
        await ctx.send("✓ Status set to DND.")

    @commands.command(name="setinvisible")
    @is_owner()
    async def setinvisible(self, ctx: commands.Context):
        await self.bot.change_presence(status=discord.Status.invisible)
        await ctx.send("✓ Status set to Invisible.")

    @commands.command(name="restart")
    @is_owner()
    async def restart(self, ctx: commands.Context):
        await ctx.send("↻ Restarting...")
        log.info(f"Restart triggered by {ctx.author} (ID: {ctx.author.id})")
        asyncio.get_event_loop().call_soon(asyncio.ensure_future, self.bot.close())

    @commands.command(name="shutdown")
    @is_owner()
    async def shutdown(self, ctx: commands.Context):
        await ctx.send("✓ Shutting down.")
        log.info(f"Shutdown triggered by {ctx.author} (ID: {ctx.author.id})")
        asyncio.get_event_loop().call_soon(asyncio.ensure_future, self.bot.close())

    @commands.command(name="addowner")
    @is_owner()
    async def addowner(self, ctx: commands.Context, user: discord.User):
        if user.id in OWNER_IDS:
            return await ctx.send(f"✕ {user.mention} is already an owner.")
        try:
            await _add_owner_db(user.id, ctx.author.id)
        except Exception as e:
            return await ctx.send(f"✕ Failed to save to database: `{e}`")
        OWNER_IDS.add(user.id)
        await ctx.send(f"✓ {user.mention} added as an owner.")
        log.info(f"Owner added: {user} (ID: {user.id}) by {ctx.author}")

    @commands.command(name="removeowner")
    @is_owner()
    async def removeowner(self, ctx: commands.Context, user: discord.User):
        if user.id not in OWNER_IDS:
            return await ctx.send(f"✕ {user.mention} is not an owner.")
        if len(OWNER_IDS) == 1:
            return await ctx.send("✕ Cannot remove the last owner.")
        try:
            await _remove_owner_db(user.id)
        except Exception as e:
            return await ctx.send(f"✕ Failed to remove from database: `{e}`")
        OWNER_IDS.discard(user.id)
        await ctx.send(f"✓ {user.mention} removed from owners.")
        log.info(f"Owner removed: {user} (ID: {user.id}) by {ctx.author}")

    @commands.command(name="owners")
    @is_owner()
    async def owners(self, ctx: commands.Context):
        lines = []
        for uid in sorted(OWNER_IDS):
            user = self.bot.get_user(uid)
            label = str(user) if user else f"Unknown ({uid})"
            lines.append(f"✓ `{uid}` — {label}")
        await ctx.send("**Owners:**\n" + "\n".join(lines))

    @commands.command(name="botstats")
    @is_owner()
    async def botstats(self, ctx: commands.Context):
        total_members = sum(g.member_count or 0 for g in self.bot.guilds)
        embed = discord.Embed(title="CoreBot Stats", color=discord.Color.blurple())
        embed.add_field(name="Guilds", value=str(len(self.bot.guilds)))
        embed.add_field(name="Users", value=f"{total_members:,}")
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms")
        embed.add_field(name="Extensions", value=str(len(self.bot.extensions)))
        embed.add_field(name="Python", value=sys.version.split()[0])
        embed.add_field(name="discord.py", value=discord.__version__)
        await ctx.send(embed=embed)

    @commands.command(name="ownerhelp", aliases=["oh"])
    @is_owner()
    async def ownerhelp(self, ctx: commands.Context):
        view = OwnerHelpView(self.bot, ctx.author, 0)
        msg = await ctx.send(embed=_make_owner_embed(self.bot, 0, ctx.author), view=view)
        view.message = msg


async def setup(bot: commands.Bot):
    await bot.add_cog(Owner(bot))