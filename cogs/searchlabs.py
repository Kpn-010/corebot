import discord
from discord.ext import commands
import httpx

DICT_API = "https://api.dictionaryapi.dev/api/v2/entries/en"

VALID_FLAGS = {"-pos", "-sentence", "-origin", "-syn", "-more"}

import re as _re


def _clean_sentence_words(text: str) -> list[str]:
    """Strip mentions, punctuation and return meaningful words from a sentence."""
    text = _re.sub(r"<@?!?[0-9]+>", "", text)
    text = _re.sub(r"[^\w\s']", " ", text)
    return [w for w in text.split() if w.isalpha() and len(w) > 1]


def _parse_position_flag(parts: list[str]) -> tuple[int | None, list[str]]:
    """
    Detect a positional flag like -1, -2, -3 in the parts list.
    Returns (position_index, remaining_parts).
    Position is 1-based from the user, converted to 0-based index.
    """
    remaining = []
    position = None
    for p in parts:
        if p.startswith("-") and p[1:].isdigit():
            position = int(p[1:]) - 1  # convert to 0-based
        else:
            remaining.append(p)
    return position, remaining


async def _fetch(word: str) -> list | None:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{DICT_API}/{word.lower()}")
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


def _get_first_meaning(data: list) -> tuple[str, str, str]:
    """Returns (part_of_speech, definition, example)"""
    for entry in data:
        for meaning in entry.get("meanings", []):
            pos = meaning.get("partOfSpeech", "unknown")
            for defn in meaning.get("definitions", []):
                definition = defn.get("definition", "")
                example = defn.get("example", "")
                if definition:
                    return pos, definition, example
    return "unknown", "No definition found.", ""


def _get_all_meanings(data: list) -> list[dict]:
    """Flatten all meanings across all entries."""
    meanings = []
    for entry in data:
        for meaning in entry.get("meanings", []):
            pos = meaning.get("partOfSpeech", "unknown")
            for defn in meaning.get("definitions", []):
                definition = defn.get("definition", "")
                example = defn.get("example", "")
                syns = defn.get("synonyms", []) or meaning.get("synonyms", [])
                ants = defn.get("antonyms", []) or meaning.get("antonyms", [])
                if definition:
                    meanings.append({
                        "pos": pos,
                        "definition": definition,
                        "example": example,
                        "synonyms": syns[:5],
                        "antonyms": ants[:5],
                    })
    return meanings


def _get_origin(data: list) -> str:
    for entry in data:
        origin = entry.get("origin", "")
        if origin:
            return origin
        # Some APIs put it in etymologies
        for meaning in entry.get("meanings", []):
            pass
    return ""


def _get_phonetic(data: list) -> str:
    for entry in data:
        phonetic = entry.get("phonetic", "")
        if phonetic:
            return phonetic
    return ""


def _get_synonyms(data: list) -> tuple[list, list]:
    """Returns (synonyms, antonyms) across all meanings."""
    syns, ants = set(), set()
    for entry in data:
        for meaning in entry.get("meanings", []):
            for s in meaning.get("synonyms", []):
                syns.add(s)
            for a in meaning.get("antonyms", []):
                ants.add(a)
            for defn in meaning.get("definitions", []):
                for s in defn.get("synonyms", []):
                    syns.add(s)
                for a in defn.get("antonyms", []):
                    ants.add(a)
    return list(syns)[:10], list(ants)[:10]


def _base_embed(word: str, phonetic: str,
                color=discord.Color.blurple()) -> discord.Embed:
    title = f"{word}"
    if phonetic:
        title += f"  {phonetic}"
    embed = discord.Embed(title=title, color=color)
    embed.set_footer(text="SearchLabs • dictionaryapi.dev")
    return embed


class MoreView(discord.ui.View):

    def __init__(self, invoker, word, pages):
        super().__init__(timeout=120)
        self.invoker = invoker
        self.word = word
        self.pages = pages
        self.page = 0
        self._sync()

    def _sync(self):
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page == len(self.pages) - 1

    def _make_embed(self) -> discord.Embed:
        m = self.pages[self.page]
        embed = discord.Embed(
            title=self.word,
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Part of Speech",
                        value=f"`{m['pos']}`",
                        inline=True)
        embed.add_field(name="Definition", value=m["definition"], inline=False)
        if m["example"]:
            embed.add_field(name="Example",
                            value=f"*{m['example']}*",
                            inline=False)
        if m["synonyms"]:
            embed.add_field(name="Synonyms",
                            value=", ".join(m["synonyms"]),
                            inline=True)
        if m["antonyms"]:
            embed.add_field(name="Antonyms",
                            value=", ".join(m["antonyms"]),
                            inline=True)
        embed.set_footer(
            text=f"SearchLabs  ⌁  Meaning {self.page + 1} of {len(self.pages)}"
        )
        return embed

    async def _edit(self, interaction: discord.Interaction):
        self._sync()
        await interaction.response.edit_message(embed=self._make_embed(),
                                                view=self)

    async def interaction_check(self,
                                interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.invoker.id:
            await interaction.response.send_message(
                "✕ This menu belongs to someone else.", ephemeral=True)
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
    async def prev_btn(self, interaction: discord.Interaction,
                       button: discord.ui.Button):
        self.page -= 1
        await self._edit(interaction)

    @discord.ui.button(label="✕", style=discord.ButtonStyle.danger)
    async def close_btn(self, interaction: discord.Interaction,
                        button: discord.ui.Button):
        await interaction.message.delete()

    @discord.ui.button(label="→", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction,
                       button: discord.ui.Button):
        self.page += 1
        await self._edit(interaction)


class SearchLabs(commands.Cog, name="SearchLabs"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="lookup", aliases=["ll"])
    async def lookup(self, ctx: commands.Context, word: str = None, *flags):
        """
        Look up a word.
        cc ll <word>            — first definition
        cc ll <word> -pos       — part of speech
        cc ll <word> -sentence  — example sentence
        cc ll <word> -origin    — etymology
        cc ll <word> -syn       — synonyms & antonyms
        cc ll <word> -more      — full paginated breakdown
        """
        if not word:
            return await ctx.send(
                "Usage: `cc ll <word> [flags]`\n"
                "Flags: `-pos` `-sentence` `-origin` `-syn` `-more`")

        # Separate word tokens from flags (anything starting with -)
        # Support: cc ll hello world -pos (multi-word lookup)
        all_args = [word] + list(flags)
        flag_set = {a.lower() for a in all_args if a.startswith("-")}
        word_parts = [a for a in all_args if not a.startswith("-")]
        word = " ".join(word_parts).strip()

        invalid = flag_set - VALID_FLAGS
        if invalid:
            return await ctx.send(
                f"✕ Unknown flag(s): {' '.join(invalid)}\n"
                f"Valid flags: `-pos` `-sentence` `-origin` `-syn` `-more`")

        async with ctx.typing():
            data = await _fetch(word)

        if data is None:
            return await ctx.send(f"✕ No results found for **{word}**.")

        phonetic = _get_phonetic(data)
        pos, definition, example = _get_first_meaning(data)

        # ── -more: full paginated embed ────────────────────────────────────
        if "-more" in flag_set:
            meanings = _get_all_meanings(data)
            if not meanings:
                return await ctx.send(f"✕ No meanings found for **{word}**.")
            view = MoreView(ctx.author, word, meanings)
            msg = await ctx.send(embed=view._make_embed(), view=view)
            view.message = msg
            return

        # ── Plain text responses for all other modes ───────────────────────
        if not flag_set:
            await ctx.send(definition)
            return

        lines = []

        if "-pos" in flag_set:
            lines.append(f"**Part of speech:** {pos}")

        if "-sentence" in flag_set:
            lines.append(example if example else "No example available.")

        if "-origin" in flag_set:
            origin = _get_origin(data)
            lines.append(origin if origin else "No origin data available.")

        if "-syn" in flag_set:
            syns, ants = _get_synonyms(data)
            lines.append(
                f"**Synonyms:** {', '.join(syns) if syns else 'None found.'}")
            lines.append(
                f"**Antonyms:** {', '.join(ants) if ants else 'None found.'}")

        await ctx.send("\n".join(lines))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if self.bot.user not in message.mentions:
            return

        # Strip the mention
        content = message.content.strip()
        for mention_fmt in (f"<@{self.bot.user.id}>",
                            f"<@!{self.bot.user.id}>"):
            content = content.replace(mention_fmt, "").strip()

        # Ignore if it's a regular command
        if content.startswith("cc "):
            return

        parts = content.split()

        # Detect positional flag (-1, -2, -3 ...) and normal flags
        position, parts = _parse_position_flag(parts)
        flag_set = {
            p.lower()
            for p in parts if p.startswith("-") and p.lower() in VALID_FLAGS
        }
        word_parts = [p for p in parts if not p.startswith("-")]
        word = " ".join(word_parts).strip()

        # ── Reply + positional flag: @corebot -3 ──────────────────────────
        if position is not None and message.reference:
            try:
                ref_msg = await message.channel.fetch_message(
                    message.reference.message_id)
                sentence_words = _clean_sentence_words(ref_msg.content)
                if not sentence_words:
                    await message.channel.send(
                        "✕ No readable words found in that message.")
                    return
                if position >= len(sentence_words):
                    await message.channel.send(
                        f"✕ That message only has {len(sentence_words)} word(s). "
                        f"Use `-1` to `-{len(sentence_words)}`.")
                    return
                word = sentence_words[position]
            except (discord.NotFound, discord.Forbidden):
                await message.channel.send("✕ Could not fetch that message.")
                return

        # ── Reply without position: @corebot (just a reply) ──────────────
        elif not word and message.reference:
            try:
                ref_msg = await message.channel.fetch_message(
                    message.reference.message_id)
                sentence_words = _clean_sentence_words(ref_msg.content)
                if not sentence_words:
                    await message.channel.send(
                        "✕ No readable words found in that message.")
                    return
                # Default: first two words as a potential term
                word = " ".join(sentence_words[:2])
            except (discord.NotFound, discord.Forbidden):
                await message.channel.send("✕ Could not fetch that message.")
                return

        if not word:
            return

        async with message.channel.typing():
            data = await _fetch(word)

        # If two-word term fails, fall back to first word
        if data is None and " " in word:
            word = word.split()[0]
            data = await _fetch(word)

        if data is None:
            await message.channel.send(f"✕ No results found for **{word}**.")
            return

        pos, definition, example = _get_first_meaning(data)

        if "-more" in flag_set:
            meanings = _get_all_meanings(data)
            if not meanings:
                await message.channel.send(
                    f"✕ No meanings found for **{word}**.")
                return
            view = MoreView(message.author, word, meanings)
            msg = await message.channel.send(embed=view._make_embed(),
                                             view=view)
            view.message = msg
            return

        if not flag_set:
            await message.channel.send(definition)
            return

        lines = []
        if "-pos" in flag_set:
            lines.append(f"**Part of speech:** {pos}")
        if "-sentence" in flag_set:
            lines.append(example if example else "No example available.")
        if "-origin" in flag_set:
            origin = _get_origin(data)
            lines.append(origin if origin else "No origin data available.")
        if "-syn" in flag_set:
            syns, ants = _get_synonyms(data)
            lines.append(
                f"**Synonyms:** {', '.join(syns) if syns else 'None found.'}")
            lines.append(
                f"**Antonyms:** {', '.join(ants) if ants else 'None found.'}")

        await message.channel.send("\n".join(lines))

    @commands.Cog.listener()
    async def on_raw_reaction_add(self,
                                  payload: discord.RawReactionActionEvent):
        # Only trigger on the lookup emoji or bot mention emoji
        emoji = str(payload.emoji)
        if emoji not in ("🔍", "📖"):
            return
        if payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(
            payload.guild_id) if payload.guild_id else None
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except (discord.NotFound, discord.Forbidden):
            return

        if not message.content:
            return

        # Strip mentions, punctuation, and take first two words
        import re
        text = message.content
        text = re.sub(r"<@?!?[0-9]+>", "", text)  # remove mentions
        text = re.sub(r"[^\w\s\-]", " ",
                      text)  # remove punctuation except hyphens
        words = text.split()

        # Separate flags from words
        flag_set = {
            w.lower()
            for w in words if w.startswith("-") and w.lower() in VALID_FLAGS
        }
        word_parts = [w for w in words if not w.startswith("-")]

        # Take first two words as the search term
        term = " ".join(word_parts[:2]).strip()
        if not term:
            return

        reactor = guild.get_member(payload.user_id) if guild else None
        if not reactor:
            return

        async with channel.typing():
            data = await _fetch(term)

        if data is None:
            # Try just the first word if two-word lookup failed
            term = word_parts[0] if word_parts else ""
            if not term:
                return
            data = await _fetch(term)
            if data is None:
                await channel.send(f"✕ No results found for **{term}**.")
                return

        pos, definition, example = _get_first_meaning(data)

        if "-more" in flag_set:
            meanings = _get_all_meanings(data)
            if not meanings:
                await channel.send(f"✕ No meanings found for **{term}**.")
                return
            view = MoreView(reactor, term, meanings)
            msg = await channel.send(
                f"*Looked up **{term}** from {message.author.mention}'s message:*",
                embed=view._make_embed(),
                view=view,
            )
            view.message = msg
            return

        lines = [
            f"*Looked up **{term}** from {message.author.mention}'s message:*"
        ]

        if not flag_set:
            lines.append(definition)
        else:
            if "-pos" in flag_set:
                lines.append(f"**Part of speech:** {pos}")
            if "-sentence" in flag_set:
                lines.append(example if example else "No example available.")
            if "-origin" in flag_set:
                origin = _get_origin(data)
                lines.append(origin if origin else "No origin data available.")
            if "-syn" in flag_set:
                syns, ants = _get_synonyms(data)
                lines.append(
                    f"**Synonyms:** {', '.join(syns) if syns else 'None found.'}"
                )
                lines.append(
                    f"**Antonyms:** {', '.join(ants) if ants else 'None found.'}"
                )

        await channel.send("\n".join(lines))


async def setup(bot: commands.Bot):
    await bot.add_cog(SearchLabs(bot))
