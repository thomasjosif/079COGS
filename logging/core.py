import aiohttp
import inspect
import discord
import os
from .setup import LoggingSetup
import redbot.core.data_manager as datam
from redbot.core.i18n import Translator
from redbot.core import Config

_ = Translator("LoggingCore", __file__)


class LoggingCore:
    def __init__(self, bot):
        self.bot = bot

        self.path = str(datam.cog_data_path(self)).replace("\\", "/")
        self.attachment_path = self.path + "/attachments"

        self.check_folder()

        self.event_types = [
            "on_member_update",
            "on_voice_state_update",
            "on_message_edit",
            "on_message_delete",
            "on_raw_bulk_message_delete",
            "on_guild_channel_create",
            "on_guild_channel_delete",
            "on_guild_channel_update",
            "on_guild_update",
            "on_guild_role_create",
            "on_guild_role_delete",
            "on_guild_role_update",
            "on_member_ban",
            "on_member_unban",
            "on_member_kick",
            "on_member_remove",
            "on_member_join",
        ]

        self.config = Config.get_conf(self, identifier=6198483584)
        default_guild = {
            "enabled": False,
            "compact": False,
            "events": {},
            "ignore": {"channels": {}, "members": {}},
        }
        self.config.register_guild(**default_guild)

    def check_folder(self):
        if not os.path.exists(self.path):
            os.mkdir(self.path)
        if not os.path.exists(self.attachment_path):
            os.mkdir(self.attachment_path)

    async def enable_event(self, guild, channel, event_type):
        async with self.config.guild(guild).events() as events:
            events[event_type].update({"enable": True, "channel": channel.id})

    async def disable_event(self, guild, event_type):
        async with self.config.guild(guild).events() as events:
            events[event_type].update({"enable": False, "channel": False})

    async def compactmode(self, guild):
        if await self.config.guild(guild).compact():
            await self.config.guild(guild).compact.set(False)
            return _("Compact mode **disabled**")
        else:
            await self.config.guild(guild).compact.set(True)
            return _("Compact mode **enabled**")

    async def ignoremember(self, guild, author):
        if str(author.id) in await self.config.guild(guild).ignore.members():
            async with self.config.guild(guild).ignore.members() as members:
                members.pop(str(author.id), None)
            return _("Tracking {} again").format(author.mention)
        else:
            async with self.config.guild(guild).ignore.members() as members:
                members.update({str(author.id): True})
            return _("Not tracking {} anymore").format(author.mention)

    async def ignorechannel(self, guild, channel):
        if str(channel.id) in await self.config.guild(guild).ignore.channels():
            async with self.config.guild(guild).ignore.channels() as channels:
                channels.pop(str(channel.id), None)
            return _("Tracking {} again").format(channel.mention)
        else:
            async with self.config.guild(guild).ignore.channels() as channels:
                channels.update({str(channel.id): True})
            return _("Not tracking {} anymore").format(channel.mention)

    async def _ignore(self, guild, author=None, channel=None):
        if channel:
            if str(channel.id) in await self.config.guild(guild).ignore.channels():
                return False
        if author:
            if str(author.id) in await self.config.guild(guild).ignore.members():
                return False
        return True

    async def _validate_event(self, guild):
        events = await self.config.guild(guild).events()
        return (
            events[inspect.stack()[1][3]]["enabled"]
            if await self.config.guild(guild).enabled()
            else False
        )

    async def _get_channel(self, guild):
        if not inspect.stack()[2][3] in ["_warn"]:
            events = await self.config.guild(guild).events()
            return discord.utils.get(
                self.bot.get_all_channels(), id=events[inspect.stack()[2][3]]["channel"]
            )
        return False

    async def _send_message_to_channel(self, guild, content=None, embed=None, attachment=None):
        channel = await self._get_channel(guild)
        if channel:
            if embed:
                if not await self.config.guild(guild).compact():
                    await channel.send(content=content, embed=embed)
                else:
                    emdict = embed.to_dict()
                    content = ""
                    if "author" in emdict:
                        content += "**{}**\n".format(emdict["author"]["name"])
                    if "fields" in emdict:
                        for field in emdict["fields"]:
                            content += "**{}:** {}\n".format(
                                field["name"].replace("\n", " ").replace("**", ""),
                                field["value"].replace("\n", ""),
                            )
                    if "description" in emdict:
                        content += "{}\n".format(emdict["description"])
                    if "footer" in emdict:
                        content += "_{}_".format(emdict["footer"]["text"])
                    await channel.send(content=content)
            elif attachment:
                await channel.send(content=content, file=discord.File(attachment))
            elif content:
                await channel.send(content=content)

    async def downloadattachment(self, url, filename, message_id):
        session = aiohttp.ClientSession()
        async with session.get(url) as r:
            data = await r.read()
            with open(self.attachment_path + "/{}-{}".format(message_id, filename), "wb") as f:
                f.write(data)
        return "{}-{}".format(message_id, filename)

    async def _start_setup(self, context):
        guild = context.guild

        events_data = await LoggingSetup(self.bot, context).setup()

        async with self.config.guild(guild).events() as events:
            events.update(events_data)
        await self.config.guild(guild).enabled.set(True)

        return True

    async def _start_auto_setup(self, context):
        guild = context.guild

        events_data = await LoggingSetup(self.bot, context).auto_setup()

        async with self.config.guild(guild).events() as events:
            events.update(events_data)
        await self.config.guild(guild).enabled.set(True)

        return True
