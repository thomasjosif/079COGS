from copy import copy
import asyncio
import inspect
import collections
import discord
import datetime
import re

from redbot.core import Config, checks, commands
from redbot.core.i18n import Translator
from redbot.core.utils.predicates import MessagePredicate

_ = Translator("Warnings", __file__)


async def warning_points_add_check(
    config: Config, ctx: commands.Context, user: discord.Member, points: int
):
    """Handles any action that needs to be taken or not based on the points"""
    guild = ctx.guild
    guild_settings = config.guild(guild)
    act = {}
    async with guild_settings.actions() as registered_actions:
        for a in registered_actions:
            # Actions are sorted in decreasing order of points.
            # The first action we find where the user is above the threshold will be the
            # highest action we can take.
            if points >= a["points"]:
                act = a
                break
    if act and act["exceed_command"] is not None:  # some action needs to be taken
        await create_and_invoke_context(ctx, act["exceed_command"], user)


async def warning_points_remove_check(
    config: Config, ctx: commands.Context, user: discord.Member, points: int
):
    guild = ctx.guild
    guild_settings = config.guild(guild)
    act = {}
    async with guild_settings.actions() as registered_actions:
        for a in registered_actions:
            if points >= a["points"]:
                act = a
            else:
                break
    if act and act["drop_command"] is not None:  # some action needs to be taken
        await create_and_invoke_context(ctx, act["drop_command"], user)


async def create_and_invoke_context(
    realctx: commands.Context, command_str: str, user: discord.Member
):
    m = copy(realctx.message)
    m.content = command_str.format(user=user.mention, prefix=realctx.prefix)
    fctx = await realctx.bot.get_context(m, cls=commands.Context)
    try:
        await realctx.bot.invoke(fctx)
    except (commands.CheckFailure, commands.CommandOnCooldown):
        await fctx.reinvoke()


def get_command_from_input(bot, userinput: str):
    com = None
    orig = userinput
    while com is None:
        com = bot.get_command(userinput)
        if com is None:
            userinput = " ".join(userinput.split(" ")[:-1])
        if len(userinput) == 0:
            break
    if com is None:
        return None, _("I could not find a command from that input!")

    check_str = inspect.getsource(checks.is_owner)
    if any(inspect.getsource(x) in check_str for x in com.checks):
        # command the user specified has the is_owner check
        return (
            None,
            _("That command requires bot owner. I can't allow you to use that for an action"),
        )
    return "{prefix}" + orig, None


async def get_command_for_exceeded_points(ctx: commands.Context):
    """Gets the command to be executed when the user is at or exceeding
    the points threshold for the action"""
    await ctx.send(
        _(
            "Enter the command to be run when the user **exceeds the points for "
            "this action to occur.**\n**If you do not wish to have a command run, enter** "
            "`none`.\n\nEnter it exactly as you would if you were "
            "actually trying to run the command, except don't put a prefix and "
            "use `{user}` in place of any user/member arguments\n\n"
            "WARNING: The command entered will be run without regard to checks or cooldowns. "
            "Commands requiring bot owner are not allowed for security reasons.\n\n"
            "Please wait 15 seconds before entering your response."
        )
    )
    await asyncio.sleep(15)

    await ctx.send(_("You may enter your response now."))

    try:
        msg = await ctx.bot.wait_for(
            "message", check=MessagePredicate.same_context(ctx), timeout=30
        )
    except asyncio.TimeoutError:
        return None
    else:
        if msg.content == "none":
            return None

    command, m = get_command_from_input(ctx.bot, msg.content)
    if command is None:
        await ctx.send(m)
        return None

    return command


async def get_command_for_dropping_points(ctx: commands.Context):
    """
    Gets the command to be executed when the user drops below the points
    threshold

    This is intended to be used for reversal of the action that was executed
    when the user exceeded the threshold
    """
    await ctx.send(
        _(
            "Enter the command to be run when the user **returns to a value below "
            "the points for this action to occur.** Please note that this is "
            "intended to be used for reversal of the action taken when the user "
            "exceeded the action's point value.\n**If you do not wish to have a command run "
            "on dropping points, enter** `none`.\n\nEnter it exactly as you would "
            "if you were actually trying to run the command, except don't put a prefix "
            "and use `{user}` in place of any user/member arguments\n\n"
            "WARNING: The command entered will be run without regard to checks or cooldowns. "
            "Commands requiring bot owner are not allowed for security reasons.\n\n"
            "Please wait 15 seconds before entering your response."
        )
    )
    await asyncio.sleep(15)

    await ctx.send(_("You may enter your response now."))

    try:
        msg = await ctx.bot.wait_for(
            "message", check=MessagePredicate.same_context(ctx), timeout=30
        )
    except asyncio.TimeoutError:
        return None
    else:
        if msg.content == "none":
            return None
    command, m = get_command_from_input(ctx.bot, msg.content)
    if command is None:
        await ctx.send(m)
        return None

    return command


async def EmbedPaginateWarnsList(
    self,
    ctx,
    items: list,
    items_per_page: int = 15,
    title=discord.Embed.Empty,
    desc=discord.Embed.Empty,
    author=discord.Embed.Empty,
    author_url=discord.Embed.Empty,
    author_icon_url=discord.Embed.Empty,
    thumbnail=discord.Embed.Empty,
):
    maxPage = len(items) // items_per_page + (len(items) % items_per_page > 0)
    pages = [items[i * items_per_page : (i + 1) * items_per_page] for i in range(maxPage)]
    count = 0
    for page in pages:
        count += 1
        # print(f"Page {count} : {page}")

    async def showPage(page):
        em = discord.Embed(title=title, description=desc, color=0x3DF270)
        em.set_author(name=author, url=author_url, icon_url=author_icon_url)
        em.set_thumbnail(url=thumbnail)
        count = (page - 1) * items_per_page
        total = len(items)
        for warning in pages[page - 1]:
            id = warning.get("id", "None")
            count += 1
            num_points = warning["points"]
            time = datetime.datetime.fromtimestamp(warning["time"]).strftime(
                "%m/%d/%y @ %I:%M %p UTC"
            )
            unwarn = (
                datetime.datetime.fromtimestamp(warning["unwarn"]).strftime(
                    "%m/%d/%y @ %I:%M %p UTC"
                )
                if warning.get("unwarn")
                else None
            )
            mod = ctx.guild.get_member(warning["mod"])
            if mod is None:
                mod = discord.utils.get(self.bot.get_all_members(), id=warning["mod"])
                if mod is None:
                    mod = await self.bot.get_user_info(warning["mod"])
            em.add_field(
                name=f"{count} of {total} | {num_points} point warning | Warning ID (*{id}*)",
                value=f"Issued by {mod.mention}",
                inline=False,
            )
            em.add_field(
                name=f"Issued on {time}",
                value=f'Reason : {warning["description"]}'
                + (f"\nUnwarning: {unwarn}" if unwarn else "")
                + "\n------------------------------------------------------------------------------",
                inline=False,
            )
        em.set_footer(
            text=f"Page {currentPage} out of {maxPage}",
            icon_url="https://www.clipartmax.com/png/middle/171-1715896_paper-book-icon-textbook-icon.png",
        )
        return em

    firstRun = True
    while True:
        if firstRun:
            firstRun = False
            currentPage = 1
            em = await showPage(currentPage)
            msg = await ctx.send(embed=em)

        if maxPage == 1 and currentPage == 1:
            toReact = ["✅"]
        elif currentPage == 1:
            toReact = ["⏩", "✅"]
        elif currentPage == maxPage:
            toReact = ["⏪", "✅"]
        elif currentPage > 1 and currentPage < maxPage:
            toReact = ["⏪", "⏩", "✅"]

        for reaction in toReact:
            await msg.add_reaction(reaction)

        def checkReaction(reaction, user):
            return user == ctx.message.author and str(reaction.emoji).startswith(
                ("⏪", "⏩", "✅")
            )  # and reaction.message == msg

        try:
            result, user = await self.bot.wait_for(
                "reaction_add", timeout=120, check=checkReaction
            )
        except asyncio.TimeoutError:
            em.set_footer(
                text=f"Page {currentPage} out of {maxPage}. Timeout. Please reinvoke the command to change pages.",
                icon_url="https://www.clipartmax.com/png/middle/171-1715896_paper-book-icon-textbook-icon.png",
            )
            try:
                await msg.edit(embed=em)
                await msg.clear_reactions()
            except (discord.NotFound, discord.Forbidden):
                pass
            break
        else:
            try:
                if "⏪" in str(result.emoji):
                    # print('Previous Page')
                    currentPage -= 1
                    em = await showPage(currentPage)
                    await msg.edit(embed=em)
                    await msg.clear_reactions()
                elif "⏩" in str(result.emoji):
                    # print('Next Page')
                    currentPage += 1
                    em = await showPage(currentPage)
                    await msg.edit(embed=em)
                    await msg.clear_reactions()
                elif "✅" in str(result.emoji):
                    # print('Close List')
                    await msg.delete()
                    await ctx.message.delete()
                    break
            except (discord.NotFound, discord.Forbidden):
                pass


class Time(commands.Converter):
    TIME_AMNT_REGEX = re.compile("([1-9][0-9]*)([a-z]+)", re.IGNORECASE)
    TIME_QUANTITIES = collections.OrderedDict(
        [
            ("seconds", 1),
            ("minutes", 60),
            ("hours", 3600),
            ("days", 86400),
            ("weeks", 604800),
            ("months", 2.628e6),
            ("years", 3.154e7),
        ]
    )  # (amount in seconds, max amount)

    def get_seconds(self, time):
        """Returns the amount of converted time or None if invalid"""
        seconds = 0
        for time_match in self.TIME_AMNT_REGEX.finditer(time):
            time_amnt = int(time_match.group(1))
            time_abbrev = time_match.group(2)
            time_quantity = discord.utils.find(
                lambda t: t[0].startswith(time_abbrev), self.TIME_QUANTITIES.items()
            )
            if time_quantity is not None:
                seconds += time_amnt * time_quantity[1]
        return None if seconds == 0 else seconds

    async def convert(self, ctx, arg):
        result = None
        seconds = self.get_seconds(arg)
        result = seconds
        if result is None:
            raise commands.BadArgument('Unable to parse Time "{}" '.format(arg))
        return result

    @classmethod
    async def fromString(cls, arg):
        result = None
        seconds = cls.get_seconds(cls, arg)
        result = seconds
        if result is None:
            raise commands.BadArgument('Unable to parse Time "{}" '.format(arg))
        return result
