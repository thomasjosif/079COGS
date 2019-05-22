import asyncio
import discord
import time
from redbot.core import commands, Config, checks, utils
from typing import Optional


class AdvertCog(commands.Cog):

    default_guild = {
        "advert_role_ID": None,
        "start_alert_message": None,
        "end_alert_message": None,
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 50745431254379423, force_registration=True)
        self.config.register_guild(**self.default_guild)

    @commands.command(name="advert", aliases=["ad"])
    @commands.guild_only()
    @checks.mod_or_permissions(manage_roles=True)
    async def advert(
        self,
        ctx,
        users: commands.Greedy[discord.Member],
        minutes: Optional[int] = 2,
        sendPM: bool = True,
    ):
        """Give a user temporary advertisment permission and access"""
        if not ctx.guild.me.guild_permissions.manage_roles:
            return await ctx.send(
                "I don't have `Manage Roles` perms. I thought we were friends ;c"
            )

        if not users:
            return await ctx.send_help()

        advert_role_ID = await self.config.guild(ctx.guild).advert_role_ID()

        if advert_role_ID is None:
            return await ctx.send(
                "Advert Role is not set. Use `{prefix}setadvert role <role>` to enable.".format(
                    prefix=ctx.prefix
                )
            )

        advert_role = ctx.guild.get_role(advert_role_ID)
        server = ctx.guild.name
        msg = f"```diff\nGave the following users Role {advert_role.name}. PM Notification Sent : {sendPM}. The role will be revoked after {minutes} minutes :\n\n"
        for member in users:
            await member.add_roles(advert_role)
            if sendPM:
                await self.alert_member(ctx, member, minutes, start_message=True)
            msg += f"+ {member} - Has Role {advert_role.name}\n"
        msg += "```"
        message = await ctx.send(msg)

        seconds = minutes * 60
        await asyncio.sleep(seconds)

        msg = (
            f"```diff\n{minutes} minutes passed and Role {advert_role.name} has been revoked :\n\n"
        )
        for member in users:
            await member.remove_roles(advert_role)
            if sendPM:
                await self.alert_member(ctx, member, minutes, start_message=False)
            msg += f"- {member} - Role Revoked ({advert_role.name})\n"
        msg += "```"
        await message.edit(content=msg)

    async def alert_member(self, ctx, member, minutes, start_message: bool = True):
        if start_message:
            alert_message = await self.config.guild(ctx.guild).start_alert_message()

            if alert_message is None:
                alert_message = "You have received access make an advertisement post in Server __**{server}**__!\n\nYou have __**{minutes}**__ to make an advertisement."
            await member.send(
                alert_message.format(
                    server=ctx.guild.name,
                    user=member.name,
                    admin=ctx.author,
                    minutes=(f"{minutes} minutes" if minutes > 1 else f"{minutes} minute"),
                )
            )
        else:
            alert_message = await self.config.guild(ctx.guild).end_alert_message()

            if alert_message is None:
                alert_message = "Your __**{minutes}**__ timer has ended to make an advertisement in Server __**{server}**__. Thank you **{user}**!"
            await member.send(
                alert_message.format(
                    server=ctx.guild.name,
                    user=member.name,
                    admin=ctx.author,
                    minutes=(f"{minutes} minutes" if minutes > 1 else f"{minutes} minute"),
                )
            )

    @commands.group(name="setadvert")
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def setadvert(self, ctx):
        """Configure advert settings"""
        pass

    @setadvert.command(name="role")
    async def role(self, ctx, role: discord.Role = None):
        """Set the advertisement role used to give advert perms"""
        advert_role_ID = await self.config.guild(ctx.guild).advert_role_ID()
        advert_role = ctx.guild.get_role(advert_role_ID)

        if role is None and advert_role is not None:
            return await ctx.send(f"{ctx.guild.name}'s Advert Role is set to `{advert_role.name}`")
        if role is not None:
            await self.config.guild(ctx.guild).advert_role_ID.set(role.id)
            if advert_role is not None:
                return await ctx.send(
                    f"```diff\n+ Updated {ctx.guild.name}'s Advert Role {role.name}\n\n- Replaced Role {advert_role.name}```"
                )
            else:
                return await ctx.send(
                    f"```diff\n+ Updated {ctx.guild.name}'s Advert Role {role.name}```"
                )

    @setadvert.command(name="startalertmessage", aliases=["startmessage"])
    async def startalertmessage(self, ctx, *, message):
        """Set the message to dm users and notify that they can advertise
        
        Available Variables in Message:
        `{server}, {user}, {admin}, {minutes}`
        """
        alert_message = await self.config.guild(ctx.guild).start_alert_message()
        if message:
            alert_message = message
            await self.config.guild(ctx.guild).start_alert_message.set(message)
        await ctx.send(f"Start Alert Message:\n```css\n{alert_message}```")

    @setadvert.command(name="endalertmessage", aliases=["endmessage"])
    async def endalertmessage(self, ctx, *, message):
        """Set the message to dm users and notify that their advertisement time has ran out.
        
        Available Variables in Message:
        `{server}, {user}, {admin}, {minutes}`
        """
        alert_message = await self.config.guild(ctx.guild).end_alert_message()
        if message:
            alert_message = message
            await self.config.guild(ctx.guild).end_alert_message.set(message)
        await ctx.send(f"End Alert Message:\n```css\n{alert_message}```")
