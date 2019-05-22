import asyncio
from builtins import dict
from contextlib import suppress
from copy import copy
from io import BytesIO

import discord
import pprint

from redbot.core import commands, checks, Config
from redbot.core.utils import common_filters, mod
from redbot.core.utils.chat_formatting import pagify, humanize_list
from redbot.core.utils.predicates import MessagePredicate
from redbot.core.i18n import Translator, cog_i18n

check_permissions = getattr(mod, "check_permissions", checks.check_permissions)

from .converter import RiftConverter, search_converter, SearchError


Cog = getattr(commands, "Cog", object)


_ = Translator("Rift", __file__)


max_size = 8_000_000  # can be 1 << 23 but some unknowns also add to the size
m_count = 0

async def close_check(ctx):
    """Admin / manage channel OR private channel"""
    if isinstance(ctx.channel, discord.DMChannel):
        return True
    return await mod.is_admin_or_superior(ctx.bot, ctx.author) or await check_permissions(
        ctx, {"manage_channels": True}
    )


class RiftError(Exception):
    pass


class Rift(Cog):
    """
    Communicate with other servers/channels.
    """

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.open_rifts = {}
        self.requesting_users = []
        self.bot.loop.create_task(self.load_rifts())

        self.config = Config.get_conf(self, identifier=2_113_674_295, force_registration=True)
        self.config.register_global(rifts=[])
        self.config.register_channel(blacklisted=False)
        self.config.register_guild(blacklisted=False)
        self.config.register_user(blacklisted=False)

    async def save_rift(self, rift):
        async with self.config.rifts() as rifts:
            rifts.append(rift.toIDs())

    async def load_rifts(self):

        def add_rift(sources, rift):
            if rift.source in sources:
                sources[rift.source].append(rift)
            else:
                sources[rift.source] = [rift]

        loaded = []
        sources = {}
        async with self.config.rifts() as rifts:
            for rift in rifts:
                author = self.bot.get_user(rift[0])
                if not isinstance(author, discord.User): continue
                source = self.bot.get_channel(rift[1]) or self.bot.get_user(rift[1])
                if not isinstance(source, discord.TextChannel) and not isinstance(source, discord.User): continue
                destination = self.bot.get_channel(rift[2]) or self.bot.get_user(rift[2])
                if not isinstance(destination, discord.TextChannel) and not isinstance(destination, discord.User): continue
                rift = RiftConverter.create(author, source, destination)
                loaded.append(rift)
                add_rift(sources, rift)

        self.open_rifts.update(((rift, {}) for rift in loaded))
        for source, rifts in sources.items():
            try:
                embed = await self.create_simple_embed(rift.author,
                            "Rift has been reloaded! \n{}".format("\n".join(str(rift) for rift in rifts)),
                            "Rift Loaded" if len(rifts) == 1 else "Rifts Loaded")
                await source.send(embed=embed)
            except (discord.Forbidden, discord.HTTPException):
                pass

    # COMMANDS

    @commands.group()
    async def rift(self, ctx):
        """
        Communicate with other channels through Red.
        """
        pass

    @rift.group()
    async def blacklist(self, ctx):
        """
        Configures blacklists.

        Blacklisted destinations cannot have rifts opened to them.
        """
        pass

    @blacklist.command(name="channel")
    @commands.check(close_check)
    async def blacklist_channel(self, ctx, *, channel: discord.TextChannel = None):
        """
        Blacklists the current channel or the specified channel.

        Can also blacklist DM channels.
        """
        if channel and isinstance(ctx.channel, discord.DMChannel):
            raise commands.BadArgument(_("You cannot blacklist a channel in DMs."))
        if isinstance(ctx.channel, discord.DMChannel):
            channel = ctx.author
            group = self.config.user(channel)
        else:
            channel = channel or ctx.channel
            group = self.config.channel(channel)
        blacklisted = not await group.blacklisted()
        await group.blacklisted.set(blacklisted)
        await ctx.maybe_send_embed(
            _("Channel is {} blacklisted.".format("now" if blacklisted else "no longer"))
        )
        if blacklisted:
            await self.close_rifts(ctx, ctx.author, channel)

    @blacklist.command(name="server")
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def blacklist_server(self, ctx):
        """
        Blacklists the current server.

        All channels and members in a server are considered blacklisted if the server is blacklisted.
        Members can still be reached if they are in another, non-blacklisted server.
        """
        group = self.config.guild(ctx.guild)
        blacklisted = not await group.blacklisted()
        await group.blacklisted.set(blacklisted)
        await ctx.maybe_send_embed(
            _("Server is {} blacklisted.".format("now" if blacklisted else "no longer"))
        )
        if blacklisted:
            await self.close_rifts(ctx, ctx.author, ctx.guild)

    @rift.command(name="close")
    @commands.check(close_check)
    async def rift_close(self, ctx, channel : discord.TextChannel = None):
        """
        Closes all rifts that lead to this channel.
        """
        if channel is None:
            channel = ctx.author if isinstance(ctx.channel, discord.DMChannel) else ctx.channel
        await self.close_rifts(ctx, ctx.author, channel)

    @rift.command(name="open")
    async def rift_open(self, ctx, *rifts: RiftConverter(_, globally=True)):
        """
        Opens a rift to the specified destination.

        The destination may be any channel or user that both you and the bot are connected to, even across servers.
        """
        if not rifts:
            return await ctx.send_help()
        rifts = set(rifts)
        create_queue = []
        for rift in rifts:
            if not await self.rift_exists(rift):
                if ctx.guild is None or rift.destination not in ctx.guild.channels:
                    accepted, reason = await self.request_access(ctx, rift)
                    if not accepted:
                        continue
                dest_open_embed = await self.create_simple_embed(ctx.author,
                                 _(rift.mention()),
                                 "A Rift has been opened."
                                 )
                #ctx.bot.loop.create_task(
                #    rift.destination.send(embed=dest_open_embed)
                #)
                await rift.destination.send(embed=dest_open_embed)
                create_queue.append(rift)

        with suppress(NameError):
            if reason is not None:
                await ctx.maybe_send_embed(reason)
            if not accepted:
                return
        if not create_queue:
            return await ctx.maybe_send_embed("Rift(s) already exist.")
        # add new rifts
        self.open_rifts.update(((rift, {}) for rift in create_queue))
        for rift in create_queue:
            await self.save_rift(rift)

        open_embed = await self.create_simple_embed(ctx.author,
                _("A rift has been opened to {}! Everything you say will be relayed there.\n"
                  "Responses will be relayed here.\nType `exit` here to quit."
                  ).format(humanize_list([str(rift.destination) for rift in create_queue]))
                , "Rift Opened!")
        await ctx.send(embed=open_embed)

    @rift.command(name="sources")
    async def rift_list_sources(self, ctx, destination: discord.TextChannel = None):
        """List sources for opened rifts"""
        if destination is None:
            destination = ctx.channel
        rifts = await self.get_rifts(destination, False)
        if rifts:
            message = ("Rifts:") + "\n\n"
            message += "\n".join(rift.mention() for rift in rifts)
            for page in pagify(message):
                await ctx.maybe_send_embed(page)
        else:
            embed = await self.create_simple_embed(self.bot.user, "No Rift Found.")
            await ctx.send(embed=embed)

    @rift.command(name="destinations", aliases=["dests"])
    async def rift_list_destinations(self, ctx, source: discord.TextChannel = None):
        """List destinations for opened rifts"""
        if source is None:
            source = ctx.channel
        rifts = await self.get_rifts(source, True)
        if rifts:
            message = ("Rifts:") + "\n\n"
            message += "\n".join(rift.mention() for rift in rifts)
            for page in pagify(message):
                await ctx.maybe_send_embed(page)
        else:
            embed = await self.create_simple_embed(self.bot.user, "No Rift Found.")
            await ctx.send(embed=embed)

    @rift.command(name="search")
    async def rift_search(self, ctx, searchby: search_converter(_) = None, *, search=None):
        """
        Searches through open rifts.

        searchby: author, source, or destination. If this isn't provided, all
        three are searched through.
        search: Search for the specified author/source/destination. If this
        isn't provided, the author or channel of the command is used.
        """
        searchby = searchby or list(range(3))
        if search is None:
            search = [ctx.author, ctx.channel, ctx.author]
        else:
            try:
                search = await RiftConverter.search(ctx, search, False, _)
            except commands.BadArgument as e:
                embed = await self.create_simple_embed(self.bot.user, str(e), "Bot Exception")
                return await ctx.send(embed=embed)
        results = set()
        for rift in self.open_rifts:
            for i in searchby:
                if rift[i] in search:
                    results.add(rift)
        if not results:
            return await ctx.maybe_send_embed(_("No rifts were found with these parameters."))
        message = _("Results:") + "\n\n"
        message += "\n".join(str(rift) for rift in results)
        for page in pagify(message):
            await ctx.maybe_send_embed(page)

    @rift_open.error
    @rift_search.error
    async def rift_error(self, ctx, error):
        if isinstance(error, commands.ConversionError):
            embed = discord.Embed(color=ctx.guild.me.color, 
                    description=str(error.__cause__),
                    title="Destination not found")
            return await ctx.send(embed=embed)
        raise error

    # UTILITIES

    #async def select_from_rifts(self, rifts):
    #    message = ("Rifts:") + "\n\n"
    #    message += f"\n**{rifts.index(rift) + 1}.** ".join(rift.mention() for rift in rifts)
    #    for page in pagify(message):
    #        await ctx.maybe_send_embed(page)

    #    await ctx.send("Select the rift's number you would like to edit the settings of")
    #    try:
    #        msg = await ctx.bot.wait_for("message", check=MessagePredicate.same_context(ctx), timeout=15)
    #    except asyncio.TimeoutError:
    #        await ctx.maybe_send_embed("Timeout. Selection cancelled.")
    #        return None
    #    try:
    #        index = int(msg.content)
    #    except ValueError:
    #        await ctx.maybe_send_embed("Invalid input.")
    #        return None
    #    try:
    #        rift = rifts[index]
    #        return rift
    #    except IndexError:
    #        await ctx.maybe_send_embed("Rift not found")
    #        return None

    async def request_access(self, ctx, rift) -> (bool, str):
            author = ctx.author
            if author.id in self.requesting_users:
                failed_embed = await self.create_simple_embed(author,
                                                              "You currently have a Rift request open. Please wait "
                                                              "until that expires before trying again.",
                                                              "Existing rift request.")
                try:
                    await ctx.send(embed=failed_embed)
                except discord.Forbidden:
                    pass
                return False, None
            destination = rift.destination
            source = rift.source
            self.requesting_users.append(author.id)
            embed = await self.create_simple_embed(
                author,
                (f"{author} is requesting to open a rift to here from #{source} in {ctx.guild.name}" + "\n" +
                f"{rift}" + "\n\n" +
                f"An admin can enter `accept` or `decline` to accept/decline this request."),
                "Requesting Cross-Server Rift Permission")
            try:
                request_msg = await destination.send(embed=embed)
            except discord.Forbidden:
                return False, f"I do not have permissions to send in {destination}"

            def check(m):
                is_accept_message = m.content.lower().strip() in ["accept", "yes", "y", "decline", "no", "n"]
                is_correct_channel = m.channel.id == rift.destination.id
                if isinstance(m.channel, discord.channel.DMChannel):
                    is_correct_channel = m.channel.recipient.id == rift.destination.id or m.channel.id == rift.destination.id
                    return is_correct_channel and is_accept_message
                return is_correct_channel and is_accept_message and m.author.guild_permissions.manage_channels

            try:
                msg = await ctx.bot.wait_for("message", check=check, timeout=25)
            except asyncio.TimeoutError:
                try:
                    await request_msg.delete()
                except discord.NotFound:
                    pass
                if author.id in self.requesting_users:
                    self.requesting_users.remove(author.id)
                return False, "No staff response to request."
            response = msg.content.lower().strip()
            if response in ["accept", "yes", "y"]:
                accepted, reason = True, f"{msg.author.name} has __**accepted**__ the request to open the cross-server rift.\n{rift}"
            elif response in ["decline","no","n"]:
                accepted, reason = False, f"{msg.author.name} has __**declined**__ the request to open the cross-server rift.\n{rift}"
            else:
                accepted, reason = False, "Unknown response."

            try:
                await request_msg.delete()
            except discord.NotFound:
                pass
            if author.id in self.requesting_users:
                self.requesting_users.remove(author.id)
            return accepted, reason

    async def close_rifts(self, ctx, closer, destination, search_source : bool = False):
        rifts = await self.get_rifts(destination, search_source)
        if rifts:
            for rift in rifts:
                del self.open_rifts[rift]
                async with self.config.rifts() as rifts:
                    if rift.toIDs() in rifts:
                        rifts.remove(rift.toIDs())
                source_embed = await self.create_simple_embed(ctx.author,
                    _("{} has closed the rift to {}.").format(closer, rift.destination),
                    "Rift Closed")
                await rift.source.send(embed=source_embed)
                dest_embed = await self.create_simple_embed(ctx.author,
                    _("Rift from {} closed by {}.").format(rift.source, closer),
                    "Rift Closed")
                await rift.destination.send(embed=dest_embed)
        else:
            embed = await self.create_simple_embed(self.bot.user, _("No rifts were found that connect to here."), "No Rifts Found")
            await ctx.send(embed=embed)

    async def get_rifts(self, destination, toggle=False):
        rifts = []
        if isinstance(destination, discord.Guild):
            if toggle:
                check = lambda rift: rift.source in destination.channels
            else:
                check = lambda rift: rift.destination in destination.channels
        else:
            if toggle:
                check = lambda rift: rift.source == destination
            else:
                check = lambda rift: rift.destination == destination
        for rift in self.open_rifts.copy():
            if check(rift):
                rifts.append(rift)
        return rifts

    async def get_embed(self, destination, attachments):
        attach = attachments[0]
        if (
            hasattr(destination, "guild")
            and await self.bot.db.guild(destination.guild).use_bot_color()
        ):
            color = destination.guild.me.colour
        else:
            color = self.bot.color
        description = "\n\n".join(
            f"{self.xbytes(attach.size)}\n**[{attach.filename}]({attach.url})**"
            for a in attachments
        )
        embed = discord.Embed(colour=color, description=description)
        embed.set_image(url=attach.url)
        return embed

    async def rift_exists(self, rift):
        for rift2 in await self.get_rifts(rift.source, True):
            if rift2.destination == rift.destination:
                return True
        return False


    def permissions(self, destination, user, is_owner=False):
        if isinstance(destination, discord.User):
            return destination.dm_channel.permissions_for(user)
        if not is_owner:
            member = destination.guild.get_member(user.id)
            if member:
                return destination.permissions_for(member)
            else:
                every = destination.guild.default_role
                overs = destination.overwrites_for(every)
                overs.read_messages = True
                overs.send_messages = True
                perms = (every.permissions.value & ~overs[1].value) | overs[0].value
                return discord.Permissions(perms)
        return discord.Permissions.all()

    async def process_message(self, rift, message, destination):
        if isinstance(destination, discord.Message):
            send_coro = destination.edit
        else:
            send_coro = destination.send
        channel = (
            message.author if isinstance(message.channel, discord.DMChannel) else message.channel
        )
        send = channel == rift.source
        destination = rift.destination if send else rift.source
        source = rift.source if send else rift.destination
        author = message.author
        me = (
            destination.dm_channel.me
            if isinstance(destination, discord.User)
            else destination.guild.me
        )
        is_owner = await self.bot.is_owner(author)
        author_perms = self.permissions(destination, author, is_owner)
        bot_perms = self.permissions(destination, me)
        content = message.content
        if not is_owner:
            if not author_perms.administrator:
                content = common_filters.filter_invites(content)
            if not author_perms.mention_everyone:
                content = common_filters.filter_mass_mentions(content)
        attachments = message.attachments
        files = []
        embed = None
        if attachments and author_perms.attach_files and bot_perms.attach_files:
            overs = await asyncio.gather(*(self.save_attach(file, files) for file in attachments))
            overs = list(filter(bool, overs))
            if overs:
                content += (
                    "\n\n"
                    + _("Attachments:")
                    + "\n"
                    + "\n".join(f"({self.xbytes(a.size)}) {a.url}" for a in attachments)
                )
        if not any((content, files, embed)):
            raise RiftError(_("No content to send."))
        msg_embed = await self.create_message_embed(ctx=message, source=source, content=content, files=attachments)
        return await send_coro(embed=msg_embed)

    async def save_attach(self, file: discord.Attachment, files) -> discord.File:
        if file.size > max_size:
            return file
        buffer = BytesIO()
        await file.save(buffer, seek_begin=True)
        files.append(discord.File(buffer, file.filename))
        return None

    def xbytes(self, b):
        blist = ("B", "KB", "MB")
        index = 0
        while True:
            if b > 900:
                b = b / 1024.0
                index += 1
            else:
                return "{:.3g} {}".format(b, blist[index])

    # EVENTS

    async def on_message(self, m):
        if m.author.bot:
            return
        channel = m.author if isinstance(m.channel, discord.channel.DMChannel) else m.channel
        sent = {}
        ctx = (await self.bot.get_context(m))
        is_command = ctx.valid or m.content.startswith(str(ctx.prefix))
        if is_command: return
        for rift, record in self.open_rifts.copy().items():
            privilege_check = (rift.author == m.author if not isinstance(m.channel, discord.channel.DMChannel) else m.author == channel)
            if privilege_check and m.content.lower() == "exit":
                await self.close_rifts(ctx, m.author, channel, search_source=(True if channel == rift.source else False))
                return

            if rift.source == channel:
                try:
                    record[m] = await self.process_message(rift, m, rift.destination)
                except discord.HTTPException as e:
                    embed = await self.create_simple_embed(self.bot.user,
                            _("I couldn't send your message due to an error: {}").format(e),
                            "Bot Exception")
                    await channel.send(embed=embed)
            elif rift.destination == channel:
                rift_chans = (rift.source, rift.destination)
                if rift_chans in sent:
                    record[m] = sent[rift_chans]
                else:
                    record[m] = sent[rift_chans] = await self.process_message(rift, m, rift.source)

    async def on_message_delete(self, m):
        if m.author.bot and not self.bot.user:
            return
        deleted = set()
        for record in self.open_rifts.copy().values():
            for source_m, embed_m in record.items():
                if m.id == source_m.id:
                    with suppress(KeyError, discord.NotFound):
                        record.pop(source_m)
                        if embed_m not in deleted:
                            deleted.add(source_m)
                            await embed_m.delete()
                            break
                elif m.id == embed_m.id:
                    with suppress(KeyError, discord.NotFound):
                        record.pop(source_m)
                        if source_m not in deleted:
                            deleted.add(source_m)
                            await source_m.delete()
                            break

    async def on_message_edit(self, b, a):
        if a.author.bot:
            return
        channel = a.author if isinstance(a.channel, discord.DMChannel) else a.channel
        sent = set()
        for rift, record in self.open_rifts.copy().items():
            if rift.source == channel and rift.author == a.author:
                with suppress(KeyError, discord.NotFound):
                    await self.process_message(rift, a, record[a])
            elif rift.destination == channel:
                rift_chans = (rift.source, rift.destination)
                if rift_chans not in sent:
                    sent.add(rift_chans)
                    with suppress(KeyError, discord.NotFound):
                        await self.process_message(rift, a, record[a])

    async def create_message_embed(self, ctx, source, content, files):
        message_content = (content[:1000] if len(content) > 1000 else content)
        embed = discord.Embed(color=ctx.author.color, description=message_content)
        embed.set_author(icon_url=ctx.author.avatar_url,name=ctx.author.name + " from #" + source.name)
        if len(files) == 1:
            file = files[0]
            if file.height is not None and file.height > 64 and file.width > 64 and not file.is_spoiler():
                embed.set_image(url=file.url)
            else:
                embed.add_field(name="Attachment:", value=file.url)
        elif len(files) > 1:
            file_str = ""
            for file in files:
                file_str += file.url
                file_str += "\n\n"
            embed.add_field(name="Attachments:", value=file_str)
        return embed

    async def create_simple_embed(self, author: discord.Member, message: str, title: str = None):
        simple_embed = discord.Embed(color=author.color, description=message)
        if title is not None:
            simple_embed.set_author(icon_url=author.avatar_url,name=title)
        return simple_embed
