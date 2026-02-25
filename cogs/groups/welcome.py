"""
cogs/groups/welcome.py — Welcome system
cc welc ch <#channel|ID|name>
cc welc msg <template>

Variables: {user} {user.name} {user.id} {server} {count} {position} {invite}
Embed:     Start message with $em and use {description ...} {thumbnail} {author {user}}
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from converters import ChannelConverter

if TYPE_CHECKING:
    from bot import CoreBot

VARIABLES_HELP = ("**Variables:**\n"
                  "`{user}` — mention the user\n"
                  "`{user.name}` — username\n"
                  "`{user.id}` — user ID\n"
                  "`{server}` — server name\n"
                  "`{count}` — member count\n"
                  "`{position}` — ordinal position (e.g. 42nd)\n"
                  "`{invite}` — first active invite URL\n\n"
                  "**Embed mode** — start with `$em`:\n"
                  "`{description Your text here}` — embed description\n"
                  "`{thumbnail}` — set thumbnail to user avatar\n"
                  "`{author {user}}` — set embed author with user avatar\n")


class Welcome(commands.Cog, name="Welcome"):

    def __init__(self, bot: CoreBot) -> None:
        self.bot = bot

    # ── Group ──────────────────────────────────────────────────────────────
    @commands.group(name="welc", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def welc(self, ctx: commands.Context) -> None:
        """Welcome system. Subcommands: ch, msg"""
        assert ctx.guild is not None
        guild_data = await self.bot.db.load(ctx.guild.id)
        welcome = guild_data.get("welcome", {})
        ch_id = welcome.get("channel_id")
        channel = ctx.guild.get_channel(ch_id) if ch_id else None
        msg = welcome.get("message", "Not set")
        embed_mode = welcome.get("embed", False)

        embed = discord.Embed(title="Welcome Settings",
                              color=discord.Color.blurple())
        embed.add_field(name="Channel",
                        value=channel.mention if channel else "Not set",
                        inline=False)
        embed.add_field(name="Embed Mode", value="✓" if embed_mode else "✕")
        embed.add_field(name="Message Template",
                        value=f"```{msg[:500]}```",
                        inline=False)
        embed.add_field(name="Help", value=VARIABLES_HELP, inline=False)
        await ctx.send(embed=embed)

    # ── cc welc ch <channel> ───────────────────────────────────────────────
    @welc.command(name="ch")
    async def welc_channel(self, ctx: commands.Context, *,
                           target: str) -> None:
        """
        Set the welcome channel.
        Usage: cc welc ch <#channel|ID|name>
               cc welc ch clear
        """
        assert ctx.guild is not None
        if target.lower() == "clear":
            await self.bot.db.set(ctx.guild.id, ["welcome", "channel_id"],
                                  None)
            await ctx.send("✓ Welcome channel cleared.")
            return

        channel = await ChannelConverter().convert(ctx, target)
        await self.bot.db.set(ctx.guild.id, ["welcome", "channel_id"],
                              channel.id)
        await ctx.send(f"✓ Welcome channel set to {channel.mention}.")

    # ── cc welc msg <template> ─────────────────────────────────────────────
    @welc.command(name="msg")
    async def welc_msg(self, ctx: commands.Context, *, template: str) -> None:
        """
        Set the welcome message template.
        Start with $em for embed mode.

        Examples:
          cc welc msg Welcome {user} to {server}! You are member #{count}.
          cc welc msg $em {description Welcome {user} to **{server}**!} {thumbnail} {author {user}}
        """
        assert ctx.guild is not None
        embed_mode = template.startswith("$em")
        if embed_mode:
            template = template[3:].strip()

        await self.bot.db.set(ctx.guild.id, ["welcome", "message"], template)
        await self.bot.db.set(ctx.guild.id, ["welcome", "embed"], embed_mode)

        mode_str = "Embed mode" if embed_mode else "Text mode"
        preview = discord.Embed(title="✓ Welcome message saved",
                                color=discord.Color.green())
        preview.add_field(name="Mode", value=mode_str)
        preview.add_field(name="Template",
                          value=f"```{template[:500]}```",
                          inline=False)
        preview.add_field(name="Variables", value=VARIABLES_HELP, inline=False)
        await ctx.send(embed=preview)

    # ── cc welc test ───────────────────────────────────────────────────────
    @welc.command(name="test")
    async def welc_test(self, ctx: commands.Context) -> None:
        """Simulate a welcome message for yourself."""
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        # Dispatch on_member_join through the bot so all listeners fire,
        # including the one in bot.py — avoids importing a bare function.
        self.bot.dispatch("member_join", ctx.author)
        await ctx.send("✓ Sent a test welcome message.", delete_after=5)


async def setup(bot: CoreBot) -> None:
    await bot.add_cog(Welcome(bot))
