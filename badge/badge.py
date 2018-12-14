# Discord
import discord

# Red
from redbot.core import commands
from redbot.core import Config
from redbot.core import checks

# Asyncio
import asyncio

# Requests
import requests

#JSON
import json

class Badge(commands.Cog):
    """Commands to give the badge to the Patreon Supporters"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=5349824615)
        default_global = {
            "TOKEN": "123",
        }
        self.config.register_global(**default_global)
        print('Addon "{}" loaded'.format(self.__class__.__name__))

    @commands.command(pass_context=True)
    @commands.has_role("Patreon Supporters")
    async def issuebadge(self, ctx, arg):
        if ctx.message.channel.id == 472408004587945984:
            rDiscordIdQuery = requests.post("https://api.scpslgame.com/admin/badge.php", data={'token': await self.config.TOKEN(), 'action': 'queryDiscordId', 'id': ctx.message.author.id})
            if (rDiscordIdQuery.text == "Badge not issued"):
                rIssue = requests.post("https://api.scpslgame.com/admin/badge.php", data={'token': await self.config.TOKEN(), 'action': 'issue', 'id': arg, 'badge': '9', 'info': ctx.message.author.name, 'info2': ctx.message.author.id})
                await ctx.send(rIssue.text)
            else:
                await ctx.send("You already have a badge!")
        else:
            return

    @commands.command(pass_context=True)
    @commands.has_role("Patreon Supporters")
    async def revokebadge(self, ctx):
        if ctx.message.channel.id == 472408004587945984:
            rDiscordIdQuery = requests.post("https://api.scpslgame.com/admin/badge.php", data={'token': await self.config.TOKEN(), 'action': 'queryDiscordId', 'id': ctx.message.author.id})
            if (rDiscordIdQuery.text == "Badge not issued"):
                await ctx.send("It seems that you don't have a badge!")
            else:
                rDiscordIdQueryJSON = json.loads(rDiscordIdQuery.text)
                rDiscordIdQueryInfo2 = rDiscordIdQueryJSON["info2"]
                rDiscordIdQuerySteamID = rDiscordIdQueryJSON["steamid"]
                messageAuthorId = ctx.message.author.id            
                messageAuthorIdToString = str(messageAuthorId)

                if(messageAuthorIdToString == rDiscordIdQueryInfo2):
                    rIssueRevoke = requests.post("https://api.scpslgame.com/admin/badge.php", data={'token': await self.config.TOKEN(), 'action': 'issue', 'id': rDiscordIdQuerySteamID})
                    await ctx.send("Status: " + rIssueRevoke.text)
                else:
                    await ctx.send("There was a problem, contact a Patreon Representative or Global Moderator")
        else:
            return

    @commands.command(pass_context=True)
    async def settoken(self, ctx, arg):
        if ctx.message.author.id == 219040433861296128:
            await self.config.TOKEN.set(arg)
        else:
            return