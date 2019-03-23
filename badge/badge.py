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

    @commands.command(pass_context=True)
    @commands.has_any_role(
        "Patreon Supporters",
        "Patreon level - Major Scientist",
        "Patreon level - Zone Manager",
        "Patreon level - Facility Manager",
    )
    async def issuebadge(self, ctx, arg):
        if ctx.message.channel.id == 472408004587945984:
            rDiscordIdQuery = requests.post(
                "https://api.scpslgame.com/admin/badge.php",
                data={
                    "token": await self.config.TOKEN(),
                    "action": "queryDiscordId",
                    "id": ctx.message.author.id,
                },
            )
            if rDiscordIdQuery.text == "Badge not issued":
                rIssue = requests.post(
                    "https://api.scpslgame.com/admin/badge.php",
                    data={
                        "token": await self.config.TOKEN(),
                        "action": "issue",
                        "id": arg,
                        "badge": "9",
                        "info": ctx.message.author.name,
                        "info2": ctx.message.author.id,
                    },
                )
                await ctx.send(rIssue.text)
            else:
                await ctx.send("You already have a badge!")
        else:
            return

    @commands.command(pass_context=True)
    @commands.has_any_role(
        "Patreon Supporters",
        "Patreon level - Major Scientist",
        "Patreon level - Zone Manager",
        "Patreon level - Facility Manager",
    )
    async def revokebadge(self, ctx):
        if ctx.message.channel.id == 472408004587945984:
            rDiscordIdQuery = requests.post(
                "https://api.scpslgame.com/admin/badge.php",
                data={
                    "token": await self.config.TOKEN(),
                    "action": "queryDiscordId",
                    "id": ctx.message.author.id,
                },
            )
            if rDiscordIdQuery.text == "Badge not issued":
                await ctx.send("It seems that you don't have a badge!")
            else:
                rDiscordIdQueryJSON = json.loads(rDiscordIdQuery.text)
                rDiscordIdQueryInfo2 = rDiscordIdQueryJSON["info2"]
                rDiscordIdQuerySteamID = rDiscordIdQueryJSON["steamid"]
                messageAuthorId = ctx.message.author.id
                messageAuthorIdToString = str(messageAuthorId)

                if messageAuthorIdToString == rDiscordIdQueryInfo2:
                    rIssueRevoke = requests.post(
                        "https://api.scpslgame.com/admin/badge.php",
                        data={
                            "token": await self.config.TOKEN(),
                            "action": "issue",
                            "id": rDiscordIdQuerySteamID,
                        },
                    )
                    await ctx.send("Status: " + rIssueRevoke.text)
                else:
                    await ctx.send(
                        "There was a problem, contact a Patreon Representative or Global Moderator"
                    )
        else:
            return

    @commands.command(pass_context=True)
    async def settoken(self, ctx, arg):
        if ctx.message.author.id == 219040433861296128:
            await self.config.TOKEN.set(arg)
        else:
            return

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
                    await self.remove_badge(user_id=after.id);

    async def on_member_remove(self, member: discord.Member):
        if member.guild.id == 330432627649544202:
            self.remove_badge(user_id=member.id)

    async def remove_badge(self, user_id):
        status = await self.query_user(user_id)
        if status != "Badge not issued":
            query_json = json.loads(status.text)
            query_info2 = query_json["info2"]
            query_steamid = query_json["steamid"]
            author_id = str(user_id)
            if author_id == query_info2:
                revote_query = requests.post(
                    "https://api.scpslgame.com/admin/badge.php",
                    data={
                        "token": await self.config.TOKEN(),
                        "action": "issue",
                        "id": query_steamid,
                    },
                )

    async def query_user(self, user_id):
        query = requests.post(
            "https://api.scpslgame.com/admin/badge.php",
            data={
                "token": await self.config.TOKEN(),
                "action": "queryDiscordId",
                "id": user_id,
            },
        )
        return query.text
