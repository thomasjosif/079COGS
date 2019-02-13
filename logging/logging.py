import discord
from redbot.core import commands
from redbot.core.i18n import Translator


from .core import LoggingCore
from .events import LoggingEvents

BaseCog = getattr(commands, "Cog", object)

_ = Translator("Logging", __file__)

# TODO:
# Documentation
# A way to show all settings (needs a complete rework, removed for now)


class Logging(LoggingEvents, BaseCog):
    def __init__(self, bot):
        self.bot = bot
        self.core = LoggingCore(bot)

        self.green = discord.Color.green()
        self.orange = discord.Color.orange()
        self.red = discord.Color.red()
        self.blue = discord.Color.blue()
        self.black = discord.Color.from_rgb(15, 2, 2)

    @commands.group(name="logging", aliases=["gp"])
    async def _logging(self, context):
        """
        The Logging Cog
        """

    @_logging.group(name="set")
    @commands.has_permissions(administrator=True)
    async def _logging_set(self, context):
        """
        Settings
        """

    @_logging_set.command(name="show")
    async def _logging_set_show(self, context):
        """
        Show all settings
        """
        await context.send("Sorry, this isn't ready yet. :(")

    @_logging_set.command(name="compact")
    async def _logging_set_compact(self, context):
        """
        Toggle compact mode for smaller messages
        """
        guild = context.guild
        await context.send(await self.core.compactmode(guild))

    @_logging_set.group(name="event")
    async def _logging_set_event(self, context):
        """
        Manually control and change event settings
        """

    @_logging_set_event.command(name="enable")
    async def _logging_set_event_enable(
        self, context, event_type: str, channel: discord.TextChannel
    ):
        """
        Enable an event
        """
        guild = context.guild
        if event_type.lower() in self.core.event_types:
            await self.core.enable_event(guild, channel, event_type)
            await context.send(_("Event '{}' enabled").format(event_type))
        else:
            await context.send(_("This event type does not exist."))
            message = _("Copy these exactly in order enable or disable them.\n")
            for event in self.core.event_types:
                message += "\n**{}**".format(event)
            embed = discord.Embed(
                title=_("Available event types"), description=message, color=self.green
            )
            await context.send(embed=embed)

    @_logging_set_event.command(name="disable")
    async def _logging_set_event_disable(self, context, event_type: str):
        """
        Disable an event
        """
        guild = context.guild
        if event_type in self.core.event_types:
            await self.core.disable_event(guild, event_type)
            await context.send(_("Event '{}' disabled").format(event_type))
        else:
            await context.send(_("This event type does not exist."))
            message = _("Copy these exactly in order enable or disable them.\n")
            for event in self.core.event_types:
                message += "\n**{}**".format(event)
            embed = discord.Embed(
                title=_("Available event types"), description=message, color=self.green
            )
            await context.send(embed=embed)

    @_logging.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def _logging_setup(self, context):
        """
        Begin your journey into authoritarianism
        """
        x = await self.core._start_setup(context)
        if x:
            await context.send(_("“Setup complete.”"))
        else:
            await context.send(_("Please try again, it didn't go quite alright."))

    @_logging.command(name="autosetup")
    @commands.has_permissions(administrator=True)
    async def _logging_autosetup(self, context):
        """
        RECOMMENDED! Begin your journey into authoritarianism, automatically.
        """
        try:
            x = await self.core._start_auto_setup(context)
            if x:
                await context.send(_("“Until they become conscious, they will never rebel”"))
            else:
                await context.send(_("Please try again, it didn't go quite alright."))
        except discord.Forbidden:
            await context.send(_("I don't have the permissions to create channels."))

    @_logging.group(name="ignore")
    @commands.has_permissions(kick_members=True)
    async def _logging_ignore(self, context):
        """
        Ignore
        """
        if (
            context.invoked_subcommand is None
            or context.invoked_subcommand == self._logging_ignore
        ):
            await context.send_help()

    @_logging_ignore.command(name="member")
    async def _logging_ignore_member(self, context, member: discord.Member):
        """
        Ignore a member, this is a toggle
        """
        guild = context.guild
        channel = context.channel
        await channel.send(await self.core.ignoremember(guild, member))

    @_logging_ignore.command(name="channel")
    async def _logging_ignore_channel(self, context, channel: discord.TextChannel):
        """
        Ignore a channel, this is a toggle
        """
        guild = context.guild
        source_channel = context.channel
        await source_channel.send(await self.core.ignorechannel(guild, channel))
