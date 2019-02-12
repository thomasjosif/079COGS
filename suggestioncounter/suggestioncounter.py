import discord

from redbot.core.config import Config
from redbot.core import commands
from datetime import datetime


def minimalist_embed(color, title: str):
    embed = discord.Embed(color=color)
    embed.set_author(name=title)
    return embed


class SuggestionCounterCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=326328326783286, force_registration=True)
        self.config.register_global(suggestions=[], suggestion_channel=472408084686438422)
        self.bot.add_listener(self.message_sent, "on_message")

    @commands.guild_only()
    @commands.command()
    async def suggestion(self, ctx, suggestion_number: str):
        """ Gets a stored suggestion """
        suggestion = None
        suggestion_message = None
        upvotes = 0
        downvotes = 0

        if not suggestion_number.isdigit():
            await ctx.send(
                embed=minimalist_embed(0xFF0000, "Please ensure that the suggestion number is a digit.")
            )
            return

        try:
            # something a bit buggy with using suggestion_index. 1 and 0 return the same element. force 1 usage
            if int(suggestion_number) == 0:
                raise ValueError

            async with self.config.suggestions() as suggestion_list:
                suggestion_index = int(suggestion_number) - 1
                suggestion = suggestion_list[suggestion_index]
                # raise errors to catch in case of suggestion id being missing,
                # channel being missing or message itself being missing
                if suggestion is None:
                    raise ValueError
                channel = discord.utils.get(ctx.guild.text_channels, id=await self.config.suggestion_channel())
                if channel is None:
                    raise ValueError
                suggestion_message = await channel.get_message(suggestion)
                if suggestion_message is None:
                    raise ValueError

                if len(suggestion_message.reactions) != 0:
                    for reaction in suggestion_message.reactions:
                        if reaction.emoji.id == 538404065667973130:
                            upvotes += 1
                        elif reaction.emoji.id == 538404065374371842:
                            downvotes += 1

        except (ValueError, IndexError):
            await ctx.send(embed=minimalist_embed(0xFF0000, f"Suggestion #{suggestion_number} not found."))
            return

        else:
            author_top_role = ctx.author.top_role.color
            creation_date = suggestion_message.created_at.strftime("%A, %d. %B %Y %I:%M%p")
            request_date = datetime.utcnow().strftime("%A, %d. %B %Y %I:%M%p")

            agree = discord.utils.get(ctx.guild.emojis, name="agree")
            disagree = discord.utils.get(ctx.guild.emojis, name="disagree")
            show_score = True
            if agree is None or disagree is None:
                show_score = False

            suggestion_embed = discord.Embed(color=author_top_role)
            suggestion_embed.set_author(name="Suggestion #" + suggestion_number)
            suggestion_embed.add_field(name="Suggested at:", value=creation_date, inline=True)
            suggestion_embed.set_thumbnail(url=suggestion_message.author.avatar_url)
            suggestion_embed.add_field(name="Suggested by:", value=suggestion_message.author.mention, inline=True)

            if show_score:
                # take 1 from the suggestion count as actually having the score visible requires a score of 1
                upvotes = ((upvotes-1) if (upvotes > 0) else 0)
                downvotes = ((downvotes-1) if (downvotes > 0) else 0)
                score_str = f"{str(upvotes)} {str(agree)} {str(downvotes)} {str(disagree)}"
                suggestion_embed.add_field(name="Score:", value=score_str, inline=True)

            suggestion_embed.add_field(name="Suggestion:", value=suggestion_message.content, inline=False)
            suggestion_embed.set_footer(text=f"Requested by {ctx.author.name} on {request_date}",
                                        icon_url=ctx.author.avatar_url)

            await ctx.send(embed=suggestion_embed)

    @commands.guild_only()
    @commands.command()
    async def suggestions(self, ctx):
        """ Lists the amount of currently stored suggestions """
        amount = 0
        async with self.config.suggestions() as suggestions:
            amount = len(suggestions)

        await ctx.send(embed=minimalist_embed(0x00FF00, f"There are currently {str(amount)} stored suggestions."))

    async def message_sent(self, message):
        """ Listener for registering new suggestions """
        suggestion_channel = await self.config.suggestion_channel()
        if message.channel.id != suggestion_channel:
            return
        async with self.config.suggestions() as suggestions:
            suggestions.append(message.id)
