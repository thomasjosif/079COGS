import aiohttp
import asyncio
import discord
import datetime
from redbot.core import commands, Config, checks
from typing import Optional
async def get_server(ip, port):
    url = 'https://kigen.co/scpsl/getinfo.php?ip={ip}&port={port}'.format(ip=ip, port=port)
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                try:
                    data = await response.json()
                except ValueError:
                    return 'ERROR : Bad Response'
        except aiohttp.ClientError:
            return 'ERROR: Connection Timeout.'

        if aiohttp.ClientResponse.status != 200:
            if aiohttp.ClientResponse.status == 404:
                return "ERROR: Not Found"
            elif aiohttp.ClientResponse.status == 500:
                return "ERROR: Internal Server Error"
    return data
class SCPSL(commands.Cog):
    """Commands related to SCP:SL Servers"""

    default_global = {"global_servers": {}}
    default_guild = {"local_mode": False, "server" : {}}

    def __init__(self, bot):
        self.bot = bot
        self.global_servers = {}
        self.config = Config.get_conf(self, 8237492837454049, force_registration=True)
        self.config.register_global(**self.default_global)
        self.config.register_guild(**self.default_guild)

    @commands.command()
    async def status(self, ctx, server_alias : str = None):
        """Lookup the status of an SCP:SL Server"""
        global_servers = await self.config.global_servers()
        server = await self.config.guild(ctx.guild).server()
        guildID = str(ctx.guild.id)
        local_mode = await self.config.guild(ctx.guild).local_mode()
        if server_alias is None and not local_mode:
            title = "__List of Currently Registered Servers " + self.bot.user.name + " is Tracking.__"
            desc = '`Syntax: !status <server>`'
            footer = "Type !help <command> for more info on a command. You can also type !help <category> for more info on a category."
            em = discord.Embed(title=title, description=desc, color=discord.Color.red())
            if server:
                em.add_field(name="(Local) " + server['name'], value="!status " + "/".join(server['aliases']), inline=False)
            for guildID, server in global_servers.items():
                em.add_field(name="(Global) " + server['name'], value="!status " + "/".join(server['aliases']))
            if not global_servers:
                em.add_field(name="Global Servers", value="__None__")
            em.set_author(name=self.bot.user.name + " Help Manual", icon_url=self.bot.user.avatar_url)
            em.set_footer(text=footer)
            try:
                await ctx.send(embed=em)
            except discord.Forbidden:
                pass
            return

        else:
            async with ctx.typing():
                if local_mode: # Does not require alias, gets ctx guild's server "!status"
                    if guildID in global_servers:
                        server = global_servers.get(guildID)
                        try:
                            await self.send_status_embed(ctx, guildID, server)
                        except discord.Forbidden:
                            pass
                    elif server:
                        await self.send_status_embed(ctx, guildID, server)
                    else:
                        await ctx.send(f"{ctx.guild.name} does not have a registered SCP:SL server")
                else:
                    if server and server_alias.lower() in server['aliases']:
                        await self.send_status_embed(ctx, guildID, server)
                    else:
                        found = await self.get_global_server_by_alias(server_alias) # Gets guild ID so we can show that guilds icon
                        if found is not None:
                            guildID, server = found
                            if server is not None:
                                try:
                                    await self.send_status_embed(ctx, guildID, server)
                                except discord.Forbidden:
                                    pass
                        else:
                            try:
                                await ctx.send(f"__**'{server_alias.capitalize()}'**__ is not a Registered Server. Use `!status` to view servers.")
                            except discord.Forbidden:
                                pass

    async def get_global_server_by_alias(self, alias):
        """Return guildID and global server if found else None"""
        global_servers = await self.config.global_servers()
        for guildID, server in global_servers.items():
            if alias.lower() in server['aliases']:
                return guildID, server
        return None

    async def send_status_embed(self, ctx, guildID, server):
        em = discord.Embed(title=server['name'], description="", color=0x3DF270)
        guild = self.bot.get_guild(int(guildID))
        em.set_thumbnail(url=self.bot.user.avatar_url)
        if guild is not None:
            if guild.icon_url.strip() != "":
                em.set_thumbnail(url=guild.icon_url)
        count = 0
        for port in server['portrange']:
            data = await get_server(server['ip'], port)
            count += 1
            players = data.get('players', 'Server Offline')
            port = data.get('port', 'Server Offline')
            ip = (server['ip'] + ":" + port if port != 'Server Offline' else 'Server Offline')

            em.add_field(name='Server #'+str(count), value=players, inline=True)
            em.add_field(name='IP', value=ip, inline=True)
        em.set_footer(text="Created For: " + str(ctx.message.author))
        em.timestamp = datetime.datetime.now() + datetime.timedelta(hours=6)
        return await ctx.send(embed=em)

    @commands.group(name='scpsl', pass_context=True, aliases=['sl'])
    @checks.guildowner_or_permissions(manage_guild=True)
    @commands.guild_only()
    async def scpsl(self, ctx):
        """Modify settings for Registered SCP:SL Servers"""
        pass

    def is_BotStaff_NW_Management_or_higher(self, ctx):
        StaffServer = self.bot.get_guild(420530084294688775)
        hasManagementOrHigher = False
        hasBotStaff = False
        if StaffServer is not None:
            member = StaffServer.get_member(ctx.author.id)
            if member is not None:
                botStaffRole = discord.utils.get(StaffServer.roles, name='Bot Engineer')
                if botStaffRole is not None:
                    hasBotStaff = botStaffRole in member.roles
                managementRole = discord.utils.get(StaffServer.roles, name='Management')
                if managementRole is not None:
                    hasManagementOrHigher = StaffServer.roles.index(member.top_role) >= managementRole.position
            return hasManagementOrHigher or hasBotStaff
        else:
            return False

    @scpsl.command(name='register')
    async def register(self, ctx, ip: str, endport : int, startport : Optional[int] = 7777, *aliases):
        """Register an SCP:SL server for to track with max 3 aliases"""
        server = await self.config.guild(ctx.guild).server()
        global_servers = await self.config.global_servers()
        guildID = str(ctx.guild.id)
        if server:
            try:
                await ctx.send(
                    f"__{ctx.guild.name} has **already registered** an SCP:SL Server.__" + '\n'
                    f"```yaml" + '\n'
                    f"Name: {server['name']}" + '\n'
                    f"IP: {server['ip']}" + '\n'
                    f"Server_Count: {server['endport'] - server['startport'] + 1}" + '\n'
                    f"Port_Range: ({server['startport']} - {server['endport']})" + '\n'
                    f"Aliases: {server['aliases']}```")
            except discord.Forbidden:
                pass
            return
        elif guildID in global_servers:
            server = global_servers[guildID]
            try:
                await ctx.send(
                    f"__{ctx.guild.name} has **already globally registered** an SCP:SL Server.__" + '\n'
                    f"```yaml" + '\n'
                    f"Name: {server['name']}" + '\n'
                    f"IP: {server['ip']}" + '\n'
                    f"Server_Count: {server['endport'] - server['startport'] + 1}" + '\n'
                    f"Port_Range: ({server['startport']} - {server['endport']})" + '\n'
                    f"Aliases: {server['aliases']}```")
            except discord.Forbidden:
                pass
            return
        if startport > endport:
            try:
                await ctx.send('Invalid port range. Startport "{startport}" cannot be higher than Endport "{endport}"')
            except discord.Forbidden:
                pass
            return
        if not aliases:
            aliases = []
        else:
            aliases = [alias.lower() for alias in aliases[:3]]

        server = {"name": ctx.guild.name, "ip": ip, "endport": endport, "startport": startport, "portrange": list(range(startport, endport + 1) if endport >= startport else range(7777, 7778)), "aliases": list(aliases)}
        await self.config.guild(ctx.guild).server.set(server)
        em = discord.Embed(color=discord.Color.red())
        em.set_author(name=self.bot.user.name + " Registered SCP:SL Servers", icon_url=self.bot.user.avatar_url)
        em.add_field(name="(Local) " + server['name'], value="!status " + "/".join(server['aliases']), inline=False)
        for guildID, server in global_servers.items():
            em.add_field(name="(Global) " + server['name'], value="!status " + "/".join(server['aliases']), inline=False)
        if not global_servers:
            em.add_field(name="Global Servers", value="__None__")
        try:
            await ctx.send(
                f"```yaml" + '\n'
                f"Name: {server['name']}" + '\n'
                f"IP: {server['ip']}" + '\n'
                f"Server_Count: {server['endport'] - server['startport'] + 1}" + '\n'
                f"Port_Range: ({server['startport']} - {server['endport']})" + '\n'
                f"Aliases: {server['aliases']}```"
                , embed=em)
        except discord.Forbidden:
            pass

    @scpsl.command(name='globalregister', aliases=['gregister'])
    async def global_register(self, ctx, ip : str, endport = 7777, startport : Optional[int] = 7777, *aliases):
        """Register an SCP:SL server for 079 to track globally with max 3 aliases"""
        server = await self.config.guild(ctx.guild).server()
        global_servers = await self.config.global_servers()
        guildID = str(ctx.guild.id)
        if not self.is_BotStaff_NW_Management_or_higher(ctx):
            try:
                await ctx.send("You must be a part of Northwood Management or NW Bot Engineer to use this command.")
            except discord.Forbidden:
                pass
            return
        if server:
            try:
                await ctx.send(
                    f"__{ctx.guild.name} has **already registered** an SCP:SL Server.__" + '\n'
                    f"```yaml" + '\n'
                    f"Name: {server['name']}" + '\n'
                    f"IP: {server['ip']}" + '\n'
                    f"Server_Count: {server['endport'] - server['startport'] + 1}" + '\n'
                    f"Port_Range: ({server['startport']} - {server['endport']})" + '\n'
                    f"Aliases: {server['aliases']}```")
            except discord.Forbidden:
                pass
            return
        elif guildID in global_servers:
            server = global_servers[guildID]
            try:
                await ctx.send(
                    f"__{ctx.guild.name} has **already globally registered** an SCP:SL Server.__" + '\n'
                    f"```yaml" + '\n'
                    f"Name: {server['name']}" + '\n'
                    f"IP: {server['ip']}" + '\n'
                    f"Server_Count: {server['endport'] - server['startport'] + 1}" + '\n'
                    f"Port_Range: ({server['startport']} - {server['endport']})" + '\n'
                    f"Aliases: {server['aliases']}```")
            except discord.Forbidden:
                pass
            return
        if startport > endport:
            try:
                await ctx.send('Invalid port range. Startport "{startport}" cannot be higher than Endport "{endport}"')
            except discord.Forbidden:
                pass
            return
        if not aliases:
            aliases = []
        else:
            aliases = [alias.lower() for alias in aliases[:3]]

        server = {"name": ctx.guild.name, "ip": ip, "endport": endport, "startport": startport, "portrange": list(range(startport, endport + 1) if endport >= startport else range(7777, 7778)), "aliases": list(aliases) }
        async with self.config.global_servers() as global_servers:
            global_servers[ctx.guild.id] = server

        em = discord.Embed(color=discord.Color.red())
        em.set_author(name=self.bot.user.name + " Registered SCP:SL Servers", icon_url=self.bot.user.avatar_url)
        for guildID, server in global_servers.items():
            em.add_field(name="(Global) " + server['name'], value="!status " + "/".join(server['aliases']), inline=False)
        if not global_servers:
            em.add_field(name="Global Servers", value="__None__")

        try:
            await ctx.send(
                f"```yaml" + '\n'
                f"Name: {server['name']}" + '\n'
                f"IP: {server['ip']}" + '\n'
                f"Server_Count: {server['endport'] - server['startport'] + 1}" + '\n'
                f"Port_Range: ({server['startport']} - {server['endport']})" + '\n'
                f"Aliases: {server['aliases']}```"
                , embed=em)
        except discord.Forbidden:
            pass

    @scpsl.command(name='unregister')
    async def unregister(self, ctx):
        """Unregister your SCP:SL Server from being tracked."""
        global_servers = await self.config.global_servers()
        registered_server = await self.config.guild(ctx.guild).server()
        guildID = str(ctx.guild.id)
        if guildID in global_servers:
            async with self.config.global_servers() as servers:
                server = servers.pop(guildID)
            try:
                await ctx.send(
                    f"__{ctx.guild.name} has **globally unregistered** an SCP:SL Server.__" + '\n'
                    f"```yaml" + '\n'
                    f"Name: {server['name']}" + '\n'
                    f"IP: {server['ip']}" + '\n'
                    f"Server_Count: {server['endport'] - server['startport'] + 1}" + '\n'
                    f"Port_Range: ({server['startport']} - {server['endport']})" + '\n'
                    f"Aliases: {server['aliases']}```")
            except discord.Forbidden:
                pass
        if registered_server:
            server = registered_server
            await self.config.guild(ctx.guild).server.set({})
            try:
                await ctx.send(
                    f"__{ctx.guild.name} has **locally unregistered** an SCP:SL Server.__" + '\n'
                    f"```yaml" + '\n'
                    f"Name: {server['name']}" + '\n'
                    f"IP: {server['ip']}" + '\n'
                    f"Server_Count: {server['endport'] - server['startport'] + 1}" + '\n'
                    f"Port_Range: ({server['startport']} - {server['endport']})" + '\n'
                    f"Aliases: {server['aliases']}```")
            except discord.Forbidden:
                pass
        elif not guildID in global_servers and not registered_server:
            try:
                await ctx.send(f"{ctx.guild.name} does not have a registered SCP:SL server")
            except discord.Forbidden:
                pass

    @scpsl.command(name='settings')
    async def settings(self, ctx):
        """View your current Registered SCP:SL Server Settings and Discord Server settings related to SCPSL"""
        global_servers = await self.config.global_servers()
        registered_server = await self.config.guild(ctx.guild).server()
        guildID = str(ctx.guild.id)
        local_mode = await self.config.guild(ctx.guild).local_mode()
        if guildID in global_servers:
            async with self.config.global_servers() as servers:
                server = servers[guildID]
            try:
                await ctx.send(
                    f"__{ctx.guild.name}'s globally registered SCP:SL Server.__" + '\n'
                    f"```yaml" + '\n'
                    f"Name: {server['name']}" + '\n'
                    f"IP: {server['ip']}" + '\n'
                    f"Server_Count: {server['endport'] - server['startport'] + 1}" + '\n'
                    f"Port_Range: ({server['startport']} - {server['endport']})" + '\n'
                    f"Aliases: {server['aliases']}" + "\n"
                    "\n"
                    "Settings: " + "\n"
                    " Local_Mode: " + str(local_mode) + "\n"
                    "```")
            except discord.Forbidden:
                pass
        elif registered_server:
            server = registered_server
            try:
                await ctx.send(
                    f"__{ctx.guild.name}'s locally registered SCP:SL Server.__" + '\n'
                    f"```yaml" + '\n'
                    f"Name: {server['name']}" + '\n'
                    f"IP: {server['ip']}" + '\n'
                    f"Server_Count: {server['endport'] - server['startport'] + 1}" + '\n'
                    f"Port_Range: ({server['startport']} - {server['endport']})" + '\n'
                    f"Aliases: {server['aliases']}" + "\n"
                    "\n"
                    "Settings: " + "\n"
                    " Local_Mode: " + str(local_mode) + "\n"
                    "```")
            except discord.Forbidden:
                pass
        elif not guildID in global_servers and not registered_server:
            try:
                await ctx.send(f"{ctx.guild.name} does not have a registered SCP:SL server")
            except discord.Forbidden:
                pass

    @scpsl.command(name="local")
    async def local(self, ctx, option : bool = None):
        """Toggle whether local mode for your server should be on, this will remove the need of an alias and allow `!status` to be used by itself."""
        if option is None:
            option = not await self.config.guild(ctx.guild).local_mode()
        await self.config.guild(ctx.guild).local_mode.set(option)
        local_mode = await self.config.guild(ctx.guild).local_mode()
        await ctx.send(f"Local Mode Set to `{local_mode}`")

    @scpsl.command(name='range')
    async def range(self, ctx, endport : int, startport : int = None):
        """Modify your SCP:SL Server's portrange to track."""
        server = await self.config.guild(ctx.guild).server()
        global_servers = await self.config.global_servers()
        guildID = str(ctx.guild.id)
        if startport is None:
            if server:
                startport = server['startport']
            elif guildID in global_servers:
                async with self.config.global_servers() as global_servers:
                    server = global_servers[ctx.guild.id]
                    startport = server['startport']
        if startport > endport:
            try:
                await ctx.send('Invalid port range. Startport "{startport}" cannot be higher than Endport "{endport}"')
            except discord.Forbidden:
                pass
            return
        d = {"endport": endport, "startport": startport, "portrange": list(range(startport, endport + 1) if endport >= startport else range(7777, 7778))}
        if server:
            server.update(d)
            await self.config.guild(ctx.guild).server.set(server)
            try:
                await ctx.send(
                    f"__{ctx.guild.name}'s locally registered SCP:SL Server.__" + '\n'
                    f"```yaml" + '\n'
                    f"Name: {server['name']}" + '\n'
                    f"IP: {server['ip']}" + '\n'
                    f"Server_Count: {server['endport'] - server['startport'] + 1}" + '\n'
                    f"Port_Range: ({server['startport']} - {server['endport']})" + '\n'
                    f"Aliases: {server['aliases']}" + "\n"
                    "```")
            except discord.Forbidden:
                pass
        elif guildID in global_servers:
            async with self.config.global_servers() as global_servers:
                server = global_servers[ctx.guild.id]
                server.update(d)
                global_servers[ctx.guild.id] = server
            try:
                await ctx.send(
                    f"__{ctx.guild.name}'s globally registered SCP:SL Server.__" + '\n'
                    f"```yaml" + '\n'
                    f"Name: {server['name']}" + '\n'
                    f"IP: {server['ip']}" + '\n'
                    f"Server_Count: {server['endport'] - server['startport'] + 1}" + '\n'
                    f"Port_Range: ({server['startport']} - {server['endport']})" + '\n'
                    f"Aliases: {server['aliases']}" + "\n"
                    "```")
            except discord.Forbidden:
                pass
            