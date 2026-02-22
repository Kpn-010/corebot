import asyncio
import os
import signal
import logging
import sys

import discord
from discord.ext import commands

log = logging.getLogger("corebot")


def _parse_owner_ids() -> set[int]:
    """
    Read OWNER_IDS from env — comma-separated Discord user IDs.
    Example:  OWNER_IDS=123456789,987654321
    Non-integer values are silently skipped so a bad entry never crashes startup.
    """
    raw = os.environ.get("OWNER_IDS", "")
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


OWNER_IDS: set[int] = _parse_owner_ids()

STATUS_TYPES = {
    "watching":  discord.ActivityType.watching,
    "playing":   discord.ActivityType.playing,
    "listening": discord.ActivityType.listening,
    "competing": discord.ActivityType.competing,
}


def is_owner():
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.author.id in OWNER_IDS or await ctx.bot.is_owner(ctx.author):
            return True
        await ctx.send("✕ Owner only.")
        return False
    return commands.check(predicate)


def _resolve_ext(name: str) -> str:
    """Normalise a cog name so users can type 'mod' or 'cogs.mod' interchangeably."""
    name = name.strip()
    if not name.startswith("cogs."):
        name = f"cogs.{name}"
    return name


class Owner(commands.Cog, name="Owner"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # cc reload [cog]
    @commands.command(name="reload")
    @is_owner()
    async def reload(self, ctx: commands.Context, *, ext: str = None):
        """
        Reload one or all cogs.
        cc reload              — reloads every loaded extension
        cc reload cogs.mod     — reloads a specific extension
        """
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

    # cc load <cog>
    @commands.command(name="load")
    @is_owner()
    async def load(self, ctx: commands.Context, *, ext: str):
        """Load an extension. cc load cogs.newcog"""
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

    # cc unload <cog>
    @commands.command(name="unload")
    @is_owner()
    async def unload(self, ctx: commands.Context, *, ext: str):
        """Unload an extension. cc unload cogs.mod"""
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

    # cc extensions
    @commands.command(name="extensions", aliases=["exts"])
    @is_owner()
    async def extensions(self, ctx: commands.Context):
        """List all currently loaded extensions."""
        exts = "\n".join(f"✓ `{e}`" for e in sorted(self.bot.extensions))
        await ctx.send(f"**Loaded extensions:**\n{exts}")

    # cc status <type> <text>
    @commands.command(name="status")
    @is_owner()
    async def status(self, ctx: commands.Context, kind: str, *, text: str):
        """
        Change the bot's status.
        cc status watching the servers
        cc status playing a game
        cc status listening to music
        cc status competing in something
        Types: watching · playing · listening · competing
        """
        kind = kind.lower()
        if kind not in STATUS_TYPES:
            return await ctx.send(f"✕ Unknown type. Use: {', '.join(STATUS_TYPES)}")

        await self.bot.change_presence(
            activity=discord.Activity(type=STATUS_TYPES[kind], name=text)
        )
        await ctx.send(f"✓ Status set to **{kind}** `{text}`")

    # cc setonline / idle / dnd / invisible
    @commands.command(name="setonline")
    @is_owner()
    async def setonline(self, ctx: commands.Context):
        """Set bot presence to Online."""
        await self.bot.change_presence(status=discord.Status.online)
        await ctx.send("✓ Status set to Online.")

    @commands.command(name="setidle")
    @is_owner()
    async def setidle(self, ctx: commands.Context):
        """Set bot presence to Idle."""
        await self.bot.change_presence(status=discord.Status.idle)
        await ctx.send("✓ Status set to Idle.")

    @commands.command(name="setdnd")
    @is_owner()
    async def setdnd(self, ctx: commands.Context):
        """Set bot presence to Do Not Disturb."""
        await self.bot.change_presence(status=discord.Status.do_not_disturb)
        await ctx.send("✓ Status set to DND.")

    @commands.command(name="setinvisible")
    @is_owner()
    async def setinvisible(self, ctx: commands.Context):
        """Set bot presence to Invisible."""
        await self.bot.change_presence(status=discord.Status.invisible)
        await ctx.send("✓ Status set to Invisible.")

    @commands.command(name="restart")
    @is_owner()
    async def restart(self, ctx: commands.Context):
        await ctx.send("↻ Restarting...")
        log.info(f"Restart triggered by {ctx.author} (ID: {ctx.author.id})")
        await asyncio.sleep(3)
        os.execv(sys.executable, [sys.executable, "bot.py"])

    @commands.command(name="shutdown")
    @is_owner()
    async def shutdown(self, ctx: commands.Context):
        await ctx.send("✓ Shutting down.")
        log.info(f"Shutdown triggered by {ctx.author} (ID: {ctx.author.id})")
        asyncio.get_event_loop().call_soon(asyncio.ensure_future, self.bot.close())

    # cc ping (owner version with extra detail)
    @commands.command(name="botstats")
    @is_owner()
    async def botstats(self, ctx: commands.Context):
        """Show internal bot stats: guilds, users, latency, extensions loaded."""
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
        "description": "Restart the bot process in-place. Works on any host without relying on restart policies.",
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
        "title": "Bot Stats",
        "description": "Show internal stats: guilds, users, latency, extensions, versions.",
        "syntax": "cc botstats",
        "example": "cc botstats",
        "aliases": "None",
    },
]


def _make_owner_embed(bot: commands.Bot, page: int, invoker: discord.User | discord.Member) -> discord.Embed:
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
    def __init__(self, bot: commands.Bot, invoker: discord.User | discord.Member, page: int = 0):
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
            await interaction.response.send_message("✕ This menu belongs to someone else.", ephemeral=True)
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


async def setup(bot: commands.Bot):
    await bot.add_cog(Owner(bot))