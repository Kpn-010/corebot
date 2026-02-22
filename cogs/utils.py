"""
cogs/utils.py — General utility commands
Prefix: cc
"""

import discord
from discord.ext import commands
from converters import MemberConverter, ChannelConverter
import time


class Utils(commands.Cog, name="Utils"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._start_time = time.time()

    # ── cc ping ────────────────────────────────────────────────────────────
    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        """Check the bot's latency."""
        ms = round(self.bot.latency * 1000)
        await ctx.send(f"Pong! **{ms}ms**")

    # ── cc uptime (alias: ut) ──────────────────────────────────────────────
    @commands.command(name="uptime", aliases=["ut"])
    async def uptime(self, ctx: commands.Context):
        """Show how long the bot has been running."""
        elapsed = int(time.time() - self._start_time)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        await ctx.send(f"Uptime: **{h}h {m}m {s}s**")

    # ── cc avatar (alias: av) ──────────────────────────────────────────────
    @commands.command(name="avatar", aliases=["av"])
    @commands.guild_only()
    async def avatar(self, ctx: commands.Context, *, user: str = None):
        """Show a user's avatar. Accepts @mention, ID, or name."""
        if user:
            member = await MemberConverter().convert(ctx, user)
        else:
            member = ctx.author

        embed = discord.Embed(title=f"{member.display_name}'s Avatar", color=discord.Color.blurple())

        # Show both guild avatar and global avatar if they differ
        if member.guild_avatar and member.guild_avatar != member.avatar:
            embed.set_image(url=member.guild_avatar.url)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="Server avatar shown • Global avatar in thumbnail")
        else:
            embed.set_image(url=member.display_avatar.url)

        formats = []
        av = member.display_avatar
        for fmt in ("png", "jpg", "webp"):
            formats.append(f"[{fmt.upper()}]({av.replace(format=fmt).url})")
        if av.is_animated():
            formats.append(f"[GIF]({av.replace(format='gif').url})")
        embed.description = " · ".join(formats)

        await ctx.send(embed=embed)

    # ── cc banner (alias: bn) ──────────────────────────────────────────────
    @commands.command(name="banner")
    @commands.guild_only()
    async def banner(self, ctx: commands.Context, *, user: str = None):
        """Show a user's banner. Accepts @mention, ID, or name."""
        if user:
            member = await MemberConverter().convert(ctx, user)
        else:
            member = ctx.author

        # Fetch full user object to get banner
        fetched = await self.bot.fetch_user(member.id)
        if not fetched.banner:
            return await ctx.send(f"✕ **{member.display_name}** has no banner set.")

        embed = discord.Embed(title=f"{member.display_name}'s Banner", color=discord.Color.blurple())
        embed.set_image(url=fetched.banner.url)
        await ctx.send(embed=embed)

    # ── cc username (alias: un) ────────────────────────────────────────────
    @commands.command(name="username", aliases=["un"])
    @commands.guild_only()
    async def username(self, ctx: commands.Context, *, user: str = None):
        """Show a user's username/display info. Accepts @mention, ID, or name."""
        if user:
            member = await MemberConverter().convert(ctx, user)
        else:
            member = ctx.author

        embed = discord.Embed(color=member.color if member.color != discord.Color.default() else discord.Color.blurple())
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.add_field(name="Username", value=f"`{member.name}`")
        embed.add_field(name="Display Name", value=f"`{member.display_name}`")
        embed.add_field(name="User ID", value=f"`{member.id}`")
        if member.global_name and member.global_name != member.name:
            embed.add_field(name="Global Name", value=f"`{member.global_name}`")
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=embed)

    # ── cc say {msg} [#channel] ────────────────────────────────────────────
    @commands.command(name="say")
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def say(self, ctx: commands.Context, *, args: str):
        """
        Send a message to a channel.
        Usage: cc say <message> [#channel or channel ID or name]
        Supports @mentions and #channels in the message body.
        """
        await ctx.message.delete()

        # Check if the last "word" resolves to a channel
        parts = args.rsplit(" ", 1)
        target_channel = ctx.channel

        if len(parts) == 2:
            channel = await ChannelConverter().convert(ctx, parts[1]) if parts[1] else None
            if channel:
                message = parts[0]
                target_channel = channel
            else:
                message = args
        else:
            message = args

        if not message.strip():
            return await ctx.send("✕ Cannot send an empty message.", delete_after=5)

        await target_channel.send(message, allowed_mentions=discord.AllowedMentions(
            everyone=False,
            roles=True,
            users=True,
        ))


async def setup(bot: commands.Bot):
    await bot.add_cog(Utils(bot))