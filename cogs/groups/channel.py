"""
cogs/groups/channel.py — Channel management group
cc channel create {name} [{access: @role|ID|name ...}]
cc channel edit {name} [{new_name}] [{access: @role|ID|name ...}]
cc channel delete {name}
"""

import discord
from discord.ext import commands
from converters import resolve_channel, resolve_role
import re


def _parse_roles(ctx: commands.Context, args: list[str]):
    """Split args into (name_parts, role_tokens). Role tokens are mentions/IDs/names after '--'."""
    if "--" in args:
        idx = args.index("--")
        return args[:idx], args[idx + 1:]
    return args, []


async def _resolve_roles(ctx: commands.Context, tokens: list[str]) -> list[discord.Role]:
    roles = []
    for token in tokens:
        role = await resolve_role(ctx, token)
        if role:
            roles.append(role)
    return roles


def _overwrites_for_roles(guild: discord.Guild, roles: list[discord.Role]) -> dict:
    """Build permission overwrites: deny @everyone, allow specified roles."""
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False)
    }
    for role in roles:
        overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
    return overwrites


class Channel(commands.Cog, name="Channel"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Group ──────────────────────────────────────────────────────────────
    @commands.group(name="channel", aliases=["ch"], invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def channel(self, ctx: commands.Context):
        """Channel management. Subcommands: create, edit, delete"""
        await ctx.send(
            "**Channel Commands:**\n"
            "`cc channel create <name> [-- @role|ID|name ...]` — Create a channel\n"
            "`cc channel edit <name> <new_name> [-- @role|ID|name ...]` — Edit a channel\n"
            "`cc channel delete <name>` — Delete a channel\n\n"
            "Use `--` to separate the name from role access list.\n"
            "Example: `cc channel create secret-chat -- @Mods admins`"
        )

    # ── cc channel create ──────────────────────────────────────────────────
    @channel.command(name="create")
    @commands.bot_has_permissions(manage_channels=True)
    async def ch_create(self, ctx: commands.Context, *, args: str):
        """
        Create a text channel.
        Usage: cc channel create <name> [-- @role|ID|name ...]
        If roles are given after --, only those roles can see the channel.
        """
        parts = args.split(" -- ", 1)
        name = parts[0].strip().lower().replace(" ", "-")
        role_tokens = parts[1].split() if len(parts) > 1 else []

        if not name:
            return await ctx.send("✕ Please provide a channel name.")

        roles = await _resolve_roles(ctx, role_tokens) if role_tokens else []
        overwrites = _overwrites_for_roles(ctx.guild, roles) if roles else {}

        channel = await ctx.guild.create_text_channel(name, overwrites=overwrites if overwrites else None)

        access_str = ", ".join(r.mention for r in roles) if roles else "everyone"
        await ctx.send(f"✓ Created {channel.mention} with access: {access_str}")

    # ── cc channel edit ────────────────────────────────────────────────────
    @channel.command(name="edit")
    @commands.bot_has_permissions(manage_channels=True)
    async def ch_edit(self, ctx: commands.Context, *, args: str):
        """
        Edit a channel's name and/or access.
        Usage: cc channel edit <channel> <new_name> [-- @role|ID|name ...]
        """
        parts = args.split(" -- ", 1)
        name_parts = parts[0].strip().split(None, 1)
        role_tokens = parts[1].split() if len(parts) > 1 else []

        if not name_parts:
            return await ctx.send("✕ Usage: `cc channel edit <channel> <new_name> [-- roles]`")

        channel_token = name_parts[0]
        channel = await resolve_channel(ctx, channel_token)
        if not channel:
            return await ctx.send(f"✕ Channel `{channel_token}` not found.")

        kwargs = {}
        if len(name_parts) > 1:
            kwargs["name"] = name_parts[1].strip().lower().replace(" ", "-")

        roles = await _resolve_roles(ctx, role_tokens) if role_tokens else None

        if roles is not None:
            kwargs["overwrites"] = _overwrites_for_roles(ctx.guild, roles)

        await channel.edit(**kwargs)

        changes = []
        if "name" in kwargs:
            changes.append(f"name → `{kwargs['name']}`")
        if roles is not None:
            access_str = ", ".join(r.mention for r in roles) if roles else "everyone"
            changes.append(f"access → {access_str}")

        await ctx.send(f"✓ Edited {channel.mention}: {' | '.join(changes) if changes else 'no changes'}")

    # ── cc channel delete ──────────────────────────────────────────────────
    @channel.command(name="delete")
    @commands.bot_has_permissions(manage_channels=True)
    async def ch_delete(self, ctx: commands.Context, *, target: str):
        """
        Delete a channel.
        Usage: cc channel delete <#channel|ID|name>
        """
        channel = await resolve_channel(ctx, target)
        if not channel:
            return await ctx.send(f"✕ Channel `{target}` not found.")
        name = channel.name
        await channel.delete(reason=f"Deleted by {ctx.author}")
        await ctx.send(f"↻ Deleted channel `#{name}`.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Channel(bot))