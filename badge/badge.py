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

# JSON
import json


class Badge(commands.Cog):
    """Commands to give the badge to the Patreon Supporters"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=5349824615)
        default_global = {"TOKEN": "123"}
        self.config.register_global(**default_global)
        print('Addon "{}" loaded'.format(self.__class__.__name__))
        self.endpoint = "https://api.scpslgame.com/v2/admin/badge.php"

    @commands.command(pass_context=True)
    @commands.has_any_role(
        "Patreon Supporter",
        "Patreon level - Major Scientist",
        "Patreon level - Zone Manager",
        "Patreon level - Facility Manager",
    )
    async def issuesteambadge(self, ctx, steam_id: str):
        """
        Issue a patreon badge to a given steamID
        """
        if ctx.message.guild.id == 330432627649544202: #Replaced with NW Guild check
            if len(steam_id) != 17 or steam_id[:1] != "7":
                await ctx.send("Please use a valid SteamID64")
                return
            discord_query_response = await self.query_discord_id(ctx.message.author.id)
            if discord_query_response == "Badge not issued":
                issue_request = requests.post(
                    self.endpoint,
                    data={
                        "token": await self.config.TOKEN(),
                        "action": "issue",
                        "id": (steam_id+"@steam"),
                        "badge": "10",
                        "info": ctx.message.author.name,
                        "info2": ctx.message.author.id,
                    },
                )
                await ctx.send(issue_request.text)
            else:
                await ctx.send("You currently have an active badge.")

    @commands.command(pass_context=True)
    @commands.has_any_role(
        "Patreon Supporter",
        "Patreon level - Major Scientist",
        "Patreon level - Zone Manager",
        "Patreon level - Facility Manager",
    )
    async def issuediscordbadge(self, ctx):
        """
        Issue a patreon badge to the user's discord account.
        """
        if ctx.message.guild.id == 330432627649544202: #Replaced with NW Guild check
            discord_query_response = await self.query_discord_id(ctx.message.author.id)
            if discord_query_response == "Badge not issued":
                str_id = str(ctx.message.author.id)
                issue_request = requests.post(
                    self.endpoint,
                    data={
                        "token": await self.config.TOKEN(),
                        "action": "issue",
                        "id": (str_id + "@discord"),
                        "badge": "10",
                        "info": ctx.message.author.name,
                        "info2": str_id,
                    },
                )

                await ctx.send(issue_request.text)
            else:
                await ctx.send("You currently have an active badge")

    @commands.command(pass_context=True)
    @commands.has_any_role(
        "Patreon Supporter",
        "Patreon level - Major Scientist",
        "Patreon level - Zone Manager",
        "Patreon level - Facility Manager",
    )
    async def revokebadge(self, ctx):
        """
        Revokes a patreon badge from yourself.
        """
        if ctx.message.guild.id == 330432627649544202: #Replaced with NW Guild check
                await ctx.send(await self.remove_badge(discord_id=str(ctx.message.author.id),
                                                       discord_name=ctx.message.author.name))

    @commands.command(pass_context=True)
    async def settoken(self, ctx, arg):
        if ctx.message.author.id == 219040433861296128:
            await self.config.TOKEN.set(arg)

    # TODO: Put this in its own cog; along with other method (on_member_remove).
    async def on_member_update(self, before, after):
        if before.guild.id == 330432627649544202:
            server = before.guild
            # TODO: Make these cog-wide
            patreon_roles = [
                discord.utils.get(server.roles, name="Patreon level - Facility Manager"),
                discord.utils.get(server.roles, name="Patreon level - Zone Manager"),
                discord.utils.get(server.roles, name="Patreon level - Major Scientist"),
                discord.utils.get(server.roles, name="Patreon level - Scientist"),
                discord.utils.get(server.roles, name="Patreon level - Janitor"),
            ]
            patreon_role = next((i for i in before.roles if i in patreon_roles), None)
            if patreon_role is not None:
                has_role_after = False
                for j in after.roles:
                    if j == patreon_role:
                        has_role_after = True
                        break
                if not has_role_after:
                    await self.remove_badge(discord_id=after.id, discord_name=after.name)

    async def on_member_remove(self, member: discord.Member):
        if member.guild.id == 330432627649544202:
            await self.remove_badge(discord_id=member.id, discord_name=member.name)

    async def remove_badge(self, discord_id: str, discord_name: str):
        """
        Attempts to remove a user's badge
        """
        status = await self.query_discord_id(discord_id)
        if status != "Badge not issued":
            query_json = json.loads(status)
            query_info2 = query_json["info2"]
            query_userid = query_json["userid"]
            author_id = str(discord_id)
            if author_id == query_info2:
                revoke_query = requests.post(
                    self.endpoint,
                    data={
                        "token": await self.config.TOKEN(),
                        "action": "issue",
                        "badge": "",
                        "id": query_userid,
                        "info": discord_name,
                        "info2": author_id
                    }
                )
                return revoke_query.text
            else:
                return "An error has occurred. Please tell a Patreon Representative or a Global Moderator."
        else:
            return "It seems that you don't have a badge!"

    async def query_discord_id(self, discord_id):
        query = requests.post(
            self.endpoint,
            data={
                "token": await self.config.TOKEN(),
                "action": "queryDiscordId",
                "id": discord_id,
            },
        )
        return query.text
