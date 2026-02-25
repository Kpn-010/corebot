"""
cogs/mod.py — Moderation commands
All guild data (warnings, muted role, image mutes) is stored in JSON via data.py
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from converters import ChannelConverter, MemberConverter

if TYPE_CHECKING:
    from cogs.logs import Logs
    from bot import CoreBot

# ── Helpers ────────────────────────────────────────────────────────────────────


def _parse_duration(s: str) -> timedelta | None:
    units = {
        "s": "seconds",
        "m": "minutes",
        "h": "hours",
        "d": "days",
        "w": "weeks"
    }
    m = re.fullmatch(r"(\d+)([smhdw])", s.lower())
    if not m:
        return None
    return timedelta(**{units[m.group(2)]: int(m.group(1))})


def _hierarchy_check(
    author: discord.Member,
    guild: discord.Guild,
    target: discord.Member,
) -> str | None:
    """Return an error string if the action is forbidden, else None."""
    if target == author:
        return "✕ You can't do that to yourself."
    if target == guild.me:
        return "✕ You can't do that to me."
    if target.top_role >= author.top_role and author != guild.owner:
        return "✕ That member has an equal or higher role than you."
    if target.top_role >= guild.me.top_role:
        return "✕ That member's top role is higher than or equal to mine."
    return None


def mod_embed(title: str, color: discord.Color,
              **fields: str) -> discord.Embed:
    embed = discord.Embed(title=title, color=color)
    for name, value in fields.items():
        embed.add_field(name=name.replace("_", " ").title(), value=value)
    return embed


def _get_logs(bot: commands.Bot) -> Logs | None:
    """Retrieve the Logs cog with the correct type, or None if not loaded."""
    cog = bot.cogs.get("Logs")
    if cog is None:
        return None
    from cogs.logs import Logs as LogsCog  # noqa: PLC0415
    return cog if isinstance(cog, LogsCog) else None


# ── Cog ────────────────────────────────────────────────────────────────────────


class Mod(commands.Cog, name="Mod"):

    def __init__(self, bot: CoreBot) -> None:
        self.bot = bot

    # ── cc kick ────────────────────────────────────────────────────────────
    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.guild_only()
    async def kick(self,
                   ctx: commands.Context,
                   target: str,
                   *,
                   reason: str = "No reason provided") -> None:
        """Kick a member. cc kick <@|ID|name> [reason]"""
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        member = await MemberConverter().convert(ctx, target)
        err = _hierarchy_check(ctx.author, ctx.guild, member)
        if err:
            await ctx.send(err)
            return

        try:
            await member.send(
                f"↻ You were kicked from **{ctx.guild.name}**.\n**Reason:** {reason}"
            )
        except discord.Forbidden:
            pass

        await member.kick(reason=f"{ctx.author} | {reason}")
        await ctx.send(embed=mod_embed(
            "Member Kicked",
            discord.Color.orange(),
            member=str(member),
            reason=reason,
            moderator=ctx.author.mention,
        ))
        logs = _get_logs(self.bot)
        if logs:
            await logs.log_mod(ctx.guild,
                               "Kick",
                               Member=str(member),
                               Reason=reason,
                               Moderator=ctx.author.mention)

    # ── cc ban ─────────────────────────────────────────────────────────────
    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    async def ban(self,
                  ctx: commands.Context,
                  target: str,
                  *,
                  reason: str = "No reason provided") -> None:
        """Ban a member. cc ban <@|ID|name> [reason]"""
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        member = await MemberConverter().convert(ctx, target)
        err = _hierarchy_check(ctx.author, ctx.guild, member)
        if err:
            await ctx.send(err)
            return

        try:
            await member.send(
                f"↻ You were banned from **{ctx.guild.name}**.\n**Reason:** {reason}"
            )
        except discord.Forbidden:
            pass

        await member.ban(reason=f"{ctx.author} | {reason}",
                         delete_message_days=0)
        await ctx.send(embed=mod_embed(
            "Member Banned",
            discord.Color.red(),
            member=str(member),
            reason=reason,
            moderator=ctx.author.mention,
        ))
        logs = _get_logs(self.bot)
        if logs:
            await logs.log_mod(ctx.guild,
                               "Ban",
                               Member=str(member),
                               Reason=reason,
                               Moderator=ctx.author.mention)

    # ── cc unban ───────────────────────────────────────────────────────────
    @commands.command(name="unban")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    async def unban(self,
                    ctx: commands.Context,
                    user_id: int,
                    *,
                    reason: str = "No reason provided") -> None:
        """Unban a user by ID. cc unban <user_id> [reason]"""
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        try:
            user = await self.bot.fetch_user(user_id)
            await ctx.guild.unban(user, reason=f"{ctx.author} | {reason}")
            await ctx.send(f"✓ Unbanned **{user}**.")
            logs = _get_logs(self.bot)
            if logs:
                await logs.log_mod(ctx.guild,
                                   "Unban",
                                   User=str(user),
                                   Reason=reason,
                                   Moderator=ctx.author.mention)
        except discord.NotFound:
            await ctx.send("✕ No banned user found with that ID.")

    # ── cc timeout ─────────────────────────────────────────────────────────
    @commands.command(name="timeout", aliases=["to"])
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @commands.guild_only()
    async def timeout(self,
                      ctx: commands.Context,
                      target: str,
                      duration: str,
                      *,
                      reason: str = "No reason provided") -> None:
        """Timeout a member. cc timeout <@|ID|name> <duration> [reason]
        Duration: 10s, 5m, 2h, 1d, 1w (max 28d)"""
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        member = await MemberConverter().convert(ctx, target)
        err = _hierarchy_check(ctx.author, ctx.guild, member)
        if err:
            await ctx.send(err)
            return

        delta = _parse_duration(duration)
        if not delta:
            await ctx.send(
                "✕ Invalid duration. Use formats: `10s` `5m` `2h` `1d` `1w`")
            return
        if delta > timedelta(days=28):
            await ctx.send("✕ Max timeout duration is 28 days.")
            return

        await member.timeout(delta, reason=f"{ctx.author} | {reason}")
        await ctx.send(embed=mod_embed(
            "Member Timed Out",
            discord.Color.yellow(),
            member=str(member),
            duration=duration,
            reason=reason,
            moderator=ctx.author.mention,
        ))
        logs = _get_logs(self.bot)
        if logs:
            await logs.log_mod(ctx.guild,
                               "Timeout",
                               Member=str(member),
                               Duration=duration,
                               Reason=reason,
                               Moderator=ctx.author.mention)

    # ── cc untimeout ───────────────────────────────────────────────────────
    @commands.command(name="untimeout", aliases=["uto"])
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @commands.guild_only()
    async def untimeout(self, ctx: commands.Context, *, target: str) -> None:
        """Remove a timeout. cc untimeout <@|ID|name>"""
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        member = await MemberConverter().convert(ctx, target)
        await member.timeout(None)
        await ctx.send(f"✓ Timeout removed for **{member}**.")
        logs = _get_logs(self.bot)
        if logs:
            await logs.log_mod(ctx.guild,
                               "Untimeout",
                               Member=str(member),
                               Moderator=ctx.author.mention)

    # ── cc purge ───────────────────────────────────────────────────────────
    @commands.command(name="purge")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def purge(self,
                    ctx: commands.Context,
                    amount: int,
                    *,
                    target: str | None = None) -> None:
        """Bulk delete messages. cc purge <amount> [optional: @|ID|name]"""
        # ctx.channel in a guild_only command is always a TextChannel (or Thread),
        # but the type is a broad union — narrow to TextChannel for .purge().
        if not isinstance(ctx.channel, discord.TextChannel):
            return
        if not 1 <= amount <= 100:
            await ctx.send("✕ Amount must be between 1 and 100.")
            return

        await ctx.message.delete()

        member = None
        if target:
            member = await MemberConverter().convert(ctx, target)

        check = (lambda m: m.author == member) if member else (lambda m: True)
        deleted = await ctx.channel.purge(limit=amount, check=check)
        msg = await ctx.send(f"↻ Deleted **{len(deleted)}** message(s).")
        await msg.delete(delay=5)

    # ── cc slowmode ────────────────────────────────────────────────────────
    @commands.command(name="slowmode", aliases=["sm"])
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    @commands.guild_only()
    async def slowmode(self, ctx: commands.Context, seconds: int) -> None:
        """Set channel slowmode (0 to disable, max 21600). cc slowmode <seconds>"""
        if not isinstance(ctx.channel, discord.TextChannel):
            return
        if not 0 <= seconds <= 21600:
            await ctx.send("✕ Must be between 0 and 21600 seconds.")
            return
        await ctx.channel.edit(slowmode_delay=seconds)
        await ctx.send("✓ Slowmode disabled." if seconds ==
                       0 else f"✓ Slowmode set to **{seconds}s**.")

    # ── cc lock / unlock ───────────────────────────────────────────────────
    @commands.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    @commands.guild_only()
    async def lock(self,
                   ctx: commands.Context,
                   *,
                   target: str | None = None) -> None:
        """Lock a channel (deny @everyone from sending). cc lock [#channel]"""
        assert ctx.guild is not None
        if target:
            channel = await ChannelConverter().convert(ctx, target)
        else:
            if not isinstance(ctx.channel, discord.TextChannel):
                return
            channel = ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(ctx.guild.default_role,
                                      overwrite=overwrite)
        await ctx.send(f"{channel.mention} has been locked.")

    @commands.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    @commands.guild_only()
    async def unlock(self,
                     ctx: commands.Context,
                     *,
                     target: str | None = None) -> None:
        """Unlock a channel. cc unlock [#channel]"""
        assert ctx.guild is not None
        if target:
            channel = await ChannelConverter().convert(ctx, target)
        else:
            if not isinstance(ctx.channel, discord.TextChannel):
                return
            channel = ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await channel.set_permissions(ctx.guild.default_role,
                                      overwrite=overwrite)
        await ctx.send(f"{channel.mention} has been unlocked.")

    # ── cc lockdown / release ──────────────────────────────────────────────
    @commands.command(name="lockdown")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    @commands.guild_only()
    async def lockdown(self, ctx: commands.Context) -> None:
        """Lock ALL text channels in the server. cc lockdown"""
        assert ctx.guild is not None
        count = 0
        for channel in ctx.guild.text_channels:
            try:
                overwrite = channel.overwrites_for(ctx.guild.default_role)
                overwrite.send_messages = False
                await channel.set_permissions(ctx.guild.default_role,
                                              overwrite=overwrite)
                count += 1
            except discord.Forbidden:
                pass
        await ctx.send(f"**Lockdown activated.** Locked {count} channel(s).")

    @commands.command(name="release", aliases=["unlockdown"])
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    @commands.guild_only()
    async def release(self, ctx: commands.Context) -> None:
        """Release server lockdown (unlock all channels). cc release"""
        assert ctx.guild is not None
        count = 0
        for channel in ctx.guild.text_channels:
            try:
                overwrite = channel.overwrites_for(ctx.guild.default_role)
                overwrite.send_messages = None
                await channel.set_permissions(ctx.guild.default_role,
                                              overwrite=overwrite)
                count += 1
            except discord.Forbidden:
                pass
        await ctx.send(f"**Lockdown lifted.** Unlocked {count} channel(s).")

    # ── cc warn ────────────────────────────────────────────────────────────
    @commands.command(name="warn")
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def warn(self,
                   ctx: commands.Context,
                   target: str,
                   *,
                   reason: str = "No reason provided") -> None:
        """Warn a member. cc warn <@|ID|name> [reason]"""
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        member = await MemberConverter().convert(ctx, target)
        guild_data = await self.bot.db.load(ctx.guild.id)
        uid = str(member.id)
        guild_data["warnings"].setdefault(uid, []).append(reason)
        await self.bot.db.save(ctx.guild.id, guild_data)
        count = len(guild_data["warnings"][uid])

        try:
            await member.send(
                f"! You received a warning in **{ctx.guild.name}**.\n"
                f"**Reason:** {reason}\n**Total warnings:** {count}")
        except discord.Forbidden:
            pass

        await ctx.send(embed=mod_embed(
            "! Member Warned",
            discord.Color.gold(),
            member=str(member),
            reason=reason,
            total_warnings=str(count),
            moderator=ctx.author.mention,
        ))
        logs = _get_logs(self.bot)
        if logs:
            await logs.log_mod(ctx.guild,
                               "Warn",
                               Member=str(member),
                               Reason=reason,
                               Warnings=str(count),
                               Moderator=ctx.author.mention)

    # ── cc warnings ────────────────────────────────────────────────────────
    @commands.command(name="warnings")
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def warnings(self, ctx: commands.Context, *, target: str) -> None:
        """View a member's warnings. cc warnings <@|ID|name>"""
        assert ctx.guild is not None
        member = await MemberConverter().convert(ctx, target)
        warns = await self.bot.db.get(ctx.guild.id,
                                      "warnings",
                                      str(member.id),
                                      default=[])
        if not warns:
            await ctx.send(f"✓ **{member}** has no warnings.")
            return
        listed = "\n".join(f"`{i+1}.` {w}" for i, w in enumerate(warns))
        embed = discord.Embed(title=f"! Warnings for {member}",
                              description=listed,
                              color=discord.Color.gold())
        embed.set_footer(text=f"Total: {len(warns)}")
        await ctx.send(embed=embed)

    # ── cc warnclean ───────────────────────────────────────────────────────
    @commands.command(name="warnclean", aliases=["clearwarnings", "wc"])
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def warnclean(self,
                        ctx: commands.Context,
                        target: str,
                        index: int | None = None) -> None:
        """
        Clear all or one warning from a member.
        cc warnclean <@|ID|name>        — clears all warnings
        cc warnclean <@|ID|name> <num>  — removes warning #num
        """
        assert ctx.guild is not None
        member = await MemberConverter().convert(ctx, target)
        guild_data = await self.bot.db.load(ctx.guild.id)
        uid = str(member.id)
        warns = guild_data["warnings"].get(uid, [])

        if not warns:
            await ctx.send(f"✓ **{member}** has no warnings to clear.")
            return

        if index is None:
            guild_data["warnings"][uid] = []
            await self.bot.db.save(ctx.guild.id, guild_data)
            await ctx.send(
                f"✓ Cleared all **{len(warns)}** warning(s) for **{member}**.")
        else:
            if not 1 <= index <= len(warns):
                await ctx.send(f"✕ Invalid warning number. Use 1–{len(warns)}."
                               )
                return
            removed = warns.pop(index - 1)
            guild_data["warnings"][uid] = warns
            await self.bot.db.save(ctx.guild.id, guild_data)
            await ctx.send(
                f"✓ Removed warning #{index} from **{member}**: `{removed}`")

    # ── cc mute (role-based) ───────────────────────────────────────────────
    @commands.command(name="mute")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.guild_only()
    async def mute(self,
                   ctx: commands.Context,
                   target: str,
                   *,
                   reason: str = "No reason provided") -> None:
        """
        Mute a member using the server's muted role.
        Set the muted role first with: cc muterole <@role|ID|name>
        """
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        member = await MemberConverter().convert(ctx, target)
        err = _hierarchy_check(ctx.author, ctx.guild, member)
        if err:
            await ctx.send(err)
            return

        muted_role_id = await self.bot.db.get(ctx.guild.id, "muted_role")
        if not muted_role_id:
            await ctx.send(
                "✕ No muted role set. Use `cc muterole <@role|ID|name>` to set one."
            )
            return

        muted_role = ctx.guild.get_role(muted_role_id)
        if not muted_role:
            await ctx.send(
                "✕ The saved muted role no longer exists. Please set a new one."
            )
            return

        if muted_role in member.roles:
            await ctx.send(f"✕ **{member}** is already muted.")
            return

        await member.add_roles(muted_role, reason=f"{ctx.author} | {reason}")
        try:
            await member.send(
                f"↻ You were muted in **{ctx.guild.name}**.\n**Reason:** {reason}"
            )
        except discord.Forbidden:
            pass
        await ctx.send(embed=mod_embed(
            "Member Muted",
            discord.Color.dark_gray(),
            member=str(member),
            reason=reason,
            moderator=ctx.author.mention,
        ))
        logs = _get_logs(self.bot)
        if logs:
            await logs.log_mod(ctx.guild,
                               "Mute",
                               Member=str(member),
                               Reason=reason,
                               Moderator=ctx.author.mention)

    @commands.command(name="unmute")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.guild_only()
    async def unmute(self, ctx: commands.Context, *, target: str) -> None:
        """Unmute a member. cc unmute <@|ID|name>"""
        assert ctx.guild is not None
        member = await MemberConverter().convert(ctx, target)
        muted_role_id = await self.bot.db.get(ctx.guild.id, "muted_role")
        if not muted_role_id:
            await ctx.send("✕ No muted role configured.")
            return
        muted_role = ctx.guild.get_role(muted_role_id)
        if not muted_role or muted_role not in member.roles:
            await ctx.send(f"✕ **{member}** is not muted.")
            return
        await member.remove_roles(muted_role,
                                  reason=f"Unmuted by {ctx.author}")
        await ctx.send(f"**{member}** has been unmuted.")
        logs = _get_logs(self.bot)
        if logs:
            await logs.log_mod(ctx.guild,
                               "Unmute",
                               Member=str(member),
                               Moderator=ctx.author.mention)

    # ── cc imute (image/attachment mute) ──────────────────────────────────
    @commands.command(name="imute")
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def imute(self,
                    ctx: commands.Context,
                    target: str,
                    *,
                    reason: str = "No reason provided") -> None:
        """
        Prevent a member from posting images/attachments.
        The bot will delete their media messages automatically.
        cc imute <@|ID|name> [reason]
        """
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        member = await MemberConverter().convert(ctx, target)
        guild_data = await self.bot.db.load(ctx.guild.id)
        uid = str(member.id)

        if guild_data["image_muted"].get(uid):
            await ctx.send(f"✕ **{member}** is already image-muted.")
            return

        guild_data["image_muted"][uid] = True
        await self.bot.db.save(ctx.guild.id, guild_data)
        await ctx.send(
            f"**{member}** is now image-muted. Their attachments will be deleted."
        )
        logs = _get_logs(self.bot)
        if logs:
            await logs.log_mod(ctx.guild,
                               "Image Mute",
                               Member=str(member),
                               Reason=reason,
                               Moderator=ctx.author.mention)

    @commands.command(name="iunmute")
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def iunmute(self, ctx: commands.Context, *, target: str) -> None:
        """Remove an image mute. cc iunmute <@|ID|name>"""
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        member = await MemberConverter().convert(ctx, target)
        guild_data = await self.bot.db.load(ctx.guild.id)
        uid = str(member.id)
        if not guild_data["image_muted"].get(uid):
            await ctx.send(f"✕ **{member}** is not image-muted.")
            return
        guild_data["image_muted"].pop(uid, None)
        await self.bot.db.save(ctx.guild.id, guild_data)
        await ctx.send(f"**{member}**'s image mute removed.")
        logs = _get_logs(self.bot)
        if logs:
            await logs.log_mod(ctx.guild,
                               "Image Unmute",
                               Member=str(member),
                               Moderator=ctx.author.mention)

    # ── cc muterole ────────────────────────────────────────────────────────
    @commands.command(name="muterole")
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def muterole(self, ctx: commands.Context, *, target: str) -> None:
        """Set the muted role for the server. cc muterole <@role|ID|name>"""
        assert ctx.guild is not None
        from converters import RoleConverter
        role = await RoleConverter().convert(ctx, target)
        await self.bot.db.set(ctx.guild.id, ["muted_role"], role.id)
        await ctx.send(f"✓ Muted role set to {role.mention}.")

    # ── Image mute enforcement (on_message) ────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return
        if not message.attachments:
            return

        uid = str(message.author.id)
        is_imuted = await self.bot.db.get(message.guild.id,
                                          "image_muted",
                                          uid,
                                          default=False)

        if is_imuted:
            try:
                await message.delete()
                await message.channel.send(
                    f"{message.author.mention} You are image-muted and cannot post attachments.",
                    delete_after=5,
                )
            except discord.Forbidden:
                pass


async def setup(bot: CoreBot) -> None:
    await bot.add_cog(Mod(bot))
