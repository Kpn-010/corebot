"""
converters.py — Universal resolvers for member, role, and channel.
Each function accepts: @mention, ID (int or str), or display name.
"""
import re
import discord
from discord.ext import commands


async def resolve_member(ctx: commands.Context,
                         value: str) -> discord.Member | None:
    """Resolve a member from a mention, user ID, username, or display name."""
    guild = ctx.guild
    if not guild:
        return None

    # Strip mention formatting
    mention_match = re.match(r"<@!?(\d+)>", value)
    if mention_match:
        value = mention_match.group(1)

    # Try ID
    if value.isdigit():
        member = guild.get_member(int(value))
        if member:
            return member
        try:
            return await guild.fetch_member(int(value))
        except discord.NotFound:
            return None

    # Try name (case-insensitive display name or username)
    value_lower = value.lower()
    return discord.utils.find(
        lambda m: m.display_name.lower() == value_lower or m.name.lower() ==
        value_lower,
        guild.members,
    )


async def resolve_role(ctx: commands.Context,
                       value: str) -> discord.Role | None:
    """Resolve a role from a mention, role ID, or role name."""
    guild = ctx.guild
    if not guild:
        return None

    mention_match = re.match(r"<@&(\d+)>", value)
    if mention_match:
        value = mention_match.group(1)

    if value.isdigit():
        role = guild.get_role(int(value))
        if role:
            return role

    value_lower = value.lower()
    return discord.utils.find(lambda r: r.name.lower() == value_lower,
                              guild.roles)


async def resolve_channel(ctx: commands.Context,
                          value: str) -> discord.TextChannel | None:
    """Resolve a text channel from a mention, channel ID, or channel name."""
    guild = ctx.guild
    if not guild:
        return None

    mention_match = re.match(r"<#(\d+)>", value)
    if mention_match:
        value = mention_match.group(1)

    if value.isdigit():

        channel = guild.get_channel(int(value))
        if isinstance(channel, discord.TextChannel):
            return channel

    value_lower = value.lower().lstrip("#")

    result = discord.utils.find(
        lambda c: isinstance(c, discord.TextChannel) and c.name.lower() ==
        value_lower,
        guild.channels,
    )
    return result if isinstance(result, discord.TextChannel) else None


class MemberConverter(commands.Converter):

    async def convert(self, ctx: commands.Context,
                      argument: str) -> discord.Member:
        member = await resolve_member(ctx, argument)
        if member is None:
            raise commands.BadArgument(f"Member `{argument}` not found.")
        return member


class RoleConverter(commands.Converter):

    async def convert(self, ctx: commands.Context,
                      argument: str) -> discord.Role:
        role = await resolve_role(ctx, argument)
        if role is None:
            raise commands.BadArgument(f"Role `{argument}` not found.")
        return role


class ChannelConverter(commands.Converter):

    async def convert(self, ctx: commands.Context,
                      argument: str) -> discord.TextChannel:
        channel = await resolve_channel(ctx, argument)
        if channel is None:
            raise commands.BadArgument(f"Channel `{argument}` not found.")
        return channel
