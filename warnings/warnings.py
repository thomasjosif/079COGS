from collections import namedtuple

import discord
import datetime
import enum
import asyncio
import fuzzywuzzy

from .helpers import (
    warning_points_add_check,
    get_command_for_exceeded_points,
    get_command_for_dropping_points,
    warning_points_remove_check,
    EmbedPaginateWarnsList,
    Time,
)
from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.mod import is_admin_or_superior, is_allowed_by_hierarchy
from redbot.core.utils.chat_formatting import warning, pagify
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS
from redbot.core.utils.predicates import MessagePredicate

from typing import Union

_ = Translator("Warnings", __file__)


class WarningType(enum.Enum):
    WARN = 1
    UNWARN = 2
    EDITED_WARN = 3
    MASS_UNWARN = 4
    AUTO_UNWARN = 5


class WarningNotFound(Exception):
    pass


@cog_i18n(_)
class Warnings(commands.Cog):
    """Warn misbehaving users and take automated actions."""

    default_global = {"tracked_warns": []}

    default_guild = {
        "actions": [],
        "reasons": {},
        "reasons_enabled": True,
        "allow_custom_reasons": False,
        "compact_list": False,
        "vips": [],
        "role_vips": [],
        "vip_warn_amount": 50,
        "vip_ignore_roles": [],
        "vip_ignore_users": [],
        "vip_ignore_commands": True,
        "loggingChannel": None,
        "filtered_words": [],
        "filter_warn_amount": 50,
        "autounwarn_enabled": True,
        "autowarn_removal_timers": {},  # {warn_amount : seconds_delay}
        # "autowarn_removal_timer": 604800,  # 604800 seconds = 1 week
        "autowarn_threshold": 3,
        "autounwarn_affect_manual": False,
        "show_filtered_word": True,
        "multiwarn_prevention_delay": 20,
    }
    default_member = {"total_points": 0, "status": "", "warnings": [], "queued_unwarn": {}}

    def __init__(self, bot: Red):
        super().__init__()
        self.config = Config.get_conf(self, identifier=5757575755)
        self.mod_settings = Config.get_conf(None, identifier=4961522000, cog_name="mod")
        self.config.register_global(**self.default_global)
        self.config.register_guild(**self.default_guild)
        self.config.register_member(**self.default_member)
        self.bot = bot
        self.unwarn_tasks = {}  # member_id : ( unwarn_task : warning_to_remove)

    # We're not utilising modlog yet - no need to register a casetype
    # @staticmethod
    # async def register_warningtype():
    #     try:
    #         await modlog.register_casetype("warning", True, "\N{WARNING SIGN}", "Warning", None)
    #     except RuntimeError:
    #         pass

    @commands.group()
    @commands.guild_only()
    @checks.guildowner_or_permissions(administrator=True)
    async def warningset(self, ctx: commands.Context):
        """Manage settings for Warnings."""
        pass

    @warningset.command(name="reasontoggle", aliases=["reasonstoggle", "rt"])
    @commands.guild_only()
    async def reasonstoggle(self, ctx: commands.Context, option: bool = None):
        """Set use of registered reasons for warnings True / False. This will allow custom reason warns without the need of the custom argument in `!warn`"""
        if option is None:
            option = not await self.config.guild(ctx.guild).reasons_enabled()
        await self.config.guild(ctx.guild).reasons_enabled.set(option)
        if option:
            await ctx.maybe_send_embed(
                f"Registered Reasons enabled. Warnings must now use a registered reason from `{ctx.prefix}reasonlist`"
            )
        else:
            await ctx.maybe_send_embed(
                "Registered Reasons disabled. All reasons will now default to 1 point each."
            )

    @warningset.command()
    @commands.guild_only()
    async def allowcustomreasons(self, ctx: commands.Context, allowed: bool):
        """Enable or disable custom reasons for a warning."""
        guild = ctx.guild
        await self.config.guild(guild).allow_custom_reasons.set(allowed)
        if allowed:
            await ctx.maybe_send_embed(_("Custom reasons have been enabled."))
        else:
            await ctx.maybe_send_embed(_("Custom reasons have been disabled."))

    @warningset.group(pass_context=True, invoke_without_command=True)
    @commands.guild_only()
    async def vip(self, ctx: commands.Context, *vips: Union[discord.Member, discord.Role]):
        """Add/remove vip(s), that causes 079 to warn users that ping a vip or edit VIP settings"""
        if ctx.invoked_subcommand is None:
            guild = ctx.guild
            VipList = await self.config.guild(guild).vips()
            RoleVipList = await self.config.guild(guild).role_vips()

            if not vips:
                await ctx.send_help()
                msg = f"{guild.name}'s VIP List:\n\n"
                for user in VipList:
                    user = self.bot.get_user(user)
                    msg += f"{user}\n"

                msg += "\nVIP Roles:\n"
                for roleID in RoleVipList:
                    role = ctx.guild.get_role(roleID)
                    msg += f"{role}\n"

                try:
                    message = "```css\n" + msg + "```"
                    await ctx.send(message)
                except discord.HTTPException:
                    pass

            else:
                vip_users = []
                vip_roles = []
                for entry in vips:
                    if type(entry) == discord.Member:
                        vip_users.append(entry)
                    elif type(entry) == discord.Role:
                        vip_roles.append(entry)
                    else:
                        continue

                msg = f"Made the following changes to {guild.name}'s VIP List:\n\n"
                if vip_users:
                    for user in vip_users:
                        if user.id in VipList:
                            VipList.remove(user.id)
                            msg += f"- Removed VIP User {user} ({user.id})\n"
                        else:
                            VipList.append(user.id)
                            msg += f"+ Added VIP User {user} ({user.id})\n"
                    await self.config.guild(guild).vips.set(VipList)

                if vip_roles:
                    msg += "\n+ VIP Roles:\n"
                    for role in vip_roles:
                        if role.id in RoleVipList:
                            RoleVipList.remove(role.id)
                            msg += f"- Removed VIP Role {role} ({role.id})\n"
                        else:
                            RoleVipList.append(role.id)
                            msg += f"+ Added VIP Role {role} ({role.id})"
                await self.config.guild(guild).role_vips.set(RoleVipList)
                try:
                    message = "```diff\n" + msg + "```"
                    await ctx.send(message)
                except discord.HTTPException:
                    pass

    @vip.command(name="warnpoints", aliases=["points"])
    @commands.guild_only()
    async def vipwarnpoints(self, ctx, amount: int = None):
        """Configure the amount of warning points a user should be given for pinging a VIP"""
        guild = ctx.guild
        warn_amount = await self.config.guild(guild).vip_warn_amount()
        if amount is not None:
            await self.config.guild(guild).vip_warn_amount.set(amount)
            warn_amount = amount
        await ctx.maybe_send_embed(
            f"Users will be given `{warn_amount} warning points` for pinging a VIP"
        )

    @vip.command(name="ignoreroles", aliases=["ignorerole"])
    @commands.guild_only()
    async def vipignoreroles(self, ctx, *roles: discord.Role):
        """Make users with a role ignored and immune from warns for pinging a VIP"""
        guild = ctx.guild
        async with self.config.guild(guild).vip_ignore_roles() as ignored_roles:
            if not roles:
                msg = f"```css\n{guild.name}'s VIP Ignored Roles List:" + "\n\n"
                if ignored_roles:
                    for roleID in ignored_roles:
                        role = guild.get_role(roleID)
                        msg += f"{role} ({roleID})" + "\n"
                else:
                    msg += "No Roles being Ignored." + "\n"
                msg += "```"
            else:
                msg = (
                    f"```diff\nMade the following changes to {guild.name}'s VIP Ignored Roles List:"
                    + "\n\n"
                )
                for role in roles:
                    if role.id in ignored_roles:
                        ignored_roles.remove(role.id)
                        msg += f"- Removed Role {role} ({role.id})" + "\n"
                    else:
                        ignored_roles.append(role.id)
                        msg += f"+ Added Role {role} ({role.id})" + "\n"
                msg += "```"
        await ctx.send(msg)

    @vip.command(name="ignoreusers", aliases=["ignoreuser"])
    @commands.guild_only()
    async def vipignoreusers(self, ctx, *users: discord.Member):
        """Make users ignored and immune from warns for pinging a VIP"""
        guild = ctx.guild
        async with self.config.guild(guild).vip_ignore_users() as ignored_users:
            if not users:
                msg = f"```css\n{guild.name}'s VIP Ignored Users List:" + "\n\n"
                if ignored_users:
                    for userID in ignored_users:
                        user = guild.get_member(userID)
                        msg += f"{user} ({userID})" + "\n"
                else:
                    msg += "No Users being Ignored." + "\n"
                msg += "```"
            else:
                msg = (
                    f"```diff\nMade the following changes to {guild.name}'s VIP Ignored Users List:"
                    + "\n\n"
                )
                for user in users:
                    if user.id in ignored_users:
                        ignored_users.remove(user.id)
                        msg += f"- Removed User {user} ({user.id})" + "\n"
                    else:
                        ignored_users.append(user.id)
                        msg += f"+ Added User {user} ({user.id})" + "\n"
                msg += "```"
        await ctx.send(msg)

    @vip.command(name="ignorecommands")
    async def vipcommandcheck(self, ctx, option: bool = None):
        """Toggle wether to ignore mentions from command usage when checking VIP mentions"""
        if option is None:
            option = not await self.config.guild(ctx.guild).vip_ignore_commands()
        await self.config.guild(ctx.guild).vip_ignore_commands.set(option)
        await ctx.maybe_send_embed(
            "Will {} ignore mentions from command usages when scanning for VIP mentions.".format(
                ("now" if option else "no longer")
            )
        )

    @warningset.group(name="autounwarn")
    async def autounwarn(self, ctx):
        """Configure settings related to auto unwarning
        
        Unwarns are setup so that if an unwarn is queued, and another is queued before a previous one finished unwarning,
        all a member's unwarns will be finished ONLY after the last queued unwarn.
        """
        pass

    @autounwarn.command(name="overview", aliases=["settings"])
    async def autounwarn_settings_overview(self, ctx):
        """Overview autounwarn settings"""
        guild_settings = self.config.guild(ctx.guild)
        enabled = await guild_settings.autounwarn_enabled()
        threshold = await guild_settings.autowarn_threshold()
        affect_manual_warns = await guild_settings.autounwarn_affect_manual()
        autounwarn_timers = await guild_settings.autowarn_removal_timers()

        msg = f"```yml\n{ctx.guild.name}'s Autounwarn Settings Overview\n\n"
        msg += "Autounwarn_Module: {}\n".format("Enabled" if enabled else "Disabled")
        msg += "Max_Warning_Threshold: {}\n".format(threshold)
        msg += "Autounwarn_Staff_Issued_Warnings: {}\n".format(affect_manual_warns)
        if autounwarn_timers:
            msg += "Autounwarn_Timers:\n"
            for num_warns, delay in autounwarn_timers.items():
                msg += f"\t{num_warns}_Warnings: {delay} seconds\n"
        else:
            msg += "Autounwarn_Timers: Disabled\n"
        msg += "```"
        await ctx.send(msg)

    @autounwarn.command(name="enable")
    async def autounwarn_enable(self, ctx, option: bool = None):
        """Toggle autounwarn module. True/False"""
        if option is None:
            option = not await self.config.guild(ctx.guild).autounwarn_enabled()
        await self.config.guild(ctx.guild).autounwarn_enabled.set(option)
        await ctx.maybe_send_embed(
            "Autounwarning: {}.".format("Enabled" if option else "Disabled")
        )

    @autounwarn.command(name="delay")
    async def autowarn_removal(self, ctx, time: Union[Time, str], num_warns: int = 1):
        """Enter default time delay for an amount of warnings to remove autowarns or "None" to clear set delay"""
        # Input filtering/correction
        num_warns = abs(num_warns)
        if (
            num_warns > 5
        ):  # Don't see a need to configure higher than 5 warns, mainly just to prevent people doing stuff on accident.
            return await ctx.maybe_send_embed(
                f"Unbale to support setting delay for reaching {num_warns} number of active warnings"
            )
        num_warns = str(num_warns)
        timers = await self.config.guild(ctx.guild).autowarn_removal_timers()
        # if timers == {-1: None}:
        #    timers = {}
        if type(time) == str:
            if time.lower().strip() in ["disable", "off", "deactivate", "no", "none"]:
                async with self.config.guild(ctx.guild).autowarn_removal_timers() as timers:
                    if num_warns in timers:
                        prev = timers[num_warns]
                        del timers[num_warns]
                        return await ctx.maybe_send_embed(
                            f"Cleared previous delay of {prev} seconds for {num_warns} number of active warnings."
                        )
                    else:
                        return await ctx.maybe_send_embed(
                            f"No previous set delay found for {num_warns} number of active warnings."
                        )

        async with self.config.guild(ctx.guild).autowarn_removal_timers() as timers:
            timers[num_warns] = time
        await ctx.maybe_send_embed(
            f"Default Auto Unwarn Timer set to {time} seconds for {num_warns} number of active warnings."
        )

    @autounwarn.command(name="threshold", aliases=["max"])
    async def autounwarn_threshold(self, ctx, threshold: int):
        """Set the max threshold of warnings a member can have before all queued unwarns are cancelled. Warnings must be removed manually afterwards."""
        await self.config.guild(ctx.guild).autowarn_threshold.set(threshold)
        await ctx.maybe_send_embed(
            f"Threshold set to {threshold} warnings"
            + "\n"
            + "If a user amasses this amount of warnings before they've been automatically unwarned,"
            + "\n"
            + "all thier queued removal of warnings will be cancelled, and their warnings must be manually removed."
        )

    @autounwarn.command(name="manual")
    async def autounwarn_affect_manual_warns(self, ctx, option: bool = None):
        """Set if staff issued warns should be queued for unwarning. True / False"""
        if option is None:
            option = not await self.config.guild(ctx.guild).autounwarn_affect_manual()
        await self.config.guild(ctx.guild).autounwarn_affect_manual.set(option)
        if option:
            await ctx.maybe_send_embed(
                f"Staff issued warns will now be queued to unwarn. Use `{ctx.prefix}warningset autounwarn overview` to preview your autounwarn settings."
            )
        else:
            await ctx.maybe_send_embed(
                "Staff issued warns will no longer be queued to unwarn by default.."
            )

    @warningset.command(name="setloggingchannel", aliases=["setchannel", "setlogging", "log"])
    @commands.guild_only()
    async def setwarnloggingchannel(self, ctx, channel: discord.TextChannel):
        """Set the Warning Logging Channel in Config"""
        prevloggingChannel = await self.config.guild(ctx.guild).loggingChannel()
        if prevloggingChannel is not None and prevloggingChannel == channel.id:
            await ctx.maybe_send_embed(
                f"Warnings Logging Channel is already set to {channel.mention}."
            )
            return

        prevloggingChannel = self.bot.get_channel(prevloggingChannel)
        await self.config.guild(ctx.guild).loggingChannel.set(channel.id)
        loggingChannel = await self.config.guild(ctx.guild).loggingChannel()
        loggingChannel = self.bot.get_channel(loggingChannel)
        if prevloggingChannel is not None:
            await ctx.maybe_send_embed(
                f"Warnings Logging Channel updated from {prevloggingChannel.mention} to {loggingChannel.mention}."
            )
        else:
            await ctx.maybe_send_embed(
                f"Warnings Logging Channel set to {loggingChannel.mention}."
            )

    @warningset.command(aliases=["mwpd"])
    @commands.guild_only()
    async def multiwarn_prevention_delay(self, ctx, delay: int):
        """Configure amount of seconds for bot to prevent multiple same-warns on a user"""
        multiwarn_prevention_delay = await self.config.guild(
            ctx.guild
        ).multiwarn_prevention_delay()
        delay = abs(delay)
        await self.config.guild(ctx.guild).multiwarn_prevention_delay.set(delay)
        await ctx.maybe_send_embed(f"Multiwarn Prevention Delay now set to {delay} seconds.")

    @warningset.command()
    @commands.guild_only()
    async def compact(self, ctx: commands.Context, option: bool = None):
        """Set compact view of listed warnings True / False."""
        if option is None:
            option = not await self.config.guild(ctx.guild).compact_list()
        await self.config.guild(ctx.guild).compact_list.set(option)
        if option:
            await ctx.maybe_send_embed("Compact listed warns enabled.")
        else:
            await ctx.maybe_send_embed("Compact listed warns disabled.")

    @commands.group()
    @commands.guild_only()
    @checks.guildowner_or_permissions(administrator=True)
    async def warnaction(self, ctx: commands.Context):
        """Manage automated actions for Warnings.

        Actions are essentially command macros. Any command can be run
        when the action is initially triggered, and/or when the action
        is lifted.

        Actions must be given a name and a points threshold. When a
        user is warned enough so that their points go over this
        threshold, the action will be executed.
        """
        pass

    @warnaction.command(name="add")
    @commands.guild_only()
    async def action_add(self, ctx: commands.Context, name: str, points: int):
        """Create an automated action.

        Duplicate action names are not allowed.
        """
        guild = ctx.guild

        exceed_command = await get_command_for_exceeded_points(ctx)
        drop_command = await get_command_for_dropping_points(ctx)

        to_add = {
            "action_name": name,
            "points": points,
            "exceed_command": exceed_command,
            "drop_command": drop_command,
        }

        # Have all details for the action, now save the action
        guild_settings = self.config.guild(guild)
        async with guild_settings.actions() as registered_actions:
            for act in registered_actions:
                if act["action_name"] == to_add["action_name"]:
                    await ctx.maybe_send_embed(_("Duplicate action name found!"))
                    break
            else:
                registered_actions.append(to_add)
                # Sort in descending order by point count for ease in
                # finding the highest possible action to take
                registered_actions.sort(key=lambda a: a["points"], reverse=True)
                await ctx.maybe_send_embed(_("Action {name} has been added.").format(name=name))

    @warnaction.command(name="del")
    @commands.guild_only()
    async def action_del(self, ctx: commands.Context, action_name: str):
        """Delete the action with the specified name."""
        guild = ctx.guild
        guild_settings = self.config.guild(guild)
        async with guild_settings.actions() as registered_actions:
            to_remove = None
            for act in registered_actions:
                if act["action_name"] == action_name:
                    to_remove = act
                    break
            if to_remove:
                registered_actions.remove(to_remove)
                await ctx.tick()
            else:
                await ctx.maybe_send_embed(
                    _("No action named {name} exists!").format(name=action_name)
                )

    @commands.group()
    @commands.guild_only()
    @checks.guildowner_or_permissions(administrator=True)
    async def warnreason(self, ctx: commands.Context):
        """Manage warning reasons.

        Reasons must be given a name, description and points value. The
        name of the reason must be given when a user is warned.
        """
        pass

    @warnreason.command(name="create", aliases=["add"])
    @commands.guild_only()
    async def reason_create(
        self, ctx: commands.Context, name: str, points: int, *, description: str
    ):
        """Create a warning reason."""
        guild = ctx.guild

        if name.lower() == "custom":
            await ctx.maybe_send_embed(_("*Custom* cannot be used as a reason name!"))
            return
        to_add = {"points": points, "description": description}
        completed = {name.lower(): to_add}

        guild_settings = self.config.guild(guild)

        async with guild_settings.reasons() as registered_reasons:
            registered_reasons.update(completed)

        await ctx.maybe_send_embed(_("The new reason has been registered."))

    @warnreason.command(name="del", aliases=["remove"])
    @commands.guild_only()
    async def reason_del(self, ctx: commands.Context, reason_name: str):
        """Delete a warning reason."""
        guild = ctx.guild
        guild_settings = self.config.guild(guild)
        async with guild_settings.reasons() as registered_reasons:
            if registered_reasons.pop(reason_name.lower(), None):
                await ctx.tick()
            else:
                await ctx.maybe_send_embed(_("That is not a registered reason name."))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(ban_members=True)
    async def reasonlist(self, ctx: commands.Context):
        """List all configured reasons for Warnings."""
        guild = ctx.guild
        guild_settings = self.config.guild(guild)
        msg_list = []
        async with guild_settings.reasons() as registered_reasons:
            for r, v in registered_reasons.items():
                if ctx.embed_requested():
                    em = discord.Embed(
                        title=_("Reason: {name}").format(name=r), description=v["description"]
                    )
                    em.add_field(name=_("Points"), value=str(v["points"]))
                    msg_list.append(em)
                else:
                    msg_list.append(
                        _(
                            "Name: {reason_name}\nPoints: {points}\nDescription: {description}"
                        ).format(reason_name=r, **v)
                    )
        if msg_list:
            await menu(ctx, msg_list, DEFAULT_CONTROLS)
        else:
            await ctx.maybe_send_embed(_("There are no reasons configured!"))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(ban_members=True)
    async def actionlist(self, ctx: commands.Context):
        """List all configured automated actions for Warnings."""
        guild = ctx.guild
        guild_settings = self.config.guild(guild)
        msg_list = []
        async with guild_settings.actions() as registered_actions:
            for r in registered_actions:
                if await ctx.embed_requested():
                    em = discord.Embed(title=_("Action: {name}").format(name=r["action_name"]))
                    em.add_field(name=_("Points"), value="{}".format(r["points"]), inline=False)
                    em.add_field(name=_("Exceed command"), value=r["exceed_command"], inline=False)
                    em.add_field(name=_("Drop command"), value=r["drop_command"], inline=False)
                    msg_list.append(em)
                else:
                    msg_list.append(
                        _(
                            "Name: {action_name}\nPoints: {points}\n"
                            "Exceed command: {exceed_command}\nDrop command: {drop_command}"
                        ).format(**r)
                    )
        if msg_list:
            await menu(ctx, msg_list, DEFAULT_CONTROLS)
        else:
            await ctx.maybe_send_embed(_("There are no actions configured!"))

    async def create_warning(self, ctx, user, points, description, mod):
        time = datetime.datetime.utcnow().timestamp()
        warning = {
            "id": hash(mod * time),
            "points": points,
            "description": description,
            "mod": mod,
            "time": time,
            "unwarn": None,
            "guild": ctx.guild.id,
            "user": user.id,
        }
        return warning

    @commands.group(pass_context=True, invoke_without_command=True)
    @commands.guild_only()
    @checks.admin_or_permissions(ban_members=True)
    async def warn(self, ctx: commands.Context, user: Union[discord.Member, str], *, reason: str):
        """Warn the user for the specified reason.

        `<reason>` must be a registered reason name, or *custom* if
        custom reasons are enabled.
        """
        if ctx.invoked_subcommand is None:
            if user == ctx.author:
                await ctx.maybe_send_embed(_("You cannot warn yourself."))
                return

            if type(user) is discord.Member and not await is_allowed_by_hierarchy(
                self.bot, self.mod_settings, ctx.guild, ctx.author, user
            ):
                return await ctx.maybe_send_embed(
                    "I cannot let you do that. You are not higher than the user in the role hierarchy."
                )

            IsMemberTuple = False
            if self.isStrUserID(user):  # User is int ID as str
                searcheduser = ctx.guild.get_member(user)
                if not await is_allowed_by_hierarchy(
                    self.bot, self.mod_settings, ctx.guild, ctx.author, user
                ):
                    return await ctx.maybe_send_embed(
                        "I cannot let you do that. You are not higher than the user in the role hierarchy."
                    )
                if searcheduser is None:  # user not in guild
                    searcheduser = await self.bot.get_user_info(user)
                    user = (
                        namedtuple("Member", "id guild display_name")(
                            searcheduser.id, ctx.guild, searcheduser.display_name
                        )
                        if searcheduser != None
                        else namedtuple("Member", "id guild")(user, ctx.guild)
                    )
                    IsMemberTuple = True
                else:
                    user = searcheduser
            elif type(user) == str:
                user = await self.GetMemberFromString(user, ctx.guild)
                if not await is_allowed_by_hierarchy(
                    self.bot, self.mod_settings, ctx.guild, ctx.author, user
                ):
                    return await ctx.maybe_send_embed(
                        "I cannot let you do that. You are not higher than the user in the role hierarchy."
                    )
                if user is None:  # user not in guild and no ID given
                    await ctx.maybe_send_embed(
                        "User not found in guild. Try mentioning them or using their UserID for an accurate search."
                    )
                    return
            reasons_enabled = await self.config.guild(ctx.guild).reasons_enabled()
            custom_allowed = await self.config.guild(ctx.guild).allow_custom_reasons()
            if not reasons_enabled:
                reason_type = {"points": 1, "description": reason}
            elif reason.lower() == "custom":
                if not custom_allowed:
                    await ctx.maybe_send_embed(
                        _(
                            "Custom reasons are not allowed! Please see `{prefix}reasonlist` for "
                            "a complete list of valid reasons."
                        ).format(prefix=ctx.prefix)
                    )
                    return
                reason_type = await self.custom_warning_reason(ctx)
            else:
                guild_settings = self.config.guild(ctx.guild)
                async with guild_settings.reasons() as registered_reasons:
                    if reason.lower() not in registered_reasons:
                        msg = _("That is not a registered reason!")
                        if custom_allowed:
                            msg += " " + _(
                                "Do `{prefix}warn {user} custom` to specify a custom reason."
                            ).format(prefix=ctx.prefix, user=ctx.author)
                        elif (
                            ctx.guild.owner == ctx.author
                            or ctx.channel.permissions_for(ctx.author).administrator
                            or await ctx.bot.is_owner(ctx.author)
                        ):
                            msg += " " + _(
                                "Do `{prefix}warningset allowcustomreasons true` to enable custom "
                                "reasons. Do `{prefix}warningset reasontoggle` to disable required reasons"
                            ).format(prefix=ctx.prefix)
                        await ctx.maybe_send_embed(msg)
                        return
                    else:
                        reason_type = registered_reasons[reason.lower()]

            time_from_last = await self.time_since_last_warning(user)
            multiwarn_prevention_delay = await self.config.guild(
                ctx.guild
            ).multiwarn_prevention_delay()
            if time_from_last > 0 and time_from_last < multiwarn_prevention_delay:
                await ctx.maybe_send_embed(
                    f"{user} was warned less than {multiwarn_prevention_delay} seconds ago. Multiple same-warn prevention cancelled this warning."
                )
                return

            member_settings = self.config.member(user)
            current_point_count = await member_settings.total_points()
            warning_to_add = await self.create_warning(
                ctx,
                user,
                points=reason_type["points"],
                description=reason_type["description"],
                mod=ctx.author.id,
            )
            async with member_settings.warnings() as user_warnings:
                user_warnings.append(warning_to_add)
            current_point_count += reason_type["points"]
            await member_settings.total_points.set(current_point_count)
            autounwarn = await self.config.guild(ctx.guild).autounwarn_affect_manual()
            if autounwarn:
                await self.queueUnwarn(ctx, user, warning_to_add)
            await self.logWarning(ctx.guild, WarningType.WARN, user, warning_to_add)
            await warning_points_add_check(self.config, ctx, user, current_point_count)
            try:
                em = discord.Embed(
                    title=_("Warning from {user}").format(user=ctx.author),
                    description=reason_type["description"],
                )
                em.add_field(name=_("Points"), value=str(reason_type["points"]))
                if IsMemberTuple:
                    user = searcheduser
                await user.send(
                    _("You have received a warning in {guild_name}.").format(
                        guild_name=ctx.guild.name
                    ),
                    embed=em,
                )
            except discord.HTTPException:
                pass
            await ctx.maybe_send_embed(_("User __**{user}**__ has been warned.").format(user=user))

    async def time_since_last_warning(self, user):
        user_warnings = await self.config.member(user).warnings()
        if len(user_warnings) == 0:
            return 0
        last_warning = user_warnings[-1]
        time = datetime.datetime.fromtimestamp(last_warning["time"])
        differance = time - datetime.datetime.utcnow()
        return int(abs(differance.total_seconds()))

    @warn.command(name="edit")
    async def warn_edit(self, ctx, user: discord.Member, warn_num: int):
        """Edit one of the warnings a user has"""
        try:
            warning = await self.get_user_warning(user, warn_num - 1)
        except WarningNotFound as e:
            return await ctx.maybe_send_embed(_(str(e)))
        if warning is None:
            return await ctx.maybe_send_embed(_("That warning doesn't exist!"))

        option, new_value = await self.interactive_warn_edit(ctx, user, warning)
        if option is None or new_value is None:
            return

        if option == "unwarn":
            await self.queueUnwarn(ctx, user, warning, forced_delay=new_value)
            await ctx.trigger_typing()
            await asyncio.sleep(2)  # Give time for queueUnwarn to update warning
            try:
                updated_warning = await self.get_user_warning(user, id=warning["id"])
            except WarningNotFound as e:
                return await ctx.maybe_send_embed(_(str(e)))
        else:
            async with self.config.member(user).warnings() as user_warnings:
                updated_warning = user_warnings[warn_num - 1]
                updated_warning[option] = new_value
            if option == "points":
                current_point_count = await self.config.member(user).total_points() + (
                    updated_warning["points"] - warning["points"]
                )
                await self.config.member(user).total_points.set(current_point_count)
                await warning_points_remove_check(self.config, ctx, user, current_point_count)
        await self.logWarning(
            ctx.guild,
            WarningType.EDITED_WARN,
            user,
            updated_warning,
            (warning, option),
            issuer=ctx.author,
        )

        em = await self.display_user_warning(ctx, user, updated_warning)
        await ctx.send(embed=em)

    async def interactive_warn_edit(self, ctx, user, warning):
        option, value = None, None

        em = await self.display_user_warning(ctx, user, warning)
        await ctx.maybe_send_embed(
            ctx.author.mention
            + "\n"
            + "Select which attribute of the warning you would like to edit."
            + "\n"
            + "`points`, `reason`, `unwarn`"
        )
        try:
            msg = await ctx.bot.wait_for(
                "message", check=MessagePredicate.same_context(ctx), timeout=25
            )
        except asyncio.TimeoutError:
            await ctx.maybe_send_embed("Warning Editing Cancelled.")
            return None, None
        msg = msg.content
        if msg.lower().strip() in ["no", "stop", "cancel", "cancel", "quit"]:
            await ctx.maybe_send_embed("Warning Editing Cancelled.")
            return None, None
        if "," in msg:
            option, new_value = msg.split(",", 2)
            option = option.strip()
            new_value = new_value.strip()
        else:
            if fuzzywuzzy.fuzz.ratio(msg, "points") > 90:
                option = "points"
            elif (
                fuzzywuzzy.fuzz.ratio(msg, "reason") > 90
                or fuzzywuzzy.fuzz.ratio(msg, "description") > 90
            ):
                option = "description"
            elif fuzzywuzzy.fuzz.ratio(msg, "unwarn") > 90:
                option = "unwarn"
            else:
                return None, None

            if option == "unwarn":
                time = (
                    datetime.datetime.fromtimestamp(warning["unwarn"]).strftime(
                        "%m/%d/%y @ %I:%M %p UTC"
                    )
                    if warning["unwarn"]
                    else None
                )
                await ctx.maybe_send_embed(
                    f"Enter time from now to replace the scheduled unwarn time `{option}: {time}`.`"
                )
            else:
                await ctx.maybe_send_embed(
                    f"Send what you would like to replace the warnings `{option}: {warning[option]}` with?"
                )
            try:
                msg = await ctx.bot.wait_for(
                    "message", check=MessagePredicate.same_context(ctx), timeout=25
                )
            except asyncio.TimeoutError:
                await ctx.maybe_send_embed("Warning Editing Cancelled.")
                return None, None
            msg = msg.content
            if msg.lower().strip() in ["no", "stop", "cancel", "cancel", "quit"]:
                await ctx.maybe_send_embed("Warning Editing Cancelled.")
                return None, None
            new_value = msg

        if option == "points":
            new_value = int(new_value)
        if option == "reason":
            option = "description"
        if option == "unwarn":
            new_value = await Time.fromString(new_value)
            if new_value is None:
                await ctx.maybe_send_embed("Invalid Time. Warning Editing Cancelled.")
                return None, None

        if option not in ["points", "description", "unwarn"]:
            return None, None

        return option, new_value

    async def display_user_warning(self, ctx, user, warning):
        em = discord.Embed(color=0x3DF270, thumbnail=user.avatar_url)
        em.set_author(name=f"Warning for {user}", icon_url=user.avatar_url)
        user_warnings = await self.config.member(user).warnings()
        index = user_warnings.index(warning) + 1
        total = len(user_warnings)
        num_points = warning["points"]
        time = datetime.datetime.fromtimestamp(warning["time"]).strftime("%m/%d/%y @ %I:%M %p UTC")
        unwarn = (
            datetime.datetime.fromtimestamp(warning["unwarn"]).strftime("%m/%d/%y @ %I:%M %p UTC")
            if warning["unwarn"]
            else None
        )
        mod = ctx.guild.get_member(warning["mod"])
        if mod is None:
            mod = discord.utils.get(self.bot.get_all_members(), id=warning["mod"])
            if mod is None:
                mod = await self.bot.get_user_info(warning["mod"])
        em.add_field(
            name=f"{index} of {total} | {num_points} point warning",
            value=f"Issued by {mod.mention}",
            inline=False,
        )
        em.add_field(
            name=f"Issued on {time}",
            value=f'Reason : {warning["description"]}'
            + (f"\nUnwarning: {unwarn}" if unwarn else ""),
            inline=False,
        )
        return em

    @commands.command(name="warnings", aliases=["warns", "listwarns", "lw"])
    @commands.guild_only()
    async def warnings(self, ctx: commands.Context, user: Union[discord.Member, str] = None):
        """List the warnings for the specified user.

        Emit `<userid>` to see your own warnings.

        Note that showing warnings for users other than yourself requires
        appropriate permissions.
        """
        if user is None:
            user = ctx.author
        else:
            if self.isStrUserID(user):  # User is int ID as str
                searcheduser = ctx.guild.get_member(user)
                if searcheduser is None:  # user not in guild
                    searcheduser = await self.bot.get_user_info(user)
                    user = (
                        namedtuple("Member", "id guild display_name")(
                            searcheduser.id, ctx.guild, searcheduser.display_name
                        )
                        if searcheduser != None
                        else namedtuple("Member", "id guild")(user, ctx.guild)
                    )
                else:
                    user = searcheduser
            elif type(user) == str:
                user = await self.GetMemberFromString(user, ctx.guild)
                if user is None:  # user not in guild and no ID given
                    await ctx.maybe_send_embed(
                        "User not found in guild. Try mentioning them or using their UserID for an accurate search."
                    )
                    return

        member_settings = self.config.member(user)
        total_points = await member_settings.total_points()
        async with member_settings.warnings() as user_warnings:
            if not user_warnings:  # no warnings for the user
                await ctx.maybe_send_embed(_(f"__**{user.display_name}**__ has no warnings!"))
            else:
                if not await self.config.guild(ctx.guild).compact_list():

                    return await EmbedPaginateWarnsList(
                        self,
                        ctx,
                        user_warnings,
                        author=f"Warnings for {user} | {total_points}",
                        author_icon_url=user.avatar_url,
                        thumbnail=user.avatar_url,
                    )
                else:
                    msg = ""
                    for warning in user_warnings:
                        id = warning.get("id", "")
                        mod = ctx.guild.get_member(warning["mod"])
                        unwarn = (
                            datetime.datetime.fromtimestamp(warning["unwarn"]).strftime(
                                "%m/%d/%y @ %I:%M %p UTC"
                            )
                            if warning["unwarn"]
                            else None
                        )
                        if mod is None:
                            mod = discord.utils.get(self.bot.get_all_members(), id=warning["mod"])
                            if mod is None:
                                mod = await self.bot.get_user_info(warning["mod"])
                        msg += _(
                            "{warn_num} | {num_points} point warning issued by {user} on {time} for "
                            "{description} {unwarn}\n"
                        ).format(
                            warn_num=f"{user_warnings.index(warning) + 1} of {len(user_warnings)} ({id})",
                            num_points=warning["points"],
                            user=mod,
                            time=datetime.datetime.fromtimestamp(warning["time"]).strftime(
                                "%m/%d/%y @ %I:%M %p UTC"
                            ),
                            description=warning["description"],
                            unwarn=f"| Unwarning at {unwarn}" if unwarn else "",
                        )
                    await ctx.send_interactive(
                        pagify(msg, shorten_by=58),
                        box_lang=_("Warnings for {user} | Total Points {total_points}").format(
                            user=user, total_points=total_points
                        ),
                    )

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(ban_members=True)
    async def unwarn(
        self,
        ctx: commands.Context,
        user: Union[discord.Member, str],
        warn_num: Union[int, str] = None,
    ):
        """Remove a warning from a user. User must be in guild."""
        if user == ctx.author and not ctx.author.guild_permissions.administrator:
            return await ctx.maybe_send_embed(_("You cannot remove warnings from yourself."))

        if type(user) == str:
            user = await self.GetMemberFromString(user, ctx.guild)
            if user is None:  # user not in guild and no ID given
                await ctx.maybe_send_embed(
                    "User not found in guild. Try mentioning them or using their UserID for an accurate search."
                )
                return

        member_settings = self.config.member(user)
        current_point_count = await member_settings.total_points()
        await warning_points_remove_check(self.config, ctx, user, current_point_count)
        try:
            async with member_settings.warnings() as user_warnings:
                if user_warnings:
                    if type(warn_num) == str:
                        if warn_num.lower() in ["all", "every", "*"]:
                            count = len(user_warnings)
                            points = current_point_count
                            warning = {
                                "points": points,
                                "description": "Cleared all warns",
                                "mod": ctx.author.id,
                                "time": datetime.datetime.utcnow().timestamp(),
                            }
                            await member_settings.warnings.set([])
                            await member_settings.total_points.set(0)
                            await self.logWarning(
                                ctx.guild, WarningType.MASS_UNWARN, user, warning
                            )
                            await ctx.maybe_send_embed(
                                f"Removed **{count}** warnings worth **{points}** points from {user.display_name}."
                            )
                            return
                        else:
                            await ctx.maybe_send_embed(
                                f'Unable to parse "{warn_num}" as __**int**__.'
                            )
                            return
                    elif warn_num is not None and (warn_num > len(user_warnings) or warn_num == 0):
                        await ctx.maybe_send_embed(_("That warning doesn't exist!"))
                        return
                    else:
                        try:
                            if warn_num:
                                warning = await self.pop_user_warning(ctx, user, warn_num - 1)
                            else:
                                warning = await self.pop_user_warning(ctx, user)
                            # warning = (
                            #    user_warnings.pop(warn_num - 1)
                            #    if warn_num != None
                            #    else user_warnings.pop()
                            # )
                            mod = discord.utils.get(self.bot.get_all_members(), id=warning["mod"])
                            if mod is None:
                                mod = self.bot.get_user_info(warning["mod"])
                            current_point_count -= warning["points"]
                            await member_settings.total_points.set(current_point_count)
                            await self.logWarning(ctx.guild, WarningType.UNWARN, user, warning)
                        except IndexError:
                            await ctx.maybe_send_embed(f"Failed to unwarn {user}")
                            return
                else:
                    return await ctx.maybe_send_embed(
                        _(f"__**{user.display_name}**__ has no warnings!")
                    )
            await ctx.maybe_send_embed(
                "Removed Warning #{warn_num} | __{points} point warning__ issued by {mod} for {description}".format(
                    warn_num=(warn_num if warn_num != None else len(user_warnings)),
                    points=warning["points"],
                    mod=mod,
                    description=warning["description"],
                )
            )
        except WarningNotFound as e:
            await ctx.maybe_send_embed(str(e))

    async def pop_user_warning(self, ctx, user, index=None):
        warning = await self.get_user_warning(user, index)
        if warning is not None:
            member_settings = self.config.member(user)
            async with member_settings.warnings() as user_warnings:
                user_warnings.remove(warning)
        return warning

    async def get_user_warning(self, user, index=None, id=None):
        member_settings = self.config.member(user)
        current_point_count = await member_settings.total_points()
        async with member_settings.warnings() as user_warnings:
            if user_warnings:
                if id is not None:
                    warnings = [w for w in user_warnings if w.get("id") == id]
                    if warnings:
                        return warnings[0]
                if index is not None and index >= len(user_warnings):
                    raise WarningNotFound(f"Warning Not Found. Index >= {len(user_warnings)}")
                if index == None:
                    warning = user_warnings[-1]
                    return warning
                else:
                    warning = user_warnings[index]
                    return warning
            else:
                raise WarningNotFound(f"No Warnings for user {user.name}")

    async def logWarning(
        self, guild, action: WarningType, user, warning, old_warning=None, issuer=None
    ):
        logChannel = await self.config.guild(guild).loggingChannel()
        logChannel = self.bot.get_channel(logChannel)
        if logChannel is None:
            return
        member_settings = self.config.member(user)
        total_points = await member_settings.total_points()
        if issuer is None:
            mod = discord.utils.get(self.bot.get_all_members(), id=warning["mod"])
        else:
            mod = issuer
        time = datetime.datetime.fromtimestamp(warning["time"])
        description = warning["description"]
        if mod is None:
            mod = self.bot.get_user_info(warning["mod"])
        if action == WarningType.MASS_UNWARN:  # Log Mass Unwarning
            color = 0x820000
            em = discord.Embed(
                title=f"Mass Unwarn | - {warning['points']} Points | Total Points : {total_points}",
                color=color,
            )
            em.set_author(name=f"{user} ( {user.id} )", icon_url=user.avatar_url)
            em.add_field(name="Reason", value=description, inline=False)
            em.set_footer(text=f"Issued By {mod.display_name}", icon_url=mod.avatar_url)
            em.timestamp = time
        elif action == WarningType.AUTO_UNWARN:
            color = 0x820000
            em = discord.Embed(
                title=f"Auto-Unwarned User | - {warning['points']} Points | Total Points : {total_points}\nWarning ID ({warning['id']})",
                color=color,
            )
            em.set_author(name=f"{user} ( {user.id} )", icon_url=user.avatar_url)
            em.add_field(name="Reason", value=description, inline=False)
            em.set_footer(text=f"Issued By {mod.display_name}", icon_url=mod.avatar_url)
            em.timestamp = time
        elif action == WarningType.EDITED_WARN:
            if old_warning:
                old_warning, option = old_warning
                color = discord.Colour.dark_gold()
                em = discord.Embed(
                    title=f"Editied Warn | -> {warning['points']} Points | Total Points : {total_points}\nWarning ID ({warning['id']})",
                    color=color,
                )
                em.set_author(name=f"{user} ( {user.id} )", icon_url=user.avatar_url)
                if option == "unwarn":
                    old_unwarn = (
                        datetime.datetime.fromtimestamp(old_warning["unwarn"]).strftime(
                            "%m/%d/%y @ %I:%M %p UTC"
                        )
                        if old_warning["unwarn"]
                        else None
                    )
                    unwarn = (
                        datetime.datetime.fromtimestamp(warning["unwarn"]).strftime(
                            "%m/%d/%y @ %I:%M %p UTC"
                        )
                        if warning["unwarn"]
                        else None
                    )
                    em.add_field(
                        name=f"Updated {option}",
                        value=f"From `{old_unwarn}` To `{unwarn}`",
                        inline=False,
                    )
                else:
                    em.add_field(
                        name=f"Updated {option}",
                        value=f"From `{old_warning[option]}` To `{warning[option]}`",
                        inline=False,
                    )
                em.set_footer(text=f"Issued By {mod.display_name}", icon_url=mod.avatar_url)
                em.timestamp = time
        else:
            if action == WarningType.WARN:  # Logging Single Warn/Unwarn
                color = 0x3DF270
                em = discord.Embed(
                    title=f"Warned User | + {warning['points']} Points | Total Points : {total_points}\nWarning ID ({warning['id']})",
                    color=color,
                )
            elif action == WarningType.UNWARN:
                color = discord.Color.red()
                em = discord.Embed(
                    title=f"Unwarned User | - {warning['points']} Points| Total Points : {total_points}\nWarning ID ({warning['id']})",
                    color=color,
                )
            em.set_author(name=f"{user} ( {user.id} )", icon_url=user.avatar_url)
            em.add_field(name="Reason", value=description, inline=False)
            em.set_footer(text=f"Issued By {mod.display_name}", icon_url=mod.avatar_url)
            em.timestamp = time
        try:
            await logChannel.send(embed=em)
        except discord.Forbidden:
            pass

    @staticmethod
    async def custom_warning_reason(ctx: commands.Context):
        """Handles getting description and points for custom reasons"""
        to_add = {"points": 0, "description": ""}

        await ctx.maybe_send_embed(_("How many points should be given for this reason?"))
        try:
            msg = await ctx.bot.wait_for(
                "message", check=MessagePredicate.same_context(ctx), timeout=30
            )
        except asyncio.TimeoutError:
            await ctx.maybe_send_embed(_("Ok then."))
            return
        try:
            int(msg.content)
        except ValueError:
            await ctx.maybe_send_embed(_("That isn't a number!"))
            return
        else:
            if int(msg.content) <= 0:
                await ctx.maybe_send_embed(_("The point value needs to be greater than 0!"))
                return
            to_add["points"] = int(msg.content)

        await ctx.maybe_send_embed(_("Enter a description for this reason."))
        try:
            msg = await ctx.bot.wait_for(
                "message", check=MessagePredicate.same_context(ctx), timeout=30
            )
        except asyncio.TimeoutError:
            await ctx.maybe_send_embed(_("Ok then."))
            return
        to_add["description"] = msg.content
        return to_add

    @staticmethod
    def isStrUserID(user: str):
        return type(user) == str and user.isdigit()

    @staticmethod
    async def GetMemberFromString(member: str, guild: discord.Guild):
        return discord.utils.find(
            lambda m: m.name[: len(member)].lower() == member.lower()
            or fuzzywuzzy.fuzz.ratio(m.display_name, member) >= 95,
            guild.members,
        )

    @commands.group(aliases=["wf"])
    @commands.guild_only()
    @checks.admin_or_permissions(ban_members=True)
    async def warnfilter(self, ctx: commands.Context):
        """Manage filter settings for Warnings."""
        pass

    @warnfilter.command(name="add")
    async def addFilter(self, ctx, *, words: str):
        """Add words to the filter to auto warn for."""
        added = []
        failed = []
        split_words = words.split()
        tmp = ""
        async with self.config.guild(ctx.guild).filtered_words() as filtered_words:
            for word in split_words:
                if word.lower() not in filtered_words:
                    if not word.startswith('"') and not word.endswith('"') and not tmp:
                        filtered_words.append(word)
                        added.append(word)
                    else:
                        if word.startswith('"'):
                            tmp += word[1:] + " "
                        elif word.endswith('"'):
                            tmp += word[:-1]
                            if tmp.lower() not in filtered_words:
                                filtered_words.append(tmp)
                                added.append(tmp)
                            else:
                                failed.append(tmp)
                            tmp = ""
                        else:
                            tmp += word + " "
                else:
                    failed.append(word)
        await ctx.message.delete()

        response = "```diff\n" + "Added the following words to the filter list:" + "\n\n"
        if added:
            for word in added:
                response += f"+ {word}" + "\n"
        if failed:
            response += "\n" + "-Failed to add the following words:" + "\n"
            for word in failed:
                response += f"- {word}" + "\n"
        response += "```"
        try:
            if len(response) < 2000:
                await ctx.send(response)
            else:
                await ctx.send(response[:1996] + "```")
        except discord.Forbidden:
            pass

    @warnfilter.command(name="showword")
    async def toggle_showing_word(self, ctx, *, show: str):
        """Toggles showing the banned word spoken in future filter warnings."""
        show = show.lower()
        if show == "true":
            show_val = True
        elif show == "false":
            show_val = False

        await self.config.guild(ctx.guild).show_filtered_word.set(show_val)
        await ctx.send(
            (
                "Filtered words are now being shown in future warnings."
                if show_val
                else "Filtered words are not being shown in future warnings."
            )
        )

    @warnfilter.command(name="remove", alias=["delete", "del"])
    async def removeFilter(self, ctx, *, words):
        """Remove words from the filter"""
        removed = []
        failed = []
        split_words = words.split()
        tmp = ""
        async with self.config.guild(ctx.guild).filtered_words() as filtered_words:
            if len(split_words) == 1 and split_words[0] in ["all", "every", "*"]:
                filtered_words = []
                await ctx.maybe_send_embed("Removed all warn filter words.")
                return
            for word in split_words:
                if not word.startswith('"') and not word.endswith('"') and not tmp:
                    if word.lower() in filtered_words:
                        filtered_words.remove(word)
                        removed.append(word)
                    else:
                        failed.append(tmp)
                else:
                    if word.startswith('"'):
                        tmp += word[1:] + " "
                    elif word.endswith('"'):
                        tmp += word[:-1]
                        if tmp.lower() in filtered_words:
                            filtered_words.remove(tmp)
                            removed.append(tmp)
                        else:
                            failed.append(tmp)
                        tmp = ""
                    else:
                        tmp += word + " "

        response = "```diff\n" + "Removed the following words from the filter list:" + "\n\n"
        if removed:
            for word in removed:
                response += f"+ {word}" + "\n"
        if failed:
            response += "\n" + "- Failed to add the following words:" + "\n"
            for word in failed:
                response += f"- {word}" + "\n"
        response += "```"
        try:
            if len(response) < 2000:
                await ctx.send(response)
            else:
                await ctx.send(response[:1996] + "```")
        except discord.Forbidden:
            pass

    @warnfilter.command(name="list")
    async def listFilter(self, ctx):
        """List current filtered words that will auto warn for."""
        filtered_words = await self.config.guild(ctx.guild).filtered_words()
        if filtered_words:
            words = ", ".join(filtered_words)
            words = "Filtered in this server:" + "\n\n" + words
            try:
                for page in pagify(words, delims=[" ", "\n"], shorten_by=8):
                    msg = await ctx.author.send(page)
            except discord.Forbidden:
                await ctx.maybe_send_embed("I can't send direct messages to you.")
            await ctx.maybe_send_embed(
                f"I DM'd you the list. Click here to jump to the list of filtered words.\n<{msg.jump_url}>"
            )
        else:
            await ctx.maybe_send_embed(
                "There are no current filtered words that trigger auto warning."
            )

    @warnfilter.command(name="points")
    @checks.guildowner_or_permissions(administrator=True)
    async def filterwarnpoints(self, ctx, amount: int = None):
        """Configure the amount of warning points a user should be given for using a filtered word"""
        guild = ctx.guild
        warn_amount = await self.config.guild(guild).filter_warn_amount()
        if amount is not None:
            await self.config.guild(guild).filter_warn_amount.set(amount)
            warn_amount = amount
        await ctx.maybe_send_embed(
            f"Users will be given `{warn_amount} warning points` for using a filtered word."
        )

    # Preperation for reloading unwarn tasks in next update

    # async def track_warning(self, warning):
    #    id = warning['id']
    #    async with self.config.tracked_warns() as tracked_warns:
    #        if id not in tracked_warns:
    #            tracked_warns.append(id)

    # async def untrack_warning(self, warning):
    #    id = warning['id']
    #    async with self.config.tracked_warns() as tracked_warns:
    #        if id in tracked_warns:
    #            tracked_warns.remove(id)

    async def get_autounwarn_delay(self, ctx, num_warnings):
        autowarn_removal_timers = await self.config.guild(ctx.guild).autowarn_removal_timers()
        if not autowarn_removal_timers:
            return None
        delays = list(autowarn_removal_timers.values())
        seconds = None
        x = 0
        while x <= num_warnings:
            s = autowarn_removal_timers.get(str(x))
            seconds = s if s is not None else seconds
            x += 1
            if (seconds in delays and delays.index(seconds) == len(delays) - 1) or (x > 5):
                break
        # Keeps looping through dict and keeps highest delay at or before num_warnings
        # If num_warnings is 3 and highest delay set is 2 weeks for 2 warnings, will retain 2 warnings for all num_warnings past or equal to 2
        return seconds

    async def queueUnwarn(self, ctx, user, warning, forced_delay=None):
        autounwarn_enabled = await self.config.guild(ctx.guild).autounwarn_enabled()
        if not autounwarn_enabled:
            return

        queued = self.unwarn_tasks.get(user.id)  # {warning_id : task}
        if forced_delay is None:
            seconds = await self.get_autounwarn_delay(
                ctx, (len(list(queued.keys())) + 1 if queued else 1)
            )
        else:
            seconds = forced_delay
        if seconds is None:
            return

        if not queued:
            self.unwarn_tasks[user.id] = {}
            queued = self.unwarn_tasks[user.id]
            warning = await self.get_user_warning(user, id=warning["id"])
            task = asyncio.ensure_future(self.autoUnwarn(ctx, seconds, user, warning))
            queued[warning["id"]] = task
            # await self.track_warning(warning)
            return True, f"Queued unWarn for warning {warning} {task}\n"
        else:
            warnings = [warning]
            warning_ids = list(queued.keys())

            if warning["id"] in warning_ids:  # Editing Scheduled Unwarn Time
                task = queued[warning["id"]]
                task.cancel()
                task = asyncio.ensure_future(self.autoUnwarn(ctx, seconds, user, warning))
                queued["id"] = task
                return True, f"Edited queued unWarn for warning {warning} {task}\n"

            for id in warning_ids:
                warning = await self.get_user_warning(user, id=id)
                warnings.append(warning)
                task = queued[id]
                task.cancel()
                del queued[id]

            autowarn_threshold = await self.config.guild(ctx.guild).autowarn_threshold()
            if len(warnings) >= autowarn_threshold:
                member_settings = self.config.member(user)
                async with member_settings.warnings() as user_warnings:
                    for id in warning_ids:
                        try:
                            warning = await self.get_user_warning(user, id=id)
                            await self.untrack_warning(warning)
                            warning = user_warnings[user_warnings.index(warning)]
                            warning["unwarn"] = None
                        except (IndexError, ValueError):
                            pass
                return False, f"Max Warnings reached. Cancelled {len(warnings)} queued unwarns."

            for warning in warnings:
                warning = await self.get_user_warning(user, id=warning["id"])
                task = asyncio.ensure_future(
                    self.autoUnwarn(ctx, (seconds + 1 * warnings.index(warning)), user, warning)
                )  # Add extra delay between tasks to prevent multiple tasks iterating over warns while editing them
                queued[warning["id"]] = task
            return True, f"\nQueued unWarns for {len(warnings)} warnings {warnings}\n"

    async def autoUnwarn(self, ctx, seconds, user, warning):
        member_settings = self.config.member(user)
        async with member_settings.warnings() as user_warnings:
            try:
                warning = user_warnings[user_warnings.index(warning)]
                warning["unwarn"] = (
                    datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds)
                ).timestamp()
            except (ValueError, IndexError):
                pass
        try:
            await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            try:
                warning = await self.get_user_warning(user, id=warning["id"])
                warning = user_warnings[user_warnings.index(warning)]
                warning["unwarn"] = None
            except (IndexError, ValueError):
                pass
        current_point_count = await member_settings.total_points()
        if ctx is not None:
            await warning_points_remove_check(self.config, ctx, user, current_point_count)
        async with member_settings.warnings() as user_warnings:
            if user_warnings:
                try:
                    warning = await self.get_user_warning(user, id=warning["id"])
                    if not warning:
                        return
                    if warning not in user_warnings:
                        return
                    warning = user_warnings.pop(user_warnings.index(warning))
                    current_point_count -= warning["points"]
                    await member_settings.total_points.set(current_point_count)
                    await self.logWarning(ctx.guild, WarningType.AUTO_UNWARN, user, warning)
                except (ValueError, IndexError):
                    if ctx is not None:
                        try:
                            await ctx.maybe_send_embed(
                                f"Failed to auto unwarn {user} for `{warning['description']}`."
                            )
                        except discord.Forbidden:
                            pass
        del self.unwarn_tasks[user.id][warning["id"]]

    async def checkFilter(self, message: discord.Message):
        ctx = await self.bot.get_context(message)
        if ctx.command == self.warnfilter:
            return

        filtered_words = await self.config.guild(message.guild).filtered_words()
        if filtered_words:
            for word in filtered_words:
                if word in message.content.lower():
                    try:
                        await message.delete()
                    except discord.Forbidden:
                        pass
                    else:
                        user = message.author
                        member_settings = self.config.member(user)
                        current_point_count = await member_settings.total_points()
                        warn_amount = await self.config.guild(message.guild).filter_warn_amount()
                        show_word = await self.config.guild(message.guild).show_filtered_word()
                        warning_to_add = await self.create_warning(
                            ctx,
                            user,
                            points=warn_amount,
                            description=f"Using filtered word {(': ||' + word + '||' if show_word else '')}.",
                            mod=message.guild.me.id,
                        )
                        await self.logWarning(
                            message.guild, WarningType.WARN, user, warning_to_add
                        )

                        async with member_settings.warnings() as user_warnings:
                            user_warnings.append(warning_to_add)
                        current_point_count += warning_to_add["points"]
                        await member_settings.total_points.set(current_point_count)
                        if ctx.valid:
                            await warning_points_add_check(
                                self.config, ctx, user, current_point_count
                            )
                        try:
                            em = discord.Embed(
                                title=_("Warning from {user}").format(user=message.guild.me),
                                description=warning_to_add["description"],
                            )
                            em.add_field(name=_("Points"), value=str(warning_to_add["points"]))
                            await user.send(
                                _("You have received a warning in {guild_name}.").format(
                                    guild_name=message.guild.name
                                ),
                                embed=em,
                            )
                        except discord.HTTPException:
                            pass
                        except discord.Forbidden:
                            pass
                        try:
                            await message.channel.send(
                                _(
                                    f"User __**{user}**__ has been warned for using a filtered word."
                                )
                            )
                        except discord.Forbidden:
                            pass
                        passed, status = await self.queueUnwarn(ctx, user, warning_to_add)

    async def VIP_PingWarn(self, message, user, vip):
        if type(vip) == discord.Role:
            vip_role = True
        else:
            vip_role = False
        ctx = await self.bot.get_context(message)
        member_settings = self.config.member(user)
        current_point_count = await member_settings.total_points()
        warn_amount = await self.config.guild(ctx.guild).vip_warn_amount()
        description = f"Pinging VIP Role {vip}" if vip_role else f"Pinging VIP {vip}"
        warning_to_add = await self.create_warning(
            ctx, user, warn_amount, description, message.guild.me.id
        )

        await self.logWarning(message.guild, WarningType.WARN, user, warning_to_add)
        async with member_settings.warnings() as user_warnings:
            user_warnings.append(warning_to_add)
        current_point_count += warning_to_add["points"]
        await member_settings.total_points.set(current_point_count)
        await warning_points_add_check(self.config, ctx, user, current_point_count)
        try:
            em = discord.Embed(
                title=_("Warning from {user}").format(user=message.guild.me),
                description=warning_to_add["description"],
            )
            em.add_field(name=_("Points"), value=str(warning_to_add["points"]))
            await user.send(
                _("You have received a warning in {guild_name}.").format(
                    guild_name=message.guild.name
                ),
                embed=em,
            )
        except (discord.HTTPException, discord.Forbidden):
            pass
        try:
            await message.channel.send(
                _("User __**{user}**__ has been warned for {description}.").format(
                    user=user, description=warning_to_add["description"]
                )
            )
        except discord.Forbidden:
            pass
        passed, status = await self.queueUnwarn(ctx, user, warning_to_add)

    async def VIP_PingWarn(self, message, user, vip):
        if type(vip) == discord.Role:
            vip_role = True
        else:
            vip_role = False
        ctx = await self.bot.get_context(message)
        member_settings = self.config.member(user)
        current_point_count = await member_settings.total_points()
        warn_amount = await self.config.guild(ctx.guild).vip_warn_amount()
        description = f"Pinging VIP Role {vip}" if vip_role else f"Pinging VIP {vip}"
        warning_to_add = {
            "points": warn_amount,
            "description": description,
            "mod": message.guild.me.id,
            "time": datetime.datetime.utcnow().timestamp(),
        }
        await self.logWarning(message.guild, "warn", user, warning_to_add)
        async with member_settings.warnings() as user_warnings:
            user_warnings.append(warning_to_add)
        current_point_count += warning_to_add["points"]
        await member_settings.total_points.set(current_point_count)
        await warning_points_add_check(self.config, ctx, user, current_point_count)
        try:
            em = discord.Embed(
                title=_("Warning from {user}").format(user=message.guild.me),
                description=warning_to_add["description"],
            )
            em.add_field(name=_("Points"), value=str(warning_to_add["points"]))
            await user.send(
                _("You have received a warning in {guild_name}.").format(
                    guild_name=message.guild.name
                ),
                embed=em,
            )
        except (discord.HTTPException, discord.Forbidden):
            pass
        try:
            await message.channel.send(
                _("User __**{user}**__ has been warned for {description}.").format(
                    user=user, description=warning_to_add["description"]
                )
            )
        except discord.Forbidden:
            pass

    async def on_message_edit(self, before, after):
        await self.on_message(after)

    async def on_message(self, message):
        def HasIgnoredRole(member):
            for role in member.roles:
                if role.id in ignored_roles:
                    return True
            return False

        def HasVipRole(member):
            for role in member.roles:
                if role.id in RoleVipList:
                    return True
            return False

        if message.guild:  # Guild only
            if not message.author.bot:  # Ignores messages from bots

                await self.checkFilter(message)

                ignore_commands = await self.config.guild(message.guild).vip_ignore_commands()
                if ignore_commands:
                    if message.content.startswith(("!", ";;", "t@", "t!", "!!", "-")):
                        return  # Ignore messages that start with common bot prefixes
                VipList = await self.config.guild(message.guild).vips()
                RoleVipList = await self.config.guild(message.guild).role_vips()
                ignored_users = await self.config.guild(message.guild).vip_ignore_users()
                ignored_roles = await self.config.guild(message.guild).vip_ignore_roles()
                if (
                    HasIgnoredRole(message.author) or message.author.id in ignored_users
                ):  # Dismiss Ignored Users and users with Ignored Roles
                    return
                for role in message.role_mentions:
                    if role.id in RoleVipList:  # Message mentions a VIP Role
                        await self.VIP_PingWarn(message, message.author, role)

                for user in message.mentions:
                    if (
                        not message.author.id in VipList
                    ):  # Other VIPs excluded from warn for pinging VIPs
                        if user.id in VipList or HasVipRole(
                            user
                        ):  # If message mentions a VIP, warn them
                            await self.VIP_PingWarn(message, message.author, user)
