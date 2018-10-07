import asyncio
import discord
from redbot.core.i18n import Translator

_ = Translator('LoggingSetup', __file__)


class LoggingSetup:
    def __init__(self, bot, context):
        self.context = context
        self.bot = bot

        self.green = discord.Color.green()
        self.orange = discord.Color.orange()
        self.red = discord.Color.red()
        self.blue = discord.Color.blue()

        self.default_events = {
            'on_ban': {
              'enabled': False,
              'channel': False
            },
            'on_guild_channel_create': {
              'enabled': False,
              'channel': False
            },
            'on_guild_channel_delete': {
              'enabled': False,
              'channel': False
            },
            'on_guild_channel_update': {
              'enabled': False,
              'channel': False
            },
            'on_guild_role_create': {
              'enabled': False,
              'channel': False
            },
            'on_guild_role_delete': {
              'enabled': False,
              'channel': False
            },
            'on_guild_role_update': {
              'enabled': False,
              'channel': False
            },
            'on_guild_update': {
              'enabled': False,
              'channel': False
            },
            'on_kick': {
              'enabled': False,
              'channel': False
            },
            'on_member_ban': {
              'enabled': False,
              'channel': False
            },
            'on_member_join': {
              'enabled': False,
              'channel': False
            },
            'on_member_remove': {
              'enabled': False,
              'channel': False
            },
            'on_member_unban': {
              'enabled': False,
              'channel': False
            },
            'on_member_update': {
              'enabled': False,
              'channel': False
            },
            'on_message_delete': {
              'enabled': False,
              'channel': False
            },
            'on_message_edit': {
              'enabled': False,
              'channel': False
            },
            'on_raw_bulk_message_delete': {
              'enabled': False,
              'channel': False
            },
            'on_voice_state_update': {
              'enabled': False,
              'channel': False
            }
        }

    async def _yes_no(self, question, context):
        channel = context.channel

        def check(message):
            return context.author.id == message.author.id
        bot_message = await channel.send(question)

        try:
            message = await self.bot.wait_for('message', timeout=120, check=check)
        except TimeoutError:
            print('Timeout!')
        if message:
            if any(n in message.content.lower() for n in ['yes', 'y']):
                await bot_message.edit(content=_('**{} Yes**').format(question))
                try:
                    await message.delete()
                except discord.Forbidden:
                    pass
                return True
        await bot_message.edit(content=_('**{} No**').format(question))
        return False

    async def _what_channel(self, question, context):
        channel = context.channel

        def check(message):
            return context.author.id == message.author.id

        bot_message = await channel.send(question)
        try:
            message = await self.bot.wait_for('message', timeout=120, check=check)
        except TimeoutError:
            print('Timeout!')
        if message:
            channel = message.raw_channel_mentions[0] if message.raw_channel_mentions else False
            if channel:
                await bot_message.edit(content='**{}**'.format(question))
                return channel
            else:
                await bot_message.edit(content=_('**That\'s not a valid channel! Disabled.**'))
                return False
        return False

    async def auto_setup(self):
        events = self.default_events

        overwrites = {
            self.context.guild.default_role: discord.PermissionOverwrite(send_messages=False),
            self.context.guild.me: discord.PermissionOverwrite(send_messages=True)
        }

        message = await self.context.send(_('Creating Logs category...'))

        big_brother_category = await self.context.guild.create_category('Logs', reason=_('Logging needs this to put all event channels in.'), overwrites=overwrites)

        await message.edit(content=_('Creating event channels...'))

        member_event_channel = await self.context.guild.create_text_channel('member-events', category=big_brother_category, reason=_('Logging will put all member events in this channel.'))
        message_event_channel = await self.context.guild.create_text_channel('message-events', category=big_brother_category, reason=_('Logging will put all message events in this channel.'))
        guild_event_channel = await self.context.guild.create_text_channel('server-events', category=big_brother_category, reason=_('Logging will put all server events in this channel.'))
        mod_event_channel = await self.context.guild.create_text_channel('mod-events', category=big_brother_category, reason=_('Logging will put all mod events in this channel.'))

        await message.edit(content=_('Setting up all events...'))

        # Member events
        events['on_member_join']['enabled'] = True
        events['on_member_ban']['enabled'] = True
        events['on_member_unban']['enabled'] = True
        events['on_member_remove']['enabled'] = True
        events['on_member_update']['enabled'] = True
        events['on_voice_state_update']['enabled'] = True

        events['on_member_join']['channel'] = member_event_channel.id
        events['on_member_ban']['channel'] = member_event_channel.id
        events['on_member_unban']['channel'] = member_event_channel.id
        events['on_member_remove']['channel'] = member_event_channel.id
        events['on_member_update']['channel'] = member_event_channel.id
        events['on_voice_state_update']['channel'] = member_event_channel.id

        # Message events
        events['on_message_delete']['enabled'] = True
        events['on_raw_bulk_message_delete']['enabled'] = True
        events['on_message_edit']['enabled'] = True

        events['on_message_delete']['channel'] = message_event_channel.id
        events['on_raw_bulk_message_delete']['channel'] = message_event_channel.id
        events['on_message_edit']['channel'] = message_event_channel.id

        # Server events
        events['on_guild_channel_create']['enabled'] = True
        events['on_guild_channel_delete']['enabled'] = True
        events['on_guild_channel_update']['enabled'] = True
        events['on_guild_update']['enabled'] = True

        events['on_guild_role_create']['enabled'] = True
        events['on_guild_role_delete']['enabled'] = True
        events['on_guild_role_update']['enabled'] = True

        events['on_guild_channel_create']['channel'] = guild_event_channel.id
        events['on_guild_channel_delete']['channel'] = guild_event_channel.id
        events['on_guild_channel_update']['channel'] = guild_event_channel.id
        events['on_guild_update']['channel'] = guild_event_channel.id

        events['on_guild_role_create']['channel'] = guild_event_channel.id
        events['on_guild_role_delete']['channel'] = guild_event_channel.id
        events['on_guild_role_update']['channel'] = guild_event_channel.id

        # Warning events
        events['on_kick']['enabled'] = True
        events['on_ban']['enabled'] = True

        events['on_kick']['channel'] = mod_event_channel.id
        events['on_ban']['channel'] = mod_event_channel.id

        await message.edit(content=_('And we\'re all done!'))
        return events

    async def setup(self):
        channel = self.context.channel
        instructions = _('You\'re required to answer them with either **\'yes\'** or **\'no\'** answers.\n\n'
                         'You get **2 minutes** to answer each question. If not answered it will be defaulted to **\'no\'**.\n\n'
                         'Then you\'re required to give a channel for each event.\n\n'
                         'Each channel _needs_ to be a channel mention, otherwise it won\'t work. You can use the same channel for all event types if your want. But remember that this is the expert mode and a lot of questions will be asked. (38 to be precise)\n'
                         'Make also sure to give proper permissions to the bot to post and embed messages in these channels.\n\n'
                         '**Good luck!**')

        embed = discord.Embed(title=_('**Welcome to the setup for Logging**'), description=instructions, color=self.green)
        await channel.send(embed=embed)
        await asyncio.sleep(10)

        events = self.default_events

        # Member events
        events['on_member_join']['enabled'] = await self._yes_no(_('Do you want to track members joining? [y]es/[n]o'), self.context)
        if events['on_member_join']['enabled']:
            events['on_member_join']['channel'] = await self._what_channel(_('Which channel should I use for this event? (please mention the channel)'), self.context)

        events['on_member_ban']['enabled'] = await self._yes_no(_('Do you want to track members being banned? [y]es/[n]o'), self.context)
        if events['on_member_ban']['enabled']:
            events['on_member_ban']['channel'] = await self._what_channel(_('Which channel should I use for this event? (please mention the channel)'), self.context)

        events['on_member_unban']['enabled'] = await self._yes_no(_('Do you want to track members being unbanned? [y]es/[n]o'), self.context)
        if events['on_member_unban']['enabled']:
            events['on_member_unban']['channel'] = await self._what_channel(_('Which channel should I use for this event? (please mention the channel)'), self.context)

        events['on_member_remove']['enabled'] = await self._yes_no(_('Do you want to track members leaving this server? [y]es/[n]o'), self.context)
        if events['on_member_remove']['enabled']:
            events['on_member_remove']['channel'] = await self._what_channel(_('Which channel should I use for this event? (please mention the channel)'), self.context)

        events['on_member_update']['enabled'] = await self._yes_no(_('Do you want to track member changes? [y]es/[n]o'), self.context)
        if events['on_member_update']['enabled']:
            events['on_member_update']['channel'] = await self._what_channel(_('Which channel should I use for this event? (please mention the channel)'), self.context)

        events['on_voice_state_update']['enabled'] = await self._yes_no(_('Do you want to track voice channel changes? [y]es/[n]o'), self.context)
        if events['on_voice_state_update']['enabled']:
            events['on_voice_state_update']['channel'] = await self._what_channel(_('Which channel should I use for this event? (please mention the channel)'), self.context)

        # Message events
        events['on_message_delete']['enabled'] = await self._yes_no(_('Do you want to track message deletion? [y]es/[n]o'), self.context)
        if events['on_message_delete']['enabled']:
            events['on_message_delete']['channel'] = await self._what_channel(_('Which channel should I use for this event? (please mention the channel)'), self.context)

        events['on_raw_bulk_message_delete']['enabled'] = await self._yes_no(_('Do you want to track bulk message deletion? [y]es/[n]o'), self.context)
        if events['on_raw_bulk_message_delete']['enabled']:
            events['on_raw_bulk_message_delete']['channel'] = await self._what_channel(_('Which channel should I use for this event? (please mention the channel)'), self.context)

        events['on_message_edit']['enabled'] = await self._yes_no(_('Do you want to track message editing? [y]es/[n]o'), self.context)
        if events['on_message_edit']['enabled']:
            events['on_message_edit']['channel'] = await self._what_channel(_('Which channel should I use for this event? (please mention the channel)'), self.context)

        # Server events
        events['on_guild_channel_create']['enabled'] = await self._yes_no(_('Do you want to track channel creation? [y]es/[n]o'), self.context)
        if events['on_guild_channel_create']['enabled']:
            events['on_guild_channel_create']['channel'] = await self._what_channel(_('Which channel should I use for this event? (please mention the channel)'), self.context)

        events['on_guild_channel_delete']['enabled'] = await self._yes_no(_('Do you want to track channel deletion? [y]es/[n]o'), self.context)
        if events['on_guild_channel_delete']['enabled']:
            events['on_guild_channel_delete']['channel'] = await self._what_channel(_('Which channel should I use for this event? (please mention the channel)'), self.context)

        events['on_guild_channel_update']['enabled'] = await self._yes_no(_('Do you want to track channel updates? [y]es/[n]o'), self.context)
        if events['on_guild_channel_update']['enabled']:
            events['on_guild_channel_update']['channel'] = await self._what_channel(_('Which channel should I use for this event? (please mention the channel)'), self.context)

        events['on_guild_update']['enabled'] = await self._yes_no(_('Do you want to track server updates? [y]es/[n]o'), self.context)
        if events['on_guild_update']['enabled']:
            events['on_guild_update']['channel'] = await self._what_channel(_('Which channel should I use for this event? (please mention the channel)'), self.context)

        events['on_guild_role_create']['enabled'] = await self._yes_no(_('Do you want to track role creation? [y]es/[n]o'), self.context)
        if events['on_guild_role_create']['enabled']:
            events['on_guild_role_create']['channel'] = await self._what_channel(_('Which channel should I use for this event? (please mention the channel)'), self.context)

        events['on_guild_role_delete']['enabled'] = await self._yes_no(_('Do you want to track role deletion? [y]es/[n]o'), self.context)
        if events['on_guild_role_delete']['enabled']:
            events['on_guild_role_delete']['channel'] = await self._what_channel(_('Which channel should I use for this event? (please mention the channel)'), self.context)

        events['on_guild_role_update']['enabled'] = await self._yes_no(_('Do you want to track role updates? [y]es/[n]o'), self.context)
        if events['on_guild_role_update']['enabled']:
            events['on_guild_role_update']['channel'] = await self._what_channel(_('Which channel should I use for this event? (please mention the channel)'), self.context)

        # Warning events
            events['on_kick']['enabled'] = await self._yes_no(_('Do you want to track member kicks? [y]es/[n]o'), self.context)
        if events['on_kick']['enabled']:
            events['on_kick']['channel'] = await self._what_channel(_('Which channel should I use for this event? (please mention the channel)'), self.context)

        events['on_ban']['enabled'] = await self._yes_no(_('Do you want to track member bans? [y]es/[n]o'), self.context)
        if events['on_ban']['enabled']:
            events['on_ban']['channel'] = await self._what_channel(_('Which channel should I use for this event? (please mention the channel)'), self.context)

        return events
