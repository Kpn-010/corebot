from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from converters import ChannelConverter

if TYPE_CHECKING:
    from bot import CoreBot

LOG_CATEGORIES = ("mod", "message", "member", "server", "voice")


class Logs(commands.Cog, name="Logs"):

    def __init__(self, bot: CoreBot) -> None:
        self.bot = bot

    # ── Helpers ────────────────────────────────────────────────────────────

    async def _log_channel(self, guild: discord.Guild,
                           category: str) -> discord.TextChannel | None:
        channel_id = await self.bot.db.get(guild.id, "logs", category)
        if not channel_id:
            return None
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return None
        return channel

    async def _send(self, guild: discord.Guild, category: str,
                    embed: discord.Embed) -> None:
        channel = await self._log_channel(guild, category)
        if channel:
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                pass

    def _embed(self, title: str, color: discord.Color,
               **fields: str) -> discord.Embed:
        embed = discord.Embed(title=title, color=color)
        for name, value in fields.items():
            embed.add_field(name=name, value=value, inline=True)
        return embed

    # ── Commands ───────────────────────────────────────────────────────────

    @commands.group(name="log", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def log(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None
        data = await self.bot.db.get(ctx.guild.id, "logs")
        lines = []
        for cat in LOG_CATEGORIES:
            ch_id = data.get(cat)
            ch = ctx.guild.get_channel(ch_id) if ch_id else None
            lines.append(f"`{cat:<8}` {ch.mention if ch else 'Not set'}")
        embed = discord.Embed(title="Log Channels",
                              description="\n".join(lines),
                              color=discord.Color.blurple())
        embed.set_footer(
            text="cc log set <category> <#channel>  |  cc log clear <category>"
        )
        await ctx.send(embed=embed)

    @log.command(name="set")
    @commands.has_permissions(manage_guild=True)
    async def log_set(self, ctx: commands.Context, category: str, *,
                      target: str) -> None:
        assert ctx.guild is not None
        category = category.lower()
        if category not in LOG_CATEGORIES:
            await ctx.send(
                f"✕ Unknown category. Choose: `{'` `'.join(LOG_CATEGORIES)}`")
            return
        channel = await ChannelConverter().convert(ctx, target)
        await self.bot.db.set(ctx.guild.id, ["logs", category], channel.id)
        await ctx.send(f"✓ `{category}` logs → {channel.mention}")

    @log.command(name="clear")
    @commands.has_permissions(manage_guild=True)
    async def log_clear(self, ctx: commands.Context, category: str) -> None:
        assert ctx.guild is not None
        category = category.lower()
        if category not in LOG_CATEGORIES:
            await ctx.send(
                f"✕ Unknown category. Choose: `{'` `'.join(LOG_CATEGORIES)}`")
            return
        await self.bot.db.set(ctx.guild.id, ["logs", category], None)
        await ctx.send(f"✓ `{category}` log channel cleared.")

    # ── Moderation events (called directly from mod cog) ───────────────────

    async def log_mod(self, guild: discord.Guild, action: str,
                      **fields: str) -> None:
        colors = {
            "Kick": discord.Color.orange(),
            "Ban": discord.Color.red(),
            "Unban": discord.Color.green(),
            "Timeout": discord.Color.yellow(),
            "Untimeout": discord.Color.green(),
            "Warn": discord.Color.gold(),
            "Mute": discord.Color.dark_gray(),
            "Unmute": discord.Color.green(),
            "Image Mute": discord.Color.dark_gray(),
            "Image Unmute": discord.Color.green(),
        }
        embed = self._embed(action, colors.get(action,
                                               discord.Color.blurple()),
                            **fields)
        await self._send(guild, "mod", embed)

    # ── Message events ─────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message,
                              after: discord.Message) -> None:
        if not before.guild or before.author.bot:
            return
        if before.content == after.content:
            return
        # message.channel is a broad union — narrow to a type that has .mention.
        if not isinstance(before.channel,
                          (discord.TextChannel, discord.Thread)):
            return

        embed = discord.Embed(title="Message Edited",
                              color=discord.Color.blurple())
        embed.set_author(name=str(before.author),
                         icon_url=before.author.display_avatar.url)
        embed.add_field(name="Channel",
                        value=before.channel.mention,
                        inline=True)
        embed.add_field(name="User", value=before.author.mention, inline=True)
        embed.add_field(name="Before",
                        value=before.content[:1024] or "*empty*",
                        inline=False)
        embed.add_field(name="After",
                        value=after.content[:1024] or "*empty*",
                        inline=False)
        embed.add_field(name="Jump",
                        value=f"[View]({after.jump_url})",
                        inline=True)
        embed.set_footer(text=f"User ID: {before.author.id}")
        await self._send(before.guild, "message", embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return
        if not isinstance(message.channel,
                          (discord.TextChannel, discord.Thread)):
            return

        embed = discord.Embed(title="Message Deleted",
                              color=discord.Color.red())
        embed.set_author(name=str(message.author),
                         icon_url=message.author.display_avatar.url)
        embed.add_field(name="Channel",
                        value=message.channel.mention,
                        inline=True)
        embed.add_field(name="User", value=message.author.mention, inline=True)
        embed.add_field(name="Content",
                        value=message.content[:1024] or "*empty*",
                        inline=False)
        if message.attachments:
            embed.add_field(name="Attachments",
                            value="\n".join(a.filename
                                            for a in message.attachments),
                            inline=False)
        embed.set_footer(text=f"Message ID: {message.id}")
        await self._send(message.guild, "message", embed)

    # ── Member events ──────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        embed = discord.Embed(title="Member Joined",
                              color=discord.Color.green())
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.add_field(name="User", value=member.mention, inline=True)
        embed.add_field(name="Account Age",
                        value=discord.utils.format_dt(member.created_at,
                                                      style="R"),
                        inline=True)
        embed.add_field(name="Member Count",
                        value=str(member.guild.member_count),
                        inline=True)
        embed.set_footer(text=f"User ID: {member.id}")
        await self._send(member.guild, "member", embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        roles = [
            r.mention for r in member.roles if r != member.guild.default_role
        ]
        embed = discord.Embed(title="Member Left", color=discord.Color.red())
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.add_field(name="User", value=str(member), inline=True)
        embed.add_field(name="Member Count",
                        value=str(member.guild.member_count),
                        inline=True)
        if roles:
            embed.add_field(name=f"Roles ({len(roles)})",
                            value=" ".join(roles[:10]),
                            inline=False)
        embed.set_footer(text=f"User ID: {member.id}")
        await self._send(member.guild, "member", embed)

    # ── Server events ──────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        embed = self._embed("Role Created",
                            discord.Color.green(),
                            Role=role.mention,
                            Color=str(role.color),
                            ID=f"`{role.id}`")
        await self._send(role.guild, "server", embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        embed = self._embed("Role Deleted",
                            discord.Color.red(),
                            Role=role.name,
                            Color=str(role.color),
                            ID=f"`{role.id}`")
        await self._send(role.guild, "server", embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role,
                                   after: discord.Role) -> None:
        changes = []
        if before.name != after.name:
            changes.append(f"Name: `{before.name}` → `{after.name}`")
        if before.color != after.color:
            changes.append(f"Color: `{before.color}` → `{after.color}`")
        if before.permissions != after.permissions:
            changes.append("Permissions changed")
        if before.hoist != after.hoist:
            changes.append(f"Hoisted: `{before.hoist}` → `{after.hoist}`")
        if before.mentionable != after.mentionable:
            changes.append(
                f"Mentionable: `{before.mentionable}` → `{after.mentionable}`")
        if not changes:
            return

        embed = discord.Embed(title="Role Updated",
                              color=discord.Color.blurple())
        embed.add_field(name="Role", value=after.mention, inline=True)
        embed.add_field(name="Changes", value="\n".join(changes), inline=False)
        embed.set_footer(text=f"Role ID: {after.id}")
        await self._send(after.guild, "server", embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(
            self, channel: discord.abc.GuildChannel) -> None:
        embed = self._embed("Channel Created",
                            discord.Color.green(),
                            Channel=channel.mention,
                            Type=type(channel).__name__,
                            ID=f"`{channel.id}`")
        await self._send(channel.guild, "server", embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(
            self, channel: discord.abc.GuildChannel) -> None:
        embed = self._embed("Channel Deleted",
                            discord.Color.red(),
                            Channel=channel.name,
                            Type=type(channel).__name__,
                            ID=f"`{channel.id}`")
        await self._send(channel.guild, "server", embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel,
                                      after: discord.abc.GuildChannel) -> None:
        changes = []
        if before.name != after.name:
            changes.append(f"Name: `{before.name}` → `{after.name}`")
        if isinstance(before, discord.TextChannel) and isinstance(
                after, discord.TextChannel):
            if before.topic != after.topic:
                changes.append("Topic changed")
            if before.slowmode_delay != after.slowmode_delay:
                changes.append(
                    f"Slowmode: `{before.slowmode_delay}s` → `{after.slowmode_delay}s`"
                )
        if not changes:
            return

        embed = discord.Embed(title="Channel Updated",
                              color=discord.Color.blurple())
        embed.add_field(name="Channel", value=after.mention, inline=True)
        embed.add_field(name="Changes", value="\n".join(changes), inline=False)
        embed.set_footer(text=f"Channel ID: {after.id}")
        await self._send(after.guild, "server", embed)

    # ── Voice events ───────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if before.channel == after.channel:
            return

        if before.channel is None and after.channel is not None:
            embed = discord.Embed(title="Joined Voice",
                                  color=discord.Color.green())
            embed.set_author(name=str(member),
                             icon_url=member.display_avatar.url)
            embed.add_field(name="User", value=member.mention, inline=True)
            embed.add_field(name="Channel",
                            value=after.channel.mention,
                            inline=True)

        elif after.channel is None and before.channel is not None:
            embed = discord.Embed(title="Left Voice",
                                  color=discord.Color.red())
            embed.set_author(name=str(member),
                             icon_url=member.display_avatar.url)
            embed.add_field(name="User", value=member.mention, inline=True)
            embed.add_field(name="Channel",
                            value=before.channel.mention,
                            inline=True)

        elif before.channel is not None and after.channel is not None:
            embed = discord.Embed(title="Moved Voice",
                                  color=discord.Color.blurple())
            embed.set_author(name=str(member),
                             icon_url=member.display_avatar.url)
            embed.add_field(name="User", value=member.mention, inline=True)
            embed.add_field(name="From",
                            value=before.channel.mention,
                            inline=True)
            embed.add_field(name="To",
                            value=after.channel.mention,
                            inline=True)

        else:
            return

        embed.set_footer(text=f"User ID: {member.id}")
        await self._send(member.guild, "voice", embed)


async def setup(bot: CoreBot) -> None:
    await bot.add_cog(Logs(bot))
