import discord
import asyncio
import collections
import re
import datetime
import inspect
from dateutil.parser import parse
from redbot.core import commands, Config, checks
from redbot.core.utils.predicates import MessagePredicate
from typing import Optional, Union


def from_NWStaff_guild(ctx):
    return ctx.guild.id == 420530084294688775


def RaiseMissingArguement():
    raise commands.MissingRequiredArgument(
        inspect.Parameter("startdate", inspect.Parameter.POSITIONAL_ONLY)
    )


class Date(commands.Converter):
    async def convert(self, ctx, arg):
        result = None
        try:
            result = parse(arg)
        except ValueError:
            result = None
        if result is None:
            raise commands.BadArgument('Unable to parse Date "{}" '.format(arg))
        return result

    @staticmethod
    async def fromString(arg):
        try:
            result = parse(arg)
        except ValueError:
            result = None
        return result


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

    async def convert(self, ctx, arg):
        result = None
        seconds = self.get_seconds(arg)
        time_now = datetime.datetime.utcnow()
        days, secs = divmod(seconds, 3600 * 24)
        end_time = time_now + datetime.timedelta(days=days, seconds=secs)
        result = end_time
        if result is None:
            raise commands.BadArgument('Unable to parse Date "{}" '.format(arg))
        return result

    @classmethod
    async def fromString(cls, arg):
        seconds = cls.get_seconds(cls, arg)
        time_now = datetime.datetime.utcnow()
        if seconds is not None:
            days, secs = divmod(seconds, 3600 * 24)
            end_time = time_now + datetime.timedelta(days=days, seconds=secs)
            return end_time
        else:
            return None

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


class LOACog(commands.Cog):
    """Commands for creating and modifying Leave of Abscences for Northwood Staff"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 8237492837454039, force_registration=True)
        self.config.register_global(
            loas=[],
            scheduledLoas=[],
            loaChannel=441315223052484618,
            loggingChannel=536271582264295457,
            loaRoleID=None,
        )
        self.futures = []
        self.time_format = (
            "%b %d, %Y @ %I:%M %p UTC"
        )  # https://docs.python.org/2/library/datetime.html#strftime-strptime-behavior
        asyncio.ensure_future(self.restart_loas())

    def is_BotStaff_NW_Management_or_higher(self, ctx):
        StaffServer = self.bot.get_guild(420530084294688775)
        hasManagementOrHigher = False
        hasBotStaff = False
        if StaffServer is not None:
            member = StaffServer.get_member(ctx.author.id)
            if member is not None:
                botStaffRole = discord.utils.get(StaffServer.roles, name="Bot Engineer")
                if botStaffRole is not None:
                    hasBotStaff = botStaffRole in member.roles
                managementRole = discord.utils.get(StaffServer.roles, name="Management")
                if managementRole is not None:
                    hasManagementOrHigher = (
                        StaffServer.roles.index(member.top_role) >= managementRole.position
                    )
            return hasManagementOrHigher or hasBotStaff
        else:
            return False

    @commands.group()
    @commands.guild_only()
    @commands.check(from_NWStaff_guild)
    async def loa(self, ctx):
        if ctx.invoked_subcommand is None:
            pass

    @loa.command(name="submit", aliases=["create"])
    async def submitLOA(self, ctx, user: Optional[discord.Member] = None):
        """Submit a Leave of Absence for your Northwood Staff position"""
        if user is None or user == ctx.author:
            user = ctx.author
        elif user is not None and not self.is_BotStaff_NW_Management_or_higher(ctx):
            await ctx.send("You are not allowed to submit LOAs for others.")
            return
        sLoas = await self.config.scheduledLoas()
        found = [loa for loa in sLoas if loa["authorID"] == user.id]
        if found:
            loa = found[0]
            await self.previewLOA("scheduled", ctx, user, loa)
            return
        loas = await self.config.loas()
        found = [loa for loa in loas if loa["authorID"] == user.id]
        if found:
            loa = found[0]
            await self.previewLOA("started", ctx, user, loa)
            return
        try:
            startdate, enddate, reason = await self.loa_time_input(ctx)
        except TypeError:
            return
        channel = ctx.message.channel
        if reason is None:
            return await ctx.send("You must provide a reason for your LOA.")
        if startdate is None:
            start_time = datetime.datetime.utcnow()
            delay = 0
        else:
            start_time = startdate
            delay = int((start_time - datetime.datetime.utcnow()).total_seconds())
        if enddate is None:
            return await ctx.send("You must provide a valid End Date for your LOA.")
        end_time = enddate
        loa = {
            "messageID": None,
            "ctxChannelID": channel.id,
            "authorID": user.id,
            "start_time": start_time.timestamp(),
            "end_time": end_time.timestamp(),
            "reason": reason,
        }
        if start_time > datetime.datetime.utcnow():
            em = discord.Embed(
                title="Northwood Studios Staff Leave of Abscence",
                description=f"Your LOA has been scheduled.",
                color=0xFF8800,
            )
            em.set_thumbnail(url=user.avatar_url)
            em.add_field(name="Staff Name", value=user.mention)
            em.add_field(name="Reason", value=reason)
            em.add_field(name="Starts On", value=start_time.strftime(self.time_format))
            em.add_field(name="Ends On", value=end_time.strftime(self.time_format))
            await ctx.send(embed=em)
            await self.logLOA("scheduled", user, loa)
            async with self.config.scheduledLoas() as sLoas:
                sLoas.append(loa)
        self.futures.append(asyncio.ensure_future(self.startLOA(ctx, user, delay, loa)))

    async def previewLOA(self, state, ctx, user, loa):
        start_time = datetime.datetime.fromtimestamp(loa["start_time"]).strftime(self.time_format)
        end_time = datetime.datetime.fromtimestamp(loa["end_time"]).strftime(self.time_format)
        reason = loa["reason"]
        em = discord.Embed()
        if state.lower() == "started":
            em.color = 0x3DF270
        elif state.lower() == "scheduled":
            em.color = 0xFF8800
        em.set_author(name="Northwood Studios Staff Leave of Abscence")
        em.set_thumbnail(url=user.avatar_url)
        em.add_field(name="Staff Name", value=user.mention)
        em.add_field(name="Reason", value=reason)
        em.add_field(name="Starts On", value=start_time)
        em.add_field(name="Ends On", value=end_time, inline=False)
        if state.lower() == "started":
            await ctx.send(
                content=f"{user.name} already has an active LOA. Use `!loa cancel` to cancel the active LOA.",
                embed=em,
            )
        elif state.lower() == "scheduled":
            await ctx.send(
                content=f"{user.name} already has a scheduled LOA. Use `!loa cancel` to cancel the scheduled LOA.",
                embed=em,
            )

    @loa.command(name="cancel", aliases=["remove", "delete"])
    async def usercancelLOA(self, ctx, user: discord.Member = None):
        """Cancel an active or scheduled LOA"""
        loaChannel = self.bot.get_channel(await self.config.loaChannel())

        if user is None or user == ctx.author:
            user = ctx.author
        elif user is not None and not self.is_BotStaff_NW_Management_or_higher(ctx):
            await ctx.send("You are not allowed to cancel LOAs for others.")
            return
        loas = await self.config.loas()
        found = [loa for loa in loas if loa["authorID"] == user.id]
        if found:
            for loa in found:
                await self.cancelLOA(loa, ctx.author)
        sLoas = await self.config.scheduledLoas()
        found2 = [loa for loa in sLoas if loa["authorID"] == user.id]
        if found2:
            for loa in found2:
                await self.cancelLOA(loa, ctx.author)
        role = ctx.guild.get_role(await self.config.loaRoleID())
        if role is not None:
            try:
                await user.remove_roles(role, reason="Ended Leave of Abscence")
            except discord.Forbidden:
                pass
        if not found and not found2:
            await ctx.send(f"`{user.display_name}` does not have an active or scheduled LOA.")

    @staticmethod
    async def loa_time_input(ctx: commands.Context):
        """Handles getting Start and End Dates/Times for LOAs"""
        await ctx.send(
            "When will your LOA begin? Enter as `month/day` or `3d`." + "\n"
            "Enter `now` if it will begin right now."
        )
        try:
            msg = await ctx.bot.wait_for(
                "message", check=MessagePredicate.same_context(ctx), timeout=10
            )
        except asyncio.TimeoutError:
            return await ctx.send("LOA Submission Cancelled.")
        startdate = await Time.fromString(msg.content)
        if startdate is None:
            startdate = await Date.fromString(msg.content)
        await ctx.send("When will your LOA end? Enter as `month/day` or `3d`.")
        try:
            msg = await ctx.bot.wait_for(
                "message", check=MessagePredicate.same_context(ctx), timeout=10
            )
        except asyncio.TimeoutError:
            return await ctx.send("LOA Submission Cancelled.")
        enddate = await Time.fromString(msg.content)
        if enddate is None:
            enddate = await Date.fromString(msg.content)
        if enddate is None:
            return await ctx.send("Unable to parse End Date.")
        await ctx.send("Enter your reason for your LOA.")
        try:
            msg = await ctx.bot.wait_for(
                "message", check=MessagePredicate.same_context(ctx), timeout=30
            )
        except asyncio.TimeoutError:
            return await ctx.send("LOA Submission Cancelled.")
        reason = msg.content
        return startdate, enddate, reason

    async def startLOA(self, ctx, user, delay, loa):
        """Begins and Activates LOA within LOA Channel"""
        await asyncio.sleep(delay)
        start_time = datetime.datetime.fromtimestamp(loa["start_time"]).strftime(self.time_format)
        end_time = datetime.datetime.fromtimestamp(loa["end_time"]).strftime(self.time_format)
        reason = loa["reason"]
        em = discord.Embed(color=0x3DF270)
        em.set_author(name="Northwood Studios Staff Leave of Abscence")
        em.set_thumbnail(url=user.avatar_url)
        em.add_field(name="Staff Name", value=user.mention)
        if reason != None:
            em.add_field(name="Reason", value=reason)
        em.add_field(name="Starts On", value=start_time)
        em.add_field(name="Ends On", value=end_time, inline=False)

        loaChannel = self.bot.get_channel(await self.config.loaChannel())
        try:
            message = await loaChannel.send(embed=em)
        except discord.Forbidden:
            await ctx.send("I do not have permissions to send a message in " + loaChannel.mention)
        except AttributeError:
            await ctx.send("LOA Channel is not set.")
        else:
            await ctx.send(f"Leave Of Abscence created in {loaChannel.mention}.")
            async with self.config.scheduledLoas() as sLoas:
                if loa in sLoas:
                    sLoas.remove(loa)
            loa["messageID"] = message.id
            seconds = (
                datetime.datetime.fromtimestamp(loa["end_time"]) - datetime.datetime.utcnow()
            ).total_seconds()
            channel = ctx
            async with self.config.loas() as loas:
                loas.append(loa)
            self.futures.append(
                asyncio.ensure_future(self.remind_loa_ended(user, channel, message, seconds, loa))
            )
            role = ctx.guild.get_role(await self.config.loaRoleID())
            if role is not None:
                try:
                    await user.add_roles(role, reason="Started Leave of Abscence")
                except discord.Forbidden:
                    pass
            await self.logLOA("started", user, loa)

    async def cancelLOA(self, loa, issuer: discord.Member = None):
        loaChannel = self.bot.get_channel(await self.config.loaChannel())
        em = discord.Embed(
            title="Northwood Studios Staff Leave of Abscence",
            description=f"Your LOA has been cancelled.",
            color=0x820000,
        )
        user = self.bot.get_user(loa["authorID"])
        start_time = datetime.datetime.fromtimestamp(loa["start_time"]).strftime(self.time_format)
        end_time = datetime.datetime.fromtimestamp(loa["end_time"]).strftime(self.time_format)
        if user is None:  # User not found
            user2 = self.bot.get_user_info(loa["authorID"])
            if user2 is not None:
                em.add_field(name="Staff Name", value=user2.name, inline=False)
        em.add_field(name="Start Time", value=start_time)
        em.add_field(name="End Time", value=end_time, inline=False)
        em.add_field(name="Reason", value=loa["reason"], inline=False)
        channel = self.bot.get_channel(loa["ctxChannelID"])
        async with self.config.scheduledLoas() as sLoas:
            if loa in sLoas:
                sLoas.remove(loa)
        async with self.config.loas() as loas:
            if loa in loas:
                try:
                    loas.remove(loa)
                except ValueError:
                    pass
        message = None
        if loa["messageID"] is not None:
            try:
                message = await loaChannel.get_message(loa["messageID"])
            except discord.NotFound:
                pass
        try:
            await channel.send(content=user.mention, embed=em)
        except AttributeError:
            await channel.send(embed=em)
        except discord.Forbidden:
            pass
        if message is not None:
            try:
                await message.delete()
            except discord.Forbidden:
                pass
        if issuer is not None:
            await self.logLOA("cancelled", user, loa, issuer)
        else:
            await self.logLOA("cancelled", user, loa)
        await self.cleanup_tasks()

    async def logLOA(self, state, user, loa, issuer: discord.Member = None):
        """"Logs LOA and it's started/ended status to Config's LOA Logging Channel."""
        loggingChannel = await self.config.loggingChannel()
        logChannel = self.bot.get_channel(loggingChannel)

        start_time = datetime.datetime.fromtimestamp(loa["start_time"]).strftime(self.time_format)
        end_time = datetime.datetime.fromtimestamp(loa["end_time"]).strftime(self.time_format)
        reason = loa["reason"]
        em = discord.Embed()
        em.set_author(name="Northwood Studios Staff Leave of Abscence " + state.capitalize())
        em.set_thumbnail(url=user.avatar_url)
        em.add_field(name="Staff Name", value=user.mention)
        if reason != None:
            em.add_field(name="Reason", value=reason)
        em.add_field(name="Start Date", value=start_time)
        em.add_field(name="End Date", value=end_time)
        if state.lower() == "started":
            em.color = 0x3DF270
        elif state.lower() == "scheduled":
            em.color = 0xFF8800
        elif state.lower() == "cancelled":
            em.color = 0x820000
            if issuer is not None:
                em.set_footer(text=f"Issued by {issuer.display_name}", icon_url=issuer.avatar_url)
        else:
            em.color = discord.Color.red()
        try:
            await logChannel.send(embed=em)
        except discord.Forbidden:
            pass

    async def remind_loa_ended(self, user, channel, message, seconds, loa):
        """Deletes the LOA and reminds the author their LOA has ended."""
        await asyncio.sleep(seconds)
        start_time = datetime.datetime.fromtimestamp(loa["start_time"]).strftime(self.time_format)
        end_time = datetime.datetime.fromtimestamp(loa["end_time"]).strftime(self.time_format)
        em = discord.Embed(
            title="Northwood Studios Staff Leave of Abscence",
            description=f"Your LOA has ended.",
            color=discord.Color.red(),
        )
        em.add_field(name="Start Time", value=start_time)
        em.add_field(name="End Time", value=end_time, inline=False)
        em.add_field(name="Reason", value=loa["reason"], inline=False)
        async with self.config.loas() as loas:
            if loa in loas:
                try:
                    loas.remove(loa)
                except ValueError:
                    pass
                await channel.send(content=user.mention, embed=em)
        if message is not None:
            try:
                await message.delete()
            except discord.Forbidden:
                pass
        role = channel.guild.get_role(await self.config.loaRoleID())
        if role is not None:
            try:
                await user.remove_roles(role, reason="Ended Leave of Abscence")
            except discord.Forbidden:
                pass
        await self.logLOA("ended", user, loa)
        await self.cleanup_tasks()

    async def restart_loas(self):
        await self.bot.wait_until_ready()
        for loa in await self.config.loas():
            time_diff = (
                datetime.datetime.fromtimestamp(loa["end_time"]) - datetime.datetime.utcnow()
            )
            seconds = max(0, time_diff.total_seconds())
            user = self.bot.get_user(loa["authorID"])
            channel = self.bot.get_channel(loa["ctxChannelID"])
            loaChannel = self.bot.get_channel(await self.config.loaChannel())
            try:
                message = await loaChannel.get_message(loa["messageID"])
            except discord.NotFound:  # If LOA not found in LoaChannel, assume it was deleted by management and end LOA.
                await self.cancelLOA(loa)
                continue
            self.futures.append(
                asyncio.ensure_future(self.remind_loa_ended(user, channel, message, seconds, loa))
            )
        for loa in await self.config.scheduledLoas():
            user = self.bot.get_user(loa["authorID"])
            ctx = self.bot.get_channel(loa["ctxChannelID"])
            start_time = datetime.datetime.fromtimestamp(loa["start_time"])
            delay = int((start_time - datetime.datetime.utcnow()).total_seconds())
            self.futures.append(asyncio.ensure_future(self.startLOA(ctx, user, delay, loa)))

    async def cleanup_tasks(self):
        for future in self.futures:
            if future.done():
                future.cancel()

    @loa.command(aliases=["setchannel"])
    async def setloachannel(self, ctx, channel: discord.TextChannel):
        """Set the LOA's Channel in Config"""
        if not self.is_BotStaff_NW_Management_or_higher(ctx):
            try:
                await ctx.send(
                    "You must be a part of Northwood Management or NW Bot Engineer to use this command."
                )
            except discord.Forbidden:
                pass
            return
        prevloaChannel = await self.config.loaChannel()
        if prevloaChannel == channel.id:
            await ctx.send(f"LOA Channel is already set to {channel.mention}.")
            return

        prevloaChannel = self.bot.get_channel(prevloaChannel)
        await self.config.loaChannel.set(channel.id)
        loaChannel = await self.config.loaChannel()
        loaChannel = self.bot.get_channel(loaChannel)
        if loaChannel is not None:
            if prevloaChannel is not None:
                await ctx.send(
                    f"LOA Channel updated from {prevloaChannel.mention} to {loaChannel.mention}."
                )
            else:
                await ctx.send(f"LOA Channel updated to {loaChannel.mention}.")
        else:
            await ctx.send("Channel not found.")

    @loa.command(aliases=["setlogging"])
    async def setloggingchannel(self, ctx, channel: discord.TextChannel):
        """Set the LOA's Logging Channel in Config"""
        if not self.is_BotStaff_NW_Management_or_higher(ctx):
            try:
                await ctx.send(
                    "You must be a part of Northwood Management or NW Bot Engineer to use this command."
                )
            except discord.Forbidden:
                pass
            return
        prevloggingChannel = await self.config.loggingChannel()
        if prevloggingChannel == channel.id:
            await ctx.send(f"LOA Logging Channel is already set to {channel.mention}.")
            return

        prevloggingChannel = self.bot.get_channel(prevloggingChannel)
        await self.config.loggingChannel.set(channel.id)
        loggingChannel = await self.config.loggingChannel()
        loggingChannel = self.bot.get_channel(loggingChannel)
        if prevloggingChannel is None:
            await ctx.send(f"LOA Logging Channel updated to {loggingChannel.mention}.")
        else:
            await ctx.send(
                f"LOA Logging Channel updated from {prevloggingChannel.mention} to {loggingChannel.mention}."
            )

    @loa.command(aliases=["role"])
    async def setrole(self, ctx, role: Union[discord.Role, str]):
        """Set the Role to be given to those who are on active LOA"""
        if not self.is_BotStaff_NW_Management_or_higher(ctx):
            try:
                await ctx.send(
                    "You must be a part of Northwood Management or NW Bot Engineer to use this command."
                )
            except discord.Forbidden:
                pass
            return
        if type(role) == str:
            if role.lower() == "none":
                await self.config.loaRoleID.set(None)
                return await ctx.send("LOA Role removed.")
            else:
                return await ctx.send(f'Role "{role}" not found.')
        prevRole = await self.config.loaRoleID()
        if prevRole == role.id:
            return await ctx.send(f"LOA Role is already set to `{role}`")
        prevRole = ctx.guild.get_role(prevRole)
        await self.config.loaRoleID.set(role.id)
        if prevRole is None:
            await ctx.send(f"LOA Role updated to `{role}`")
        else:
            await ctx.send(f"LOA Role updated from `{prevRole}` to `{role}`")

    @loa.command(hidden=True)
    async def listloas(self, ctx):
        """List current LOAs loaded from config. For debugging purposes."""
        if not self.is_BotStaff_NW_Management_or_higher(ctx):
            try:
                await ctx.send(
                    "You must be a part of Northwood Management or NW Bot Engineer to use this command."
                )
            except discord.Forbidden:
                pass
            return
        done = [future.done() for future in self.futures]
        sLoas = await self.config.scheduledLoas()
        async with self.config.loas() as loas:
            await ctx.send(
                f"`{len(loas)}`   LOAs in config."
                + "\n"
                + f"`{len(sLoas)}`   Scheduled LOAs in config."
                + "\n"
                + f"`{len(done)}/{len(self.futures)}`   Futures in config."
            )

    async def on_message_delete(self, message):
        loaChannel = await self.config.loaChannel()
        loaChannel = self.bot.get_channel(loaChannel)
        if loaChannel is None:
            pass
        else:
            if message.channel == loaChannel:
                loas = await self.config.loas()
                loas = [loa for loa in loas if loa["messageID"] == message.id]
                if len(loas) > 0:  # Confirm that message deleted is a LOA
                    if message.guild.me.guild_permissions.view_audit_log:
                        async for entry in message.guild.audit_logs(
                            action=discord.AuditLogAction.message_delete, limit=1
                        ):
                            if entry.extra.channel == loaChannel:
                                issuer = entry.user
                                user = entry.target
                                await self.cancelLOA(loas[0], issuer)
                    else:  # Bot does not have Audit Log Perms
                        await self.cancelLOA(loas[0])
