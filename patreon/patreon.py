import discord

from redbot.core import commands

import asyncio


class Patreon(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def on_member_update(self, before, after):
        if before.guild.id == 330432627649544202:
            server = before.guild
            patroles = [discord.utils.get(server.roles, name="Patreon level - Facility Manager"),
                        discord.utils.get(server.roles, name="Patreon level - Zone Manager"),
                        discord.utils.get(server.roles, name="Patreon level - Major Scientist"),
                        discord.utils.get(server.roles, name="Patreon level - Scientist"),
                        discord.utils.get(server.roles, name="Patreon level - Janitor")]
            if before.roles == after.roles:
                return
            elif len(list(set(after.roles).intersection(patroles))) > 0 and discord.utils.get(server.roles,
                                                                                              name="Patreon Supporters") not in after.roles:
                await asyncio.sleep(1)
                await after.add_roles(discord.utils.get(server.roles, name="Patreon Supporters"))
                return
            elif len(list(set(after.roles).intersection(patroles))) == 0 and discord.utils.get(server.roles,
                                                                                               name="Patreon Supporters") in after.roles:
                await asyncio.sleep(1)
                await after.remove_roles(discord.utils.get(server.roles, name="Patreon Supporters"))
                return
        else:
            return
