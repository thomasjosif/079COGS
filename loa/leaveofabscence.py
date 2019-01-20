import discord
import asyncio
import collections
import re
import datetime
from redbot.core import commands, Config, checks
from typing import Optional

def from_NWStaff_guild(ctx):
        return ctx.guild.id == 420530084294688775

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
        asyncio.ensure_future(self.restart_loas())

    @commands.group()
    @commands.guild_only()
    @commands.check(from_NWStaff_guild)
    async def loa(self, ctx):
        if ctx.invoked_subcommand is None:
            pass

    @loa.command(name='submit', aliases=['create'])
    async def submitLOA(self, ctx, time, user : Optional[discord.Member] = None, *, reason = None):
        """Submit a Leave of Absence for your Northwood Staff position"""

        channel = ctx.message.channel
        if user is None:
            user = ctx.author

        seconds =  self.get_seconds(time)
        if seconds is None:
            await ctx.send('Invalid Time. Please enter __**End Time**__ for LOA. \nExamples for time: `5d, 2w4d, 1mo, 1y1mo2w5d`')
            return

        time_now = datetime.datetime.utcnow()
        days, secs = divmod(seconds, 3600*24)
        end_time = time_now + datetime.timedelta(days=days, seconds=secs)

        em = discord.Embed(color=0x3DF270)
        em.set_author(name='Northwood Studios Staff Leave of Abscence')
        em.set_thumbnail(url=user.avatar_url)
        em.add_field(name='Staff Name', value=user.mention)
        em.add_field(name='Ends On', value=end_time.strftime('%m/%d/%y @ %I:%M %p UTC'))
        if reason != None:
            em.add_field(name='Reason', value=reason, inline=False)

        loaChannel = self.bot.get_channel(await self.config.loaChannel())
        try:
            message = await loaChannel.send(embed=em)
        except discord.Forbidden:
            await ctx.send('I do not have permissions to send a message in ' + loaChannel.mention)
        else:
            await ctx.send(f'Leave Of Abscence created in {loaChannel.mention}.')

            loa = {'messageID': message.id, 'ctxChannelID' : channel.id, 'authorID':user.id, 'start_time': time_now.timestamp(), 'end_time': end_time.timestamp(), 'reason': reason}

            async with self.config.loas() as loas:
                loas.append(loa)
            self.futures.append(asyncio.ensure_future(self.remind_loa_ended(user, channel, message, seconds, loa)))
            await self.logLOA("started", user, loa)

    @loa.command()
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
        await ctx.send(f'LOA Channel updated from {prevloaChannel.mention} to {loaChannel.mention}.')

    @loa.command()
    @commands.has_permissions(manage_channels=True)
    async def setloggingchannel(self, ctx, channel : discord.TextChannel):
        """Set the LOA's Logging Channel in Config"""
        prevloggingChannel = await self.config.loggingChannel()
        if prevloggingChannel == channel.id:
            await ctx.send(f'LOA Logging Channel is already set to {channel.mention}.')
            return

        prevloggingChannel = self.bot.get_channel(prevloggingChannel)
        await self.config.prevloggingChannel.set(channel.id)
        loggingChannel = await self.config.loggingChannel()
        loggingChannel = self.bot.get_channel(loggingChannel)
        await ctx.send(f'LOA Logging Channel updated from {prevloaChannel.mention} to {loaChannel.mention}.')

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
                end_time = loa['end_time'].strftime('%m/%d/%y @ %I:%M %p UTC')
                loaChannel = await self.config.loaChannel()
                loaChannel = self.bot.get_channel(loaChannel)
                message = loaChannel.get_message(loa['messageID'])
                await message.delete()
                loas.remove(loa)
                response += f'- {user}\'s LOA. Scheduled End : {end_time}'
        await ctx.send(response)

    async def logLOA(self, state, user, loa):
        """"Logs LOA and it's started/ended status to Config's LOA Logging Channel."""
        loggingChannel = await self.config.loggingChannel()
        logChannel = self.bot.get_channel(loggingChannel)

        end_time = datetime.datetime.fromtimestamp(loa['end_time']).strftime('%m/%d/%y @ %I:%M %p UTC')
        reason = loa['reason']
        color = (discord.Color.green() if state.lower() == "started" else discord.Color.red())

        em = discord.Embed(color=color)
        em.set_author(name='Northwood Studios Staff Leave of Abscence ' + state.capitalize())
        em.set_thumbnail(url=user.avatar_url)
        em.add_field(name='Staff Name', value=user.mention)
        em.add_field(name='Ends Date', value=end_time)
        if reason != None:
            em.add_field(name='Reason', value=reason, inline=False)
        try:
            await logChannel.send(embed=em)
        except discord.Forbidden:
            pass

    async def remind_loa_ended(self, user, channel, message, seconds, loa):
        """Deletes the LOA and reminds the author their LOA has ended."""
        await asyncio.sleep(seconds)
        end_time = datetime.datetime.fromtimestamp(loa['end_time']).strftime('%m/%d/%y @ %I:%M %p UTC')
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
