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
    async def ping(self, ctx: commands.Context) -> None:
        """Check the bot's latency."""
        ms = round(self.bot.latency * 1000)
        await ctx.send(f"Pong! **{ms}ms**")

    # ── cc uptime (alias: ut) ──────────────────────────────────────────────
    @commands.command(name="uptime", aliases=["ut"])
    async def uptime(self, ctx: commands.Context) -> None:
        """Show how long the bot has been running."""
        elapsed = int(time.time() - self._start_time)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        await ctx.send(f"Uptime: **{h}h {m}m {s}s**")

    # ── cc avatar (alias: av) ──────────────────────────────────────────────
    @commands.command(name="avatar", aliases=["av"])
    @commands.guild_only()
    async def avatar(self,
                     ctx: commands.Context,
                     *,
                     user: str | None = None) -> None:
        """Show a user's avatar. Accepts @mention, ID, or name."""
        if user:
            member = await MemberConverter().convert(ctx, user)
        else:
            # guild_only() guarantees ctx.author is a Member, not a bare User.
            assert isinstance(ctx.author, discord.Member)
            member = ctx.author

        embed = discord.Embed(title=f"{member.display_name}'s Avatar",
                              color=discord.Color.blurple())

        if member.guild_avatar and member.guild_avatar != member.avatar:
            embed.set_image(url=member.guild_avatar.url)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(
                text="Server avatar shown • Global avatar in thumbnail")
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
    async def banner(self,
                     ctx: commands.Context,
                     *,
                     user: str | None = None) -> None:
        """Show a user's banner. Accepts @mention, ID, or name."""
        if user:
            member = await MemberConverter().convert(ctx, user)
        else:
            assert isinstance(ctx.author, discord.Member)
            member = ctx.author

        fetched = await self.bot.fetch_user(member.id)
        if not fetched.banner:
            await ctx.send(f"✕ **{member.display_name}** has no banner set.")
            return

        embed = discord.Embed(title=f"{member.display_name}'s Banner",
                              color=discord.Color.blurple())
        embed.set_image(url=fetched.banner.url)
        await ctx.send(embed=embed)

    # ── cc username (alias: un) ────────────────────────────────────────────
    @commands.command(name="username", aliases=["un"])
    @commands.guild_only()
    async def username(self,
                       ctx: commands.Context,
                       *,
                       user: str | None = None) -> None:
        """Show a user's username/display info. Accepts @mention, ID, or name."""
        if user:
            member = await MemberConverter().convert(ctx, user)
        else:
            assert isinstance(ctx.author, discord.Member)
            member = ctx.author

        embed = discord.Embed(color=member.color if member.color != discord.
                              Color.default() else discord.Color.blurple())
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.add_field(name="Username", value=f"`{member.name}`")
        embed.add_field(name="Display Name", value=f"`{member.display_name}`")
        embed.add_field(name="User ID", value=f"`{member.id}`")
        if member.global_name and member.global_name != member.name:
            embed.add_field(name="Global Name",
                            value=f"`{member.global_name}`")
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=embed)

    # ── cc say {msg} [#channel] ────────────────────────────────────────────
    @commands.command(name="say")
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def say(self, ctx: commands.Context, *, args: str) -> None:
        """
        Send a message to a channel.
        Usage: cc say <message> [#channel or channel ID or name]
        Supports @mentions and #channels in the message body.
        """
        await ctx.message.delete()

        # ctx.channel can be a variety of channel types — we annotate
        # target_channel as discord.abc.Messageable so both the initial
        # assignment and the TextChannel re-assignment are compatible.
        target_channel: discord.abc.Messageable = ctx.channel  # type: ignore[assignment]
        message = args

        parts = args.rsplit(" ", 1)
        if len(parts) == 2:
            try:
                channel = await ChannelConverter().convert(ctx, parts[1])
                target_channel = channel
                message = parts[0]
            except commands.BadArgument:
                message = args

        if not message.strip():
            await ctx.send("✕ Cannot send an empty message.", delete_after=5)
            return

        await target_channel.send(message,
                                  allowed_mentions=discord.AllowedMentions(
                                      everyone=False,
                                      roles=True,
                                      users=True,
                                  ))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Utils(bot))
