import asyncio
import datetime
import json
import urllib
import urllib.request
from datetime import datetime as dt

import discord
from discord import Colour
from redbot.core import Config
from redbot.core import commands


def upperFirst(string):
	fChar = string[:1]
	oChars = string[1:]
	return fChar.upper() + oChars


class SteamReminder(commands.Cog):
	INTERNAL_STATUS_URL = "https://status.scpslgame.com/api/getMonitorList/6B17Xuqor"
	STEAM_STATUS_URL = "https://crowbar.steamstat.us/Barney"

	def __init__(self, bot):
		super().__init__()
		self.db = Config.get_conf(self, 118624118624, force_registration=True)
		self.bot = bot

		self.lastResponse = None

		default_guild_settings = {
			"reminderchannel":  -1,
			"alertroom":        -1,
			"alertsenabled":    False,
			"alertlastmessage": -1
		}
		default_global_settings = {
			"alertsdelay":    10
		}

		self.db.register_guild(**default_guild_settings)
		self.db.register_global(**default_global_settings)

		self.statusTask = asyncio.ensure_future(self._checkStatusTask())
		self.reminderTask = asyncio.ensure_future(self._reminderTask())

	def __unload(self):
		self.statusTask.cancel()
		self.reminderTask.cancel()

	async def _checkStatusTask(self):
		await self.bot.wait_until_ready()
		while True:
			delay = await self.db.alertsdelay()
			await asyncio.sleep(delay * 60)  # Delay is stored in minutes, asyncio.sleep takes seconds.

			internalStatus = await self._getInternalStatus()
			steamStatus = await self._getSteamStatus()

			combinedStatus = internalStatus + steamStatus

			if self.lastResponse is not None:  # Has last response
				if self.lastResponse == combinedStatus:  # If it's the same as the last, don't bother posting
					continue

			self.lastResponse = combinedStatus

			statusEmbed = self._getStatusEmbed(combinedStatus)

			guilds = self.bot.guilds
			for guild in guilds:
				guildDb = self.db.guild(guild)  # Note, takes Guild rather than Guild.id
				enabled = await guildDb.alertsenabled()
				if enabled:  # Alerts enabled in this guild
					lastMessage = await guildDb.alertlastmessage()
					alertroomid = await guildDb.alertroom()
					channel = guild.get_channel(alertroomid)
					if not lastMessage == -1:  # Delete last message, if it exists
						message = await channel.get_message(lastMessage)
						await message.delete()

					message = await channel.send(embed=statusEmbed)
					await guildDb.alertlastmessage.set(message.id)

	def _secondsUntilTuesday(self):
		remindDay = 1  # 0 Monday, 6 Sunday
		timeToRemind = 12  # 12 Noon

		now = dt.utcnow()

		time = now
		while (True):
			if (time.weekday() == remindDay):  # Where 0 is Monday
				break;
			else:
				time += datetime.timedelta(hours=12);

		time += datetime.timedelta(hours=(timeToRemind - time.hour))
		time += datetime.timedelta(minutes=(0 - time.minute))

		delta = time - now
		seconds = delta.total_seconds()
		return seconds

	async def _reminderTask(self):
		await self.bot.wait_until_ready()
		while True:
			seconds = self._secondsUntilTuesday()

			await asyncio.sleep(seconds)  # Sleep until next Tuesday

			reminderEmbed = discord.Embed(
				title="Steam Reminder",
				description="Steam servers will go down for scheduled maintenance sometime Today.\nThere may be connection problems or authentication issues, please wait and they should be back up shortly."
			)

			guilds = self.bot.guilds
			for guild in guilds:
				guildDb = self.db.guild(guild)
				reminderChannelId = await guildDb.reminderchannel()  # Channel to post in
				if reminderChannelId != -1:  # If it's set
					reminderChannel = guild.get_channel(reminderChannelId)
					message = await reminderChannel.send(embed=reminderEmbed)  # Send

	async def _hasManageChannelsPerm(self, member):
		if member.guild_permissions.administrator or member.guild_permissions.manage_roles:
			return True
		return False

	def _isNWManagementOrBotStaff(self, member):  # This is yoinked from the LOA Cog (leaveofabscence.py)
		StaffServer = self.bot.get_guild(420530084294688775)  # NW Guild
		if StaffServer is not None:
			member = StaffServer.get_member(member.id)
			if member is not None:
				botStaffRole = discord.utils.get(StaffServer.roles, name="Bot Engineer")
				if botStaffRole is not None:
					hasBotStaff = botStaffRole in member.roles
					if hasBotStaff:
						return True
				managementRole = discord.utils.get(StaffServer.roles, name="Management")
				if managementRole is not None:
					hasManagementOrHigher = (
							StaffServer.roles.index(member.top_role) >= managementRole.position
					)
					if hasManagementOrHigher:
						return True
			return False
		else:
			return False

	async def _makeRequest(self, url):
		try:
			req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})  # SteamStatus API returns 403 without User-Agent data
			resp = urllib.request.urlopen(req, timeout=3)
			if resp.status != 200:
				return False
			data = resp.read().decode("utf-8")
			return data
		except urllib.error.URLError as e:
			return False

	async def _getInternalStatus(self):
		internalStatusData = await asyncio.create_task(self._makeRequest(self.INTERNAL_STATUS_URL))
		if internalStatusData is False:
			return [{
				"name":        "Unable to connect to internal services API",
				"statusClass": "Bad"
			}]
		internalStatusJson = json.loads(internalStatusData)

		outDict = []

		for server in internalStatusJson["psp"]["monitors"]:
			outDict.append(server)

		return outDict

	async def _getSteamStatus(self):
		steamStatusData = await asyncio.create_task(self._makeRequest(self.STEAM_STATUS_URL))
		if steamStatusData is False:
			return [{
				"name":        "Unable to connect to SteamStat.us API",
				"statusClass": "Bad"
			}]
		steamStatusJson = json.loads(steamStatusData)

		outDict = []

		steamServices = steamStatusJson["services"]
		for serviceStr in ["cms", "cms-ws"]:
			service = steamServices[serviceStr]
			outDict.append(
				{
					"name":        "Steam " + serviceStr.upper(),
					"statusClass": service["status"]
				}
			)

		return outDict

	def _getStatusEmbed(self, servicesInfo):
		embed = discord.Embed(title="Server Statuses")

		successCount = 0
		totalCount = 9

		for service in servicesInfo:
			embed.add_field(name=service["name"], value=upperFirst(service["statusClass"]))
			if service["statusClass"] == "good" or service["statusClass"] == "success":
				successCount += 1

		failCount = totalCount - successCount

		# Switch between green and red depending on number of failed services
		redPercent = (failCount / totalCount) * 255
		greenPercent = (successCount / totalCount) * 255

		embed.colour = Colour.from_rgb(int(redPercent), int(greenPercent), 0)

		if failCount > 0:
			string = "are {0} services".format(failCount)
			if failCount == 1:
				string = "is 1 service"
			embed.add_field(name="Overall Status", value="There may be some latency issues because there {0} not operating at full capacity.".format(string))
		else:
			embed.add_field(name="Overall Status", value="All services running at full capacity.")

		embed.timestamp = dt.utcnow()
		embed.set_footer(text="SteamAPI from http://steamstat.us/ .")
		return embed

	@commands.command()
	async def serverstatus(self, ctx):
		async with ctx.channel.typing():
			internalStatus = await self._getInternalStatus()
			steamStatus = await self._getSteamStatus()

			embed = self._getStatusEmbed(internalStatus + steamStatus)

			await ctx.send(embed=embed)

	@commands.group()
	@commands.guild_only()
	async def steamreminder(self, ctx):
		"""SteamReminder

		Automatically post about Tuesday's Steam Maintenence
		Automated posts about unexpected downtimes
		"""
		if ctx.invoked_subcommand is None:
			pass

	@steamreminder.group()
	async def alerts(self, ctx):
		"""Alert subsection for automatic downtime alerts for Steam or SCP:SL servers"""
		if ctx.invoked_subcommand is None:
			pass

	@alerts.command()
	async def toggle(self, ctx):
		"""Enable or Disable automatic downtime alerts for this Guild"""
		if self._isNWManagementOrBotStaff(ctx.author):
			enabled = await self.db.guild(ctx.guild).alertsenabled()
			await self.db.guild(ctx.guild).alertsenabled.set(not enabled)
			string = "Disabled"
			if not enabled:
				string = "Enabled"
			await ctx.send("Alerts are now **{0}**".format(string))
		else:
			await ctx.send("You require `manage-channels` permission to use this command.")

	@alerts.command(name="setchannel")
	async def alertsetchannel(self, ctx, channel: discord.TextChannel):
		"""Set the channel where alerts should be posted for this Guild"""
		if self._hasManageChannelsPerm(ctx.author):
			await self.db.guild(ctx.guild).alertroom.set(channel.id)
			await ctx.send("Alerts channel set to **{0}** ({1}).".format(channel.mention, channel.id))
		else:
			await ctx.send("You require `manage-channels` permission to use this command.")

	@alerts.command(name="clearchannel")
	async def alertclearchannel(self, ctx):
		"""Clear the downtime Alert channel."""
		if self._hasManageChannelsPerm(ctx.author):
			await self.db.guild(ctx.guild).alertroom.set(-1)
			await ctx.send("Cleared alerts channel!")
		else:
			await ctx.send("You require `manage-channels` permission to use this command.")

	# TODO: Make this only available to important people, and global
	@alerts.command()
	async def setdelay(self, ctx, num: int):
		"""(Global) Set how often the status should be queried"""
		if self._isNWManagementOrBotStaff(ctx.author):
			if num >= 1:
				await self.db.alertsdelay.set(num)
				if num == 1:
					await ctx.send("Alerts check delay set to **{0} minute**.".format(num))
				else:
					await ctx.send("Alerts check delay set to **{0} minutes**.".format(num))
			else:
				await ctx.send("Please use a valid number.")
		else:
			await ctx.send("This command is restricted to NW Studio Staff Bot Engineers or Management.")

	@steamreminder.command()
	async def setchannel(self, ctx, channel: discord.TextChannel):
		"""Set the channel where Steam maintenance reminders should be posted for this Guild"""
		if self._hasManageChannelsPerm(ctx.author):
			await self.db.guild(ctx.guild).reminderchannel.set(channel.id)
			await ctx.send("Reminder channel set to **{0}** ({1}).".format(channel.mention, channel.id))
		else:
			await ctx.send("You require `manage-channels` permission to use this command.")

	@steamreminder.command()
	async def clearchannel(self, ctx):
		"""Clear the Steam reminder channel."""
		if self._hasManageChannelsPerm(ctx.author):
			await self.db.guild(ctx.guild).reminderchannel.set(-1)
			await ctx.send("Cleared reminder channel!")
		else:
			await ctx.send("You require `manage-channels` permission to use this command.")
