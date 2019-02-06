import discord
import asyncio
import collections
import re
import datetime
from dateutil.parser import parse
from redbot.core import commands, Config, checks
from typing import Optional

def from_NWStaff_guild(ctx):
        return ctx.guild.id == 420530084294688775

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

class LOACog(commands.Cog):
    """Commands for creating and modifying Leave of Abscences for Northwood Staff"""

    # Behavior related constants
    TIME_AMNT_REGEX = re.compile("([1-9][0-9]*)([a-z]+)", re.IGNORECASE)
    TIME_QUANTITIES = collections.OrderedDict([("seconds", 1), ("minutes", 60),
                                               ("hours", 3600), ("days", 86400),
                                               ("weeks", 604800), ("months", 2.628e+6),
                                               ("years", 3.154e+7)])  # (amount in seconds, max amount)

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 8237492837454039, force_registration=True)
        self.config.register_global(loas = [], loaChannel = 441315223052484618, loggingChannel = 536271582264295457)
        self.futures = []
        self.time_format = "%b %d, %Y @ %I:%M %p UTC" #https://docs.python.org/2/library/datetime.html#strftime-strptime-behavior
        asyncio.ensure_future(self.restart_loas())

    @commands.group()
    @commands.guild_only()
    @commands.check(from_NWStaff_guild)
    async def loa(self, ctx):
        if ctx.invoked_subcommand is None:
            pass

    @loa.command(name='submit', aliases=['create'])
    async def submitLOA(self, ctx, enddate : Date, startdate : Optional[Date] = None, user : Optional[discord.Member] = None, *, reason = None):
        """Submit a Leave of Absence for your Northwood Staff position"""
        channel = ctx.message.channel
        if user is not None and not ctx.author.guild_permissions.manage_channels:
            await ctx.send("You are not allowed to submit LOAs for others.")
            return
        if user is None:
            user = ctx.author
        if reason is None:
            return await ctx.send("You must provide a reason for your LOA.")
        if startdate is None:
            start_time = datetime.datetime.utcnow()
            delay = 0
        else:
            start_time = startdate
            delay = int((start_time - datetime.datetime.utcnow()).total_seconds())
        #days, secs = divmod(seconds, 3600*24)
        #end_time = start_time + datetime.timedelta(days=days, seconds=secs)
        end_time = enddate
        loa = {'messageID': None, 'ctxChannelID' : channel.id, 'authorID':user.id, 'start_time': start_time.timestamp(), 'end_time': end_time.timestamp(), 'reason': reason}
        if start_time > end_time:
            await ctx.send("Invalid Start date. Cannot be less than end date")
            return
        if start_time > datetime.datetime.utcnow():
            em = discord.Embed(title="Northwood Studios Staff Leave of Abscence", description=f'Your LOA has been scheduled.', color=0xff8800)
            em.set_thumbnail(url=user.avatar_url)
            em.add_field(name='Staff Name', value=user.mention)
            if reason != None:
                em.add_field(name='Reason', value=reason)
            em.add_field(name='Starts On', value=start_time.strftime(self.time_format))
            em.add_field(name='Ends On', value=end_time.strftime(self.time_format))
            await ctx.send(embed=em)
            await self.logLOA("scheduled", user, loa)
        self.futures.append(asyncio.ensure_future(self.startLOA(ctx, user, delay, loa)))
            #self.startLOA(ctx, user, delay, loa)


    @loa.command(aliases=['setchannel'])
    @commands.has_permissions(manage_channels=True)
    async def setloachannel(self, ctx, channel : discord.TextChannel):
        """Set the LOA's Channel in Config"""
        prevloaChannel = await self.config.loaChannel()
        if prevloaChannel == channel.id:
            await ctx.send(f'LOA Channel is already set to {channel.mention}.')
            return

        prevloaChannel = self.bot.get_channel(prevloaChannel)
        await self.config.loaChannel.set(channel.id)
        loaChannel = await self.config.loaChannel()
        loaChannel = self.bot.get_channel(loaChannel)
        if loaChannel is not None:
            if prevloaChannel is not None:
                await ctx.send(f'LOA Channel updated from {prevloaChannel.mention} to {loaChannel.mention}.')
            else:
                await ctx.send(f'LOA Channel updated to {loaChannel.mention}.')
        else:
            await ctx.send("Channel not found.")

    @loa.command(aliases=['setlogging'])
    @commands.has_permissions(manage_channels=True)
    async def setloggingchannel(self, ctx, channel : discord.TextChannel):
        """Set the LOA's Logging Channel in Config"""
        prevloggingChannel = await self.config.loggingChannel()
        if prevloggingChannel == channel.id:
            await ctx.send(f'LOA Logging Channel is already set to {channel.mention}.')
            return

        prevloggingChannel = self.bot.get_channel(prevloggingChannel)
        await self.config.loggingChannel.set(channel.id)
        loggingChannel = await self.config.loggingChannel()
        loggingChannel = self.bot.get_channel(loggingChannel)
        await ctx.send(f'LOA Logging Channel updated from {prevloggingChannel.mention} to {loggingChannel.mention}.')

    @loa.command(hidden=True)
    @commands.has_permissions(manage_channels=True)
    async def listloas(self, ctx):
        """List current LOAs loaded from config. For debugging purposes."""
        async with self.config.loas() as loas:
            await ctx.send(f'`{len(loas)}`   LOAs in config.')

    @loa.command(hidden=True)
    @commands.has_permissions(manage_channels=True)
    async def reset(self, ctx):
        """Resets current LOAs. For debugging purposes."""
        for future in self.futures:
            future.cancel()

        response = f'```diff\nCleared LOAs. {count} Removed.\n\n'
        async with self.config.loas() as loas:
            count = 0
            for loa in loas:
                count += 1
                user = self.bot.get_user(loa['authorID'])
                end_time = loa['end_time'].strftime(self.time_format)
                loaChannel = await self.config.loaChannel()
                loaChannel = self.bot.get_channel(loaChannel)
                message = loaChannel.get_message(loa['messageID'])
                await message.delete()
                loas.remove(loa)
                response += f'- {user}\'s LOA. Scheduled End : {end_time}'
        await ctx.send(response)

    async def startLOA(self, ctx, user, delay, loa):
        """Begins and Activates LOA within LOA Channel"""
        await asyncio.sleep(delay)
        start_time = datetime.datetime.fromtimestamp(loa['start_time']).strftime(self.time_format)
        end_time = datetime.datetime.fromtimestamp(loa['end_time']).strftime(self.time_format)
        reason = loa['reason']

        em = discord.Embed(color=0x3DF270)
        em.set_author(name='Northwood Studios Staff Leave of Abscence')
        em.set_thumbnail(url=user.avatar_url)
        em.add_field(name='Staff Name', value=user.mention)
        if reason != None:
                em.add_field(name='Reason', value=reason)
        em.add_field(name='Starts On', value=start_time)
        em.add_field(name='Ends On', value=end_time, inline = False)

        loaChannel = self.bot.get_channel(await self.config.loaChannel())
        try:
            message = await loaChannel.send(embed=em)
        except discord.Forbidden:
            await ctx.send('I do not have permissions to send a message in ' + loaChannel.mention)
        except AttributeError:
            await ctx.send('LOA Channel is not set.')
        else:
            await ctx.send(f'Leave Of Abscence created in {loaChannel.mention}.')

            loa["messageID"] = message.id
            seconds = (datetime.datetime.fromtimestamp(loa["end_time"]) - datetime.datetime.utcnow()).total_seconds()
            channel = ctx.message.channel
            async with self.config.loas() as loas:
                loas.append(loa)
            self.futures.append(asyncio.ensure_future(self.remind_loa_ended(user, channel, message, seconds, loa)))
            await self.logLOA("started", user, loa)

    async def logLOA(self, state, user, loa):
        """"Logs LOA and it's started/ended status to Config's LOA Logging Channel."""
        loggingChannel = await self.config.loggingChannel()
        logChannel = self.bot.get_channel(loggingChannel)

        start_time = datetime.datetime.fromtimestamp(loa['start_time']).strftime(self.time_format)
        end_time = datetime.datetime.fromtimestamp(loa['end_time']).strftime(self.time_format)
        reason = loa['reason']
        if state.lower() == "started":
            color = 0x3DF270
        elif state.lower() == "scheduled":
            color = 0xff8800
        else:
            color = discord.Color.red()

        em = discord.Embed(color=color)
        em.set_author(name='Northwood Studios Staff Leave of Abscence ' + state.capitalize())
        em.set_thumbnail(url=user.avatar_url)
        em.add_field(name='Staff Name', value=user.mention)
        if reason != None:
            em.add_field(name='Reason', value=reason)
        em.add_field(name='Starts On', value=start_time)
        em.add_field(name='Ends Date', value=end_time)
        try:
            await logChannel.send(embed=em)
        except discord.Forbidden:
            pass

    async def remind_loa_ended(self, user, channel, message, seconds, loa):
        """Deletes the LOA and reminds the author their LOA has ended."""
        await asyncio.sleep(seconds)
        end_time = datetime.datetime.fromtimestamp(loa['end_time']).strftime(self.time_format)
        em = discord.Embed(title="Northwood Studios Staff Leave of Abscence", description=f'Your LOA has ended.', color=discord.Color.red())
        em.add_field(name='End Time', value=end_time, inline=False)
        em.add_field(name='Reason', value=loa['reason'], inline=False)
        await channel.send(content=user.mention, embed=em)
        async with self.config.loas() as loas:
            loas.remove(loa)
        try:
            await message.delete()
        except discord.Forbidden:
            pass
        await self.logLOA("ended", user, loa)

    async def restart_loas(self):
        await self.bot.wait_until_ready()
        for loa in await self.config.loas():
            time_diff = datetime.datetime.fromtimestamp(loa["end_time"]) - datetime.datetime.utcnow()
            seconds = max(0, time_diff.total_seconds())
            user = self.bot.get_user(loa['authorID'])
            channel = self.bot.get_user(loa['ctxChannelID'])
            loaChannel = self.bot.get_channel(await self.config.loaChannel())
            message = loaChannel.get_message(loa['messageID'])

            self.futures.append(asyncio.ensure_future(self.remind_loa_ended(user, channel, message, seconds, loa)))

    def get_seconds(self, time):
        """Returns the amount of converted time or None if invalid"""
        seconds = 0
        for time_match in self.TIME_AMNT_REGEX.finditer(time):
            time_amnt = int(time_match.group(1))
            time_abbrev = time_match.group(2)
            time_quantity = discord.utils.find(lambda t: t[0].startswith(time_abbrev), self.TIME_QUANTITIES.items())
            if time_quantity is not None:
                seconds += time_amnt * time_quantity[1]
        return None if seconds == 0 else seconds