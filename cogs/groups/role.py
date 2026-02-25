"""
cogs/groups/role.py — Role management group
cc role create <n> [color] [icon emoji/url]
cc role edit <@role|ID|name> [new_name] [color] [icon]
cc role delete <@role|ID|name>
cc role steal <emoji> [name]
"""

import re

import aiohttp
import discord
from discord.ext import commands

from converters import RoleConverter, resolve_role


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
            async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
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


class RoleInView(discord.ui.View):
    # Declared at class level so pyright knows the attribute exists.
    message: discord.Message

    def __init__(self, invoker: discord.Member | discord.User, pages: list,
                 make_embed) -> None:
        super().__init__(timeout=120)
        self.invoker = invoker
        self.pages = pages
        self.make_embed = make_embed
        self.page = 0
        self._sync()

    def _sync(self) -> None:
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page == len(self.pages) - 1

    async def _edit(self, interaction: discord.Interaction) -> None:
        self._sync()
        await interaction.response.edit_message(embed=self.make_embed(
            self.page),
                                                view=self)

    async def interaction_check(self,
                                interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.invoker.id:
            await interaction.response.send_message(
                "✕ This menu belongs to someone else.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        # Item[Self] does not expose .disabled — narrow to Button first.
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        try:
            await self.message.edit(view=self)
        except Exception:
            pass

    @discord.ui.button(label="←", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction,
                       button: discord.ui.Button) -> None:
        self.page -= 1
        await self._edit(interaction)

    @discord.ui.button(label="✕", style=discord.ButtonStyle.danger)
    async def close_btn(self, interaction: discord.Interaction,
                        button: discord.ui.Button) -> None:
        # interaction.message is Message | None — guard before calling .delete().
        if interaction.message is not None:
            await interaction.message.delete()

    @discord.ui.button(label="→", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction,
                       button: discord.ui.Button) -> None:
        self.page += 1
        await self._edit(interaction)


class Role(commands.Cog, name="Role"):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Group ──────────────────────────────────────────────────────────────
    @commands.group(name="role", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def role(self, ctx: commands.Context) -> None:
        """Role management group."""
        await ctx.send(
            "**Role Commands:**\n"
            "`cc role add <@member> <@role>` — Give a role to a member\n"
            "`cc role remove <@member> <@role>` — Remove a role from a member\n"
            "`cc role in [role]` — List members in a role\n"
            "`cc role create <n> [#hex] [emoji/url]` — Create a role\n"
            "`cc role edit <role> [new_name] [#hex] [emoji/url]` — Edit a role\n"
            "`cc role delete <role>` — Delete a role\n"
            "`cc role steal <emoji> [name]` — Add an emoji from another server\n"
        )

    # ── cc role add ────────────────────────────────────────────────────────
    @role.command(name="add")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_add(self, ctx: commands.Context, member: discord.Member, *,
                       target: str) -> None:
        """Give a role to a member. Usage: cc role add <@member|ID> <@role|ID|name>"""
        assert ctx.guild is not None
        role = await RoleConverter().convert(ctx, target)
        if role >= ctx.guild.me.top_role:
            await ctx.send(
                "✕ That role is higher than or equal to my top role.")
            return
        if role in member.roles:
            await ctx.send(f"✕ {member.mention} already has {role.mention}.")
            return
        await member.add_roles(role, reason=f"Role added by {ctx.author}")
        await ctx.send(f"✓ Gave {role.mention} to {member.mention}.")

    # ── cc role remove ─────────────────────────────────────────────────────
    @role.command(name="remove")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_remove(self, ctx: commands.Context, member: discord.Member,
                          *, target: str) -> None:
        """Remove a role from a member. Usage: cc role remove <@member|ID> <@role|ID|name>"""
        assert ctx.guild is not None
        role = await RoleConverter().convert(ctx, target)
        if role >= ctx.guild.me.top_role:
            await ctx.send(
                "✕ That role is higher than or equal to my top role.")
            return
        if role not in member.roles:
            await ctx.send(f"✕ {member.mention} does not have {role.mention}.")
            return
        await member.remove_roles(role, reason=f"Role removed by {ctx.author}")
        await ctx.send(f"✓ Removed {role.mention} from {member.mention}.")

    # ── cc role in ─────────────────────────────────────────────────────────
    @role.command(name="in")
    @commands.guild_only()
    async def role_in(self,
                      ctx: commands.Context,
                      *,
                      target: str = "everyone") -> None:
        """List members in a role. Usage: cc role in [role]"""
        assert ctx.guild is not None
        if target.lower() in ("everyone", "all", "@everyone"):
            members = ctx.guild.members
            role_name = "@everyone"
        else:
            role = await RoleConverter().convert(ctx, target)
            members = role.members
            role_name = role.name

        if not members:
            await ctx.send(f"✕ No members found in **{role_name}**.")
            return

        members = sorted(members, key=lambda m: m.display_name.lower())
        total = len(members)

        page_size = 20
        pages = [members[i:i + page_size] for i in range(0, total, page_size)]

        def make_embed(page_idx: int) -> discord.Embed:
            chunk = pages[page_idx]
            lines = [
                f"`{i + 1 + page_idx * page_size}.` {m.mention} — {m.display_name}"
                for i, m in enumerate(chunk)
            ]
            embed = discord.Embed(
                title=f"Members in {role_name}",
                description="\n".join(lines),
                color=discord.Color.blurple(),
            )
            embed.set_footer(
                text=
                f"{total} member(s) total  ⌁  Page {page_idx + 1} of {len(pages)}"
            )
            return embed

        if len(pages) == 1:
            await ctx.send(embed=make_embed(0))
            return

        view = RoleInView(ctx.author, pages, make_embed)
        msg = await ctx.send(embed=make_embed(0), view=view)
        view.message = msg

    # ── cc role create ─────────────────────────────────────────────────────
    @role.command(name="create")
    @commands.bot_has_permissions(manage_roles=True)
    async def role_create(self, ctx: commands.Context, *, args: str) -> None:
        """Create a role. Usage: cc role create <n> [#hex_color] [custom_emoji or URL]"""
        assert ctx.guild is not None
        parts = args.split()
        name_parts = []
        color = discord.Color.default()
        icon_bytes = None

        for i, part in enumerate(parts):
            c = _parse_color(part)
            if c is not None and name_parts:
                color = c
                remaining = parts[i + 1:]
                if remaining:
                    icon_bytes = await _get_emoji_image(ctx, remaining[0])
                break
            else:
                name_parts.append(part)

        name = " ".join(name_parts) if name_parts else parts[0]

        kwargs: dict = {"name": name, "color": color}
        if icon_bytes and "ROLE_ICONS" in ctx.guild.features:
            kwargs["display_icon"] = icon_bytes
        elif icon_bytes:
            await ctx.send(
                "! This server doesn't support role icons (requires level 2 boost). Role created without icon."
            )

        new_role = await ctx.guild.create_role(**kwargs)
        embed = discord.Embed(title="✓ Role Created", color=new_role.color)
        embed.add_field(name="Name", value=new_role.mention)
        embed.add_field(name="Color", value=str(new_role.color))
        embed.add_field(name="ID", value=f"`{new_role.id}`")
        await ctx.send(embed=embed)

    # ── cc role edit ───────────────────────────────────────────────────────
    @role.command(name="edit")
    @commands.bot_has_permissions(manage_roles=True)
    async def role_edit(self, ctx: commands.Context, *, args: str) -> None:
        """Edit an existing role. Usage: cc role edit <@role|ID|name> [new_name] [#hex] [emoji/url]"""
        assert ctx.guild is not None
        parts = args.split()
        if not parts:
            await ctx.send("✕ Please specify a role.")
            return

        role = await resolve_role(ctx, parts[0])
        if not role:
            await ctx.send(f"✕ Role `{parts[0]}` not found.")
            return

        remaining = parts[1:]
        new_name = None
        new_color = None
        icon_bytes = None

        for i, part in enumerate(remaining):
            c = _parse_color(part)
            if c is not None:
                new_color = c
                icon_token = remaining[i +
                                       1] if i + 1 < len(remaining) else None
                if icon_token:
                    icon_bytes = await _get_emoji_image(ctx, icon_token)
                break
            else:
                new_name = (new_name + " " +
                            part).strip() if new_name else part

        kwargs: dict = {}
        if new_name:
            kwargs["name"] = new_name
        if new_color is not None:
            kwargs["color"] = new_color
        if icon_bytes and "ROLE_ICONS" in ctx.guild.features:
            kwargs["display_icon"] = icon_bytes

        if not kwargs:
            await ctx.send(
                "✕ No changes provided. Specify a new name, color, or icon.")
            return

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
    async def role_delete(self, ctx: commands.Context, *, target: str) -> None:
        """Delete a role. Usage: cc role delete <@role|ID|name>"""
        assert ctx.guild is not None
        role = await resolve_role(ctx, target)
        if not role:
            await ctx.send(f"✕ Role `{target}` not found.")
            return
        if role >= ctx.guild.me.top_role:
            await ctx.send("✕ I can't delete a role above my own.")
            return

        name = role.name
        await role.delete(reason=f"Deleted by {ctx.author}")
        await ctx.send(f"↻ Deleted role `@{name}`.")

    # ── cc role steal <emoji> [name] ───────────────────────────────────────
    @role.command(name="steal")
    @commands.has_permissions(manage_emojis=True)
    @commands.bot_has_permissions(manage_emojis=True)
    async def role_steal(self,
                         ctx: commands.Context,
                         emoji_token: str,
                         *,
                         name: str | None = None) -> None:
        """Steal an emoji from another server. Usage: cc role steal <emoji> [name]"""
        assert ctx.guild is not None
        custom_match = re.match(r"<(a?):(\w+):(\d+)>", emoji_token)
        if not custom_match:
            await ctx.send(
                "✕ Please provide a custom emoji (not a built-in one). Example: `cc role steal :emoji:`"
            )
            return

        animated = bool(custom_match.group(1))
        emoji_name = name or custom_match.group(2)
        emoji_id = int(custom_match.group(3))
        fmt = "gif" if animated else "png"
        url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{fmt}"

        img_bytes = await _fetch_bytes(url)
        if not img_bytes:
            await ctx.send("✕ Failed to fetch the emoji image.")
            return

        try:
            new_emoji = await ctx.guild.create_custom_emoji(name=emoji_name,
                                                            image=img_bytes)
            await ctx.send(f"✓ Added emoji {new_emoji} as `:{new_emoji.name}:`"
                           )
        except discord.HTTPException as e:
            await ctx.send(f"✕ Failed to add emoji: {e}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Role(bot))
