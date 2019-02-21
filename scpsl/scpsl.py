import aiohttp
import asyncio
import discord
import datetime
import ipaddress
import requests
import json
import dns.resolver
from pprint import pprint
from urllib.parse import urlparse
from redbot.core import commands, Config, checks
from redbot.core.utils.predicates import MessagePredicate
from typing import Optional


class InvalidIP(Exception):
    pass


class ServerNotFound(Exception):
    pass


class AliasTaken(Exception):
    pass


class InvalidInput(Exception):
    def __init__(self, ip=None, endport=None, startport=None, aliases=None):
        self.ip = ip
        self.endport = endport
        self.startport = startport
        self.aliases = aliases


def url_validator(x):
    try:
        result = urlparse(x)
        return all([result.scheme, result.netloc, result.path])
    except:
        return False


async def IPconvert(ip):
    result = None
    try:
        ipaddress.ip_address(ip)
        result = str(ip)
    except ValueError:
        try:
            query = dns.resolver.query(ip)
        except dns.resolver.NXDOMAIN:
            result = None
        else:
            result = query[0].to_text()
    return result


# Using Kigen's API
# async def get_server(ip, port):
#    url = "https://kigen.co/scpsl/getinfo.php?ip={ip}&port={port}".format(ip=ip, port=port)
#    async with aiohttp.ClientSession() as session:
#        try:
#            async with session.get(url) as response:
#                try:
#                    data = await response.json()
#                except ValueError:
#                    return "ERROR : Bad Response"
#        except aiohttp.ClientError:
#            return "ERROR: Connection Timeout."

#        if aiohttp.ClientResponse.status != 200:
#            if aiohttp.ClientResponse.status == 404:
#                return "ERROR: Not Found"
#            elif aiohttp.ClientResponse.status == 500:
#                return "ERROR: Internal Server Error"
#    return data


async def fetchServerList():
    global serverlist
    url = "https://api.scpslgame.com/lobbylist.php?format=json"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                try:
                    serverlist = json.loads(await response.read())
                    return serverlist
                except ValueError:
                    raise Exception("ERROR : Bad Response")
        except aiohttp.ClientError:
            raise Exception("ERROR: Connection Timeout.")

        if aiohttp.ClientResponse.status != 200:
            if aiohttp.ClientResponse.status == 404:
                raise Exception("ERROR: Not Found")
            elif aiohttp.ClientResponse.status == 500:
                raise Exception("ERROR: Internal Server Error")


# Using SCPSLGame API
async def get_server_port(ipaddress, port):
    global serverlist
    ip = await IPconvert(ipaddress)
    if ip is None:
        raise InvalidIP
    if not serverlist:  # Refresh just incase it failed before this method was invoked.
        serverlist = await fetchServerList()
    server = [
        server
        for server in serverlist
        if (server.get("ip") == ip and server.get("port") == str(port))
    ]
    if server:
        return server[0]
    else:
        raise ServerNotFound


class SCPSL(commands.Cog):
    """Commands related to SCP:SL Servers"""

    default_global = {"global_servers": {}}
    default_guild = {"enabled": True, "local_mode": False, "server": {}}

    def __init__(self, bot):
        self.bot = bot
        self.global_servers = {}
        self.config = Config.get_conf(self, 8237492837454049, force_registration=True)
        self.config.register_global(**self.default_global)
        self.config.register_guild(**self.default_guild)

    @commands.command(name="lookup", aliases=["search"])
    async def lookup(self, ctx, ip: str = None):
        """Lookup the status of a SCP:SL Server by IP"""
        if await self.config.guild(ctx.guild).enabled():
            global serverlist
            if ip is None:
                raise commands.BadArgument
            ip = await IPconvert(ip)
            if ip is None:
                return await ctx.send("Invalid IP Address.")
            try:
                serverlist
            except NameError:
                serverlist = await fetchServerList()
            ports = [server.get("port") for server in serverlist if server.get("ip") == ip]
            if not ports:
                return await ctx.send("Server not found")
            server = {"portrange": ports, "ip": ip}
            await self.send_status_embed(ctx, server)

    @commands.command()
    async def status(self, ctx, server_alias: str = None):
        """View the status of a Registered SCP:SL Server"""
        if await self.config.guild(ctx.guild).enabled():
            global serverlist
            global_servers = await self.config.global_servers()
            try:
                server = await self.config.guild(ctx.guild).server()
                guildID = str(ctx.guild.id)
                local_mode = await self.config.guild(ctx.guild).local_mode()
            except AttributeError:
                server = None
                guildID = None
                local_mode = False
            if server_alias is None and not local_mode:
                await ctx.trigger_typing()
                try:
                    serverlist
                except NameError:
                    serverlist = await fetchServerList()
                title = (
                    "__List of Currently Registered Servers "
                    + self.bot.user.name
                    + " is Tracking.__"
                )
                desc = "`Syntax: !status <server>`"
                footer = f"{len(serverlist)} Servers on Server List"
                em = discord.Embed(title=title, description=desc, color=discord.Color.red())
                if server:
                    em.add_field(
                        name="(Local) " + server["name"],
                        value="!status " + "/".join(server["aliases"]),
                        inline=False,
                    )
                for guildID, server in global_servers.items():
                    em.add_field(
                        name="(Global) " + server["name"],
                        value="!status " + "/".join(server["aliases"]),
                        inline=False,
                    )
                if not global_servers:
                    em.add_field(name="Global Servers", value="__None__")
                em.set_author(
                    name=self.bot.user.name + " Help Manual", icon_url=self.bot.user.avatar_url
                )
                em.set_footer(text=footer, icon_url="https://i.imgur.com/ihqxxtV.png")
                em.timestamp = datetime.datetime.now() + datetime.timedelta(hours=6)
                try:
                    await ctx.send(embed=em)
                except discord.Forbidden:
                    pass
                return

            else:
                await ctx.trigger_typing()
                if local_mode:  # Does not require alias, gets ctx guild's server "!status"
                    if guildID in global_servers:
                        server = global_servers.get(guildID)
                        try:
                            return await self.send_status_embed(ctx, server)
                        except discord.Forbidden:
                            pass
                    elif server:
                        return await self.send_status_embed(ctx, server)
                    else:
                        return await ctx.send(
                            f"{ctx.guild.name} does not have a registered SCP:SL server"
                        )
                else:
                    if server and server_alias.lower() in server["aliases"]:
                        try:
                            return await self.send_status_embed(ctx, server)
                        except InvalidIP:
                            return await ctx.send(
                                "Invalid IP ` {ip} `  Unregister using `{prefix}scpsl unregister` and then register the SCPSL server again.".format(
                                    ip=server["ip"], prefix=ctx.prefix
                                )
                            )
                    else:
                        found = await self.get_global_server_by_alias(
                            server_alias
                        )  # Gets guild ID so we can show that guilds icon
                        if found is not None:
                            guildID, server = found
                            if server is not None:
                                try:
                                    return await self.send_status_embed(ctx, server)
                                except discord.Forbidden:
                                    pass
                        else:
                            try:
                                return await ctx.send(
                                    f"__**'{server_alias.capitalize()}'**__ is not a Registered Server. Use `!status` to view servers."
                                )
                            except discord.Forbidden:
                                pass

    async def get_global_server_by_alias(self, alias):
        """Return guildID and global server if found else None"""
        global_servers = await self.config.global_servers()
        for guildID, server in global_servers.items():
            if alias.lower() in server["aliases"]:
                return guildID, server
        return None

    async def send_status_embed(self, ctx, server):
        name = server.get("name", discord.Embed.Empty)
        icon_url = server.get("icon_url", self.bot.user.avatar_url)
        em = discord.Embed(title=name, description="", color=0x3DF270)
        if url_validator(icon_url):
            em.set_thumbnail(url=icon_url)
        else:
            em.set_thumbnail(url=self.bot.user.avatar_url)
        count = 0
        await fetchServerList()
        for port in server["portrange"]:
            try:
                data = await get_server_port(server["ip"], port)
            except ServerNotFound:
                continue
            else:
                count += 1
                players = data.get("players", "Server Offline")
                port = data.get("port", "Server Offline")
                ip = server["ip"] + ":" + port if port != "Server Offline" else "Server Offline"

                em.add_field(name="Server #" + str(count), value=players, inline=True)
                em.add_field(name="IP", value=ip, inline=True)
        em.set_footer(text="Created For: " + str(ctx.message.author))
        em.timestamp = datetime.datetime.now() + datetime.timedelta(hours=6)
        return await ctx.send(embed=em)

    @commands.group(name="scpsl", pass_context=True, aliases=["sl"])
    @checks.guildowner_or_permissions(manage_guild=True)
    @commands.guild_only()
    async def scpsl(self, ctx):
        """Commands related to tracking SCP:SL Servers"""
        pass

    @scpsl.command(name="enable")
    async def enable(self, ctx, option: bool = None):
        """Toggle whether the SCPSL commands are active on your server or not."""
        if option is None:
            option = not await self.config.guild(ctx.guild).enabled()
        await self.config.guild(ctx.guild).enabled.set(option)
        enabled = await self.config.guild(ctx.guild).enabled()
        response = "enabled" if enabled else "disabled"
        await ctx.send(f"SCPSL Module `{response}`")

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

    async def verifyAlias(self, list):
        servers = await self.config.global_servers()
        aliases = [alias for server in servers for alias in servers[server]["aliases"]]
        result = True
        for alias in list:
            if alias.lower() in aliases:
                raise AliasTaken(f"Alias `{alias}` is already used by another server.")
                result = False
        return True

    async def verifyName(self, name):
        servers = await self.config.global_servers()
        names = [servers[server]["name"].strip().lower() for server in servers]
        result = True
        if name.strip().lower() in names:
            raise AliasTaken(f"Name `{name}` is already used by another server.")
            result = False
        return True

    async def registration_input(self, ctx):
        """Handles getting required input for registering SCPSL servers to the bot."""
        attempt = 0
        ip = endport = startport = aliases = None
        while ip is None:
            await ctx.send(
                "Enter the IP Address of your SCP:SL Server." + "\n"
                "__*Type `cancel` to Cancel at any moment.*__"
            )
            try:
                msg = await ctx.bot.wait_for(
                    "message", check=MessagePredicate.same_context(ctx), timeout=25
                )
            except asyncio.TimeoutError:
                return await ctx.send("Server Registration Cancelled.")
            if msg.content.strip().lower() in ["cancel", "exit", "stop"]:
                return await ctx.send("Server Registration Cancelled.")
            ipAddress = await IPconvert(msg.content)
            if ipAddress is None:
                await ctx.send("Invalid IP Address.")
                continue
            else:
                ip = msg.content.strip()
        while endport is None or startport is None:
            await ctx.send(
                f"Enter a port range to track at {ip}. Serpate with `-`" + "\n"
                '*Ex.  "7777 - 7780"*'
            )
            try:
                msg = await ctx.bot.wait_for(
                    "message", check=MessagePredicate.same_context(ctx), timeout=25
                )
            except asyncio.TimeoutError:
                return await ctx.send("Server Registration Cancelled.")
            if msg.content.strip().lower() in ["cancel", "exit", "stop"]:
                return await ctx.send("Server Registration Cancelled.")
            if "-" in msg.content:
                startport, endport = msg.content.split("-")
                try:
                    startport = int(startport)
                    endport = int(endport)
                except ValueError:
                    await ctx.send("Invalid Port Range.")
                    continue
            else:
                startport = 7777
                if len(msg.content.strip()) <= 4:
                    try:
                        endport = int(msg.content.strip())
                    except ValueError:
                        await ctx.send("Invalid Port Range.")
                        continue
                else:
                    await ctx.send("Invalid Port Range. Expected a 4 digit port.")
                    continue
            if startport > endport:
                await ctx.send(
                    f'Invalid port range. Startport "{startport}" cannot be higher than Endport "{endport}"'
                )
                startport = endport = None
                continue

        while aliases is None:
            await ctx.send(
                "Enter a list of Aliases to use `!status <alias>` to view your Server status. *Max. 3 Aliases*"
            )
            try:
                msg = await ctx.bot.wait_for(
                    "message", check=MessagePredicate.same_context(ctx), timeout=35
                )
            except asyncio.TimeoutError:
                return await ctx.send("Server Registration Cancelled.")
            if msg.content.strip().lower() in ["cancel", "exit", "stop"]:
                return await ctx.send("Server Registration Cancelled.")
            aliases = msg.content.strip().split(" ")
            if not aliases:
                aliases = []
            else:
                try:
                    await self.verifyAlias(aliases)
                    # aliases = [alias.lower() for alias in aliases[:3] if await self.verifyAlias(alias)]
                except AliasTaken as e:
                    await ctx.send(str(e))
                    aliases = None
                    continue
                else:
                    aliases = [alias.lower() for alias in aliases[:3]]
            return ip, endport, startport, aliases

    @scpsl.command(name="register")
    async def register(self, ctx):
        """Register an SCP:SL server for to track with max 3 aliases"""
        if not await self.config.guild(ctx.guild).enabled():
            return await ctx.send(
                "SCPSL Module disabled on this server. Use `{prefix}scpsl enable` to enable the module for this server.".format(
                    prefix=ctx.prefix
                )
            )
        server = await self.config.guild(ctx.guild).server()
        global_servers = await self.config.global_servers()
        guildID = str(ctx.guild.id)
        if server:
            try:
                await ctx.send(
                    f"__{ctx.guild.name} has **already registered** an SCP:SL Server.__" + "\n"
                    f"```yaml" + "\n"
                    f"Name: {server['name']}" + "\n"
                    f"Icon_Url: {server['icon_url']}" + "\n"
                    f"IP: {server['ip']}" + "\n"
                    f"Server_Count: {server['endport'] - server['startport'] + 1}" + "\n"
                    f"Port_Range: ({server['startport']} - {server['endport']})" + "\n"
                    f"Aliases: {server['aliases']}```"
                )
            except discord.Forbidden:
                pass
            return
        elif guildID in global_servers:
            server = global_servers[guildID]
            try:
                await ctx.send(
                    f"__{ctx.guild.name} has **already globally registered** an SCP:SL Server.__"
                    + "\n"
                    f"```yaml" + "\n"
                    f"Name: {server['name']}" + "\n"
                    f"Icon_Url: {server['icon_url']}" + "\n"
                    f"IP: {server['ip']}" + "\n"
                    f"Server_Count: {server['endport'] - server['startport'] + 1}" + "\n"
                    f"Port_Range: ({server['startport']} - {server['endport']})" + "\n"
                    f"Aliases: {server['aliases']}```"
                )
            except discord.Forbidden:
                pass
            return
        try:
            ip, endport, startport, aliases = await self.registration_input(ctx)
        except TypeError:
            return
        server_to_add = {
            "name": ctx.guild.name,
            "icon_url": ctx.guild.icon_url,
            "ip": ip,
            "endport": endport,
            "startport": startport,
            "portrange": list(
                range(startport, endport + 1) if endport >= startport else range(7777, 7778)
            ),
            "aliases": list(aliases),
        }
        await self.config.guild(ctx.guild).server.set(server_to_add)
        em = discord.Embed(color=discord.Color.red())
        em.set_author(
            name=self.bot.user.name + " Registered SCP:SL Servers",
            icon_url=self.bot.user.avatar_url,
        )
        server = server_to_add
        em.add_field(
            name="(Local) " + server["name"],
            value="!status " + "/".join(server["aliases"]),
            inline=False,
        )
        for guildID, server in global_servers.items():
            em.add_field(
                name="(Global) " + server["name"],
                value="!status " + "/".join(server["aliases"]),
                inline=False,
            )
        if not global_servers:
            em.add_field(name="Global Servers", value="__None__")
        try:
            server = server_to_add
            await ctx.send(
                f"```yaml" + "\n"
                f"Name: {server['name']}" + "\n"
                f"Icon_Url: {server['icon_url']}" + "\n"
                f"IP: {server['ip']}" + "\n"
                f"Server_Count: {server['endport'] - server['startport'] + 1}" + "\n"
                f"Port_Range: ({server['startport']} - {server['endport']})" + "\n"
                f"Aliases: {server['aliases']}```",
                embed=em,
            )
        except discord.Forbidden:
            pass

    @scpsl.command(name="globalregister", aliases=["gregister"])
    async def global_register(self, ctx):
        """Register an SCP:SL server for 079 to track globally with max 3 aliases"""
        if not await self.config.guild(ctx.guild).enabled():
            return await ctx.send(
                "SCPSL Module disabled on this server. Use `{prefix}scpsl enable` to enable the module for this server.".format(
                    prefix=ctx.prefix
                )
            )
        server = await self.config.guild(ctx.guild).server()
        global_servers = await self.config.global_servers()
        guildID = str(ctx.guild.id)
        if not self.is_BotStaff_NW_Management_or_higher(ctx):
            try:
                await ctx.send(
                    "You must be a part of Northwood Management or NW Bot Engineer to use this command."
                )
            except discord.Forbidden:
                pass
            return
        if server:
            try:
                await ctx.send(
                    f"__{ctx.guild.name} has **already registered** an SCP:SL Server.__" + "\n"
                    f"```yaml" + "\n"
                    f"Name: {server['name']}" + "\n"
                    f"Icon_Url: {server['icon_url']}" + "\n"
                    f"IP: {server['ip']}" + "\n"
                    f"Server_Count: {server['endport'] - server['startport'] + 1}" + "\n"
                    f"Port_Range: ({server['startport']} - {server['endport']})" + "\n"
                    f"Aliases: {server['aliases']}```"
                )
            except discord.Forbidden:
                pass
            return
        elif guildID in global_servers:
            server = global_servers[guildID]
            try:
                await ctx.send(
                    f"__{ctx.guild.name} has **already globally registered** an SCP:SL Server.__"
                    + "\n"
                    f"```yaml" + "\n"
                    f"Name: {server['name']}" + "\n"
                    f"Icon_Url: {server['icon_url']}" + "\n"
                    f"IP: {server['ip']}" + "\n"
                    f"Server_Count: {server['endport'] - server['startport'] + 1}" + "\n"
                    f"Port_Range: ({server['startport']} - {server['endport']})" + "\n"
                    f"Aliases: {server['aliases']}```"
                )
            except discord.Forbidden:
                pass
            return
        try:
            ip, endport, startport, aliases = await self.registration_input(ctx)
        except TypeError:
            return
        server_to_add = {
            "name": ctx.guild.name,
            "icon_url": ctx.guild.icon_url,
            "ip": ip,
            "endport": endport,
            "startport": startport,
            "portrange": list(
                range(startport, endport + 1) if endport >= startport else range(7777, 7778)
            ),
            "aliases": list(aliases),
        }
        async with self.config.global_servers() as global_servers:
            global_servers[ctx.guild.id] = server_to_add

        em = discord.Embed(color=discord.Color.red())
        em.set_author(
            name=self.bot.user.name + " Registered SCP:SL Servers",
            icon_url=self.bot.user.avatar_url,
        )
        for guildID, server in global_servers.items():
            em.add_field(
                name="(Global) " + server["name"],
                value="!status " + "/".join(server["aliases"]),
                inline=False,
            )
        if not global_servers:
            em.add_field(name="Global Servers", value="__None__")
        server = server_to_add
        try:
            await ctx.send(
                f"```yaml" + "\n"
                f"Name: {server['name']}" + "\n"
                f"Icon_Url: {server['icon_url']}" + "\n"
                f"IP: {server['ip']}" + "\n"
                f"Server_Count: {server['endport'] - server['startport'] + 1}" + "\n"
                f"Port_Range: ({server['startport']} - {server['endport']})" + "\n"
                f"Aliases: {server['aliases']}```",
                embed=em,
            )
        except discord.Forbidden:
            pass

    @scpsl.command(name="unregister")
    async def unregister(self, ctx):
        """Unregister your SCP:SL Server from being tracked."""
        if not await self.config.guild(ctx.guild).enabled():
            return await ctx.send(
                "SCPSL Module disabled on this server. Use `{prefix}scpsl enable` to enable the module for this server.".format(
                    prefix=ctx.prefix
                )
            )
        global_servers = await self.config.global_servers()
        registered_server = await self.config.guild(ctx.guild).server()
        guildID = str(ctx.guild.id)
        if guildID in global_servers:
            async with self.config.global_servers() as servers:
                server = servers.pop(guildID)
            try:
                await ctx.send(
                    f"__{ctx.guild.name} has **globally unregistered** an SCP:SL Server.__" + "\n"
                    f"```yaml" + "\n"
                    f"Name: {server['name']}" + "\n"
                    f"Icon_Url: {server['icon_url']}" + "\n"
                    f"IP: {server['ip']}" + "\n"
                    f"Server_Count: {server['endport'] - server['startport'] + 1}" + "\n"
                    f"Port_Range: ({server['startport']} - {server['endport']})" + "\n"
                    f"Aliases: {server['aliases']}```"
                )
            except discord.Forbidden:
                pass
        if registered_server:
            server = registered_server
            await self.config.guild(ctx.guild).server.set({})
            try:
                await ctx.send(
                    f"__{ctx.guild.name} has **locally unregistered** an SCP:SL Server.__" + "\n"
                    f"```yaml" + "\n"
                    f"Name: {server['name']}" + "\n"
                    f"Icon_Url: {server['icon_url']}" + "\n"
                    f"IP: {server['ip']}" + "\n"
                    f"Server_Count: {server['endport'] - server['startport'] + 1}" + "\n"
                    f"Port_Range: ({server['startport']} - {server['endport']})" + "\n"
                    f"Aliases: {server['aliases']}```"
                )
            except discord.Forbidden:
                pass
        elif not guildID in global_servers and not registered_server:
            try:
                await ctx.send(f"{ctx.guild.name} does not have a registered SCP:SL server")
            except discord.Forbidden:
                pass

    @scpsl.command(name="settings")
    async def settings(self, ctx):
        """View your current Registered SCP:SL Server Settings and Discord Server settings related to SCPSL"""
        if not await self.config.guild(ctx.guild).enabled():
            return await ctx.send(
                "SCPSL Module disabled on this server. Use `{prefix}scpsl enable` to enable the module for this server.".format(
                    prefix=ctx.prefix
                )
            )
        global_servers = await self.config.global_servers()
        registered_server = await self.config.guild(ctx.guild).server()
        guildID = str(ctx.guild.id)
        local_mode = await self.config.guild(ctx.guild).local_mode()
        if guildID in global_servers:
            async with self.config.global_servers() as servers:
                server = servers[guildID]
            try:
                await ctx.send(
                    f"__{ctx.guild.name}'s globally registered SCP:SL Server.__" + "\n"
                    f"```yaml" + "\n"
                    f"Name: {server['name']}" + "\n"
                    f"Icon_Url: {server['icon_url']}" + "\n"
                    f"IP: {server['ip']}" + "\n"
                    f"Server_Count: {server['endport'] - server['startport'] + 1}" + "\n"
                    f"Port_Range: ({server['startport']} - {server['endport']})" + "\n"
                    f"Aliases: {server['aliases']}" + "\n"
                    "\n"
                    "Settings: " + "\n"
                    " Local_Mode: " + str(local_mode) + "\n"
                    "```"
                )
            except discord.Forbidden:
                pass
        elif registered_server:
            server = registered_server
            try:
                await ctx.send(
                    f"__{ctx.guild.name}'s locally registered SCP:SL Server.__" + "\n"
                    f"```yaml" + "\n"
                    f"Name: {server['name']}" + "\n"
                    f"Icon_Url: {server['icon_url']}" + "\n"
                    f"IP: {server['ip']}" + "\n"
                    f"Server_Count: {server['endport'] - server['startport'] + 1}" + "\n"
                    f"Port_Range: ({server['startport']} - {server['endport']})" + "\n"
                    f"Aliases: {server['aliases']}" + "\n"
                    "\n"
                    "Settings: " + "\n"
                    " Local_Mode: " + str(local_mode) + "\n"
                    "```"
                )
            except discord.Forbidden:
                pass
        elif not guildID in global_servers and not registered_server:
            try:
                await ctx.send(f"{ctx.guild.name} does not have a registered SCP:SL server")
            except discord.Forbidden:
                pass

    @scpsl.command(name="local")
    async def local(self, ctx, option: bool = None):
        """Toggle whether local mode for your server should be on, this will remove the need of an alias and allow `!status` to be used by itself."""
        if not await self.config.guild(ctx.guild).enabled():
            return await ctx.send(
                "SCPSL Module disabled on this server. Use `{prefix}scpsl enable` to enable the module for this server.".format(
                    prefix=ctx.prefix
                )
            )
        if option is None:
            option = not await self.config.guild(ctx.guild).local_mode()
        await self.config.guild(ctx.guild).local_mode.set(option)
        local_mode = await self.config.guild(ctx.guild).local_mode()
        await ctx.send(f"Local Mode Set to `{local_mode}`")

    @scpsl.group(name="edit")
    async def edit(self, ctx):
        """Modify settings for Registered SCP:SL Servers"""
        pass

    @edit.command(name="name")
    async def changeName(self, ctx):
        """Modify your SCP:SL Server's Name as appeared on discord."""
        if not await self.config.guild(ctx.guild).enabled():
            return await ctx.send(
                "SCPSL Module disabled on this server. Use `{prefix}scpsl enable` to enable the module for this server.".format(
                    prefix=ctx.prefix
                )
            )
        server = await self.config.guild(ctx.guild).server()
        global_servers = await self.config.global_servers()
        guildID = str(ctx.guild.id)
        endport = startport = None
        if not guildID in global_servers and not server:
            try:
                await ctx.send(f"{ctx.guild.name} does not have a registered SCP:SL server")
            except discord.Forbidden:
                pass
            return
        name = None
        while name is None:
            await ctx.send(
                "Enter a name to be displayed for your SCP:SL Server." + "\n"
                "__*Type `default` to use the discord server's name by default.*__"
            )
            try:
                msg = await ctx.bot.wait_for(
                    "message", check=MessagePredicate.same_context(ctx), timeout=25
                )
            except asyncio.TimeoutError:
                return await ctx.send("Server Editing Cancelled.")
            if msg.content.strip().lower() in ["cancel", "exit", "stop"]:
                return await ctx.send("Server Editing Cancelled.")
            name = msg.content[:40]  # 40 Character Limit
            try:
                await self.verifyName(name)
            except AliasTaken as e:
                await ctx.send(str(e))
                name = None
                continue
            else:
                ip = msg.content.strip()
        d = {"name": name}
        await self.updateServer(ctx, d)

    @edit.command(name="ip")
    async def changeIP(self, ctx):
        """Modify your SCP:SL Server's IP Address."""
        if not await self.config.guild(ctx.guild).enabled():
            return await ctx.send(
                "SCPSL Module disabled on this server. Use `{prefix}scpsl enable` to enable the module for this server.".format(
                    prefix=ctx.prefix
                )
            )
        server = await self.config.guild(ctx.guild).server()
        global_servers = await self.config.global_servers()
        guildID = str(ctx.guild.id)
        if not guildID in global_servers and not server:
            try:
                await ctx.send(f"{ctx.guild.name} does not have a registered SCP:SL server")
            except discord.Forbidden:
                pass
            return
        ip = None
        while ip is None:
            await ctx.send("Enter the IP Address of your SCP:SL Server.")
            try:
                msg = await ctx.bot.wait_for(
                    "message", check=MessagePredicate.same_context(ctx), timeout=25
                )
            except asyncio.TimeoutError:
                return await ctx.send("Server Registration Cancelled.")
            if msg.content.strip().lower() in ["cancel", "exit", "stop"]:
                return await ctx.send("Server Editing Cancelled.")
            test = await IPconvert(msg.content)
            if test is None:
                await ctx.send("Invalid IP Address.")
                continue
            else:
                ip = msg.content.strip()
        d = {"ip": ip}
        await self.updateServer(ctx, d)

    @edit.command(name="icon", aliases=["pic", "image"])
    async def changeIcon(self, ctx):
        """Modify your SCP:SL Server's Icon as shown on discord."""
        if not await self.config.guild(ctx.guild).enabled():
            return await ctx.send(
                "SCPSL Module disabled on this server. Use `{prefix}scpsl enable` to enable the module for this server.".format(
                    prefix=ctx.prefix
                )
            )
        server = await self.config.guild(ctx.guild).server()
        global_servers = await self.config.global_servers()
        guildID = str(ctx.guild.id)
        if not guildID in global_servers and not server:
            try:
                await ctx.send(f"{ctx.guild.name} does not have a registered SCP:SL server")
            except discord.Forbidden:
                pass
            return
        await ctx.send("Enter a url to set as your Icon Thumbnail.")
        try:
            msg = await ctx.bot.wait_for(
                "message", check=MessagePredicate.same_context(ctx), timeout=25
            )
        except asyncio.TimeoutError:
            return await ctx.send("Server Registration Cancelled.")
        if msg.content.strip().lower() in ["cancel", "exit", "stop"]:
            return await ctx.send("Server Editing Cancelled.")
        image = msg.content.strip()
        d = {"icon_url": image}
        await self.updateServer(ctx, d)

    @edit.command(name="range")
    async def range(self, ctx):
        """Modify your SCP:SL Server's portrange to track."""
        if not await self.config.guild(ctx.guild).enabled():
            return await ctx.send(
                "SCPSL Module disabled on this server. Use `{prefix}scpsl enable` to enable the module for this server.".format(
                    prefix=ctx.prefix
                )
            )
        server = await self.config.guild(ctx.guild).server()
        global_servers = await self.config.global_servers()
        guildID = str(ctx.guild.id)
        endport = startport = None
        if not guildID in global_servers and not server:
            try:
                await ctx.send(f"{ctx.guild.name} does not have a registered SCP:SL server")
            except discord.Forbidden:
                pass
            return
        while endport is None or startport is None:
            await ctx.send(
                "Enter a port range to track. Serpate with `-`. Enter single port to set endport"
                + "\n"
                '*Ex.  Range : "7777 - 7780"*   *Endport : 7778*'
            )
            try:
                msg = await ctx.bot.wait_for(
                    "message", check=MessagePredicate.same_context(ctx), timeout=25
                )
            except asyncio.TimeoutError:
                return await ctx.send("Server Editing Cancelled.")
            if msg.content.strip().lower() in ["cancel", "exit", "stop"]:
                return await ctx.send("Server Editing Cancelled.")
            if "-" in msg.content:
                startport, endport = msg.content.split("-")
                try:
                    startport = int(startport)
                    endport = int(endport)
                except ValueError:
                    await ctx.send("Invalid Port Range.")
                    continue
            else:
                if server:
                    startport = server["startport"]
                elif guildID in global_servers:
                    async with self.config.global_servers() as global_servers:
                        server = global_servers[guildID]
                        startport = server["startport"]
                if len(msg.content.strip()) <= 4:
                    try:
                        endport = int(msg.content.strip())
                    except ValueError:
                        await ctx.send("Invalid Port Range.")
                        continue
                else:
                    await ctx.send("Invalid Port Range. Expected a 4 digit port.")
                    continue
            if startport > endport:
                await ctx.send(
                    f'Invalid port range. Startport "{startport}" cannot be higher than Endport "{endport}"'
                )
                startport = endport = None
                continue
        d = {
            "endport": endport,
            "startport": startport,
            "portrange": list(
                range(startport, endport + 1) if endport >= startport else range(7777, 7778)
            ),
        }
        await self.updateServer(ctx, d)

    @edit.command(name="aliases", aliases=["alias"])
    async def _aliases(self, ctx):
        """Modify your SCP:SL Server's aliases. Will overwrite previous aliases."""
        if not await self.config.guild(ctx.guild).enabled():
            return await ctx.send(
                "SCPSL Module disabled on this server. Use `{prefix}scpsl enable` to enable the module for this server.".format(
                    prefix=ctx.prefix
                )
            )
        server = await self.config.guild(ctx.guild).server()
        global_servers = await self.config.global_servers()
        guildID = str(ctx.guild.id)
        if not guildID in global_servers and not server:
            try:
                await ctx.send(f"{ctx.guild.name} does not have a registered SCP:SL server")
            except discord.Forbidden:
                pass
            return
        if (
            server
        ):  # Remove and Store Aliases to bypass Alias Verification from checking own server's aliases
            temp_aliases = server.pop("aliases")
            await self.config.guild(ctx.guild).server.set(server)
        elif guildID in global_servers:
            async with self.config.global_servers() as global_servers:
                svr = global_servers[ctx.guild.id]
                temp_aliases = svr.pop("aliases")
        d = {"aliases": temp_aliases}
        aliases = None
        while aliases is None:
            await ctx.send(
                "Enter a list of Aliases to use `!status <alias>` to view your Server status. *Max. 3 Aliases*"
                + "\n"
                "*Type `cancel` to Cancel.*"
            )
            try:
                msg = await ctx.bot.wait_for(
                    "message", check=MessagePredicate.same_context(ctx), timeout=35
                )
            except asyncio.TimeoutError:
                if server:  # Readd temp stored aliases
                    server.update(d)
                    await self.config.guild(ctx.guild).server.set(server)
                elif guildID in global_servers:
                    async with self.config.global_servers() as global_servers:
                        server = global_servers[ctx.guild.id]
                        server.update(d)
                        global_servers[ctx.guild.id] = server
                return await ctx.send("Server Editing Cancelled.")
            if msg.content.strip().lower() in ["cancel", "exit", "stop"]:
                if server:  # Readd temp stored aliases
                    server.update(d)
                    await self.config.guild(ctx.guild).server.set(server)
                elif guildID in global_servers:
                    async with self.config.global_servers() as global_servers:
                        server = global_servers[ctx.guild.id]
                        server.update(d)
                        global_servers[ctx.guild.id] = server
                return await ctx.send("Server Editing Cancelled.")
            aliases = msg.content.strip().split(" ")
            if not aliases:
                aliases = []
            else:
                try:
                    await self.verifyAlias(aliases)
                except AliasTaken as e:
                    await ctx.send(str(e))
                    aliases = None
                    continue
                else:
                    aliases = [alias.lower() for alias in aliases[:3]]
        d = {"aliases": list(aliases)}
        await self.updateServer(ctx, d)

    async def updateServer(self, ctx, changes: dict, showSettings: bool = True):
        """Update changes as a dictionary to a Registered Server"""
        server = await self.config.guild(ctx.guild).server()
        global_servers = await self.config.global_servers()
        guildID = str(ctx.guild.id)

        if server:
            server.update(changes)
            await self.config.guild(ctx.guild).server.set(server)
            try:
                await ctx.send(
                    f"__{ctx.guild.name}'s locally registered SCP:SL Server.__" + "\n"
                    f"```yaml" + "\n"
                    f"Name: {server['name']}" + "\n"
                    f"Icon_Url: {server['icon_url']}" + "\n"
                    f"IP: {server['ip']}" + "\n"
                    f"Server_Count: {server['endport'] - server['startport'] + 1}" + "\n"
                    f"Port_Range: ({server['startport']} - {server['endport']})" + "\n"
                    f"Aliases: {server['aliases']}"
                    "```"
                )
            except discord.Forbidden:
                pass
        elif guildID in global_servers:
            async with self.config.global_servers() as global_servers:
                server = global_servers[ctx.guild.id]
                server.update(d)
                global_servers[ctx.guild.id] = server
            try:
                await ctx.send(
                    f"__{ctx.guild.name}'s globally registered SCP:SL Server.__" + "\n"
                    f"```yaml" + "\n"
                    f"Name: {server['name']}" + "\n"
                    f"Icon_Url: {server['icon_url']}" + "\n"
                    f"IP: {server['ip']}" + "\n"
                    f"Server_Count: {server['endport'] - server['startport'] + 1}" + "\n"
                    f"Port_Range: ({server['startport']} - {server['endport']})" + "\n"
                    f"Aliases: {server['aliases']}"
                    "```"
                )
            except discord.Forbidden:
                pass
