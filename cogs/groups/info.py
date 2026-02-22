"""
cogs/groups/info.py — Info command group
Usage: cc info <subcommand>
Aliases: si, ui, ci, ri work as top-level shortcuts
"""

import discord
from discord.ext import commands
from converters import MemberConverter, RoleConverter, ChannelConverter


class Info(commands.Cog, name="Info"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Group ──────────────────────────────────────────────────────────────
    @commands.group(name="info", invoke_without_command=True)
    @commands.guild_only()
    async def info(self, ctx: commands.Context):
        """Info command group. Subcommands: server, user, channel, role"""
        await ctx.send(
            "Info subcommands:\n"
            "`cc info server` (alias: `cc si`)\n"
            "`cc info user [@user]` (alias: `cc ui`)\n"
            "`cc info channel [#channel]` (alias: `cc ci`)\n"
            "`cc info role [@role]` (alias: `cc ri`)"
        )

    # ── cc info server / cc si ─────────────────────────────────────────────
    @info.command(name="server", aliases=["sv"])
    async def server(self, ctx: commands.Context):
        """Show server information."""
        g = ctx.guild
        embed = discord.Embed(title=g.name, color=discord.Color.blurple())
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        if g.banner:
            embed.set_image(url=g.banner.url)

        embed.add_field(name="Owner", value=g.owner.mention if g.owner else "Unknown")
        embed.add_field(name="Members", value=f"{g.member_count:,}")
        embed.add_field(name="Boosts", value=f"Level {g.premium_tier} ({g.premium_subscription_count} boosts)")
        embed.add_field(name="Channels", value=f"{len(g.text_channels)} ·  {len(g.voice_channels)}")
        embed.add_field(name="Roles", value=str(len(g.roles)))
        embed.add_field(name="Emojis", value=str(len(g.emojis)))
        embed.add_field(name="Created", value=discord.utils.format_dt(g.created_at, style="D"), inline=False)
        embed.set_footer(text=f"Server ID: {g.id}")
        await ctx.send(embed=embed)

    # ── cc info user / cc ui ───────────────────────────────────────────────
    @info.command(name="user", aliases=["u"])
    async def user(self, ctx: commands.Context, *, target: str = None):
        """Show user information. Accepts @mention, ID, or name."""
        if target:
            member = await MemberConverter().convert(ctx, target)
        else:
            member = ctx.author

        roles = [r.mention for r in reversed(member.roles) if r != ctx.guild.default_role]
        perms = []
        if member.guild_permissions.administrator:
            perms.append("Administrator")
        elif member.guild_permissions.manage_guild:
            perms.append("Manage Server")

        color = member.color if member.color != discord.Color.default() else discord.Color.blurple()
        embed = discord.Embed(title=str(member), color=color)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=f"`{member.id}`")
        embed.add_field(name="Nickname", value=member.nick or "None")
        embed.add_field(name="Bot", value="✓" if member.bot else "✕")
        embed.add_field(name="Account Created", value=discord.utils.format_dt(member.created_at, style="D"))
        embed.add_field(name="Joined Server", value=discord.utils.format_dt(member.joined_at, style="D"))
        embed.add_field(name="Top Role", value=member.top_role.mention)
        embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles[:10]) + (" ..." if len(roles) > 10 else "") or "None", inline=False)
        if perms:
            embed.add_field(name="Key Permissions", value=", ".join(perms), inline=False)
        embed.set_footer(text=f"User ID: {member.id}")
        await ctx.send(embed=embed)

    # ── cc info channel / cc ci ────────────────────────────────────────────
    @info.command(name="channel", aliases=["ch"])
    async def channel(self, ctx: commands.Context, *, target: str = None):
        """Show channel information. Accepts #mention, ID, or name."""
        if target:
            channel = await ChannelConverter().convert(ctx, target)
        else:
            channel = ctx.channel

        embed = discord.Embed(title=f"#{channel.name}", color=discord.Color.blurple())
        embed.add_field(name="ID", value=f"`{channel.id}`")
        embed.add_field(name="Category", value=channel.category.name if channel.category else "None")
        embed.add_field(name="Topic", value=channel.topic or "None", inline=False)
        embed.add_field(name="Slowmode", value=f"{channel.slowmode_delay}s" if channel.slowmode_delay else "Off")
        embed.add_field(name="NSFW", value="✓" if channel.is_nsfw() else "✕")
        embed.add_field(name="Position", value=str(channel.position))
        embed.add_field(name="Created", value=discord.utils.format_dt(channel.created_at, style="D"))
        embed.set_footer(text=f"Channel ID: {channel.id}")
        await ctx.send(embed=embed)

    # ── cc info role / cc ri ───────────────────────────────────────────────
    @info.command(name="role", aliases=["r"])
    async def role(self, ctx: commands.Context, *, target: str = None):
        """Show role information. Accepts @mention, ID, or name."""
        if target:
            role = await RoleConverter().convert(ctx, target)
        else:
            return await ctx.send("✕ Please specify a role: `cc info role <@role|ID|name>`")

        key_perms = [
            perm.replace("_", " ").title()
            for perm, value in role.permissions
            if value and perm in (
                "administrator", "manage_guild", "manage_channels", "manage_roles",
                "kick_members", "ban_members", "manage_messages", "mention_everyone",
                "moderate_members"
            )
        ]
        embed = discord.Embed(title=f"@{role.name}", color=role.color)
        embed.add_field(name="ID", value=f"`{role.id}`")
        embed.add_field(name="Color", value=str(role.color))
        embed.add_field(name="Members", value=str(len(role.members)))
        embed.add_field(name="Mentionable", value="✓" if role.mentionable else "✕")
        embed.add_field(name="Hoisted", value="✓" if role.hoist else "✕")
        embed.add_field(name="Position", value=str(role.position))
        embed.add_field(name="Created", value=discord.utils.format_dt(role.created_at, style="D"))
        if key_perms:
            embed.add_field(name="Key Permissions", value=", ".join(key_perms), inline=False)
        embed.set_footer(text=f"Role ID: {role.id}")
        await ctx.send(embed=embed)


# ── Top-level alias commands (cc si, cc ui, cc ci, cc ri) ──────────────────────

class InfoAliases(commands.Cog, name="InfoAliases"):
    """Standalone aliases for info subcommands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="si")
    @commands.guild_only()
    async def si(self, ctx: commands.Context):
        """Alias for cc info server"""
        cmd = self.bot.get_command("info server")
        await ctx.invoke(cmd)

    @commands.command(name="ui")
    @commands.guild_only()
    async def ui(self, ctx: commands.Context, *, target: str = None):
        """Alias for cc info user"""
        cmd = self.bot.get_command("info user")
        await ctx.invoke(cmd, target=target)

    @commands.command(name="ci")
    @commands.guild_only()
    async def ci(self, ctx: commands.Context, *, target: str = None):
        """Alias for cc info channel"""
        cmd = self.bot.get_command("info channel")
        await ctx.invoke(cmd, target=target)

    @commands.command(name="ri")
    @commands.guild_only()
    async def ri(self, ctx: commands.Context, *, target: str = None):
        """Alias for cc info role"""
        cmd = self.bot.get_command("info role")
        await ctx.invoke(cmd, target=target)


async def setup(bot: commands.Bot):
    await bot.add_cog(Info(bot))
    await bot.add_cog(InfoAliases(bot))