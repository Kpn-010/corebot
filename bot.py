import asyncio
import logging
import os
import signal
from typing import Callable, List

import discord
from aiohttp import ClientSession, web
from discord.ext import commands

from data import GuildDB

logging.basicConfig(
    level=logging.INFO,
    format="[{asctime}] [{levelname:<8}] {name}: {message}",
    datefmt="%Y-%m-%d %H:%M:%S",
    style="{",
)
log = logging.getLogger("corebot")

EXTENSIONS: List[str] = [
    "cogs.owner",
    "cogs.help",
    "cogs.utils",
    "cogs.mod",
    "cogs.groups.info",
    "cogs.groups.auto",
    "cogs.groups.welcome",
    "cogs.groups.channel",
    "cogs.groups.role",
    "cogs.logs",
    "cogs.searchlabs",
]


async def _keepalive(port: int) -> None:
    async def _ok(_: web.Request) -> web.Response:
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/", _ok)
    app.router.add_get("/health", _ok)

    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    log.info(f"Keep-alive listening on :{port}")


class CoreBot(commands.Bot):
    def __init__(
        self,
        *args,
        initial_extensions: List[str],
        web_client: ClientSession,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.initial_extensions = initial_extensions
        self.session: ClientSession = web_client
        self.db: GuildDB = GuildDB()

    async def setup_hook(self) -> None:
        for ext in self.initial_extensions:
            try:
                await self.load_extension(ext)
                log.info(f"Loaded: {ext}")
            except Exception as exc:
                log.error(f"Failed to load {ext}: {exc}", exc_info=exc)

    async def close(self) -> None:
        await self.db.close()
        await super().close()

    async def on_ready(self) -> None:
        assert self.user is not None
        log.info(f"Ready — {self.user} (ID: {self.user.id}) | {len(self.guilds)} guild(s)")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} {'server' if len(self.guilds) == 1 else 'servers'} | cc",
            )
        )

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandInvokeError):
            error = error.original  # type: ignore[assignment]

        if isinstance(error, commands.MissingRequiredArgument):
            # ctx.command can be None if the command lookup itself failed,
            # so we guard before accessing .qualified_name and .signature.
            if ctx.command is not None:
                usage = f"\nUsage: `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`"
            else:
                usage = ""
            await ctx.send(f"✕ Missing: `{error.param.name}`{usage}")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"✕ {error}")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send(f"✕ You need: {', '.join(f'`{p}`' for p in error.missing_permissions)}")
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send(f"✕ I'm missing: {', '.join(f'`{p}`' for p in error.missing_permissions)}")
        elif isinstance(error, commands.CommandNotFound):
            pass
        elif isinstance(error, commands.CheckFailure):
            await ctx.send("✕ You don't have permission to use this command.")
        else:
            log.error(f"Unhandled error [{ctx.command}]: {error}", exc_info=error)
            await ctx.send(f"✕ Unexpected error: `{type(error).__name__}`")

    async def on_member_join(self, member: discord.Member) -> None:
        guild = member.guild
        gdata = await self.db.load(guild.id)

        role_key = "bot" if member.bot else "member"
        role_id = gdata["auto_role"].get(role_key)
        if role_id:
            role = guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason="CoreBot Auto Role")
                except discord.Forbidden:
                    pass

        if member.bot:
            return

        welcome = gdata.get("welcome", {})
        channel_id = welcome.get("channel_id")
        if not channel_id:
            return

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        template: str = welcome.get("message", "Welcome {user} to **{server}**! You are member #{count}.")
        embed_mode: bool = welcome.get("embed", False)

        invite_url = "N/A"
        try:
            invites = await guild.invites()
            if invites:
                invite_url = invites[0].url
        except discord.Forbidden:
            pass

        # guild.member_count is typed as int | None — it is None when the member
        # list has not been fetched yet. We collapse to int here so that both the
        # f-string formatting and the _ordinal() call satisfy the type checker.
        member_count: int = guild.member_count or 0

        def fill(text: str) -> str:
            return (
                text
                .replace("{user}", member.mention)
                .replace("{user.name}", member.name)
                .replace("{user.id}", str(member.id))
                .replace("{server}", guild.name)
                .replace("{count}", str(member_count))
                .replace("{position}", _ordinal(member_count))
                .replace("{invite}", invite_url)
            )

        if embed_mode:
            await channel.send(embed=_parse_welcome_embed(member, template, fill))
        else:
            await channel.send(fill(template))


def _extract_tag(raw: str, keyword: str) -> tuple[str | None, str]:
    """
    Find the first {keyword <content>} block in raw.

    Uses a brace-depth counter instead of regex so that the content can freely
    contain braces — Discord mentions like <@123>, nested {user} variables,
    blockquote lines starting with >, bold/italic markdown, etc. — without the
    match terminating prematurely on an inner closing brace.

    Returns (content_inside_tag, raw_with_tag_removed).
    If the tag is not found, returns (None, raw_unchanged).
    """
    search = "{" + keyword
    start = raw.find(search)
    if start == -1:
        return None, raw

    depth = 0
    i = start
    while i < len(raw):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                # Slice out the content between the keyword and the closing brace
                content = raw[start + 1 + len(keyword): i].strip()
                removed = raw[:start] + raw[i + 1:]
                return content, removed
        i += 1

    # Unmatched opening brace — return raw unchanged
    return None, raw


def _parse_welcome_embed(member: discord.Member, raw: str, fill: Callable[[str], str]) -> discord.Embed:
    embed = discord.Embed(color=discord.Color.blurple())

    # {author {user}} or {author <@id>} — sets embed author to the joining member
    content, raw = _extract_tag(raw, "author")
    if content is not None:
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)

    # {description <multiline content with full discord markdown>}
    content, raw = _extract_tag(raw, "description")
    if content is not None:
        embed.description = fill(content)

    # {thumbnail} — sets thumbnail to the member's avatar
    content, raw = _extract_tag(raw, "thumbnail")
    if content is not None:
        embed.set_thumbnail(url=member.display_avatar.url)

    # Anything left over after tag extraction becomes the description
    # if one wasn't already set (handles plain $em with no block tags)
    if leftover := fill(raw.strip()):
        if not embed.description:
            embed.description = leftover

    return embed


def _ordinal(n: int) -> str:
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10 if n % 100 not in (11, 12, 13) else 0, "th")
    return f"{n}{suffix}"


async def main() -> None:
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN environment variable is not set.")

    port = int(os.environ.get("PORT", 8080))
    intents = discord.Intents.all()

    # Backoff on 429s so Render's crash/restart loop doesn't keep hammering Discord.
    backoff = [0, 15, 30, 60, 120]

    for attempt, delay in enumerate(backoff):
        if delay:
            log.warning(f"Rate limited — attempt {attempt + 1}/{len(backoff)}, waiting {delay}s.")
            await asyncio.sleep(delay)

        try:
            async with ClientSession() as session:
                async with CoreBot(
                    command_prefix="cc ",
                    intents=intents,
                    case_insensitive=True,
                    help_command=None,
                    initial_extensions=EXTENSIONS,
                    web_client=session,
                ) as bot:
                    loop = asyncio.get_running_loop()

                    def _handle_signal():
                        log.info("Signal received — shutting down cleanly.")
                        asyncio.ensure_future(bot.close())

                    for sig in (signal.SIGINT, signal.SIGTERM):
                        loop.add_signal_handler(sig, _handle_signal)

                    await asyncio.gather(_keepalive(port), bot.start(token))
            return

        except discord.HTTPException as e:
            if e.status == 429:
                if attempt + 1 < len(backoff):
                    log.error(f"429 rate limited (attempt {attempt + 1}). Retrying in {backoff[attempt + 1]}s.")
                else:
                    log.error("429 rate limited — all retries exhausted.")
                    raise
            else:
                raise


if __name__ == "__main__":
    asyncio.run(main())