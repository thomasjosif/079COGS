import asyncio
import discord
from redbot.core import checks, commands, Config

UNIQUE_ID = 413588955

class Bulletin(commands.Cog):
    """Bulletinboards for listing game servers"""

    def __init__(self):
        self.config = Config.get_conf(self, identifier=UNIQUE_ID)

        default_guild = {
            "servers": {
                "enabled": False,
                "channel":  0,
                "data": {}
            },
            "partners": {
                "enabled": False,
                "channel":  0,
                "data": {}
            },
            "localservers": {
                "enabled": False,
                "channel":  0,
                "data": {}
            },
            "media": {
                "enabled": False,
                "channel":  0,
                "data": {}
            }
        }
        self.config.register_guild(**default_guild)

    # Yes/No and channel selection taken from here:
    # https://github.com/BotEX-Developers/079COGS/blob/master/logging/setup.py
    async def _yes_no(self, question, ctx):
        channel = ctx.channel

        def check(message):
            return ctx.author.id == message.author.id

        bot_message = await channel.send(question)

        try:
            message = await ctx.bot.wait_for("message", timeout=120, check=check)
        except TimeoutError:
            print("Timeout!")
        if message:
            if any(n in message.content.lower() for n in ["yes", "y"]):
                await bot_message.edit(content="**{}: Yes**".format(question))
                try:
                    await message.delete()
                except discord.Forbidden:
                    pass
                return True
        await bot_message.edit(content="**{} No**".format(question))
        return False

    async def _what_channel(self, question, ctx):
        channel = ctx.channel

        def check(message):
            return ctx.author.id == message.author.id

        bot_message = await channel.send(question)
        try:
            message = await ctx.bot.wait_for("message", timeout=120, check=check)
        except TimeoutError:
            print("Timeout!")
        if message:
            channel = message.raw_channel_mentions[0] if message.raw_channel_mentions else False
            if channel:
                await bot_message.edit(content="**{}**".format(question))
                return channel
            else:
                await bot_message.edit(content="**That's not a valid channel! Disabled.**")
                return False
        return False

    async def _text_question(self, question, ctx):
        channel = ctx.channel

        def check(message):
            return ctx.author.id == message.author.id

        bot_message = await channel.send(question)
        try:
            message = await ctx.bot.wait_for("message", timeout=120, check=check)
        except TimeoutError:
            print("Timeout!")
        if message:
            await bot_message.edit(content="**{}**".format(question))
            return message.content
        return "Not specified! Please-re-run setup"
    @checks.mod_or_permissions(manage_messages=True)
    @commands.guild_only()
    @commands.group()
    async def bulletin(self, ctx):
        """Manage active bulletin boards."""

    @checks.mod_or_permissions(manage_messages=True)
    @commands.guild_only()
    @bulletin.command()
    async def setup(self, ctx):
        """Configures bulletin board settings, must be run before you use this cog!"""

        if await self._yes_no("Do you want to enable the servers module? [y]es/[n]o", ctx):
            serverschannel = await self._what_channel(
                "Which channel should I use for server listings? (please mention the channel)",
                ctx,
            )
            if serverschannel:
                await self.config.guild(ctx.guild).servers.enabled.set(True)
                await self.config.guild(ctx.guild).servers.channel.set(serverschannel)
            else:
                await self.config.guild(ctx.guild).servers.enabled.set(False)
        if await self._yes_no("Do you want to enable the partners module? [y]es/[n]o", ctx):
            partnerschannel = await self._what_channel(
                "Which channel should I use for partner listings? (please mention the channel)",
                ctx,
            )
            if partnerschannel:
                await self.config.guild(ctx.guild).partners.enabled.set(True)
                await self.config.guild(ctx.guild).partners.channel.set(partnerschannel)
            else:
                await self.config.guild(ctx.guild).partners.enabled.set(False)
        if await self._yes_no("Do you want to enable the local servers module? [y]es/[n]o", ctx):
            localserverschannel = await self._what_channel(
                "Which channel should I use for localized server listings? (please mention the channel)",
                ctx,
            )
            if localserverschannel:
                await self.config.guild(ctx.guild).localservers.enabled.set(True)
                await self.config.guild(ctx.guild).localservers.channel.set(localserverschannel)
            else:
                await self.config.guild(ctx.guild).localservers.enabled.set(False)
        if await self._yes_no("Do you want to enable the media module? [y]es/[n]o", ctx):
            mediachannel = await self._what_channel(
                "Which channel should I use for media links? (please mention the channel)",
                ctx,
            )
            if mediachannel:
                await self.config.guild(ctx.guild).media.enabled.set(True)
                await self.config.guild(ctx.guild).media.channel.set(mediachannel)
            else:
                await self.config.guild(ctx.guild).media.enabled.set(False)
        return

    @checks.is_owner()
    @commands.guild_only()
    @bulletin.command()
    async def reset(self, ctx):
        """Clears all bulletin configuration settings."""
        if await self._yes_no("Are you sure you want to reset all settings and data? **THIS CANNOT BE REVERSED!** ["
                              "y]es/[n]o", ctx):
            await self.config.clear_all()
            await ctx.send("Success! Cleared all configuration settings and data.")
    @checks.mod_or_permissions(manage_messages=True)
    @commands.guild_only()
    @commands.group()
    async def mediabulletin(self, ctx):
        """Fancy embedded media links"""

    @checks.mod_or_permissions(manage_messages=True)
    @commands.guild_only()
    @mediabulletin.command()
    async def config(self, ctx):
        if not await self.config.guild(ctx.guild).media.enabled():
            await ctx.send("The media module is not enabled! You can change this by running `[p]bulletin setup`")
            return
        embed = discord.Embed(title="{Main Website}", colour=discord.Colour(0x20ed0), url="https://discordapp.com",
                              description="{Main Description}")

        embed.set_thumbnail(url="https://cdn.discordapp.com/embed/avatars/0.png")
        embed.set_author(name="{Main Title}", url="https://discordapp.com",
                         icon_url="https://cdn.discordapp.com/embed/avatars/0.png")
        embed.set_footer(text="{Footer Text}", icon_url="https://cdn.discordapp.com/embed/avatars/0.png")

        embed.add_field(name="{Media Title}", value="{Media Link}")

        await ctx.send(content="This is an example of the media embed", embed=embed)

        datadict = {}
        datadict["maintitile"] = await self._text_question("Please define the {Main Title}: ", ctx)
        datadict["thumbnailimage"] = await self._text_question("Please provide an image link for the main title (top left image): ", ctx)
        datadict["mainwebsite"] = await self._text_question("Please define the {Main Website} (please provide a link): ", ctx)
        datadict["maindesc"] = await self._text_question("Please define the {Main Description} (markdown supported!): ", ctx)
        datadict["thumbnailimage"] = await self._text_question("Please provide an image link for the thumbnail (top right image): ", ctx)
        datadict["footerimage"] = await self._text_question("Please provide an image link for the footer (bottom right image): ", ctx)
        datadict["footertext"] = await self._text_question("Please provide the {Footer Text}: ", ctx)
        await ctx.send(datadict)
        print(datadict)

        medialinksdict = {}

        
        while True:
            if await self._yes_no("Do you want to add an additional media link [y]es/[n]o?", ctx):

            else:
                break