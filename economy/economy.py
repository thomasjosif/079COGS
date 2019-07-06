import calendar
import logging
import random
from collections import defaultdict, deque
from enum import Enum
from typing import cast, Iterable

import discord

from redbot.cogs.bank import check_global_setting_guildowner, check_global_setting_admin
from redbot.core import Config, bank, commands, errors
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import box
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

from redbot.core.bot import Red

T_ = Translator("Economy", __file__)

logger = logging.getLogger("red.economy")

NUM_ENC = "\N{COMBINING ENCLOSING KEYCAP}"


class SMReel(Enum):
    seven = "<:think7:423526659744858122>"
    peanut = "<:peanutthinking:423524672110329857> " #
    haha = "<:hahayes:423527488795443213>"
    dab = "<:hubertdab:498133199965388800>"
    fn = "<:049:423520449482326036>"
    lol = "<:lol:330506869649047552>"
    sn = "<:035lul:577850023119945738> " #
    ss = "<:scientistsweat:498330844402941953>"
    nnn = "<:999:423524521384083456>"
    fps = "<:457:423520068136337428>"
    oof = "<:Oof:492894982785597461>"
    lgb = "<:pepeinspecting:575808313112002605>" #


_ = lambda s: s
PAYOUTS = {
    (SMReel.seven, SMReel.seven, SMReel.seven): {
        "payout": lambda x: x * 500 + x,
        "phrase": _("JACKPOT! 777! Your bid has been multiplied * 500!"),
    },
    (SMReel.haha, SMReel.haha, SMReel.haha): {
        "payout": lambda x: x + 800,
        "phrase": _("+800, because I'm happy!"),
    },
    (SMReel.peanut, SMReel.peanut, SMReel.peanut): {
        "payout": lambda x: x + 1000,
        "phrase": _("Triple peanut! +1000!"),
    },
    (SMReel.seven, SMReel.seven): {
        "payout": lambda x: x * 4 + x,
        "phrase": _("77! Your bid has been multiplied * 4!"),
    },
    (SMReel.peanut, SMReel.peanut): {
        "payout": lambda x: x * 3 + x,
        "phrase": _("Double peanut! Your bid has been multiplied * 3!"),
    },
    "3 symbols": {"payout": lambda x: x + 500, "phrase": _("Three symbols! +500!")},
    "2 symbols": {
        "payout": lambda x: x * 2 + x,
        "phrase": _("Two consecutive symbols! Your bid has been multiplied * 2!"),
    },
}

SLOT_PAYOUTS_MSG = _(
    "Slot machine payouts:\n"
    "{seven.value} {seven.value} {seven.value} Bet * 2500\n"
    "{peanut.value} {peanut.value} {peanut.value} +1000\n"
    "{haha.value} {haha.value} {haha.value} +800\n"
    "{seven.value} {seven.value} Bet * 4\n"
    "{peanut.value} {peanut.value} Bet * 3\n\n"
    "Three symbols: +500\n"
    "Two symbols: Bet * 2"
).format(**SMReel.__dict__)
_ = T_


def guild_only_check():
    async def pred(ctx: commands.Context):
        if await bank.is_global():
            return True
        elif not await bank.is_global() and ctx.guild is not None:
            return True
        else:
            return False

    return commands.check(pred)


class SetParser:
    def __init__(self, argument):
        allowed = ("+", "-")
        self.sum = int(argument)
        if argument and argument[0] in allowed:
            if self.sum < 0:
                self.operation = "withdraw"
            elif self.sum > 0:
                self.operation = "deposit"
            else:
                raise RuntimeError
            self.sum = abs(self.sum)
        elif argument.isdigit():
            self.operation = "set"
        else:
            raise RuntimeError


@cog_i18n(_)
class Economy(commands.Cog):
    """Get rich and have fun with imaginary currency!"""

    default_guild_settings = {
        "PAYDAY_TIME": 300,
        "PAYDAY_CREDITS": 120,
        "SLOT_MIN": 5,
        "SLOT_MAX": 100,
        "SLOT_TIME": 0,
        "REGISTER_CREDITS": 0,
    }

    default_global_settings = default_guild_settings

    default_member_settings = {"next_payday": 0, "last_slot": 0}

    default_role_settings = {"PAYDAY_CREDITS": 0}

    default_user_settings = default_member_settings

    def __init__(self, bot: Red):
        super().__init__()
        self.bot = bot
        self.file_path = "data/economy/settings.json"
        self.config = Config.get_conf(self, 1256844281)
        self.config.register_guild(**self.default_guild_settings)
        self.config.register_global(**self.default_global_settings)
        self.config.register_member(**self.default_member_settings)
        self.config.register_user(**self.default_user_settings)
        self.config.register_role(**self.default_role_settings)
        self.slot_register = defaultdict(dict)

    @guild_only_check()
    @commands.group(name="bank")
    async def _bank(self, ctx: commands.Context):
        """Manage the bank."""
        pass

    @_bank.command()
    async def balance(self, ctx: commands.Context, user: discord.Member = None):
        """Show the user's account balance.

        Defaults to yours."""
        if user is None:
            user = ctx.author

        bal = await bank.get_balance(user)
        currency = await bank.get_currency_name(ctx.guild)

        await ctx.send(
            _("{user}'s balance is {num} {currency}").format(
                user=user.display_name, num=bal, currency=currency
            )
        )

    @_bank.command()
    async def transfer(self, ctx: commands.Context, to: discord.Member, amount: int):
        """Transfer currency to other users."""
        from_ = ctx.author
        currency = await bank.get_currency_name(ctx.guild)

        try:
            await bank.transfer_credits(from_, to, amount)
        except (ValueError, errors.BalanceTooHigh) as e:
            return await ctx.send(str(e))

        await ctx.send(
            _("{user} transferred {num} {currency} to {other_user}").format(
                user=from_.display_name, num=amount, currency=currency, other_user=to.display_name
            )
        )

    @_bank.command(name="set")
    @check_global_setting_admin()
    async def _set(self, ctx: commands.Context, to: discord.Member, creds: SetParser):
        """Set the balance of user's bank account.

        Passing positive and negative values will add/remove currency instead.

        Examples:
        - `[p]bank set @Twentysix 26` - Sets balance to 26
        - `[p]bank set @Twentysix +2` - Increases balance by 2
        - `[p]bank set @Twentysix -6` - Decreases balance by 6
        """
        author = ctx.author
        currency = await bank.get_currency_name(ctx.guild)

        try:
            if creds.operation == "deposit":
                await bank.deposit_credits(to, creds.sum)
                msg = _("{author} added {num} {currency} to {user}'s account.").format(
                    author=author.display_name,
                    num=creds.sum,
                    currency=currency,
                    user=to.display_name,
                )
            elif creds.operation == "withdraw":
                await bank.withdraw_credits(to, creds.sum)
                msg = _("{author} removed {num} {currency} from {user}'s account.").format(
                    author=author.display_name,
                    num=creds.sum,
                    currency=currency,
                    user=to.display_name,
                )
            else:
                await bank.set_balance(to, creds.sum)
                msg = _("{author} set {user}'s account balance to {num} {currency}.").format(
                    author=author.display_name,
                    num=creds.sum,
                    currency=currency,
                    user=to.display_name,
                )
        except (ValueError, errors.BalanceTooHigh) as e:
            await ctx.send(str(e))
        else:
            await ctx.send(msg)

    @_bank.command()
    @check_global_setting_guildowner()
    async def reset(self, ctx, confirmation: bool = False):
        """Delete all bank accounts."""
        if confirmation is False:
            await ctx.send(
                _(
                    "This will delete all bank accounts for {scope}.\nIf you're sure, type "
                    "`{prefix}bank reset yes`"
                ).format(
                    scope=self.bot.user.name if await bank.is_global() else _("this server"),
                    prefix=ctx.prefix,
                )
            )
        else:
            await bank.wipe_bank(guild=ctx.guild)
            await ctx.send(
                _("All bank accounts for {scope} have been deleted.").format(
                    scope=self.bot.user.name if await bank.is_global() else _("this server")
                )
            )

    @guild_only_check()
    @commands.command()
    async def payday(self, ctx: commands.Context):
        """Get some free currency."""
        author = ctx.author
        guild = ctx.guild

        cur_time = calendar.timegm(ctx.message.created_at.utctimetuple())
        credits_name = await bank.get_currency_name(ctx.guild)
        if await bank.is_global():  # Role payouts will not be used
            next_payday = await self.config.user(author).next_payday()
            if cur_time >= next_payday:
                try:
                    await bank.deposit_credits(author, await self.config.PAYDAY_CREDITS())
                except errors.BalanceTooHigh as exc:
                    await bank.set_balance(author, exc.max_balance)
                    await ctx.send(
                        _(
                            "You've reached the maximum amount of {currency}! (**{balance:,}**) "
                            "Please spend some more \N{GRIMACING FACE}\n\n"
                            "You currently have {new_balance} {currency}."
                        ).format(currency=credits_name, new_balance=exc.max_balance)
                    )
                    return
                next_payday = cur_time + await self.config.PAYDAY_TIME()
                await self.config.user(author).next_payday.set(next_payday)

                pos = await bank.get_leaderboard_position(author)
                await ctx.send(
                    _(
                        "{author.mention} Here, take some {currency}. "
                        "Enjoy! (+{amount} {currency}!)\n\n"
                        "You currently have {new_balance} {currency}.\n\n"
                        "You are currently #{pos} on the global leaderboard!"
                    ).format(
                        author=author,
                        currency=credits_name,
                        amount=await self.config.PAYDAY_CREDITS(),
                        new_balance=await bank.get_balance(author),
                        pos=pos,
                    )
                )

            else:
                dtime = self.display_time(next_payday - cur_time)
                await ctx.send(
                    _(
                        "{author.mention} Too soon. For your next payday you have to wait {time}."
                    ).format(author=author, time=dtime)
                )
        else:
            next_payday = await self.config.member(author).next_payday()
            if cur_time >= next_payday:
                credit_amount = await self.config.guild(guild).PAYDAY_CREDITS()
                for role in author.roles:
                    role_credits = await self.config.role(
                        role
                    ).PAYDAY_CREDITS()  # Nice variable name
                    if role_credits > credit_amount:
                        credit_amount = role_credits
                try:
                    await bank.deposit_credits(author, credit_amount)
                except errors.BalanceTooHigh as exc:
                    await bank.set_balance(author, exc.max_balance)
                    await ctx.send(
                        _(
                            "You've reached the maximum amount of {currency}! "
                            "Please spend some more \N{GRIMACING FACE}\n\n"
                            "You currently have {new_balance} {currency}."
                        ).format(currency=credits_name, new_balance=exc.max_balance)
                    )
                    return
                next_payday = cur_time + await self.config.guild(guild).PAYDAY_TIME()
                await self.config.member(author).next_payday.set(next_payday)
                pos = await bank.get_leaderboard_position(author)
                await ctx.send(
                    _(
                        "{author.mention} Here, take some {currency}. "
                        "Enjoy! (+{amount} {currency}!)\n\n"
                        "You currently have {new_balance} {currency}.\n\n"
                        "You are currently #{pos} on the global leaderboard!"
                    ).format(
                        author=author,
                        currency=credits_name,
                        amount=credit_amount,
                        new_balance=await bank.get_balance(author),
                        pos=pos,
                    )
                )
            else:
                dtime = self.display_time(next_payday - cur_time)
                await ctx.send(
                    _(
                        "{author.mention} Too soon. For your next payday you have to wait {time}."
                    ).format(author=author, time=dtime)
                )

    @commands.command()
    @guild_only_check()
    async def leaderboard(self, ctx: commands.Context, top: int = 10, show_global: bool = False):
        """Print the leaderboard.

        Defaults to top 10.
        """
        guild = ctx.guild
        author = ctx.author
        if top < 1:
            top = 10
        if (
            await bank.is_global() and show_global
        ):  # show_global is only applicable if bank is global
            guild = None
        bank_sorted = await bank.get_leaderboard(positions=top, guild=guild)
        header = "{pound:4}{name:36}{score:2}\n".format(
            pound="#", name=_("Name"), score=_("Score")
        )
        highscores = [
            (
                f"{f'{pos}.': <{3 if pos < 10 else 2}} {acc[1]['name']: <{35}s} "
                f"{acc[1]['balance']: >{2 if pos < 10 else 1}}\n"
            )
            if acc[0] != author.id
            else (
                f"{f'{pos}.': <{3 if pos < 10 else 2}} <<{acc[1]['name'] + '>>': <{33}s} "
                f"{acc[1]['balance']: >{2 if pos < 10 else 1}}\n"
            )
            for pos, acc in enumerate(bank_sorted, 1)
        ]
        if highscores:
            pages = [
                f"```md\n{header}{''.join(''.join(highscores[x:x + 10]))}```"
                for x in range(0, len(highscores), 10)
            ]
            await menu(ctx, pages, DEFAULT_CONTROLS)
        else:
            await ctx.send(_("There are no accounts in the bank."))

    @commands.command()
    @guild_only_check()
    async def payouts(self, ctx: commands.Context):
        """Show the payouts for the slot machine."""
        await ctx.author.send(SLOT_PAYOUTS_MSG)

    @commands.command()
    @guild_only_check()
    async def slot(self, ctx: commands.Context, bid: int):
        """Use the slot machine."""
        author = ctx.author
        guild = ctx.guild
        channel = ctx.channel
        if await bank.is_global():
            valid_bid = await self.config.SLOT_MIN() <= bid <= await self.config.SLOT_MAX()
            slot_time = await self.config.SLOT_TIME()
            last_slot = await self.config.user(author).last_slot()
        else:
            valid_bid = (
                await self.config.guild(guild).SLOT_MIN()
                <= bid
                <= await self.config.guild(guild).SLOT_MAX()
            )
            slot_time = await self.config.guild(guild).SLOT_TIME()
            last_slot = await self.config.member(author).last_slot()
        now = calendar.timegm(ctx.message.created_at.utctimetuple())

        if (now - last_slot) < slot_time:
            await ctx.send(_("You're on cooldown, try again in a bit."))
            return
        if not valid_bid:
            await ctx.send(_("That's an invalid bid amount, sorry :/"))
            return
        if not await bank.can_spend(author, bid):
            await ctx.send(_("You ain't got enough money, friend."))
            return
        if await bank.is_global():
            await self.config.user(author).last_slot.set(now)
        else:
            await self.config.member(author).last_slot.set(now)
        await self.slot_machine(author, channel, bid)

    @staticmethod
    async def slot_machine(author, channel, bid):
        default_reel = deque(cast(Iterable, SMReel))
        reels = []
        for i in range(3):
            default_reel.rotate(random.randint(-999, 999))  # weeeeee
            new_reel = deque(default_reel, maxlen=3)  # we need only 3 symbols
            reels.append(new_reel)  # for each reel
        rows = (
            (reels[0][0], reels[1][0], reels[2][0]),
            (reels[0][1], reels[1][1], reels[2][1]),
            (reels[0][2], reels[1][2], reels[2][2]),
        )

        slot = "~~\n~~"  # Mobile friendly
        for i, row in enumerate(rows):  # Let's build the slot to show
            sign = "  "
            if i == 1:
                sign = ">"
            slot += "{}{} {} {}\n".format(sign, *[c.value for c in row])

        payout = PAYOUTS.get(rows[1])
        if not payout:
            # Checks for two-consecutive-symbols special rewards
            payout = PAYOUTS.get((rows[1][0], rows[1][1]), PAYOUTS.get((rows[1][1], rows[1][2])))
        if not payout:
            # Still nothing. Let's check for 3 generic same symbols
            # or 2 consecutive symbols
            has_three = rows[1][0] == rows[1][1] == rows[1][2]
            has_two = (rows[1][0] == rows[1][1]) or (rows[1][1] == rows[1][2])
            if has_three:
                payout = PAYOUTS["3 symbols"]
            elif has_two:
                payout = PAYOUTS["2 symbols"]

        if payout:
            then = await bank.get_balance(author)
            pay = payout["payout"](bid)
            now = then - bid + pay
            try:
                await bank.set_balance(author, now)
            except errors.BalanceTooHigh as exc:
                await bank.set_balance(author, exc.max_balance)
                await channel.send(
                    _(
                        "You've reached the maximum amount of {currency}! "
                        "Please spend some more \N{GRIMACING FACE}\n{old_balance} -> {new_balance}!"
                    ).format(
                        currency=await bank.get_currency_name(getattr(channel, "guild", None)),
                        old_balance=then,
                        new_balance=exc.max_balance,
                    )
                )
                return
            phrase = T_(payout["phrase"])
        else:
            then = await bank.get_balance(author)
            await bank.withdraw_credits(author, bid)
            now = then - bid
            phrase = _("Nothing!")
        await channel.send(
            (
                "{slot}\n{author.mention} {phrase}\n\n"
                + _("Your bid: {amount}")
                + "\n{old_balance} → {new_balance}!"
            ).format(
                slot=slot,
                author=author,
                phrase=phrase,
                amount=bid,
                old_balance=then,
                new_balance=now,
            )
        )

    @commands.group()
    @guild_only_check()
    @check_global_setting_admin()
    async def economyset(self, ctx: commands.Context):
        """Manage Economy settings."""
        guild = ctx.guild
        if ctx.invoked_subcommand is None:
            if await bank.is_global():
                conf = self.config
            else:
                conf = self.config.guild(ctx.guild)
            await ctx.send(
                box(
                    _(
                        "----Economy Settings---\n"
                        "Minimum slot bid: {slot_min}\n"
                        "Maximum slot bid: {slot_max}\n"
                        "Slot cooldown: {slot_time}\n"
                        "Payday amount: {payday_amount}\n"
                        "Payday cooldown: {payday_time}\n"
                        "Amount given at account registration: {register_amount}"
                    ).format(
                        slot_min=await conf.SLOT_MIN(),
                        slot_max=await conf.SLOT_MAX(),
                        slot_time=await conf.SLOT_TIME(),
                        payday_time=await conf.PAYDAY_TIME(),
                        payday_amount=await conf.PAYDAY_CREDITS(),
                        register_amount=await bank.get_default_balance(guild),
                    )
                )
            )

    @economyset.command()
    async def slotmin(self, ctx: commands.Context, bid: int):
        """Set the minimum slot machine bid."""
        if bid < 1:
            await ctx.send(_("Invalid min bid amount."))
            return
        guild = ctx.guild
        if await bank.is_global():
            await self.config.SLOT_MIN.set(bid)
        else:
            await self.config.guild(guild).SLOT_MIN.set(bid)
        credits_name = await bank.get_currency_name(guild)
        await ctx.send(
            _("Minimum bid is now {bid} {currency}.").format(bid=bid, currency=credits_name)
        )

    @economyset.command()
    async def slotmax(self, ctx: commands.Context, bid: int):
        """Set the maximum slot machine bid."""
        slot_min = await self.config.SLOT_MIN()
        if bid < 1 or bid < slot_min:
            await ctx.send(
                _("Invalid maximum bid amount. Must be greater than the minimum amount.")
            )
            return
        guild = ctx.guild
        credits_name = await bank.get_currency_name(guild)
        if await bank.is_global():
            await self.config.SLOT_MAX.set(bid)
        else:
            await self.config.guild(guild).SLOT_MAX.set(bid)
        await ctx.send(
            _("Maximum bid is now {bid} {currency}.").format(bid=bid, currency=credits_name)
        )

    @economyset.command()
    async def slottime(self, ctx: commands.Context, seconds: int):
        """Set the cooldown for the slot machine."""
        guild = ctx.guild
        if await bank.is_global():
            await self.config.SLOT_TIME.set(seconds)
        else:
            await self.config.guild(guild).SLOT_TIME.set(seconds)
        await ctx.send(_("Cooldown is now {num} seconds.").format(num=seconds))

    @economyset.command()
    async def paydaytime(self, ctx: commands.Context, seconds: int):
        """Set the cooldown for payday."""
        guild = ctx.guild
        if await bank.is_global():
            await self.config.PAYDAY_TIME.set(seconds)
        else:
            await self.config.guild(guild).PAYDAY_TIME.set(seconds)
        await ctx.send(
            _("Value modified. At least {num} seconds must pass between each payday.").format(
                num=seconds
            )
        )

    @economyset.command()
    async def paydayamount(self, ctx: commands.Context, creds: int):
        """Set the amount earned each payday."""
        guild = ctx.guild
        if creds <= 0 or creds > bank.MAX_BALANCE:
            await ctx.send(_("Har har so funny."))
            return
        credits_name = await bank.get_currency_name(guild)
        if await bank.is_global():
            await self.config.PAYDAY_CREDITS.set(creds)
        else:
            await self.config.guild(guild).PAYDAY_CREDITS.set(creds)
        await ctx.send(
            _("Every payday will now give {num} {currency}.").format(
                num=creds, currency=credits_name
            )
        )

    @economyset.command()
    async def rolepaydayamount(self, ctx: commands.Context, role: discord.Role, creds: int):
        """Set the amount earned each payday for a role."""
        guild = ctx.guild
        if creds <= 0 or creds > bank.MAX_BALANCE:
            await ctx.send(_("Har har so funny."))
            return
        credits_name = await bank.get_currency_name(guild)
        if await bank.is_global():
            await ctx.send(_("The bank must be per-server for per-role paydays to work."))
        else:
            await self.config.role(role).PAYDAY_CREDITS.set(creds)
            await ctx.send(
                _(
                    "Every payday will now give {num} {currency} "
                    "to people with the role {role_name}."
                ).format(num=creds, currency=credits_name, role_name=role.name)
            )

    @economyset.command()
    async def registeramount(self, ctx: commands.Context, creds: int):
        """Set the initial balance for new bank accounts."""
        guild = ctx.guild
        if creds < 0:
            creds = 0
        credits_name = await bank.get_currency_name(guild)
        await bank.set_default_balance(creds, guild)
        await ctx.send(
            _("Registering an account will now give {num} {currency}.").format(
                num=creds, currency=credits_name
            )
        )

    # What would I ever do without stackoverflow?
    @staticmethod
    def display_time(seconds, granularity=2):
        intervals = (  # Source: http://stackoverflow.com/a/24542445
            (_("weeks"), 604800),  # 60 * 60 * 24 * 7
            (_("days"), 86400),  # 60 * 60 * 24
            (_("hours"), 3600),  # 60 * 60
            (_("minutes"), 60),
            (_("seconds"), 1),
        )

        result = []

        for name, count in intervals:
            value = seconds // count
            if value:
                seconds -= value * count
                if value == 1:
                    name = name.rstrip("s")
                result.append("{} {}".format(value, name))
        return ", ".join(result[:granularity])
