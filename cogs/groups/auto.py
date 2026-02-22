"""
cogs/groups/auto.py — Auto role command group
cc auto role <@member|ID|name>    (alias: cc ar)
cc auto role bot <@bot|ID|name>   (alias: cc arb)
"""

import discord
from discord.ext import commands
from converters import RoleConverter



class Auto(commands.Cog, name="Auto"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Group ──────────────────────────────────────────────────────────────
    @commands.group(name="auto", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def auto(self, ctx: commands.Context):
        """Auto role group. Subcommands: role, rolebot"""
        guild_data = await ctx.bot.db.load(ctx.guild.id)
        ar = guild_data["auto_role"]
        member_role = ctx.guild.get_role(ar["member"]) if ar["member"] else None
        bot_role = ctx.guild.get_role(ar["bot"]) if ar["bot"] else None
        await ctx.send(
            f"**Auto Role Settings**\n"
            f"Member Role: {member_role.mention if member_role else 'Not set'}\n"
            f"Bot Role: {bot_role.mention if bot_role else 'Not set'}\n\n"
            f"Set with: `cc ar <@role|ID|name>` · `cc arb <@role|ID|name>`\n"
            f"Remove with: `cc ar clear` · `cc arb clear`"
        )

    # ── cc auto role / cc ar ───────────────────────────────────────────────
    @auto.command(name="role", aliases=["r"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def auto_role(self, ctx: commands.Context, *, target: str):
        """
        Set the auto role assigned to new members.
        Usage: cc ar <@role|role ID|role name>
               cc ar clear
        """
        if target.lower() == "clear":
            await ctx.bot.db.set(ctx.guild.id, ["auto_role", "member"], None)
            return await ctx.send("✓ Member auto role cleared.")

        role = await RoleConverter().convert(ctx, target)

        if role >= ctx.guild.me.top_role:
            return await ctx.send("✕ I can't assign a role that's higher than or equal to my top role.")

        await ctx.bot.db.set(ctx.guild.id, ["auto_role", "member"], role.id)
        await ctx.send(f"✓ Members will now receive {role.mention} when they join.")

    # ── cc auto rolebot / cc arb ───────────────────────────────────────────
    @auto.command(name="rolebot", aliases=["rb"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def auto_role_bot(self, ctx: commands.Context, *, target: str):
        """
        Set the auto role assigned to bots when they join.
        Usage: cc arb <@role|role ID|role name>
               cc arb clear
        """
        if target.lower() == "clear":
            await ctx.bot.db.set(ctx.guild.id, ["auto_role", "bot"], None)
            return await ctx.send("✓ Bot auto role cleared.")

        role = await RoleConverter().convert(ctx, target)

        if role >= ctx.guild.me.top_role:
            return await ctx.send("✕ I can't assign a role that's higher than or equal to my top role.")

        await ctx.bot.db.set(ctx.guild.id, ["auto_role", "bot"], role.id)
        await ctx.send(f"✓ Bots will now receive {role.mention} when they join.")


# ── Top-level alias cog ────────────────────────────────────────────────────────

class AutoAliases(commands.Cog, name="AutoAliases"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="ar")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def ar(self, ctx: commands.Context, *, target: str):
        """Alias: cc auto role"""
        await ctx.invoke(self.bot.get_command("auto role"), target=target)

    @commands.command(name="arb")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def arb(self, ctx: commands.Context, *, target: str):
        """Alias: cc auto rolebot"""
        await ctx.invoke(self.bot.get_command("auto rolebot"), target=target)


async def setup(bot: commands.Bot):
    await bot.add_cog(Auto(bot))
    await bot.add_cog(AutoAliases(bot))