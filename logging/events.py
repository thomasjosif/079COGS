import discord
from datetime import datetime
from .core import LoggingCore
from redbot.core.i18n import Translator

_ = Translator("Logging", __file__)


class LoggingEvents:
    def __init__(self, bot):
        self.bot = bot
        self.core = LoggingCore(bot)

    async def on_member_join(self, author):
        guild = author.guild
        if await self.core._validate_event(guild) and author.id != self.bot.user.id:

            embed = discord.Embed(
                color=self.green,
                description=_("**{0.name}#{0.discriminator}** ({0.id})").format(author),
            )
            embed.set_author(name=_("Member joined"))
            embed.set_footer(text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
            await self.core._send_message_to_channel(guild, embed=embed)

    async def on_member_ban(self, guild, author):
        if await self.core._validate_event(guild) and author.id != self.bot.user.id:

            async for entry in guild.audit_logs(limit=2):
                if entry.action is discord.AuditLogAction.ban:
                    if entry.reason:
                        reason = entry.reason
                    else:
                        reason = False

            embed = discord.Embed(color=self.red)
            embed.set_author(name=_("Member has been banned"))
            embed.add_field(
                name=_("**Member**"),
                value="**{0.name}#{0.discriminator}** ({0.name} {0.id})".format(author),
                inline=False,
            )
            embed.set_footer(text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))

            if reason:
                embed.add_field(name="Reason", value=reason)

            await self.core._send_message_to_channel(guild, embed=embed)

    async def on_member_unban(self, guild, author):
        if await self.core._validate_event(guild) and author.id != self.bot.user.id:

            embed = discord.Embed(color=self.orange)
            embed.set_author(name=_("Member has been unbanned"))
            embed.add_field(
                name=_("**Member**"),
                value="**{0.name}#{0.discriminator}** ({0.name} {0.id})".format(author),
                inline=False,
            )
            embed.set_footer(text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))

            await self.core._send_message_to_channel(guild, embed=embed)

    async def on_member_remove(self, author):
        guild = author.guild
        if await self.core._validate_event(guild) and author.id != self.bot.user.id:

            embed = discord.Embed(
                color=self.red,
                description=_("**{0.name}#{0.discriminator}** ({0.name} {0.id})").format(author),
            )
            embed.set_author(name=_("Member left"))
            embed.set_footer(text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))

            await self.core._send_message_to_channel(guild, embed=embed)

    async def on_member_update(self, before, after):
        guild = after.guild
        author = after

        if await self.core._ignore(guild, author=author):

            if await self.core._validate_event(guild) and after.id != self.bot.user.id:

                if before.name != after.name:
                    embed = discord.Embed(
                        color=self.blue,
                        description=_("From **{0.name}** ({0.id}) to **{1.name}**").format(
                            before, after
                        ),
                    )
                    embed.set_author(name=_("Name changed"))
                    await self.core._send_message_to_channel(guild, embed=embed)
                if before.nick != after.nick:
                    embed = discord.Embed(
                        color=self.blue,
                        description=_("From **{0.nick}** ({0.id}) to **{1.nick}**").format(
                            before, after
                        ),
                    )
                    embed.set_author(name=_("Nickname changed"))
                    await self.core._send_message_to_channel(guild, embed=embed)

                if before.roles != after.roles:
                    if len(before.roles) > len(after.roles):
                        for role in before.roles:
                            if role not in after.roles:
                                embed = discord.Embed(
                                    color=self.blue,
                                    description=_(
                                        "**{0.name}** ({0.id}) " "lost role **{1.name}**"
                                    ).format(before, role),
                                )
                                embed.set_author(name=_("Role removed"))
                                await self.core._send_message_to_channel(guild, embed=embed)
                    elif len(before.roles) < len(after.roles):
                        for role in after.roles:
                            if role not in before.roles:
                                embed = discord.Embed(
                                    color=self.blue,
                                    description=_(
                                        "**{0.name}** ({0.id}) got " "role **{1.name}**"
                                    ).format(before, role),
                                )
                                embed.set_author(name=_("Role applied"))
                                await self.core._send_message_to_channel(guild, embed=embed)

    async def on_message_delete(self, message):
        guild = message.guild
        author = message.author
        channel = message.channel

        if isinstance(channel, discord.abc.GuildChannel):
            if await self.core._ignore(guild, author=author, channel=channel):

                if await self.core._validate_event(guild) and author.id != self.bot.user.id:

                    embed = discord.Embed(color=self.red)
                    embed.set_author(name=_("Message removed"))
                    embed.add_field(
                        name=_("Member"),
                        value="{0.name}#{0.discriminator}\n({0.id})".format(author),
                    )

                    embed.add_field(name=_("Channel"), value=message.channel.mention)
                    if message.content:
                        embed.add_field(
                            name=_("Message"), value=message.clean_content, inline=False
                        )

                    embed.set_footer(
                        text=_("Message ID: {} | {}").format(
                            message.id, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                        )
                    )

                    await self.core._send_message_to_channel(guild, embed=embed)

                    if message.attachments:
                        for attachment in message.attachments:
                            filename = await self.core.downloadattachment(
                                attachment.url, attachment.filename, message.id
                            )
                            message = _("Attachment file for message: {}").format(message.id)
                            await self.core._send_message_to_channel(
                                guild,
                                content=message,
                                attachment=self.core.attachment_path + "/" + filename,
                            )

    async def on_message_edit(self, before, after):
        guild = after.guild
        author = after.author
        channel = after.channel

        if isinstance(channel, discord.abc.GuildChannel):
            if await self.core._ignore(guild, author=author, channel=channel):
                if (
                    await self.core._validate_event(guild)
                    and author.id != self.bot.user.id
                    and before.clean_content != after.clean_content
                ):

                    embed = discord.Embed(color=self.blue)
                    embed.set_author(name=_("Message changed"))
                    embed.add_field(
                        name=_("Member"),
                        value="{0.name}#{0.discriminator}\n({0.id})".format(author),
                    )
                    embed.add_field(name=_("Channel"), value=before.channel.mention)
                    embed.add_field(name=_("Before"), value=before.clean_content, inline=False)
                    embed.add_field(name=_("After"), value=after.clean_content, inline=False)
                    embed.set_footer(
                        text=_("Message ID: {} | {}").format(
                            after.id, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                        )
                    )

                    await self.core._send_message_to_channel(guild, embed=embed)

    async def on_guild_channel_create(self, channel):
        if isinstance(channel, discord.abc.GuildChannel):
            guild = channel.guild

            if await self.core._validate_event(guild):

                if isinstance(channel, discord.CategoryChannel):
                    embed = discord.Embed(color=self.green)
                    embed.set_author(name=_("Category {0.name} created").format(channel))
                else:
                    embed = discord.Embed(color=self.green)
                    embed.set_author(name=_("Channel #{0.name} created").format(channel))

                embed.set_footer(text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))

                await self.core._send_message_to_channel(guild, embed=embed)

    async def on_guild_channel_delete(self, channel):
        if isinstance(channel, discord.abc.GuildChannel):
            guild = channel.guild

            if await self.core._validate_event(guild):

                if isinstance(channel, discord.CategoryChannel):
                    embed = discord.Embed(color=self.red)
                    embed.set_author(name=_("Category {0.name} deleted").format(channel))
                else:
                    embed = discord.Embed(color=self.red)
                    embed.set_author(name=_("Channel #{0.name} deleted").format(channel))
                embed.set_footer(text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))

                await self.core._send_message_to_channel(guild, embed=embed)

    async def on_guild_channel_update(self, before, after):
        channel = after

        if isinstance(channel, discord.abc.GuildChannel):
            guild = after.guild

            if await self.core._validate_event(guild):
                if before.name != after.name:
                    embed = discord.Embed(color=self.blue)
                    if isinstance(channel, discord.CategoryChannel):
                        embed.set_author(
                            name=_("Category {0.name} renamed to {1.name}").format(before, after)
                        )
                    elif isinstance(channel, discord.VoiceChannel):
                        embed.set_author(
                            name=_("Voice channel #{0.name} renamed to #{1.name}").format(
                                before, after
                            )
                        )
                    elif isinstance(channel, discord.TextChannel):
                        embed.set_author(
                            name=_("Channel #{0.name} renamed to #{1.name}").format(before, after)
                        )
                    embed.set_footer(
                        text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
                    )
                    await self.core._send_message_to_channel(guild, embed=embed)
                if before.position != after.position:
                    if isinstance(channel, discord.CategoryChannel):
                        embed = discord.Embed(color=self.blue)
                        embed.set_author(
                            name=_(
                                "Category {0.name} moved from {0.position} " " to {1.position}"
                            ).format(before, after)
                        )
                        embed.set_footer(
                            text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
                        )
                        await self.core._send_message_to_channel(guild, embed=embed)
                    elif isinstance(channel, discord.VoiceChannel):
                        embed = discord.Embed(color=self.blue)
                        embed.set_author(
                            name=_(
                                "Voice channel #{0.name} moved from {0.position} "
                                " to {1.position}"
                            ).format(before, after)
                        )
                        embed.set_footer(
                            text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
                        )
                        await self.core._send_message_to_channel(guild, embed=embed)
                    if isinstance(channel, discord.TextChannel):
                        embed = discord.Embed(color=self.blue)
                        embed.set_author(
                            name=_(
                                "Channel #{0.name} moved from {0.position} " " to {1.position}"
                            ).format(before, after)
                        )
                        embed.set_footer(
                            text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
                        )
                        await self.core._send_message_to_channel(guild, embed=embed)

    async def on_guild_role_create(self, role):
        guild = role.guild

        if await self.core._validate_event(guild):

            embed = discord.Embed(color=self.green)
            embed.set_author(name=_("Role {0.name} has been created").format(role))
            embed.set_footer(text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))

            await self.core._send_message_to_channel(guild, embed=embed)

    async def on_guild_role_delete(self, role):
        guild = role.guild

        if await self.core._validate_event(guild):

            embed = discord.Embed(color=self.red)
            embed.set_author(name=_("Role {0.name} has been deleted").format(role))
            embed.set_footer(text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))

            await self.core._send_message_to_channel(guild, embed=embed)

    async def on_guild_role_update(self, before, after):
        guild = after.guild

        if await self.core._validate_event(guild):
            if before.name != after.name and after:
                embed = discord.Embed(color=self.blue)
                embed.set_author(name=_("Role {0.name} renamed to {1.name}").format(before, after))
                embed.set_footer(text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
                await self.core._send_message_to_channel(guild, embed=embed)
            if before.color != after.color:
                embed = discord.Embed(color=self.blue)
                embed.set_author(
                    name=_("Role color for {0.name}" "changed from {0.color} to {1.color}").format(
                        before, after
                    )
                )
                embed.set_footer(text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
                await self.core._send_message_to_channel(guild, embed=embed)
            if before.mentionable != after.mentionable:
                embed = discord.Embed(color=self.blue)
                if after.mentionable:
                    embed.set_author(
                        name=_("{Role {0.name} has been made mentionable").format(after)
                    )
                else:
                    embed.set_author(
                        name=_("Role {0.name} has been made unmentionable").format(after)
                    )
                embed.set_footer(text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
                await self.core._send_message_to_channel(guild, embed=embed)
            if before.hoist != after.hoist:
                embed = discord.Embed(color=self.blue)
                if after.hoist:
                    embed.set_author(name=_("Role {0.name} is now shown seperately").format(after))
                else:
                    embed.set_author(
                        name=_("Role {0.name} is now not shown seperately anymore").format(after)
                    )
                embed.set_footer(text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
                await self.core._send_message_to_channel(guild, embed=embed)
            if before.permissions != after.permissions:
                embed = discord.Embed(color=self.blue)
                embed.set_author(
                    name=_(
                        "Role {0.name} changed permissions from {0.permissions.value} "
                        " to {1.permissions.value}"
                    ).format(before, after)
                )
                embed.set_footer(text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
                await self.core._send_message_to_channel(guild, embed=embed)
            if before.position != after.position:
                embed = discord.Embed(color=self.blue)
                embed.set_author(
                    name=_(
                        "Role {0.name} changed position from {0.position} " " to {1.position}"
                    ).format(before, after)
                )
                embed.set_footer(text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
                await self.core._send_message_to_channel(guild, embed=embed)

    async def on_guild_update(self, before, after):
        guild = after
        if await self.core._validate_event(guild):
            if before.owner != after.owner:
                embed = discord.Embed(color=self.blue)
                embed.set_author(
                    name=_(
                        "Server owner changed from {0.owner.name} (id {0.owner.id})"
                        "to {1.owner.name} (id {1.owner.id})"
                    ).format(before, after)
                )
                embed.set_footer(text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
                await self.core._send_message_to_channel(guild, embed=embed)
            if before.region != after.region:
                embed = discord.Embed(color=self.blue)
                embed.set_author(
                    name=_("Server region changed from {0.region} to {1.region}").format(
                        before, after
                    )
                )
                embed.set_footer(text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
                await self.core._send_message_to_channel(guild, embed=embed)
            if before.name != after.name:
                embed = discord.Embed(color=self.blue)
                embed.set_author(
                    name=_("Server name changed from {0.name} to {1.name}").format(before, after)
                )
                embed.set_footer(text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
                await self.core._send_message_to_channel(guild, embed=embed)
            if before.icon_url != after.icon_url:
                embed = discord.Embed(color=self.blue)
                embed.set_author(
                    name=_("Server icon changed from {0.icon_url} to {1.icon_url}").format(
                        before, after
                    )
                )
                embed.set_footer(text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
                await self.core._send_message_to_channel(guild, embed=embed)

    async def on_voice_state_update(self, author, before, after):
        guild = author.guild
        if await self.core._ignore(guild, author=author):
            if await self.core._validate_event(guild):
                if not before.channel and after.channel:
                    embed = discord.Embed(color=self.blue)
                    embed.set_author(
                        name=_("{0.name} joined voice channel #{1.channel}").format(author, after),
                        icon_url=author.avatar_url,
                    )
                    embed.set_footer(
                        text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
                    )
                    await self.core._send_message_to_channel(guild, embed=embed)
                elif before.channel and not after.channel:
                    embed = discord.Embed(color=self.blue)
                    embed.set_author(
                        name=_("{0.name} left voice channel #{1.channel}").format(author, before),
                        icon_url=author.avatar_url,
                    )
                    embed.set_footer(
                        text="{}".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
                    )
                    await self.core._send_message_to_channel(guild, embed=embed)
