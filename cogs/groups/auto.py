import discord
from discord.ext import commands
from converters import RoleConverter


class Auto(commands.Cog, name="Auto"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── cc auto ────────────────────────────────────────────────────────────

    @commands.group(name="auto", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def auto(self, ctx: commands.Context):
        guild_data = await ctx.bot.db.load(ctx.guild.id)
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
    async def auto_role(self, ctx: commands.Context, *, target: str):
        if target.lower() == "clear":
            await ctx.bot.db.set(ctx.guild.id, ["auto_role", "member"], None)
            return await ctx.send("✓ Member auto role cleared.")
        role = await RoleConverter().convert(ctx, target)
        if role >= ctx.guild.me.top_role:
            return await ctx.send(
                "✕ That role is higher than or equal to my top role.")
        await ctx.bot.db.set(ctx.guild.id, ["auto_role", "member"], role.id)
        await ctx.send(f"✓ Members will receive {role.mention} when they join."
                       )

    # ── cc auto rolebot / cc arb ───────────────────────────────────────────

    @auto.command(name="rolebot", aliases=["rb"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def auto_role_bot(self, ctx: commands.Context, *, target: str):
        if target.lower() == "clear":
            await ctx.bot.db.set(ctx.guild.id, ["auto_role", "bot"], None)
            return await ctx.send("✓ Bot auto role cleared.")
        role = await RoleConverter().convert(ctx, target)
        if role >= ctx.guild.me.top_role:
            return await ctx.send(
                "✕ That role is higher than or equal to my top role.")
        await ctx.bot.db.set(ctx.guild.id, ["auto_role", "bot"], role.id)
        await ctx.send(f"✓ Bots will receive {role.mention} when they join.")

    # ── Reaction Roles ─────────────────────────────────────────────────────

    @commands.group(name="rr", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def rr(self, ctx: commands.Context):
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
                     *, target: str):
        """Bind an emoji on a message to a role. cc rr add <msg_id> <emoji> <role>"""
        role = await RoleConverter().convert(ctx, target)
        if role >= ctx.guild.me.top_role:
            return await ctx.send(
                "✕ That role is higher than or equal to my top role.")

        # Resolve the message from any channel in the guild
        msg = None
        for channel in ctx.guild.text_channels:
            try:
                msg = await channel.fetch_message(message_id)
                break
            except (discord.NotFound, discord.Forbidden):
                continue

        if not msg:
            return await ctx.send(
                "✕ Message not found. Make sure the ID is correct and I can see that channel."
            )

        # Add the reaction to the message
        try:
            await msg.add_reaction(emoji)
        except discord.HTTPException:
            return await ctx.send(
                "✕ Invalid emoji or I couldn't add that reaction.")

        # Save to db
        data = await ctx.bot.db.load(ctx.guild.id)
        data["reaction_roles"].setdefault(str(message_id), {})[emoji] = role.id
        await ctx.bot.db.save(ctx.guild.id, data)

        await ctx.send(f"✓ {emoji} on message `{message_id}` → {role.mention}")

    @rr.command(name="remove")
    @commands.has_permissions(manage_roles=True)
    async def rr_remove(self, ctx: commands.Context, message_id: int,
                        emoji: str):
        """Remove an emoji→role binding. cc rr remove <msg_id> <emoji>"""
        data = await ctx.bot.db.load(ctx.guild.id)
        msg_map = data["reaction_roles"].get(str(message_id), {})

        if emoji not in msg_map:
            return await ctx.send(
                "✕ No binding found for that emoji on that message.")

        del msg_map[emoji]
        if not msg_map:
            del data["reaction_roles"][str(message_id)]
        else:
            data["reaction_roles"][str(message_id)] = msg_map

        await ctx.bot.db.save(ctx.guild.id, data)
        await ctx.send(
            f"✓ Removed binding for {emoji} on message `{message_id}`.")

    @rr.command(name="clear")
    @commands.has_permissions(manage_roles=True)
    async def rr_clear(self, ctx: commands.Context, message_id: int):
        """Remove all emoji→role bindings for a message. cc rr clear <msg_id>"""
        data = await ctx.bot.db.load(ctx.guild.id)
        if str(message_id) not in data["reaction_roles"]:
            return await ctx.send("✕ No reaction roles set for that message.")
        del data["reaction_roles"][str(message_id)]
        await ctx.bot.db.save(ctx.guild.id, data)
        await ctx.send(
            f"✓ Cleared all reaction roles for message `{message_id}`.")

    @rr.command(name="list")
    @commands.has_permissions(manage_roles=True)
    async def rr_list(self, ctx: commands.Context):
        """List all reaction role bindings in this server."""
        data = await ctx.bot.db.load(ctx.guild.id)
        rr = data.get("reaction_roles", {})

        if not rr:
            return await ctx.send("✕ No reaction roles configured.")

        embed = discord.Embed(title="Reaction Roles",
                              color=discord.Color.blurple())
        for msg_id, mappings in rr.items():
            lines = []
            for emoji, role_id in mappings.items():
                role = ctx.guild.get_role(role_id)
                lines.append(
                    f"{emoji} → {role.mention if role else f'Unknown ({role_id})'}"
                )
            embed.add_field(
                name=f"Message `{msg_id}`",
                value="\n".join(lines),
                inline=False,
            )
        await ctx.send(embed=embed)

    # ── Reaction role event listeners ──────────────────────────────────────

    async def _get_rr_map(self, guild_id: int, message_id: int) -> dict:
        data = await self.bot.db.load(guild_id)
        return data.get("reaction_roles", {}).get(str(message_id), {})

    @commands.Cog.listener()
    async def on_raw_reaction_add(self,
                                  payload: discord.RawReactionActionEvent):
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
    async def on_raw_reaction_remove(self,
                                     payload: discord.RawReactionActionEvent):
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

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="ar")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def ar(self, ctx: commands.Context, *, target: str):
        await ctx.invoke(self.bot.get_command("auto role"), target=target)

    @commands.command(name="arb")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def arb(self, ctx: commands.Context, *, target: str):
        await ctx.invoke(self.bot.get_command("auto rolebot"), target=target)


async def setup(bot: commands.Bot):
    await bot.add_cog(Auto(bot))
    await bot.add_cog(AutoAliases(bot))
