"""
cogs/groups/role.py — Role management group
cc role create <n> [color] [icon emoji/url]
cc role edit <@role|ID|name> [new_name] [color] [icon]
cc role delete <@role|ID|name>
cc role steal <emoji> [name]
"""

import discord
from discord.ext import commands
from converters import resolve_role, RoleConverter
import re
import aiohttp
import io


def _parse_color(token: str) -> discord.Color | None:
    """Parse hex color like #FF5733 or FF5733."""
    token = token.lstrip("#")
    try:
        return discord.Color(int(token, 16))
    except (ValueError, TypeError):
        return None


async def _fetch_bytes(url: str) -> bytes | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.read()
    except Exception:
        return None


async def _get_emoji_image(ctx: commands.Context, token: str) -> bytes | None:
    """
    Try to resolve an emoji token to its image bytes.
    Supports: custom emoji <:name:id>, emoji URL, or attachment.
    """
    custom_match = re.match(r"<a?:\w+:(\d+)>", token)
    if custom_match:
        emoji_id = int(custom_match.group(1))
        animated = token.startswith("<a:")
        fmt = "gif" if animated else "png"
        url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{fmt}"
        return await _fetch_bytes(url)

    if token.startswith("http"):
        return await _fetch_bytes(token)

    return None


class Role(commands.Cog, name="Role"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Group ──────────────────────────────────────────────────────────────
    @commands.group(name="role", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def role(self, ctx: commands.Context):
        """Role management group."""
        await ctx.send(
            "**Role Commands:**\n"
            "`cc role create <n> [#hex] [emoji/url]` — Create a role\n"
            "`cc role edit <role> [new_name] [#hex] [emoji/url]` — Edit a role\n"
            "`cc role delete <role>` — Delete a role\n"
            "`cc role steal <emoji> [name]` — Add an emoji from another server\n"
        )

    # ── cc role create ─────────────────────────────────────────────────────
    @role.command(name="create")
    @commands.bot_has_permissions(manage_roles=True)
    async def role_create(self, ctx: commands.Context, *, args: str):
        """
        Create a role.
        Usage: cc role create <n> [#hex_color] [custom_emoji or URL]
        Example: cc role create Moderator #FF5733
        """
        parts = args.split()
        name_parts = []
        color = discord.Color.default()
        icon_bytes = None

        for i, part in enumerate(parts):
            c = _parse_color(part)
            if c is not None and not name_parts:
                # color before name? skip — only apply if we have a name
                pass
            if c is not None and name_parts:
                color = c
                # Check remaining for icon
                remaining = parts[i + 1:]
                if remaining:
                    icon_bytes = await _get_emoji_image(ctx, remaining[0])
                break
            else:
                name_parts.append(part)

        name = " ".join(name_parts) if name_parts else args.split()[0]

        kwargs = {"name": name, "color": color}
        if icon_bytes and "ROLE_ICONS" in ctx.guild.features:
            kwargs["display_icon"] = icon_bytes
        elif icon_bytes and "ROLE_ICONS" not in ctx.guild.features:
            await ctx.send("! This server doesn't support role icons (requires level 2 boost). Role created without icon.")

        new_role = await ctx.guild.create_role(**kwargs)
        embed = discord.Embed(title="✓ Role Created", color=new_role.color)
        embed.add_field(name="Name", value=new_role.mention)
        embed.add_field(name="Color", value=str(new_role.color))
        embed.add_field(name="ID", value=f"`{new_role.id}`")
        await ctx.send(embed=embed)

    # ── cc role edit ───────────────────────────────────────────────────────
    @role.command(name="edit")
    @commands.bot_has_permissions(manage_roles=True)
    async def role_edit(self, ctx: commands.Context, *, args: str):
        """
        Edit an existing role.
        Usage: cc role edit <@role|ID|name> [new_name] [#hex] [emoji/url]
        """
        parts = args.split()
        if not parts:
            return await ctx.send("✕ Please specify a role.")

        # First token is the target role
        role = await resolve_role(ctx, parts[0])
        if not role:
            return await ctx.send(f"✕ Role `{parts[0]}` not found.")

        remaining = parts[1:]
        new_name = None
        new_color = None
        icon_bytes = None

        for i, part in enumerate(remaining):
            c = _parse_color(part)
            if c is not None:
                new_color = c
                icon_token = remaining[i + 1] if i + 1 < len(remaining) else None
                if icon_token:
                    icon_bytes = await _get_emoji_image(ctx, icon_token)
                break
            else:
                new_name = (new_name + " " + part).strip() if new_name else part

        kwargs = {}
        if new_name:
            kwargs["name"] = new_name
        if new_color is not None:
            kwargs["color"] = new_color
        if icon_bytes and "ROLE_ICONS" in ctx.guild.features:
            kwargs["display_icon"] = icon_bytes

        if not kwargs:
            return await ctx.send("✕ No changes provided. Specify a new name, color, or icon.")

        await role.edit(**kwargs)
        changes = []
        if "name" in kwargs:
            changes.append(f"name → `{kwargs['name']}`")
        if "color" in kwargs:
            changes.append(f"color → `{kwargs['color']}`")
        if "display_icon" in kwargs:
            changes.append("icon updated")

        await ctx.send(f"✓ Edited {role.mention}: {' | '.join(changes)}")

    # ── cc role delete ─────────────────────────────────────────────────────
    @role.command(name="delete")
    @commands.bot_has_permissions(manage_roles=True)
    async def role_delete(self, ctx: commands.Context, *, target: str):
        """
        Delete a role.
        Usage: cc role delete <@role|ID|name>
        """
        role = await resolve_role(ctx, target)
        if not role:
            return await ctx.send(f"✕ Role `{target}` not found.")
        if role >= ctx.guild.me.top_role:
            return await ctx.send("✕ I can't delete a role above my own.")

        name = role.name
        await role.delete(reason=f"Deleted by {ctx.author}")
        await ctx.send(f"↻ Deleted role `@{name}`.")

    # ── cc role steal <emoji> [name] ───────────────────────────────────────
    @role.command(name="steal")
    @commands.has_permissions(manage_emojis=True)
    @commands.bot_has_permissions(manage_emojis=True)
    async def role_steal(self, ctx: commands.Context, emoji_token: str, *, name: str = None):
        """
        Steal an emoji from another server and add it to this one.
        Usage: cc role steal <emoji> [name]
        The emoji can be a custom emoji from any server the bot is in.
        """
        custom_match = re.match(r"<(a?):(\w+):(\d+)>", emoji_token)
        if not custom_match:
            return await ctx.send("✕ Please provide a custom emoji (not a built-in one). Example: `cc role steal :emoji:`")

        animated = bool(custom_match.group(1))
        emoji_name = name or custom_match.group(2)
        emoji_id = int(custom_match.group(3))
        fmt = "gif" if animated else "png"
        url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{fmt}"

        img_bytes = await _fetch_bytes(url)
        if not img_bytes:
            return await ctx.send("✕ Failed to fetch the emoji image.")

        try:
            new_emoji = await ctx.guild.create_custom_emoji(name=emoji_name, image=img_bytes)
            await ctx.send(f"✓ Added emoji {new_emoji} as `:{new_emoji.name}:`")
        except discord.HTTPException as e:
            await ctx.send(f"✕ Failed to add emoji: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Role(bot))