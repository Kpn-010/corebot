from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from converters import RoleConverter

if TYPE_CHECKING:
    from bot import CoreBot


class Auto(commands.Cog, name="Auto"):

    def __init__(self, bot: CoreBot) -> None:
        self.bot = bot

    # ── cc auto ────────────────────────────────────────────────────────────

    @commands.group(name="auto", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def auto(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None
        guild_data = await self.bot.db.load(ctx.guild.id)
        ar = guild_data["auto_role"]
        rr = guild_data.get("reaction_roles", {})

        member_role = ctx.guild.get_role(
            ar["member"]) if ar["member"] else None
        bot_role = ctx.guild.get_role(ar["bot"]) if ar["bot"] else None

        embed = discord.Embed(title="Auto Role Settings",
                              color=discord.Color.blurple())
        embed.add_field(
            name="Member Auto Role",
            value=member_role.mention if member_role else "Not set",
            inline=True,
        )
        embed.add_field(
            name="Bot Auto Role",
            value=bot_role.mention if bot_role else "Not set",
            inline=True,
        )

        if rr:
            lines = []
            for msg_id, mappings in rr.items():
                for emoji, role_id in mappings.items():
                    role = ctx.guild.get_role(role_id)
                    role_str = role.mention if role else f"Unknown ({role_id})"
                    lines.append(f"{emoji} → {role_str} (msg `{msg_id}`)")
            embed.add_field(
                name=f"Reaction Roles ({len(lines)})",
                value="\n".join(lines[:10]) +
                (" ..." if len(lines) > 10 else ""),
                inline=False,
            )
        else:
            embed.add_field(name="Reaction Roles",
                            value="None configured",
                            inline=False)

        embed.set_footer(
            text=
            "cc ar  •  cc arb  •  cc rr add  •  cc rr remove  •  cc rr list")
        await ctx.send(embed=embed)

    # ── cc auto role / cc ar ───────────────────────────────────────────────

    @auto.command(name="role", aliases=["r"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def auto_role(self, ctx: commands.Context, *, target: str) -> None:
        assert ctx.guild is not None
        if target.lower() == "clear":
            await self.bot.db.set(ctx.guild.id, ["auto_role", "member"], None)
            await ctx.send("✓ Member auto role cleared.")
            return
        role = await RoleConverter().convert(ctx, target)
        if role >= ctx.guild.me.top_role:
            await ctx.send(
                "✕ That role is higher than or equal to my top role.")
            return
        await self.bot.db.set(ctx.guild.id, ["auto_role", "member"], role.id)
        await ctx.send(f"✓ Members will receive {role.mention} when they join."
                       )

    # ── cc auto rolebot / cc arb ───────────────────────────────────────────

    @auto.command(name="rolebot", aliases=["rb"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def auto_role_bot(self, ctx: commands.Context, *,
                            target: str) -> None:
        assert ctx.guild is not None
        if target.lower() == "clear":
            await self.bot.db.set(ctx.guild.id, ["auto_role", "bot"], None)
            await ctx.send("✓ Bot auto role cleared.")
            return
        role = await RoleConverter().convert(ctx, target)
        if role >= ctx.guild.me.top_role:
            await ctx.send(
                "✕ That role is higher than or equal to my top role.")
            return
        await self.bot.db.set(ctx.guild.id, ["auto_role", "bot"], role.id)
        await ctx.send(f"✓ Bots will receive {role.mention} when they join.")

    # ── Reaction Roles ─────────────────────────────────────────────────────

    @commands.group(name="rr", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def rr(self, ctx: commands.Context) -> None:
        await ctx.send(
            "Reaction role subcommands:\n"
            "`cc rr add <message_id> <emoji> <@role|ID|name>` — bind emoji to role\n"
            "`cc rr remove <message_id> <emoji>` — remove a binding\n"
            "`cc rr clear <message_id>` — remove all bindings for a message\n"
            "`cc rr list` — list all reaction role bindings")

    @rr.command(name="add")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True, add_reactions=True)
    async def rr_add(self, ctx: commands.Context, message_id: int, emoji: str,
                     *, target: str) -> None:
        """Bind an emoji on a message to a role. cc rr add <msg_id> <emoji> <role>"""
        assert ctx.guild is not None
        role = await RoleConverter().convert(ctx, target)
        if role >= ctx.guild.me.top_role:
            await ctx.send(
                "✕ That role is higher than or equal to my top role.")
            return

        msg = None
        for channel in ctx.guild.text_channels:
            try:
                msg = await channel.fetch_message(message_id)
                break
            except (discord.NotFound, discord.Forbidden):
                continue

        if not msg:
            await ctx.send(
                "✕ Message not found. Make sure the ID is correct and I can see that channel."
            )
            return

        try:
            await msg.add_reaction(emoji)
        except discord.HTTPException:
            await ctx.send("✕ Invalid emoji or I couldn't add that reaction.")
            return

        data = await self.bot.db.load(ctx.guild.id)
        data["reaction_roles"].setdefault(str(message_id), {})[emoji] = role.id
        await self.bot.db.save(ctx.guild.id, data)
        await ctx.send(f"✓ {emoji} on message `{message_id}` → {role.mention}")

    @rr.command(name="remove")
    @commands.has_permissions(manage_roles=True)
    async def rr_remove(self, ctx: commands.Context, message_id: int,
                        emoji: str) -> None:
        """Remove an emoji→role binding. cc rr remove <msg_id> <emoji>"""
        assert ctx.guild is not None
        data = await self.bot.db.load(ctx.guild.id)
        msg_map = data["reaction_roles"].get(str(message_id), {})

        if emoji not in msg_map:
            await ctx.send("✕ No binding found for that emoji on that message."
                           )
            return

        del msg_map[emoji]
        if not msg_map:
            del data["reaction_roles"][str(message_id)]
        else:
            data["reaction_roles"][str(message_id)] = msg_map

        await self.bot.db.save(ctx.guild.id, data)
        await ctx.send(
            f"✓ Removed binding for {emoji} on message `{message_id}`.")

    @rr.command(name="clear")
    @commands.has_permissions(manage_roles=True)
    async def rr_clear(self, ctx: commands.Context, message_id: int) -> None:
        """Remove all emoji→role bindings for a message. cc rr clear <msg_id>"""
        assert ctx.guild is not None
        data = await self.bot.db.load(ctx.guild.id)
        if str(message_id) not in data["reaction_roles"]:
            await ctx.send("✕ No reaction roles set for that message.")
            return
        del data["reaction_roles"][str(message_id)]
        await self.bot.db.save(ctx.guild.id, data)
        await ctx.send(
            f"✓ Cleared all reaction roles for message `{message_id}`.")

    @rr.command(name="list")
    @commands.has_permissions(manage_roles=True)
    async def rr_list(self, ctx: commands.Context) -> None:
        """List all reaction role bindings in this server."""
        assert ctx.guild is not None
        data = await self.bot.db.load(ctx.guild.id)
        rr = data.get("reaction_roles", {})

        if not rr:
            await ctx.send("✕ No reaction roles configured.")
            return

        embed = discord.Embed(title="Reaction Roles",
                              color=discord.Color.blurple())
        for msg_id, mappings in rr.items():
            lines = []
            for emoji, role_id in mappings.items():
                role = ctx.guild.get_role(role_id)
                lines.append(
                    f"{emoji} → {role.mention if role else f'Unknown ({role_id})'}"
                )
            embed.add_field(name=f"Message `{msg_id}`",
                            value="\n".join(lines),
                            inline=False)
        await ctx.send(embed=embed)

    # ── Reaction role event listeners ──────────────────────────────────────

    async def _get_rr_map(self, guild_id: int, message_id: int) -> dict:
        data = await self.bot.db.load(guild_id)
        return data.get("reaction_roles", {}).get(str(message_id), {})

    @commands.Cog.listener()
    async def on_raw_reaction_add(
            self, payload: discord.RawReactionActionEvent) -> None:
        assert self.bot.user is not None
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return
        rr_map = await self._get_rr_map(payload.guild_id, payload.message_id)
        if not rr_map:
            return

        emoji_str = str(payload.emoji)
        role_id = rr_map.get(emoji_str)
        if not role_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        role = guild.get_role(role_id)
        member = guild.get_member(payload.user_id)
        if role and member:
            try:
                await member.add_roles(role, reason="Reaction Role")
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(
            self, payload: discord.RawReactionActionEvent) -> None:
        assert self.bot.user is not None
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return
        rr_map = await self._get_rr_map(payload.guild_id, payload.message_id)
        if not rr_map:
            return

        emoji_str = str(payload.emoji)
        role_id = rr_map.get(emoji_str)
        if not role_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        role = guild.get_role(role_id)
        member = guild.get_member(payload.user_id)
        if role and member:
            try:
                await member.remove_roles(role, reason="Reaction Role removed")
            except discord.Forbidden:
                pass


# ── Top-level alias cog ────────────────────────────────────────────────────────


class AutoAliases(commands.Cog, name="AutoAliases"):

    def __init__(self, bot: CoreBot) -> None:
        self.bot = bot

    @commands.command(name="ar")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def ar(self, ctx: commands.Context, *, target: str) -> None:
        # Fetch the cog directly and call the callback to avoid Command[CogT]
        # invariance issues that arise from ctx.invoke with a looked-up command.
        auto_cog = self.bot.cogs.get("Auto")
        if isinstance(auto_cog, Auto):
            await auto_cog.auto_role(ctx, target=target)

    @commands.command(name="arb")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def arb(self, ctx: commands.Context, *, target: str) -> None:
        auto_cog = self.bot.cogs.get("Auto")
        if isinstance(auto_cog, Auto):
            await auto_cog.auto_role_bot(ctx, target=target)


async def setup(bot: CoreBot) -> None:
    await bot.add_cog(Auto(bot))
    await bot.add_cog(AutoAliases(bot))
