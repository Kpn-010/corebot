import discord
from discord.ext import commands


# All modules with their commands defined statically.
# Each entry: (title, description, syntax, example, permissions, aliases)
MODULES = [
    {
        "group": "Utils",
        "commands": [
            {
                "title": "Ping",
                "description": "Check the bot's response latency.",
                "syntax": "cc ping",
                "example": "cc ping",
                "permissions": "None",
                "aliases": "None",
            },
            {
                "title": "Uptime",
                "description": "Show how long the bot has been running.",
                "syntax": "cc uptime",
                "example": "cc uptime",
                "permissions": "None",
                "aliases": "ut",
            },
            {
                "title": "Avatar",
                "description": "Show a user's avatar. Accepts @mention, ID, or name.",
                "syntax": "cc avatar [@user]",
                "example": "cc avatar @john",
                "permissions": "None",
                "aliases": "av",
            },
            {
                "title": "Banner",
                "description": "Show a user's banner. Accepts @mention, ID, or name.",
                "syntax": "cc banner [@user]",
                "example": "cc banner @john",
                "permissions": "None",
                "aliases": "None",
            },
            {
                "title": "Username",
                "description": "Show a user's username and display name info.",
                "syntax": "cc username [@user]",
                "example": "cc username @john",
                "permissions": "None",
                "aliases": "un",
            },
            {
                "title": "Say",
                "description": "Make the bot send a message. Optional channel target at the end.",
                "syntax": "cc say <message> [#channel]",
                "example": "cc say hello everyone #general",
                "permissions": "Manage Messages",
                "aliases": "None",
            },
        ],
    },
    {
        "group": "Info Group",
        "commands": [
            {
                "title": "Server Info",
                "description": "Display information about the current server.",
                "syntax": "cc info server",
                "example": "cc si",
                "permissions": "None",
                "aliases": "si",
            },
            {
                "title": "User Info",
                "description": "Display information about a user.",
                "syntax": "cc info user [@user]",
                "example": "cc ui @john",
                "permissions": "None",
                "aliases": "ui",
            },
            {
                "title": "Channel Info",
                "description": "Display information about a channel.",
                "syntax": "cc info channel [#channel]",
                "example": "cc ci #general",
                "permissions": "None",
                "aliases": "ci",
            },
            {
                "title": "Role Info",
                "description": "Display information about a role.",
                "syntax": "cc info role <@role|ID|name>",
                "example": "cc ri @Moderator",
                "permissions": "None",
                "aliases": "ri",
            },
        ],
    },
    {
        "group": "Auto Group",
        "commands": [
            {
                "title": "Auto Role",
                "description": "Set the role automatically assigned to new members. Use `clear` to remove.",
                "syntax": "cc auto role <@role|ID|name>",
                "example": "cc ar @Member",
                "permissions": "Manage Roles",
                "aliases": "ar",
            },
            {
                "title": "Auto Role (Bot)",
                "description": "Set the role automatically assigned to bots when they join. Use `clear` to remove.",
                "syntax": "cc auto rolebot <@role|ID|name>",
                "example": "cc arb @Bots",
                "permissions": "Manage Roles",
                "aliases": "arb",
            },
        ],
    },
    {
        "group": "Welcome Group",
        "commands": [
            {
                "title": "Welcome Channel",
                "description": "Set the channel where welcome messages are sent. Use `clear` to remove.",
                "syntax": "cc welc ch <#channel|ID|name>",
                "example": "cc welc ch #welcome",
                "permissions": "Manage Guild",
                "aliases": "None",
            },
            {
                "title": "Welcome Message",
                "description": "Set the welcome message template. Start with `$em` for embed mode.\nVariables: `{user}` `{user.name}` `{user.id}` `{server}` `{count}` `{position}` `{invite}`\nEmbed tags: `{description <text>}` `{thumbnail}` `{author {user}}`",
                "syntax": "cc welc msg <template>",
                "example": "cc welc msg Welcome {user} to {server}!",
                "permissions": "Manage Guild",
                "aliases": "None",
            },
            {
                "title": "Welcome Test",
                "description": "Trigger a test welcome message for yourself.",
                "syntax": "cc welc test",
                "example": "cc welc test",
                "permissions": "Manage Guild",
                "aliases": "None",
            },
        ],
    },
    {
        "group": "Channel Group",
        "commands": [
            {
                "title": "Channel Create",
                "description": "Create a text channel. Use `--` to separate name from role access list.",
                "syntax": "cc channel create <name> [-- @role ...]",
                "example": "cc channel create secret -- @Mods",
                "permissions": "Manage Channels",
                "aliases": "None",
            },
            {
                "title": "Channel Edit",
                "description": "Edit a channel's name and/or role access. Use `--` before roles.",
                "syntax": "cc channel edit <channel> [new-name] [-- @role ...]",
                "example": "cc channel edit #old new-name -- @Mods",
                "permissions": "Manage Channels",
                "aliases": "None",
            },
            {
                "title": "Channel Delete",
                "description": "Delete a text channel.",
                "syntax": "cc channel delete <#channel|ID|name>",
                "example": "cc channel delete #old-chat",
                "permissions": "Manage Channels",
                "aliases": "None",
            },
        ],
    },
    {
        "group": "Role Group",
        "commands": [
            {
                "title": "Role Create",
                "description": "Create a role with optional color and icon.",
                "syntax": "cc role create <name> [#hex] [emoji/url]",
                "example": "cc role create Mod #FF5733",
                "permissions": "Manage Roles",
                "aliases": "None",
            },
            {
                "title": "Role Edit",
                "description": "Edit a role's name, color, or icon.",
                "syntax": "cc role edit <@role|ID|name> [new-name] [#hex] [emoji/url]",
                "example": "cc role edit @Mod SuperMod #00FF00",
                "permissions": "Manage Roles",
                "aliases": "None",
            },
            {
                "title": "Role Delete",
                "description": "Delete a role.",
                "syntax": "cc role delete <@role|ID|name>",
                "example": "cc role delete @OldRole",
                "permissions": "Manage Roles",
                "aliases": "None",
            },
            {
                "title": "Role Steal",
                "description": "Steal a custom emoji from another server and add it to this one.",
                "syntax": "cc role steal <:emoji:> [name]",
                "example": "cc role steal :cool: cool_emoji",
                "permissions": "Manage Emojis",
                "aliases": "None",
            },
        ],
    },
    {
        "group": "Moderation",
        "commands": [
            {
                "title": "Kick",
                "description": "Kick a member from the server.",
                "syntax": "cc kick <@|ID|name> [reason]",
                "example": "cc kick @john spamming",
                "permissions": "Kick Members",
                "aliases": "None",
            },
            {
                "title": "Ban",
                "description": "Ban a member from the server.",
                "syntax": "cc ban <@|ID|name> [reason]",
                "example": "cc ban @john rule violation",
                "permissions": "Ban Members",
                "aliases": "None",
            },
            {
                "title": "Unban",
                "description": "Unban a user by their ID.",
                "syntax": "cc unban <user_id> [reason]",
                "example": "cc unban 123456789",
                "permissions": "Ban Members",
                "aliases": "None",
            },
            {
                "title": "Timeout",
                "description": "Timeout a member. Duration: `10s` `5m` `2h` `1d` `1w` (max 28d).",
                "syntax": "cc timeout <@|ID|name> <duration> [reason]",
                "example": "cc timeout @john 10m spamming",
                "permissions": "Moderate Members",
                "aliases": "to",
            },
            {
                "title": "Untimeout",
                "description": "Remove a timeout from a member.",
                "syntax": "cc untimeout <@|ID|name>",
                "example": "cc untimeout @john",
                "permissions": "Moderate Members",
                "aliases": "uto",
            },
            {
                "title": "Purge",
                "description": "Bulk delete up to 100 messages. Optionally filter by user.",
                "syntax": "cc purge <amount> [@user]",
                "example": "cc purge 20 @john",
                "permissions": "Manage Messages",
                "aliases": "None",
            },
            {
                "title": "Slowmode",
                "description": "Set slowmode on the current channel. 0 to disable.",
                "syntax": "cc slowmode <seconds>",
                "example": "cc slowmode 5",
                "permissions": "Manage Channels",
                "aliases": "sm",
            },
            {
                "title": "Lock / Unlock",
                "description": "Lock or unlock a channel for @everyone.",
                "syntax": "cc lock [#channel]\ncc unlock [#channel]",
                "example": "cc lock #general",
                "permissions": "Manage Channels",
                "aliases": "None",
            },
            {
                "title": "Lockdown / Release",
                "description": "Lock or unlock ALL text channels in the server.",
                "syntax": "cc lockdown\ncc release",
                "example": "cc lockdown",
                "permissions": "Manage Channels",
                "aliases": "release / unlockdown",
            },
            {
                "title": "Warn",
                "description": "Warn a member. Warning is saved and DM'd to the user.",
                "syntax": "cc warn <@|ID|name> [reason]",
                "example": "cc warn @john rule 3 violation",
                "permissions": "Manage Messages",
                "aliases": "None",
            },
            {
                "title": "Warnings",
                "description": "View all warnings for a member.",
                "syntax": "cc warnings <@|ID|name>",
                "example": "cc warnings @john",
                "permissions": "Manage Messages",
                "aliases": "None",
            },
            {
                "title": "Warn Clean",
                "description": "Clear all or a specific warning from a member.",
                "syntax": "cc warnclean <@|ID|name> [#]",
                "example": "cc warnclean @john 2",
                "permissions": "Manage Messages",
                "aliases": "wc, clearwarnings",
            },
            {
                "title": "Mute Role",
                "description": "Set the server's muted role used by `cc mute`.",
                "syntax": "cc muterole <@role|ID|name>",
                "example": "cc muterole @Muted",
                "permissions": "Manage Roles",
                "aliases": "None",
            },
            {
                "title": "Mute",
                "description": "Mute a member using the configured muted role.",
                "syntax": "cc mute <@|ID|name> [reason]",
                "example": "cc mute @john flooding",
                "permissions": "Manage Roles",
                "aliases": "None",
            },
            {
                "title": "Unmute",
                "description": "Remove the muted role from a member.",
                "syntax": "cc unmute <@|ID|name>",
                "example": "cc unmute @john",
                "permissions": "Manage Roles",
                "aliases": "None",
            },
            {
                "title": "Image Mute",
                "description": "Prevent a member from posting attachments. Bot auto-deletes their media.",
                "syntax": "cc imute <@|ID|name> [reason]",
                "example": "cc imute @john posting nsfw",
                "permissions": "Manage Messages",
                "aliases": "None",
            },
            {
                "title": "Image Unmute",
                "description": "Remove an image mute from a member.",
                "syntax": "cc iunmute <@|ID|name>",
                "example": "cc iunmute @john",
                "permissions": "Manage Messages",
                "aliases": "None",
            },
        ],
    },
]

# Flatten into a list of pages: (group_name, cmd_index_in_group, total_in_group, cmd_data)
def _build_pages():
    pages = []
    for module in MODULES:
        group = module["group"]
        cmds = module["commands"]
        for i, cmd in enumerate(cmds):
            pages.append((group, i + 1, len(cmds), cmd))
    return pages

PAGES = _build_pages()


def _make_embed(bot: commands.Bot, page: int, invoker: discord.User | discord.Member) -> discord.Embed:
    group, idx, total, cmd = PAGES[page]

    embed = discord.Embed(
        title=f"Group: {group} ‣ Module {idx}",
        description=(
            f"> {cmd['description']}\n"
            f"```\n"
            f"Syntax:  {cmd['syntax']}\n"
            f"Example: {cmd['example']}\n"
            f"```\n"
            f"**Permissions:**\n{cmd['permissions']}"
        ),
        color=discord.Color.blurple(),
    )

    embed.set_author(
        name="Corebot Help",
        icon_url=bot.user.display_avatar.url if bot.user else None,
    )

    embed.set_footer(
        text=f"Aliases: {cmd['aliases']}  ⌁  Page {page + 1} of {len(PAGES)}",
        icon_url=invoker.display_avatar.url,
    )

    return embed


class HelpView(discord.ui.View):
    def __init__(self, bot: commands.Bot, invoker: discord.User | discord.Member, page: int = 0):
        super().__init__(timeout=120)
        self.bot = bot
        self.invoker = invoker
        self.page = page
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page == len(PAGES) - 1

    async def _edit(self, interaction: discord.Interaction):
        self._update_buttons()
        await interaction.response.edit_message(
            embed=_make_embed(self.bot, self.page, self.invoker),
            view=self,
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.invoker.id:
            await interaction.response.send_message("✕ This menu belongs to someone else.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except Exception:
            pass

    @discord.ui.button(label="←", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        await self._edit(interaction)

    @discord.ui.button(label="✕", style=discord.ButtonStyle.danger)
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

    @discord.ui.button(label="→", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        await self._edit(interaction)


class Help(commands.Cog, name="Help"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="help", aliases=["h"])
    async def help(self, ctx: commands.Context, *, query: str = None):
        """Show the help menu. Optionally jump to a command: cc help ban"""
        page = 0

        if query:
            query = query.lower().strip()
            for i, (group, idx, total, cmd) in enumerate(PAGES):
                if (
                    query in cmd["title"].lower()
                    or query in cmd["syntax"].lower()
                    or query in cmd["aliases"].lower()
                ):
                    page = i
                    break

        view = HelpView(self.bot, ctx.author, page)
        msg = await ctx.send(embed=_make_embed(self.bot, page, ctx.author), view=view)
        view.message = msg

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        content = message.content.strip()

        # Bare prefix "cc" with nothing after it
        if content.lower() == "cc":
            view = HelpView(self.bot, message.author, 0)
            msg = await message.channel.send(
                embed=_make_embed(self.bot, 0, message.author),
                view=view,
            )
            view.message = msg
            return

        # Bare mention with nothing else
        if self.bot.user and self.bot.user.mentioned_in(message):
            mention_strs = [f"<@{self.bot.user.id}>", f"<@!{self.bot.user.id}>"]
            if content in mention_strs:
                view = HelpView(self.bot, message.author, 0)
                msg = await message.channel.send(
                    embed=_make_embed(self.bot, 0, message.author),
                    view=view,
                )
                view.message = msg


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))