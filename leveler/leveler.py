import discord
from redbot.core import commands
from discord.utils import find
from redbot.core.utils.chat_formatting import pagify
import platform, asyncio, string, operator, random, textwrap
import os, re, aiohttp
import math
import redbot.cogs.bank
from redbot.core.utils.settings import Settings
from redbot.core.utils.dataIO import fileIO
from redbot.core import checks, bank

try:
    import pymongo
    from pymongo import MongoClient
except:
    raise RuntimeError("Can't load pymongo. Do 'pip3 install pymongo'.")
try:
    import scipy
    import scipy.misc
    import scipy.cluster
except:
    pass
try:
    from PIL import Image, ImageDraw, ImageFont, ImageColor, ImageOps, ImageFilter
except:
    raise RuntimeError("Can't load pillow. Do 'pip3 install pillow'.")
import time

# fonts
font_file = "data/leveler/fonts/font.ttf"
font_bold_file = "data/leveler/fonts/font_bold.ttf"
font_unicode_file = "data/leveler/fonts/unicode.ttf"

# Credits (None)
bg_credits = {}

# directory
user_directory = "data/leveler/users"

prefix = "!"
default_avatar_url = "http://i.imgur.com/XPDO9VH.jpg"

try:
    client = MongoClient()
    db = client["leveler"]
except:
    print("Can't load database. Follow instructions on Git/online to install MongoDB.")


class Leveler(commands.Cog):
    """A level up thing with image generation!"""

    def __init__(self, bot):
        self.bot = bot
        self.backgrounds = fileIO("data/leveler/backgrounds.json", "load")
        self.badges = fileIO("data/leveler/badges.json", "load")
        self.settings = fileIO("data/leveler/settings.json", "load")
        bot_settings = fileIO("data/red/settings.json", "load")
        self.owner = bot_settings["OWNER"]
        self.session = aiohttp.ClientSession(loop=self.bot.loop)
        dbs = client.database_names()
        if "leveler" not in dbs:
            self.pop_database()

    def pop_database(self):
        if os.path.exists("data/leveler/users"):
            for userid in os.listdir(user_directory):
                userinfo = fileIO("data/leveler/users/{}/info.json".format(str(userid)), "load")
                userinfo["user_id"] = str(userid)
                db.users.insert_one(userinfo)

    def create_global(self):

        userinfo = fileIO("data/leveler/users/{}/info.json".format(str(userid)), "load")
        userinfo["user_id"] = str(userid)
        db.users.insert_one(userinfo)

    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(name="profile", pass_context=True, no_pm=True)
    async def profile(self, ctx, *, user: discord.Member = None):
        """Displays a user profile."""
        if user == None:
            user = ctx.message.author
        channel = ctx.message.channel
        guild = user.guild
        curr_time = time.time()

        # creates user if doesn't exist
        await self._create_user(user, guild)
        userinfo = db.users.find_one({"user_id": str(str(user.id))})

        # check if disabled
        if str(guild.id) in self.settings["disabled_guilds"]:
            await ctx.send("**Leveler commands for this guild are disabled!**")
            return

        # no cooldown for text only
        if "text_only" in self.settings and str(guild.id) in self.settings["text_only"]:
            em = await self.profile_text(user, guild, userinfo)
            await channel.send("", embed=em)
        else:
            await self.draw_profile(user, guild)

            await channel.send(
                "**User profile for {}**".format(self._is_mention(user)),
                file=discord.File("data/leveler/temp/{}_profile.png".format(str(user.id))),
            )
            db.users.update_one(
                {"user_id": str(str(user.id))}, {"$set": {"profile_block": curr_time}}, upsert=True
            )
            try:
                os.remove("data/leveler/temp/{}_profile.png".format(str(user.id)))
            except:
                pass

    async def profile_text(self, user, guild, userinfo):
        def test_empty(text):
            if text == "":
                return "None"
            else:
                return text

        em = discord.Embed(description="", colour=user.colour)
        em.add_field(name="Title:", value=test_empty(userinfo["title"]))
        em.add_field(name="Reps:", value=userinfo["rep"])
        em.add_field(name="Global Rank:", value="#{}".format(await self._find_global_rank(user)))
        em.add_field(
            name="guild Rank:", value="#{}".format(await self._find_guild_rank(user, guild))
        )
        em.add_field(
            name="guild Level:", value=format(userinfo["servers"][str(guild.id)]["level"])
        )
        em.add_field(name="Total Exp:", value=userinfo["total_exp"])
        em.add_field(name="guild Exp:", value=await self._find_guild_exp(user, guild))
        try:
            credits = await bank.get_balance(user)
        except:
            credits = 0
        em.add_field(name="Credits: ", value="${}".format(credits))
        em.add_field(name="Info: ", value=test_empty(userinfo["info"]))
        em.add_field(
            name="Badges: ", value=test_empty(", ".join(userinfo["badges"])).replace("_", " ")
        )
        em.set_author(name="Profile for {}".format(user.name), url=user.avatar_url)
        em.set_thumbnail(url=user.avatar_url)
        return em

    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(pass_context=True, no_pm=True)
    async def rank(self, ctx, user: discord.Member = None):
        """Displays the rank of a user."""
        if user == None:
            user = ctx.message.author
        channel = ctx.message.channel
        guild = user.guild
        curr_time = time.time()

        # creates user if doesn't exist
        await self._create_user(user, guild)
        userinfo = db.users.find_one({"user_id": str(str(user.id))})

        # check if disabled
        if str(guild.id) in self.settings["disabled_guilds"]:
            await ctx.send("**Leveler commands for this guild are disabled!**")
            return

        # no cooldown for text only
        if "text_only" in self.settings and str(guild.id) in self.settings["text_only"]:
            em = await self.rank_text(user, guild, userinfo)
            await channel.send("", embed=em)
        else:
            await self.draw_rank(user, guild)

            await channel.send(
                "**Ranking & Statistics for {}**".format(self._is_mention(user)),
                file=discord.File("data/leveler/temp/{}_rank.png".format(str(user.id))),
            )
            db.users.update_one(
                {"user_id": str(str(user.id))},
                {"$set": {"rank_block".format(str(guild.id)): curr_time}},
                upsert=True,
            )
            try:
                os.remove("data/leveler/temp/{}_rank.png".format(str(user.id)))
            except:
                pass

    async def rank_text(self, user, guild, userinfo):
        em = discord.Embed(description="", colour=user.colour)
        em.add_field(
            name="guild Rank", value="#{}".format(await self._find_guild_rank(user, guild))
        )
        em.add_field(name="Reps", value=userinfo["rep"])
        em.add_field(name="guild Level", value=userinfo["servers"][str(guild.id)]["level"])
        em.add_field(name="guild Exp", value=await self._find_guild_exp(user, guild))
        em.set_author(name="Rank and Statistics for {}".format(user.name), url=user.avatar_url)
        em.set_thumbnail(url=user.avatar_url)
        return em

    # should the user be mentioned based on settings?
    def _is_mention(self, user):
        if "mention" not in self.settings.keys() or self.settings["mention"]:
            return user.mention
        else:
            return user.name

    # @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(pass_context=True, no_pm=True)
    async def top(self, ctx, *options):
        """Displays leaderboard. Add "global" parameter for global"""
        guild = ctx.message.guild
        user = ctx.message.author

        if str(guild.id) in self.settings["disabled_guilds"]:
            await ctx.send("**Leveler commands for this guild are disabled!**")
            return

        users = []
        board_type = ""
        user_stat = None
        if "-rep" in options and "-global" in options:
            title = "Global Rep Leaderboard for {}\n".format(self.bot.user.name)
            for userinfo in db.users.find({}):
                try:
                    users.append((userinfo["username"], userinfo["rep"]))
                except:
                    users.append((userinfo["user_id"], userinfo["rep"]))

                if str(user.id) == userinfo["user_id"]:
                    user_stat = userinfo["rep"]

            board_type = "Rep"
            footer_text = "Your Rank: {}         {}: {}".format(
                await self._find_global_rep_rank(user), board_type, user_stat
            )
            icon_url = self.bot.user.avatar_url
        elif "-global" in options:
            title = "Global Exp Leaderboard for {}\n".format(self.bot.user.name)
            for userinfo in db.users.find({}):
                try:
                    users.append((userinfo["username"], userinfo["total_exp"]))
                except:
                    users.append((userinfo["user_id"], userinfo["total_exp"]))

                if str(user.id) == userinfo["user_id"]:
                    user_stat = userinfo["total_exp"]

            board_type = "Points"
            footer_text = "Your Rank: {}         {}: {}".format(
                await self._find_global_rank(user), board_type, user_stat
            )
            icon_url = self.bot.user.avatar_url
        elif "-rep" in options:
            title = "Rep Leaderboard for {}\n".format(guild.name)
            for userinfo in db.users.find({}):
                userid = userinfo["user_id"]
                if "servers" in userinfo and str(guild.id) in userinfo["servers"]:
                    try:
                        users.append((userinfo["username"], userinfo["rep"]))
                    except:
                        users.append((userinfo["user_id"], userinfo["rep"]))

                if str(user.id) == userinfo["user_id"]:
                    user_stat = userinfo["rep"]

            board_type = "Rep"
            print(await self._find_guild_rep_rank(user, guild))
            footer_text = "Your Rank: {}         {}: {}".format(
                await self._find_guild_rep_rank(user, guild), board_type, user_stat
            )
            icon_url = guild.icon_url
        elif "-lvl" in options or "-level" in options:
            title = "Level Leaderboard for {}\n".format(guild.name)
            for userinfo in db.users.find({}):
                userid = userinfo["user_id"]
                if "servers" in userinfo and str(guild.id) in userinfo["servers"]:
                    level = userinfo["servers"][str(guild.id)]["level"]
                    try:
                        users.append((userinfo["username"], level))
                    except:
                        users.append((userinfo["user_id"], level))

                if str(user.id) == userinfo["user_id"]:
                    user_stat = userinfo["servers"][str(guild.id)]["level"]

            board_type = "Level"
            print(await self._find_guild_rep_rank(user, guild))
            footer_text = "Your Rank: {}         {}: {}".format(
                await self._find_guild_level_rank(user, guild), board_type, user_stat
            )
            icon_url = guild.icon_url
        else:
            title = "Exp Leaderboard for {}\n".format(guild.name)
            for userinfo in db.users.find({}):
                try:
                    userid = userinfo["user_id"]
                    if "servers" in userinfo and str(guild.id) in userinfo["servers"]:
                        guild_exp = 0
                        for i in range(userinfo["servers"][str(guild.id)]["level"]):
                            guild_exp += self._required_exp(i)
                        guild_exp += userinfo["servers"][str(guild.id)]["current_exp"]
                        try:
                            users.append((userinfo["username"], guild_exp))
                        except:
                            users.append((userinfo["user_id"], guild_exp))
                except:
                    pass
            board_type = "Points"
            footer_text = "Your Rank: {}         {}: {}".format(
                await self._find_guild_rank(user, guild),
                board_type,
                await self._find_guild_exp(user, guild),
            )
            icon_url = guild.icon_url
        sorted_list = sorted(users, key=operator.itemgetter(1), reverse=True)

        # multiple page support
        page = 1
        per_page = 15
        pages = math.ceil(len(sorted_list) / per_page)
        for option in options:
            if str(option).isdigit():
                if page >= 1 and int(option) <= pages:
                    page = int(str(option))
                else:
                    await ctx.send(
                        "**Please enter a valid page number! (1 - {})**".format(str(pages))
                    )
                    return
                break

        msg = ""
        msg += "**Rank              Name (Page {}/{})**\n".format(page, pages)
        rank = 1 + per_page * (page - 1)
        start_index = per_page * page - per_page
        end_index = per_page * page

        default_label = "   "
        special_labels = ["♔", "♕", "♖", "♗", "♘", "♙"]

        for single_user in sorted_list[start_index:end_index]:
            if rank - 1 < len(special_labels):
                label = special_labels[rank - 1]
            else:
                label = default_label

            msg += u"`{:<2}{:<2}{:<2}   # {:<22}".format(
                rank, label, u"➤", self._truncate_text(single_user[0], 20)
            )
            msg += u"{:>5}{:<2}{:<2}{:<5}`\n".format(
                " ", " ", " ", "Total {}: ".format(board_type) + str(single_user[1])
            )
            rank += 1
        msg += "----------------------------------------------------\n"
        msg += "`{}`".format(footer_text)

        em = discord.Embed(description="", colour=user.colour)
        em.set_author(name=title, icon_url=icon_url)
        em.description = msg

        await ctx.send(embed=em)

    @commands.cooldown(1, 30, commands.BucketType.user)
    @commands.command(pass_context=True, no_pm=True)
    async def rep(self, ctx, user: discord.Member = None):
        """Gives a reputation point to a designated player."""
        channel = ctx.message.channel
        org_user = ctx.message.author
        guild = org_user.guild
        # creates user if doesn't exist
        await self._create_user(org_user, guild)
        if user:
            await self._create_user(user, guild)
        org_userinfo = db.users.find_one({"user_id": str(org_user.id)})
        curr_time = time.time()

        if str(guild.id) in self.settings["disabled_guilds"]:
            await ctx.send("**Leveler commands for this guild are disabled!**")
            return
        if user and str(user.id) == str(org_user.id):
            await ctx.send("**You can't give a rep to yourself!**")
            return
        if user and user.bot:
            await ctx.send("**You can't give a rep to a bot!**")
            return
        if "rep_block" not in org_userinfo:
            org_userinfo["rep_block"] = 0

        delta = float(curr_time) - float(org_userinfo["rep_block"])
        if user and delta >= 43200.0 and delta > 0:
            userinfo = db.users.find_one({"user_id": str(str(user.id))})
            db.users.update_one({"user_id": str(org_user.id)}, {"$set": {"rep_block": curr_time}})
            db.users.update_one(
                {"user_id": str(str(user.id))}, {"$set": {"rep": userinfo["rep"] + 1}}
            )
            await ctx.send(
                "**You have just given {} a reputation point!**".format(self._is_mention(user))
            )
        else:
            # calulate time left
            seconds = 43200 - delta
            if seconds < 0:
                await ctx.send("**You can give a rep!**")
                return

            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            await ctx.send(
                "**You need to wait {} hours, {} minutes, and {} seconds until you can give reputation again!**".format(
                    int(h), int(m), int(s)
                )
            )

    @commands.command(pass_context=True, no_pm=True)
    async def lvlinfo(self, ctx, user: discord.Member = None):
        """Gives more specific details about user profile image."""

        if not user:
            user = ctx.message.author
        guild = ctx.message.guild
        userinfo = db.users.find_one({"user_id": str(str(user.id))})

        guild = ctx.message.guild

        if str(guild.id) in self.settings["disabled_guilds"]:
            await ctx.send("**Leveler commands for this guild are disabled!**")
            return

        # creates user if doesn't exist
        await self._create_user(user, guild)
        msg = ""
        msg += "Name: {}\n".format(user.name)
        msg += "Title: {}\n".format(userinfo["title"])
        msg += "Reps: {}\n".format(userinfo["rep"])
        msg += "guild Level: {}\n".format(userinfo["servers"][str(guild.id)]["level"])
        total_guild_exp = 0
        for i in range(userinfo["servers"][str(guild.id)]["level"]):
            total_guild_exp += self._required_exp(i)
        total_guild_exp += userinfo["servers"][str(guild.id)]["current_exp"]
        msg += "guild Exp: {}\n".format(total_guild_exp)
        msg += "Total Exp: {}\n".format(userinfo["total_exp"])
        msg += "Info: {}\n".format(userinfo["info"])
        msg += "Profile background: {}\n".format(userinfo["profile_background"])
        msg += "Rank background: {}\n".format(userinfo["rank_background"])
        msg += "Levelup background: {}\n".format(userinfo["levelup_background"])
        if "profile_info_color" in userinfo.keys() and userinfo["profile_info_color"]:
            msg += "Profile info color: {}\n".format(
                self._rgb_to_hex(userinfo["profile_info_color"])
            )
        if "profile_exp_color" in userinfo.keys() and userinfo["profile_exp_color"]:
            msg += "Profile exp color: {}\n".format(
                self._rgb_to_hex(userinfo["profile_exp_color"])
            )
        if "rep_color" in userinfo.keys() and userinfo["rep_color"]:
            msg += "Rep section color: {}\n".format(self._rgb_to_hex(userinfo["rep_color"]))
        if "badge_col_color" in userinfo.keys() and userinfo["badge_col_color"]:
            msg += "Badge section color: {}\n".format(
                self._rgb_to_hex(userinfo["badge_col_color"])
            )
        if "rank_info_color" in userinfo.keys() and userinfo["rank_info_color"]:
            msg += "Rank info color: {}\n".format(self._rgb_to_hex(userinfo["rank_info_color"]))
        if "rank_exp_color" in userinfo.keys() and userinfo["rank_exp_color"]:
            msg += "Rank exp color: {}\n".format(self._rgb_to_hex(userinfo["rank_exp_color"]))
        if "levelup_info_color" in userinfo.keys() and userinfo["levelup_info_color"]:
            msg += "Level info color: {}\n".format(
                self._rgb_to_hex(userinfo["levelup_info_color"])
            )
        msg += "Badges: "
        msg += ", ".join(userinfo["badges"])

        em = discord.Embed(description=msg, colour=user.colour)
        em.set_author(
            name="Profile Information for {}".format(user.name), icon_url=user.avatar_url
        )
        await ctx.send(embed=em)

    def _rgb_to_hex(self, rgb):
        rgb = tuple(rgb[:3])
        return "#%02x%02x%02x" % rgb

    @commands.group(name="lvlset", pass_context=True)
    async def lvlset(self, ctx):
        """Profile Configuration Options"""
        if ctx.invoked_subcommand is None:

            return

    @lvlset.group(name="profile", pass_context=True)
    async def profileset(self, ctx):
        """Profile options"""
        if ctx.invoked_subcommand is None or isinstance(ctx.invoked_subcommand, commands.Group):

            return

    @lvlset.group(name="rank", pass_context=True)
    async def rankset(self, ctx):
        """Rank options"""
        if ctx.invoked_subcommand is None or isinstance(ctx.invoked_subcommand, commands.Group):

            return

    @lvlset.group(name="levelup", pass_context=True)
    async def levelupset(self, ctx):
        """Level-Up options"""
        if ctx.invoked_subcommand is None or isinstance(ctx.invoked_subcommand, commands.Group):

            return

    @profileset.command(name="color", pass_context=True, no_pm=True)
    async def profilecolors(self, ctx, section: str, color: str):
        """Set info color. e.g [p]lvlset profile color [exp|rep|badge|info|all] [default|white|hex|auto]"""
        user = ctx.message.author
        guild = ctx.message.guild
        # creates user if doesn't exist
        await self._create_user(user, guild)
        userinfo = db.users.find_one({"user_id": str(str(user.id))})

        section = section.lower()
        default_info_color = (30, 30, 30, 200)
        white_info_color = (150, 150, 150, 180)
        default_rep = (92, 130, 203, 230)
        default_badge = (128, 151, 165, 230)
        default_exp = (255, 255, 255, 230)
        default_a = 200

        if str(guild.id) in self.settings["disabled_guilds"]:
            await ctx.send("**Leveler commands for this guild are disabled!**")
            return

        if "text_only" in self.settings and str(guild.id) in self.settings["text_only"]:
            await ctx.send("**Text-only commands allowed.**")
            return

        # get correct section for db query
        if section == "rep":
            section_name = "rep_color"
        elif section == "exp":
            section_name = "profile_exp_color"
        elif section == "badge":
            section_name = "badge_col_color"
        elif section == "info":
            section_name = "profile_info_color"
        elif section == "all":
            section_name = "all"
        else:
            await ctx.send("**Not a valid section. (rep, exp, badge, info, all)**")
            return

        # get correct color choice
        if color == "auto":
            if section == "exp":
                color_ranks = [random.randint(2, 3)]
            elif section == "rep":
                color_ranks = [random.randint(2, 3)]
            elif section == "badge":
                color_ranks = [0]  # most prominent color
            elif section == "info":
                color_ranks = [random.randint(0, 1)]
            elif section == "all":
                color_ranks = [random.randint(2, 3), random.randint(2, 3), 0, random.randint(0, 2)]

            hex_colors = await self._auto_color(userinfo["profile_background"], color_ranks)
            set_color = []
            for hex_color in hex_colors:
                color_temp = self._hex_to_rgb(hex_color, default_a)
                set_color.append(color_temp)

        elif color == "white":
            set_color = [white_info_color]
        elif color == "default":
            if section == "exp":
                set_color = [default_exp]
            elif section == "rep":
                set_color = [default_rep]
            elif section == "badge":
                set_color = [default_badge]
            elif section == "info":
                set_color = [default_info_color]
            elif section == "all":
                set_color = [default_exp, default_rep, default_badge, default_info_color]
        elif self._is_hex(color):
            set_color = [self._hex_to_rgb(color, default_a)]
        else:
            await ctx.send("**Not a valid color. (default, hex, white, auto)**")
            return

        if section == "all":
            if len(set_color) == 1:
                db.users.update_one(
                    {"user_id": str(str(user.id))},
                    {
                        "$set": {
                            "profile_exp_color": set_color[0],
                            "rep_color": set_color[0],
                            "badge_col_color": set_color[0],
                            "profile_info_color": set_color[0],
                        }
                    },
                )
            elif color == "default":
                db.users.update_one(
                    {"user_id": str(str(user.id))},
                    {
                        "$set": {
                            "profile_exp_color": default_exp,
                            "rep_color": default_rep,
                            "badge_col_color": default_badge,
                            "profile_info_color": default_info_color,
                        }
                    },
                )
            elif color == "auto":
                db.users.update_one(
                    {"user_id": str(str(user.id))},
                    {
                        "$set": {
                            "profile_exp_color": set_color[0],
                            "rep_color": set_color[1],
                            "badge_col_color": set_color[2],
                            "profile_info_color": set_color[3],
                        }
                    },
                )
            await ctx.send("**Colors for profile set.**")
        else:
            print("update one")
            db.users.update_one(
                {"user_id": str(str(user.id))}, {"$set": {section_name: set_color[0]}}
            )
            await ctx.send("**Color for profile {} set.**".format(section))

    @rankset.command(name="color", pass_context=True, no_pm=True)
    async def rankcolors(self, ctx, section: str, color: str = None):
        """Set info color. e.g [p]lvlset rank color [exp|info] [default|white|hex|auto]"""
        user = ctx.message.author
        guild = ctx.message.guild
        # creates user if doesn't exist
        await self._create_user(user, guild)
        userinfo = db.users.find_one({"user_id": str(str(user.id))})

        section = section.lower()
        default_info_color = (30, 30, 30, 200)
        white_info_color = (150, 150, 150, 180)
        default_exp = (255, 255, 255, 230)
        default_a = 200

        if str(guild.id) in self.settings["disabled_guilds"]:
            await ctx.send("**Leveler commands for this guild are disabled!**")
            return

        if "text_only" in self.settings and str(guild.id) in self.settings["text_only"]:
            await ctx.send("**Text-only commands allowed.**")
            return

        # get correct section for db query
        if section == "exp":
            section_name = "rank_exp_color"
        elif section == "info":
            section_name = "rank_info_color"
        elif section == "all":
            section_name = "all"
        else:
            await ctx.send("**Not a valid section. (exp, info, all)**")
            return

        # get correct color choice
        if color == "auto":
            if section == "exp":
                color_ranks = [random.randint(2, 3)]
            elif section == "info":
                color_ranks = [random.randint(0, 1)]
            elif section == "all":
                color_ranks = [random.randint(2, 3), random.randint(0, 1)]

            hex_colors = await self._auto_color(userinfo["rank_background"], color_ranks)
            set_color = []
            for hex_color in hex_colors:
                color_temp = self._hex_to_rgb(hex_color, default_a)
                set_color.append(color_temp)
        elif color == "white":
            set_color = [white_info_color]
        elif color == "default":
            if section == "exp":
                set_color = [default_exp]
            elif section == "info":
                set_color = [default_info_color]
            elif section == "all":
                set_color = [default_exp, default_rep, default_badge, default_info_color]
        elif self._is_hex(color):
            set_color = [self._hex_to_rgb(color, default_a)]
        else:
            await ctx.send("**Not a valid color. (default, hex, white, auto)**")
            return

        if section == "all":
            if len(set_color) == 1:
                db.users.update_one(
                    {"user_id": str(str(user.id))},
                    {"$set": {"rank_exp_color": set_color[0], "rank_info_color": set_color[0]}},
                )
            elif color == "default":
                db.users.update_one(
                    {"user_id": str(str(user.id))},
                    {
                        "$set": {
                            "rank_exp_color": default_exp,
                            "rank_info_color": default_info_color,
                        }
                    },
                )
            elif color == "auto":
                db.users.update_one(
                    {"user_id": str(str(user.id))},
                    {"$set": {"rank_exp_color": set_color[0], "rank_info_color": set_color[1]}},
                )
            await ctx.send("**Colors for rank set.**")
        else:
            db.users.update_one(
                {"user_id": str(str(user.id))}, {"$set": {section_name: set_color[0]}}
            )
            await ctx.send("**Color for rank {} set.**".format(section))

    @levelupset.command(name="color", pass_context=True, no_pm=True)
    async def levelupcolors(self, ctx, section: str, color: str = None):
        """Set info color. e.g [p]lvlset color [info] [default|white|hex|auto]"""
        user = ctx.message.author
        guild = ctx.message.guild
        # creates user if doesn't exist
        await self._create_user(user, guild)
        userinfo = db.users.find_one({"user_id": str(str(user.id))})

        section = section.lower()
        default_info_color = (30, 30, 30, 200)
        white_info_color = (150, 150, 150, 180)
        default_a = 200

        if str(guild.id) in self.settings["disabled_guilds"]:
            await ctx.send("**Leveler commands for this guild are disabled!**")
            return

        if "text_only" in self.settings and str(guild.id) in self.settings["text_only"]:
            await ctx.send("**Text-only commands allowed.**")
            return

        # get correct section for db query
        if section == "info":
            section_name = "levelup_info_color"
        else:
            await ctx.send("**Not a valid section. (info)**")
            return

        # get correct color choice
        if color == "auto":
            if section == "info":
                color_ranks = [random.randint(0, 1)]
            hex_colors = await self._auto_color(userinfo["levelup_background"], color_ranks)
            set_color = []
            for hex_color in hex_colors:
                color_temp = self._hex_to_rgb(hex_color, default_a)
                set_color.append(color_temp)
        elif color == "white":
            set_color = [white_info_color]
        elif color == "default":
            if section == "info":
                set_color = [default_info_color]
        elif self._is_hex(color):
            set_color = [self._hex_to_rgb(color, default_a)]
        else:
            await ctx.send("**Not a valid color. (default, hex, white, auto)**")
            return

        db.users.update_one({"user_id": str(str(user.id))}, {"$set": {section_name: set_color[0]}})
        await ctx.send("**Color for level-up {} set.**".format(section))

    # uses k-means algorithm to find color from bg, rank is abundance of color, descending
    async def _auto_color(self, url: str, ranks):
        phrases = ["Calculating colors..."]  # in case I want more
        # try:
        await ctx.send("**{}**".format(random.choice(phrases)))
        clusters = 10

        async with self.session.get(url) as r:
            image = await r.content.read()
        with open("data/leveler/temp_auto.png", "wb") as f:
            f.write(image)

        im = Image.open("data/leveler/temp_auto.png").convert("RGBA")
        im = im.resize((290, 290))  # resized to reduce time
        ar = scipy.misc.fromimage(im)
        shape = ar.shape
        ar = ar.reshape(scipy.product(shape[:2]), shape[2])

        codes, dist = scipy.cluster.vq.kmeans(ar.astype(float), clusters)
        vecs, dist = scipy.cluster.vq.vq(ar, codes)  # assign codes
        counts, bins = scipy.histogram(vecs, len(codes))  # count occurrences

        # sort counts
        freq_index = []
        index = 0
        for count in counts:
            freq_index.append((index, count))
            index += 1
        sorted_list = sorted(freq_index, key=operator.itemgetter(1), reverse=True)

        colors = []
        for rank in ranks:
            color_index = min(rank, len(codes))
            peak = codes[sorted_list[color_index][0]]  # gets the original index
            peak = peak.astype(int)

            colors.append("".join(format(c, "02x") for c in peak))
        return colors  # returns array
        # except:
        # await ctx.send("```Error or no scipy. Install scipy doing 'pip3 install numpy' and 'pip3 install scipy' or read here: https://github.com/AznStevy/Maybe-Useful-Cogs/blob/master/README.md```")

    # converts hex to rgb
    def _hex_to_rgb(self, hex_num: str, a: int):
        h = hex_num.lstrip("#")

        # if only 3 characters are given
        if len(str(h)) == 3:
            expand = "".join([x * 2 for x in str(h)])
            h = expand

        colors = [int(h[i : i + 2], 16) for i in (0, 2, 4)]
        colors.append(a)
        return tuple(colors)

    # dampens the color given a parameter
    def _moderate_color(self, rgb, a, moderate_num):
        new_colors = []
        for color in rgb[:3]:
            if color > 128:
                color -= moderate_num
            else:
                color += moderate_num
            new_colors.append(color)
        new_colors.append(230)

        return tuple(new_colors)

    @profileset.command(pass_context=True, no_pm=True)
    async def info(self, ctx, *, info):
        """Set your user info."""
        user = ctx.message.author
        guild = ctx.message.guild
        # creates user if doesn't exist
        await self._create_user(user, guild)
        userinfo = db.users.find_one({"user_id": str(str(user.id))})
        max_char = 150

        if str(guild.id) in self.settings["disabled_guilds"]:
            await ctx.send("Leveler commands for this guild are disabled.")
            return

        if len(info) < max_char:
            db.users.update_one({"user_id": str(str(user.id))}, {"$set": {"info": info}})
            await ctx.send("**Your info section has been succesfully set!**")
        else:
            await ctx.send(
                "**Your description has too many characters! Must be <{}**".format(max_char)
            )

    @levelupset.command(name="bg", pass_context=True, no_pm=True)
    async def levelbg(self, ctx, *, image_name: str):
        """Set your level background"""
        user = ctx.message.author
        guild = ctx.message.guild
        # creates user if doesn't exist
        await self._create_user(user, guild)
        userinfo = db.users.find_one({"user_id": str(str(user.id))})

        if str(guild.id) in self.settings["disabled_guilds"]:
            await ctx.send("Leveler commands for this guild are disabled.")
            return

        if "text_only" in self.settings and str(guild.id) in self.settings["text_only"]:
            await ctx.send("**Text-only commands allowed.**")
            return

        if image_name in self.backgrounds["levelup"].keys():
            if await self._process_purchase(ctx):
                db.users.update_one(
                    {"user_id": str(str(user.id))},
                    {"$set": {"levelup_background": self.backgrounds["levelup"][image_name]}},
                )
                await ctx.send("**Your new level-up background has been succesfully set!**")
        else:
            await ctx.send(
                "That is not a valid bg. See available bgs at `{}backgrounds levelup`".format(
                    prefix[0]
                )
            )

    @profileset.command(name="bg", pass_context=True, no_pm=True)
    async def profilebg(self, ctx, *, image_name: str):
        """Set your profile background"""
        user = ctx.message.author
        guild = ctx.message.guild
        # creates user if doesn't exist
        await self._create_user(user, guild)
        userinfo = db.users.find_one({"user_id": str(str(user.id))})

        if str(guild.id) in self.settings["disabled_guilds"]:
            await ctx.send("Leveler commands for this guild are disabled.")
            return

        if "text_only" in self.settings and str(guild.id) in self.settings["text_only"]:
            await ctx.send("**Text-only commands allowed.**")
            return

        if image_name in self.backgrounds["profile"].keys():
            if await self._process_purchase(ctx):
                db.users.update_one(
                    {"user_id": str(str(user.id))},
                    {"$set": {"profile_background": self.backgrounds["profile"][image_name]}},
                )
                await ctx.send("**Your new profile background has been succesfully set!**")
        else:
            await ctx.send(
                "That is not a valid bg. See available bgs at `{}backgrounds profile`".format(
                    prefix[0]
                )
            )

    @rankset.command(name="bg", pass_context=True, no_pm=True)
    async def rankbg(self, ctx, *, image_name: str):
        """Set your rank background"""
        user = ctx.message.author
        guild = ctx.message.guild
        # creates user if doesn't exist
        await self._create_user(user, guild)
        userinfo = db.users.find_one({"user_id": str(str(user.id))})

        if str(guild.id) in self.settings["disabled_guilds"]:
            await ctx.send("Leveler commands for this guild are disabled.")
            return

        if "text_only" in self.settings and str(guild.id) in self.settings["text_only"]:
            await ctx.send("**Text-only commands allowed.**")
            return

        if image_name in self.backgrounds["rank"].keys():
            if await self._process_purchase(ctx):
                db.users.update_one(
                    {"user_id": str(str(user.id))},
                    {"$set": {"rank_background": self.backgrounds["rank"][image_name]}},
                )
                await ctx.send("**Your new rank background has been succesfully set!**")
        else:
            await ctx.send(
                "That is not a valid bg. See available bgs at `{}backgrounds rank`".format(
                    prefix[0]
                )
            )

    @profileset.command(pass_context=True, no_pm=True)
    async def title(self, ctx, *, title):
        """Set your title."""
        user = ctx.message.author
        guild = ctx.message.guild
        # creates user if doesn't exist
        await self._create_user(user, guild)
        userinfo = db.users.find_one({"user_id": str(str(user.id))})
        max_char = 20

        if str(guild.id) in self.settings["disabled_guilds"]:
            await ctx.send("Leveler commands for this guild are disabled.")
            return

        if len(title) < max_char:
            userinfo["title"] = title
            db.users.update_one({"user_id": str(str(user.id))}, {"$set": {"title": title}})
            await ctx.send("**Your title has been succesfully set!**")
        else:
            await ctx.send("**Your title has too many characters! Must be <{}**".format(max_char))

    @checks.admin_or_permissions(manage_guild=True)
    @commands.group(pass_context=True)
    async def lvladmin(self, ctx):
        """Admin Toggle Features"""
        if ctx.invoked_subcommand is None:

            return

    @checks.admin_or_permissions(manage_guild=True)
    @lvladmin.group(pass_context=True)
    async def overview(self, ctx):
        """A list of settings"""
        user = ctx.message.author

        disabled_guilds = []
        private_levels = []
        disabled_levels = []
        locked_channels = []

        for guild in self.bot.guilds:
            if (
                "disabled_guilds" in self.settings.keys()
                and str(str(guild.id)) in self.settings["disabled_guilds"]
            ):
                disabled_guilds.append(guild.name)
            if (
                "lvl_msg_lock" in self.settings.keys()
                and str(guild.id) in self.settings["lvl_msg_lock"].keys()
            ):
                for channel in guild.channels:
                    if self.settings["lvl_msg_lock"][str(guild.id)] == channel.id:
                        locked_channels.append("\n{} → #{}".format(guild.name, channel.name))
            if "lvl_msg" in self.settings.keys() and str(guild.id) in self.settings["lvl_msg"]:
                disabled_levels.append(guild.name)
            if (
                "private_lvl_msg" in self.settings.keys()
                and str(guild.id) in self.settings["private_lvl_msg"]
            ):
                private_levels.append(guild.name)

        num_users = 0
        for i in db.users.find({}):
            num_users += 1

        msg = ""
        msg += "**guilds:** {}\n".format(len(self.bot.guilds))
        msg += "**Unique Users:** {}\n".format(num_users)
        if "mention" in self.settings.keys():
            msg += "**Mentions:** {}\n".format(str(self.settings["mention"]))
        msg += "**Background Price:** {}\n".format(self.settings["bg_price"])
        if "badge_type" in self.settings.keys():
            msg += "**Badge type:** {}\n".format(self.settings["badge_type"])
        msg += "**Disabled guilds:** {}\n".format(", ".join(disabled_guilds))
        msg += "**Enabled Level Messages:** {}\n".format(", ".join(disabled_levels))
        msg += "**Private Level Messages:** {}\n".format(", ".join(private_levels))
        msg += "**Channel Locks:** {}\n".format(", ".join(locked_channels))
        em = discord.Embed(description=msg, colour=user.colour)
        em.set_author(name="Settings Overview for {}".format(self.bot.user.name))
        await ctx.send(embed=em)

    @lvladmin.command(pass_context=True, no_pm=True)
    async def msgcredits(self, ctx, credits: int = 0):
        """Credits per message logged. Default = 0"""
        channel = ctx.message.channel
        guild = ctx.message.guild

        if credits < 0 or credits > 1000:
            await ctx.send("**Please enter a valid number (0 - 1000)**".format(channel.name))
            return

        if "msg_credits" not in self.settings.keys():
            self.settings["msg_credits"] = {}

        self.settings["msg_credits"][str(guild.id)] = credits
        await ctx.send("**Credits per message logged set to `{}`.**".format(str(credits)))

        fileIO("data/leveler/settings.json", "save", self.settings)

    @lvladmin.command(name="lock", pass_context=True, no_pm=True)
    async def lvlmsglock(self, ctx):
        """Locks levelup messages to one channel. Disable command via locked channel."""
        channel = ctx.message.channel
        guild = ctx.message.guild

        if "lvl_msg_lock" not in self.settings.keys():
            self.settings["lvl_msg_lock"] = {}

        if str(guild.id) in self.settings["lvl_msg_lock"]:
            if channel.id == self.settings["lvl_msg_lock"][str(guild.id)]:
                del self.settings["lvl_msg_lock"][str(guild.id)]
                await ctx.send("**Level-up message lock disabled.**".format(channel.name))
            else:
                self.settings["lvl_msg_lock"][str(guild.id)] = channel.id
                await ctx.send("**Level-up message lock changed to `#{}`.**".format(channel.name))
        else:
            self.settings["lvl_msg_lock"][str(guild.id)] = channel.id
            await ctx.send("**Level-up messages locked to `#{}`**".format(channel.name))

        fileIO("data/leveler/settings.json", "save", self.settings)

    async def _process_purchase(self, ctx):
        user = ctx.message.author
        guild = ctx.message.guild

        try:
            if self.settings["bg_price"] != 0:
                if not bank.can_spend(user, self.settings["bg_price"]):
                    await ctx.send(
                        "**Insufficient funds. Backgrounds changes cost: ${}**".format(
                            self.settings["bg_price"]
                        )
                    )
                    return False
                else:
                    await ctx.send(
                        "**{}, you are about to buy a background for `{}`. Confirm by typing `yes`.**".format(
                            self._is_mention(user), self.settings["bg_price"]
                        )
                    )
                    answer = await self.bot.wait_for_message(timeout=15, author=user)
                    if answer is None:
                        await ctx.send("**Purchase canceled.**")
                        return False
                    elif "yes" not in answer.content.lower():
                        await ctx.send("**Background not purchased.**")
                        return False
                    else:
                        new_balance = bank.get_balance(user) - self.settings["bg_price"]
                        await bank.set_balance(user, new_balance)
                        return True
            else:
                if self.settings["bg_price"] == 0:
                    return True
                else:
                    await ctx.send(
                        "**You don't have an account. Do {}bank register**".format(prefix)
                    )
                    return False
        except:
            if self.settings["bg_price"] == 0:
                return True
            else:
                await ctx.send(
                    "**There was an error with economy cog. Fix to allow purchases or set price to $0. Currently ${}**".format(
                        prefix, self.settings["bg_price"]
                    )
                )
                return False

    async def _give_chat_credit(self, user, guild):
        try:
            if "msg_credits" in self.settings:
                await bank.deposit_credits(user, self.settings["msg_credits"][str(guild.id)])
        except:
            pass

    @checks.is_owner()
    @lvladmin.command(no_pm=True)
    async def setprice(self, price: int):
        """Set a price for background changes."""
        if price < 0:
            await ctx.send("**That is not a valid background price.**")
        else:
            self.settings["bg_price"] = price
            await ctx.send("**Background price set to: `{}`!**".format(price))
            fileIO("data/leveler/settings.json", "save", self.settings)

    @checks.is_owner()
    @lvladmin.command(pass_context=True, no_pm=True)
    async def setlevel(self, ctx, user: discord.Member, level: int):
        """Set a user's level. (What a cheater C:)."""
        org_user = ctx.message.author
        guild = user.guild
        channel = ctx.message.channel
        # creates user if doesn't exist
        await self._create_user(user, guild)
        userinfo = db.users.find_one({"user_id": str(str(user.id))})

        if str(guild.id) in self.settings["disabled_guilds"]:
            await ctx.send("Leveler commands for this guild are disabled.")
            return

        if level < 0:
            await ctx.send("**Please enter a positive number.**")
            return

        # get rid of old level exp
        old_guild_exp = 0
        for i in range(userinfo["servers"][str(guild.id)]["level"]):
            old_guild_exp += self._required_exp(i)
        userinfo["total_exp"] -= old_guild_exp
        userinfo["total_exp"] -= userinfo["servers"][str(guild.id)]["current_exp"]

        # add in new exp
        total_exp = self._level_exp(level)
        userinfo["servers"][str(guild.id)]["current_exp"] = 0
        userinfo["servers"][str(guild.id)]["level"] = level
        userinfo["total_exp"] += total_exp

        db.users.update_one(
            {"user_id": str(str(user.id))},
            {
                "$set": {
                    "servers.{}.level".format(str(guild.id)): level,
                    "servers.{}.current_exp".format(str(guild.id)): 0,
                    "total_exp": userinfo["total_exp"],
                }
            },
        )
        await ctx.send(
            "**{}'s Level has been set to `{}`.**".format(self._is_mention(user), level)
        )
        await self._handle_levelup(user, userinfo, guild, channel)

    @checks.is_owner()
    @lvladmin.command(no_pm=True)
    async def mention(self):
        """Toggle mentions on messages."""
        if "mention" not in self.settings.keys() or self.settings["mention"] == True:
            self.settings["mention"] = False
            await ctx.send("**Mentions disabled.**")
        else:
            self.settings["mention"] = True
            await ctx.send("**Mentions enabled.**")
        fileIO("data/leveler/settings.json", "save", self.settings)

    async def _valid_image_url(self, url):
        max_byte = 1000

        try:
            async with self.session.get(url) as r:
                image = await r.content.read()
            with open("data/leveler/test.png", "wb") as f:
                f.write(image)
            image = Image.open("data/leveler/test.png").convert("RGBA")
            os.remove("data/leveler/test.png")
            return True
        except:
            return False

    @checks.admin_or_permissions(manage_guild=True)
    @lvladmin.command(pass_context=True, no_pm=True)
    async def toggle(self, ctx):
        """Toggle most leveler commands on the current guild."""
        guild = ctx.message.guild
        if str(guild.id) in self.settings["disabled_guilds"]:
            self.settings["disabled_guilds"] = list(
                filter(lambda a: a != str(guild.id), self.settings["disabled_guilds"])
            )
            await ctx.send("**Leveler enabled on `{}`.**".format(guild.name))
        else:
            self.settings["disabled_guilds"].append(str(guild.id))
            await ctx.send("**Leveler disabled on `{}`.**".format(guild.name))
        fileIO("data/leveler/settings.json", "save", self.settings)

    @checks.admin_or_permissions(manage_guild=True)
    @lvladmin.command(pass_context=True, no_pm=True)
    async def textonly(self, ctx, all: str = None):
        """Toggle text-based messages on the guild."""
        guild = ctx.message.guild
        user = ctx.message.author
        # deals with enabled array

        if "text_only" not in self.settings.keys():
            self.settings["text_only"] = []

        if all != None:
            if str(user.id) == self.owner:
                if all == "disableall":
                    self.settings["text_only"] = []
                    await ctx.send("**Text-only disabled for all guilds.**")
                elif all == "enableall":
                    self.settings["lvl_msg"] = []
                    for guild in self.bot.guilds:
                        self.settings["text_only"].append(str(guild.id))
                    await ctx.send("**Text-only messages enabled for all guilds.**")
            else:
                await ctx.send("**No Permission.**")
        else:
            if str(guild.id) in self.settings["text_only"]:
                self.settings["text_only"].remove(str(guild.id))
                await ctx.send("**Text-only messages disabled for `{}`.**".format(guild.name))
            else:
                self.settings["text_only"].append(str(guild.id))
                await ctx.send("**Text-only messages enabled for `{}`.**".format(guild.name))
        fileIO("data/leveler/settings.json", "save", self.settings)

    @checks.admin_or_permissions(manage_guild=True)
    @lvladmin.command(name="alerts", pass_context=True, no_pm=True)
    async def lvlalert(self, ctx, all: str = None):
        """Toggle level-up messages on the guild."""
        guild = ctx.message.guild
        user = ctx.message.author

        # old version was boolean
        if not isinstance(self.settings["lvl_msg"], list):
            self.settings["lvl_msg"] = []

        if all != None:
            if str(user.id) == self.owner:
                if all == "disableall":
                    self.settings["lvl_msg"] = []
                    await ctx.send("**Level-up messages disabled for all guilds.**")
                elif all == "enableall":
                    self.settings["lvl_msg"] = []
                    for guild in self.bot.guilds:
                        self.settings["lvl_msg"].append(str(guild.id))
                    await ctx.send("**Level-up messages enabled for all guilds.**")
            else:
                await ctx.send("**No Permission.**")
        else:
            if str(guild.id) in self.settings["lvl_msg"]:
                self.settings["lvl_msg"].remove(str(guild.id))
                await ctx.send("**Level-up alerts disabled for `{}`.**".format(guild.name))
            else:
                self.settings["lvl_msg"].append(str(guild.id))
                await ctx.send("**Level-up alerts enabled for `{}`.**".format(guild.name))
        fileIO("data/leveler/settings.json", "save", self.settings)

    @checks.admin_or_permissions(manage_guild=True)
    @lvladmin.command(name="private", pass_context=True, no_pm=True)
    async def lvlprivate(self, ctx, all: str = None):
        """Toggles if lvl alert is a private message to the user."""
        guild = ctx.message.guild
        # deals with ENABLED array, not disabled

        if "private_lvl_msg" not in self.settings.keys():
            self.settings["private_lvl_msg"] = []

        if all != None:
            if str(user.id) == self.owner:
                if all == "disableall":
                    self.settings["private_lvl_msg"] = []
                    await ctx.send("**Private level-up messages disabled for all guilds.**")
                elif all == "enableall":
                    self.settings["private_lvl_msg"] = []
                    for guild in self.bot.guilds:
                        self.settings["private_lvl_msg"].append(str(guild.id))
                    await ctx.send("**Private level-up messages enabled for all guilds.**")
            else:
                await ctx.send("**No Permission.**")
        else:
            if str(guild.id) in self.settings["private_lvl_msg"]:
                self.settings["private_lvl_msg"].remove(str(guild.id))
                await ctx.send("**Private level-up alerts disabled for `{}`.**".format(guild.name))
            else:
                self.settings["private_lvl_msg"].append(str(guild.id))
                await ctx.send("**Private level-up alerts enabled for `{}`.**".format(guild.name))

        fileIO("data/leveler/settings.json", "save", self.settings)

    @commands.group(pass_context=True)
    async def badge(self, ctx):
        """Badge Configuration Options"""
        if ctx.invoked_subcommand is None:

            return

    @badge.command(name="available", pass_context=True, no_pm=True)
    async def available(self, ctx, global_badge: str = None):
        """Get a list of available badges for guild or 'global'."""
        user = ctx.message.author
        guild = ctx.message.guild

        # get guild stuff
        ids = [
            ("global", "Global", self.bot.user.avatar_url),
            (str(guild.id), guild.name, guild.icon_url),
        ]

        title_text = "**Available Badges**"
        index = 0
        for guildid, guildname, icon_url in ids:
            em = discord.Embed(description="", colour=user.colour)
            em.set_author(name="{}".format(guildname), icon_url=icon_url)
            msg = ""
            guild_badge_info = db.badges.find_one({"guild_id": guildid})
            if guild_badge_info:
                guild_badges = guild_badge_info["badges"]
                for badgename in guild_badges:
                    badgeinfo = guild_badges[badgename]
                    if badgeinfo["price"] == -1:
                        price = "Non-purchasable"
                    elif badgeinfo["price"] == 0:
                        price = "Free"
                    else:
                        price = badgeinfo["price"]

                    msg += "**• {}** ({}) - {}\n".format(
                        badgename, price, badgeinfo["description"]
                    )
            else:
                msg = "None"

            em.description = msg

            total_pages = 0
            for page in pagify(msg, ["\n"]):
                total_pages += 1

            counter = 1
            for page in pagify(msg, ["\n"]):
                if index == 0:
                    await ctx.send(title_text, embed=em)
                else:
                    await ctx.send(embed=em)
                index += 1

                em.set_footer(text="Page {} of {}".format(counter, total_pages))
                counter += 1

    @badge.command(name="list", pass_context=True, no_pm=True)
    async def listuserbadges(self, ctx, user: discord.Member = None):
        """Get the badges of a user."""
        if user == None:
            user = ctx.message.author
        guild = ctx.message.guild
        await self._create_user(user, guild)
        userinfo = db.users.find_one({"user_id": str(str(user.id))})
        userinfo = self._badge_convert_dict(userinfo)

        # sort
        priority_badges = []
        for badgename in userinfo["badges"].keys():
            badge = userinfo["badges"][badgename]
            priority_num = badge["priority_num"]
            if priority_num != -1:
                priority_badges.append((badge, priority_num))
        sorted_badges = sorted(priority_badges, key=operator.itemgetter(1), reverse=True)

        badge_ranks = ""
        counter = 1
        for badge, priority_num in sorted_badges[:12]:
            badge_ranks += "**{}. {}** ({}) [{}] **—** {}\n".format(
                counter,
                badge["badge_name"],
                badge["guild_name"],
                priority_num,
                badge["description"],
            )
            counter += 1
        if not badge_ranks:
            badge_ranks = "None"

        em = discord.Embed(description="", colour=user.colour)

        total_pages = 0
        for page in pagify(badge_ranks, ["\n"]):
            total_pages += 1

        counter = 1
        for page in pagify(badge_ranks, ["\n"]):
            em.description = page
            em.set_author(name="Badges for {}".format(user.name), icon_url=user.avatar_url)
            em.set_footer(text="Page {} of {}".format(counter, total_pages))
            await ctx.send(embed=em)
            counter += 1

    @badge.command(name="buy", pass_context=True, no_pm=True)
    async def buy(self, ctx, name: str, global_badge: str = None):
        '''Get a badge from repository. optional = "-global"'''
        user = ctx.message.author
        guild = ctx.message.guild
        if global_badge == "-global":
            guildid = "global"
        else:
            guildid = str(guild.id)
        await self._create_user(user, guild)
        userinfo = db.users.find_one({"user_id": str(str(user.id))})
        userinfo = self._badge_convert_dict(userinfo)
        guild_badge_info = db.badges.find_one({"guild_id": guildid})

        if guild_badge_info:
            guild_badges = guild_badge_info["badges"]
            if name in guild_badges:

                if "{}_{}".format(name, str(guildid)) not in userinfo["badges"].keys():
                    badge_info = guild_badges[name]
                    if badge_info["price"] == -1:
                        await ctx.send("**That badge is not purchasable.**".format(name))
                    elif badge_info["price"] == 0:
                        userinfo["badges"]["{}_{}".format(name, str(guildid))] = guild_badges[name]
                        db.users.update_one(
                            {"user_id": userinfo["user_id"]},
                            {"$set": {"badges": userinfo["badges"]}},
                        )
                        await ctx.send("**`{}` has been obtained.**".format(name))
                    else:
                        # use the economy cog
                        await ctx.send(
                            '**{}, you are about to buy the `{}` badge for `{}`. Confirm by typing "yes"**'.format(
                                self._is_mention(user), name, badge_info["price"]
                            )
                        )
                        answer = await self.bot.wait_for_message(timeout=15, author=user)
                        if answer is None:
                            await ctx.send("**Purchase canceled.**")
                            return
                        elif "yes" not in answer.content.lower():
                            await ctx.send("**Badge not purchased.**")
                            return
                        else:
                            if badge_info["price"] <= await bank.get_balance(user):
                                await bank.withdraw_credits(user, badge_info["price"])
                                userinfo["badges"][
                                    "{}_{}".format(name, str(guildid))
                                ] = guild_badges[name]
                                db.users.update_one(
                                    {"user_id": userinfo["user_id"]},
                                    {"$set": {"badges": userinfo["badges"]}},
                                )
                                await ctx.send(
                                    "**You have bought the `{}` badge for `{}`.**".format(
                                        name, badge_info["price"]
                                    )
                                )
                            elif bank.get_balance(user) < badge_info["price"]:
                                await ctx.send(
                                    "**Not enough money! Need `{}` more.**".format(
                                        badge_info["price"] - bank.get_balance(user)
                                    )
                                )
                            else:
                                await ctx.send(
                                    "**User does not exist in bank. Do {}bank register**".format(
                                        prefix
                                    )
                                )
                else:
                    await ctx.send("**{}, you already have this badge!**".format(user.name))
            else:
                await ctx.send(
                    "**The badge `{}` does not exist. (try `{}badge available`)**".format(
                        name, prefix[0]
                    )
                )
        else:
            await ctx.send(
                "**There are no badges to get! (try `{}badge get [name] -global`).**".format(
                    prefix[0]
                )
            )

    @badge.command(name="set", pass_context=True, no_pm=True)
    async def set(self, ctx, name: str, priority_num: int):
        """Set a badge to profile. -1(invis), 0(not on profile), max: 5000."""
        user = ctx.message.author
        guild = ctx.message.author
        await self._create_user(user, guild)

        userinfo = db.users.find_one({"user_id": str(str(user.id))})
        userinfo = self._badge_convert_dict(userinfo)

        if priority_num < -1 or priority_num > 5000:
            await ctx.send("**Invalid priority number! -1-5000**")
            return

        for badge in userinfo["badges"]:
            if userinfo["badges"][badge]["badge_name"] == name:
                userinfo["badges"][badge]["priority_num"] = priority_num
                db.users.update_one(
                    {"user_id": userinfo["user_id"]}, {"$set": {"badges": userinfo["badges"]}}
                )
                await ctx.send(
                    "**The `{}` badge priority has been set to `{}`!**".format(
                        userinfo["badges"][badge]["badge_name"], priority_num
                    )
                )
                break
        else:
            await ctx.send("**You don't have that badge!**")

    def _badge_convert_dict(self, userinfo):
        if "badges" not in userinfo or not isinstance(userinfo["badges"], dict):
            db.users.update_one({"user_id": userinfo["user_id"]}, {"$set": {"badges": {}}})
        return db.users.find_one({"user_id": userinfo["user_id"]})

    @checks.mod_or_permissions(manage_roles=True)
    @badge.command(name="add", pass_context=True, no_pm=True)
    async def addbadge(
        self, ctx, name: str, bg_img: str, border_color: str, price: int, *, description: str
    ):
        """Add a badge. name = "Use Quotes", Colors = #hex. bg_img = url, price = -1(non-purchasable), 0,..."""

        user = ctx.message.author
        guild = ctx.message.guild

        # check members
        required_members = 35
        members = 0
        for member in guild.members:
            if not member.bot:
                members += 1

        if str(user.id) == self.owner:
            pass
        elif members < required_members:
            await ctx.send(
                "**You may only add badges in guilds with {}+ non-bot members**".format(
                    required_members
                )
            )
            return

        if "-global" in description and str(user.id) == self.owner:
            description = description.replace("-global", "")
            guildid = "global"
            guildname = "global"
        else:
            guildid = str(guild.id)
            guildname = guild.name

        if "." in name:
            await ctx.send("**Name cannot contain `.`**")
            return

        if not await self._valid_image_url(bg_img):
            await ctx.send("**Background is not valid. Enter hex or image url!**")
            return

        if not self._is_hex(border_color):
            await ctx.send("**Border color is not valid!**")
            return

        if price < -1:
            await ctx.send("**Price is not valid!**")
            return

        if len(description.split(" ")) > 40:
            await ctx.send("**Description is too long! <=40**")
            return

        badges = db.badges.find_one({"guild_id": guildid})
        if not badges:
            db.badges.insert_one({"guild_id": guildid, "badges": {}})
            badges = db.badges.find_one({"guild_id": guildid})

        new_badge = {
            "badge_name": name,
            "bg_img": bg_img,
            "price": price,
            "description": description,
            "border_color": border_color,
            "guild_id": guildid,
            "guild_name": guildname,
            "priority_num": 0,
        }

        if name not in badges["badges"].keys():
            # create the badge regardless
            badges["badges"][name] = new_badge
            db.badges.update_one({"guild_id": guildid}, {"$set": {"badges": badges["badges"]}})
            await ctx.send("**`{}` Badge added in `{}` guild.**".format(name, guildname))
        else:
            # update badge in the guild
            badges["badges"][name] = new_badge
            db.badges.update_one({"guild_id": guildid}, {"$set": {"badges": badges["badges"]}})

            # go though all users and update the badge. Doing it this way because dynamic does more accesses when doing profile
            for user in db.users.find({}):
                try:
                    user = self._badge_convert_dict(user)
                    userbadges = user["badges"]
                    badge_name = "{}_{}".format(name, guildid)
                    if badge_name in userbadges.keys():
                        user_priority_num = userbadges[badge_name]["priority_num"]
                        new_badge[
                            "priority_num"
                        ] = user_priority_num  # maintain old priority number set by user
                        userbadges[badge_name] = new_badge
                        db.users.update_one(
                            {"user_id": user["user_id"]}, {"$set": {"badges": userbadges}}
                        )
                except:
                    pass
            await ctx.send("**The `{}` badge has been updated**".format(name))

    @checks.is_owner()
    @badge.command(no_pm=True)
    async def type(self, name: str):
        """circles or bars."""
        valid_types = ["circles", "bars"]
        if name.lower() not in valid_types:
            await ctx.send("**That is not a valid badge type!**")
            return

        self.settings["badge_type"] = name.lower()
        await ctx.send("**Badge type set to `{}`**".format(name.lower()))
        fileIO("data/leveler/settings.json", "save", self.settings)

    def _is_hex(self, color: str):
        if color != None and len(color) != 4 and len(color) != 7:
            return False

        reg_ex = r"^#(?:[0-9a-fA-F]{3}){1,2}$"
        return re.search(reg_ex, str(color))

    @checks.mod_or_permissions(manage_roles=True)
    @badge.command(name="delete", pass_context=True, no_pm=True)
    async def delbadge(self, ctx, *, name: str):
        """Delete a badge and remove from all users."""
        user = ctx.message.author
        channel = ctx.message.channel
        guild = user.guild

        return

        if "-global" in name and str(user.id) == self.owner:
            name = name.replace(" -global", "")
            guildid = "global"
        else:
            guildid = str(guild.id)

        # creates user if doesn't exist
        await self._create_user(user, guild)
        userinfo = db.users.find_one({"user_id": str(str(user.id))})
        userinfo = self._badge_convert_dict(userinfo)

        if str(guild.id) in self.settings["disabled_guilds"]:
            await ctx.send("Leveler commands for this guild are disabled.")
            return

        guildbadges = db.badges.find_one({"guild_id": guildid})
        if name in guildbadges["badges"].keys():
            del guildbadges["badges"][name]
            db.badges.update_one(
                {"guild_id": guildbadges["guild_id"]}, {"$set": {"badges": guildbadges["badges"]}}
            )
            # remove the badge if there
            for user_info_temp in db.users.find({}):
                try:
                    user_info_temp = self._badge_convert_dict(user_info_temp)

                    badge_name = "{}_{}".format(name, guildid)
                    if badge_name in user_info_temp["badges"].keys():
                        del user_info_temp["badges"][badge_name]
                        db.users.update_one(
                            {"user_id": user_info_temp["user_id"]},
                            {"$set": {"badges": user_info_temp["badges"]}},
                        )
                except:
                    pass

            await ctx.send("**The `{}` badge has been removed.**".format(name))
        else:
            await ctx.send("**That badge does not exist.**")

    @checks.mod_or_permissions(manage_roles=True)
    @badge.command(pass_context=True, no_pm=True)
    async def give(self, ctx, user: discord.Member, name: str):
        """Give a user a badge with a certain name"""
        org_user = ctx.message.author
        guild = org_user.guild
        # creates user if doesn't exist
        await self._create_user(user, guild)
        userinfo = db.users.find_one({"user_id": str(str(user.id))})
        userinfo = self._badge_convert_dict(userinfo)

        if str(guild.id) in self.settings["disabled_guilds"]:
            await ctx.send("Leveler commands for this guild are disabled.")
            return

        guildbadges = db.badges.find_one({"guild_id": str(guild.id)})
        badges = guildbadges["badges"]
        badge_name = "{}_{}".format(name, str(guild.id))

        if name not in badges:
            await ctx.send("**That badge doesn't exist in this guild!**")
            return
        elif badge_name in badges.keys():
            await ctx.send("**{} already has that badge!**".format(self._is_mention(user)))
            return
        else:
            userinfo["badges"][badge_name] = badges[name]
            db.users.update_one(
                {"user_id": str(str(user.id))}, {"$set": {"badges": userinfo["badges"]}}
            )
            await ctx.send(
                "**{} has just given `{}` the `{}` badge!**".format(
                    self._is_mention(org_user), self._is_mention(user), name
                )
            )

    @checks.mod_or_permissions(manage_roles=True)
    @badge.command(pass_context=True, no_pm=True)
    async def take(self, ctx, user: discord.Member, name: str):
        """Take a user's badge."""
        org_user = ctx.message.author
        guild = org_user.guild
        # creates user if doesn't exist
        await self._create_user(user, guild)
        userinfo = db.users.find_one({"user_id": str(str(user.id))})
        userinfo = self._badge_convert_dict(userinfo)

        if str(guild.id) in self.settings["disabled_guilds"]:
            await ctx.send("Leveler commands for this guild are disabled.")
            return

        guildbadges = db.badges.find_one({"guild_id": str(guild.id)})
        badges = guildbadges["badges"]
        badge_name = "{}_{}".format(name, str(guild.id))

        if name not in badges:
            await ctx.send("**That badge doesn't exist in this guild!**")
        elif badge_name not in userinfo["badges"]:
            await ctx.send("**{} does not have that badge!**".format(self._is_mention(user)))
        else:
            if userinfo["badges"][badge_name]["price"] == -1:
                del userinfo["badges"][badge_name]
                db.users.update_one(
                    {"user_id": str(str(user.id))}, {"$set": {"badges": userinfo["badges"]}}
                )
                await ctx.send(
                    "**{} has taken the `{}` badge from {}! :upside_down:**".format(
                        self._is_mention(org_user), name, self._is_mention(user)
                    )
                )
            else:
                await ctx.send("**You can't take away purchasable badges!**")

    @checks.mod_or_permissions(manage_roles=True)
    @badge.command(name="link", no_pm=True, pass_context=True)
    async def linkbadge(self, ctx, badge_name: str, level: int):
        """Associate a role with a level."""
        guild = ctx.message.guild
        guildbadges = db.badges.find_one({"guild_id": str(guild.id)})

        if guildbadges == None:
            await ctx.send("**This guild does not have any badges!**")
            return

        if badge_name not in guildbadges["badges"].keys():
            await ctx.send("**Please make sure the `{}` badge exists!**".format(badge_name))
            return
        else:
            guild_linked_badges = db.badgelinks.find_one({"guild_id": str(guild.id)})
            if not guild_linked_badges:
                new_guild = {"guild_id": str(guild.id), "badges": {badge_name: str(level)}}
                db.badgelinks.insert_one(new_guild)
            else:
                guild_linked_badges["badges"][badge_name] = str(level)
                db.badgelinks.update_one(
                    {"guild_id": str(guild.id)},
                    {"$set": {"badges": guild_linked_badges["badges"]}},
                )
            await ctx.send(
                "**The `{}` badge has been linked to level `{}`**".format(badge_name, level)
            )

    @checks.admin_or_permissions(manage_roles=True)
    @badge.command(name="unlink", no_pm=True, pass_context=True)
    async def unlinkbadge(self, ctx, badge_name: str):
        """Delete a role/level association."""
        guild = ctx.message.guild

        guild_linked_badges = db.badgelinks.find_one({"guild_id": str(guild.id)})
        badge_links = guild_linked_badges["badges"]

        if badge_name in badge_links.keys():
            await ctx.send(
                "**Badge/Level association `{}`/`{}` removed.**".format(
                    badge_name, badge_links[badge_name]
                )
            )
            del badge_links[badge_name]
            db.badgelinks.update_one(
                {"guild_id": str(guild.id)}, {"$set": {"badges": badge_links}}
            )
        else:
            await ctx.send("**The `{}` badge is not linked to any levels!**".format(badge_name))

    @checks.mod_or_permissions(manage_roles=True)
    @badge.command(name="listlinks", no_pm=True, pass_context=True)
    async def listbadge(self, ctx):
        """List level/role associations."""
        guild = ctx.message.guild
        user = ctx.message.author

        guild_badges = db.badgelinks.find_one({"guild_id": str(guild.id)})

        em = discord.Embed(description="", colour=user.colour)
        em.set_author(
            name="Current Badge - Level Links for {}".format(guild.name), icon_url=guild.icon_url
        )

        if guild_badges == None or "badges" not in guild_badges or guild_badges["badges"] == {}:
            msg = "None"
        else:
            badges = guild_badges["badges"]
            msg = "**Badge** → Level\n"
            for badge in badges.keys():
                msg += "**• {} →** {}\n".format(badge, badges[badge])

        em.description = msg
        await ctx.send(embed=em)

    @commands.group(pass_context=True)
    async def role(self, ctx):
        """Admin Background Configuration"""
        if ctx.invoked_subcommand is None:

            return

    @checks.mod_or_permissions(manage_roles=True)
    @role.command(name="link", no_pm=True, pass_context=True)
    async def linkrole(self, ctx, role_name: str, level: int, remove_role=None):
        """Associate a role with a level. Removes previous role if given."""
        guild = ctx.message.guild

        role_obj = discord.utils.find(lambda r: r.name == role_name, guild.roles)
        remove_role_obj = discord.utils.find(lambda r: r.name == remove_role, guild.roles)
        if role_obj == None or (remove_role != None and remove_role_obj == None):
            if remove_role == None:
                await ctx.send("**Please make sure the `{}` role exists!**".format(role_name))
            else:
                await ctx.send(
                    "**Please make sure the `{}` and/or `{}` roles exist!**".format(
                        role_name, remove_role
                    )
                )
        else:
            guild_roles = db.roles.find_one({"guild_id": str(guild.id)})
            if not guild_roles:
                new_guild = {
                    "guild_id": str(guild.id),
                    "roles": {role_name: {"level": str(level), "remove_role": remove_role}},
                }
                db.roles.insert_one(new_guild)
            else:
                if role_name not in guild_roles["roles"]:
                    guild_roles["roles"][role_name] = {}

                guild_roles["roles"][role_name]["level"] = str(level)
                guild_roles["roles"][role_name]["remove_role"] = remove_role
                db.roles.update_one(
                    {"guild_id": str(guild.id)}, {"$set": {"roles": guild_roles["roles"]}}
                )

            if remove_role == None:
                await ctx.send(
                    "**The `{}` role has been linked to level `{}`**".format(role_name, level)
                )
            else:
                await ctx.send(
                    "**The `{}` role has been linked to level `{}`. Will also remove `{}` role.**".format(
                        role_name, level, remove_role
                    )
                )

    @checks.mod_or_permissions(manage_roles=True)
    @role.command(name="unlink", no_pm=True, pass_context=True)
    async def unlinkrole(self, ctx, role_name: str):
        """Delete a role/level association."""
        guild = ctx.message.guild

        guild_roles = db.roles.find_one({"guild_id": str(guild.id)})
        roles = guild_roles["roles"]

        if role_name in roles:
            await ctx.send(
                "**Role/Level association `{}`/`{}` removed.**".format(
                    role_name, roles[role_name]["level"]
                )
            )
            del roles[role_name]
            db.roles.update_one({"guild_id": str(guild.id)}, {"$set": {"roles": roles}})
        else:
            await ctx.send("**The `{}` role is not linked to any levels!**".format(role_name))

    @checks.mod_or_permissions(manage_roles=True)
    @role.command(name="listlinks", no_pm=True, pass_context=True)
    async def listrole(self, ctx):
        """List level/role associations."""
        guild = ctx.message.guild
        user = ctx.message.author

        guild_roles = db.roles.find_one({"guild_id": str(guild.id)})

        em = discord.Embed(description="", colour=user.colour)
        em.set_author(
            name="Current Role - Level Links for {}".format(guild.name), icon_url=guild.icon_url
        )

        if guild_roles == None or "roles" not in guild_roles or guild_roles["roles"] == {}:
            msg = "None"
        else:
            roles = guild_roles["roles"]
            msg = "**Role** → Level\n"
            for role in roles:
                if roles[role]["remove_role"] != None:
                    msg += "**• {} →** {} (Removes: {})\n".format(
                        role, roles[role]["level"], roles[role]["remove_role"]
                    )
                else:
                    msg += "**• {} →** {}\n".format(role, roles[role]["level"])

        em.description = msg
        await ctx.send(embed=em)

    @lvladmin.group(name="bg", pass_context=True)
    async def lvladminbg(self, ctx):
        """Admin Background Configuration"""
        if ctx.invoked_subcommand is None or isinstance(ctx.invoked_subcommand, commands.Group):

            return

    @checks.is_owner()
    @lvladminbg.command(no_pm=True)
    async def addprofilebg(self, name: str, url: str):
        """Add a profile background. Proportions: (290px x 290px)"""
        if name in self.backgrounds["profile"].keys():
            await ctx.send("**That profile background name already exists!**")
        elif not await self._valid_image_url(url):
            await ctx.send("**That is not a valid image url!**")
        else:
            self.backgrounds["profile"][name] = url
            fileIO("data/leveler/backgrounds.json", "save", self.backgrounds)
            await ctx.send("**New profile background(`{}`) added.**".format(name))

    @checks.is_owner()
    @lvladminbg.command(no_pm=True)
    async def addrankbg(self, name: str, url: str):
        """Add a rank background. Proportions: (360px x 100px)"""
        if name in self.backgrounds["rank"].keys():
            await ctx.send("**That rank background name already exists!**")
        elif not await self._valid_image_url(url):
            await ctx.send("**That is not a valid image url!**")
        else:
            self.backgrounds["rank"][name] = url
            fileIO("data/leveler/backgrounds.json", "save", self.backgrounds)
            await ctx.send("**New rank background(`{}`) added.**".format(name))

    @checks.is_owner()
    @lvladminbg.command(no_pm=True)
    async def addlevelbg(self, name: str, url: str):
        """Add a level-up background. Proportions: (85px x 105px)"""
        if name in self.backgrounds["levelup"].keys():
            await ctx.send("**That level-up background name already exists!**")
        elif not await self._valid_image_url(url):
            await ctx.send("**That is not a valid image url!**")
        else:
            self.backgrounds["levelup"][name] = url
            fileIO("data/leveler/backgrounds.json", "save", self.backgrounds)
            await ctx.send("**New level-up background(`{}`) added.**".format(name))

    @checks.is_owner()
    @lvladminbg.command(no_pm=True, pass_context=True)
    async def setcustombg(self, ctx, bg_type: str, user_id: str, img_url: str):
        """Set one-time custom background"""
        valid_types = ["profile", "rank", "levelup"]
        type_input = bg_type.lower()

        if type_input not in valid_types:
            await ctx.send("**Please choose a valid type: `profile`, `rank`, `levelup`.")
            return

        # test if valid user_id
        userinfo = db.users.find_one({"user_id": user_id})
        if not userinfo:
            await ctx.send("**That is not a valid user id!**")
            return

        if not await self._valid_image_url(img_url):
            await ctx.send("**That is not a valid image url!**")
            return

        db.users.update_one(
            {"user_id": user_id}, {"$set": {"{}_background".format(type_input): img_url}}
        )
        await ctx.send("**User {} custom {} background set.**".format(user_id, bg_type))

    @checks.is_owner()
    @lvladminbg.command(no_pm=True)
    async def delprofilebg(self, name: str):
        """Delete a profile background."""
        if name in self.backgrounds["profile"].keys():
            del self.backgrounds["profile"][name]
            fileIO("data/leveler/backgrounds.json", "save", self.backgrounds)
            await ctx.send("**The profile background(`{}`) has been deleted.**".format(name))
        else:
            await ctx.send("**That profile background name doesn't exist.**")

    @checks.is_owner()
    @lvladminbg.command(no_pm=True)
    async def delrankbg(self, name: str):
        """Delete a rank background."""
        if name in self.backgrounds["rank"].keys():
            del self.backgrounds["rank"][name]
            fileIO("data/leveler/backgrounds.json", "save", self.backgrounds)
            await ctx.send("**The rank background(`{}`) has been deleted.**".format(name))
        else:
            await ctx.send("**That rank background name doesn't exist.**")

    @checks.is_owner()
    @lvladminbg.command(no_pm=True)
    async def dellevelbg(self, name: str):
        """Delete a level background."""
        if name in self.backgrounds["levelup"].keys():
            del self.backgrounds["levelup"][name]
            fileIO("data/leveler/backgrounds.json", "save", self.backgrounds)
            await ctx.send("**The level-up background(`{}`) has been deleted.**".format(name))
        else:
            await ctx.send("**That level-up background name doesn't exist.**")

    @commands.command(name="backgrounds", pass_context=True, no_pm=True)
    async def disp_backgrounds(self, ctx, type: str = None):
        """Gives a list of backgrounds. [p]backgrounds [profile|rank|levelup]"""
        guild = ctx.message.guild
        user = ctx.message.author
        max_all = 18

        if str(guild.id) in self.settings["disabled_guilds"]:
            await ctx.send("**Leveler commands for this guild are disabled!**")
            return

        em = discord.Embed(description="", colour=user.colour)
        if not type:
            em.set_author(
                name="All Backgrounds for {}".format(self.bot.user.name),
                icon_url=self.bot.user.avatar_url,
            )

            for category in self.backgrounds.keys():
                bg_url = []
                for background_name in sorted(self.backgrounds[category].keys()):
                    bg_url.append(
                        "[{}]({})".format(
                            background_name, self.backgrounds[category][background_name]
                        )
                    )
                max_bg = min(max_all, len(bg_url))
                bgs = ", ".join(bg_url[0:max_bg])
                if len(bg_url) >= max_all:
                    bgs += "..."
                em.add_field(name=category.upper(), value=bgs, inline=False)
            await ctx.send(embed=em)
        else:
            if type.lower() == "profile":
                em.set_author(
                    name="Profile Backgrounds for {}".format(self.bot.user.name),
                    icon_url=self.bot.user.avatar_url,
                )
                bg_key = "profile"
            elif type.lower() == "rank":
                em.set_author(
                    name="Rank Backgrounds for {}".format(self.bot.user.name),
                    icon_url=self.bot.user.avatar_url,
                )
                bg_key = "rank"
            elif type.lower() == "levelup":
                em.set_author(
                    name="Level Up Backgrounds for {}".format(self.bot.user.name),
                    icon_url=self.bot.user.avatar_url,
                )
                bg_key = "levelup"
            else:
                bg_key = None

            if bg_key:
                bg_url = []
                for background_name in sorted(self.backgrounds[bg_key].keys()):
                    bg_url.append(
                        "[{}]({})".format(
                            background_name, self.backgrounds[bg_key][background_name]
                        )
                    )
                bgs = ", ".join(bg_url)

                total_pages = 0
                for page in pagify(bgs, [" "]):
                    total_pages += 1

                counter = 1
                for page in pagify(bgs, [" "]):
                    em.description = page
                    em.set_footer(text="Page {} of {}".format(counter, total_pages))
                    await ctx.send(embed=em)
                    counter += 1
            else:
                await ctx.send("**Invalid Background Type. (profile, rank, levelup)**")

    async def draw_profile(self, user, guild):
        font_thin_file = "data/leveler/fonts/Uni_Sans_Thin.ttf"
        font_heavy_file = "data/leveler/fonts/Uni_Sans_Heavy.ttf"
        font_file = "data/leveler/fonts/SourceSansPro-Regular.ttf"
        font_bold_file = "data/leveler/fonts/SourceSansPro-Semibold.ttf"

        name_fnt = ImageFont.truetype(font_heavy_file, 30)
        name_u_fnt = ImageFont.truetype(font_unicode_file, 30)
        title_fnt = ImageFont.truetype(font_heavy_file, 22)
        title_u_fnt = ImageFont.truetype(font_unicode_file, 23)
        label_fnt = ImageFont.truetype(font_bold_file, 18)
        exp_fnt = ImageFont.truetype(font_bold_file, 13)
        large_fnt = ImageFont.truetype(font_thin_file, 33)
        rep_fnt = ImageFont.truetype(font_heavy_file, 26)
        rep_u_fnt = ImageFont.truetype(font_unicode_file, 30)
        text_fnt = ImageFont.truetype(font_file, 14)
        text_u_fnt = ImageFont.truetype(font_unicode_file, 14)
        symbol_u_fnt = ImageFont.truetype(font_unicode_file, 15)

        def _write_unicode(text, init_x, y, font, unicode_font, fill):
            write_pos = init_x

            for char in text:
                if char.isalnum() or char in string.punctuation or char in string.whitespace:
                    draw.text((write_pos, y), char, font=font, fill=fill)
                    write_pos += font.getsize(char)[0]
                else:
                    draw.text((write_pos, y), u"{}".format(char), font=unicode_font, fill=fill)
                    write_pos += unicode_font.getsize(char)[0]

        # get urls
        userinfo = db.users.find_one({"user_id": str(str(user.id))})
        self._badge_convert_dict(userinfo)
        userinfo = db.users.find_one(
            {"user_id": str(str(user.id))}
        )  ##############################################
        bg_url = userinfo["profile_background"]
        profile_url = user.avatar_url

        # COLORS
        white_color = (240, 240, 240, 255)
        light_color = (160, 160, 160, 255)
        if "rep_color" not in userinfo.keys() or not userinfo["rep_color"]:
            rep_fill = (92, 130, 203, 230)
        else:
            rep_fill = tuple(userinfo["rep_color"])
        # determines badge section color, should be behind the titlebar
        if "badge_col_color" not in userinfo.keys() or not userinfo["badge_col_color"]:
            badge_fill = (128, 151, 165, 230)
        else:
            badge_fill = tuple(userinfo["badge_col_color"])
        if "profile_info_color" in userinfo.keys():
            info_fill = tuple(userinfo["profile_info_color"])
        else:
            info_fill = (30, 30, 30, 220)
        info_fill_tx = (info_fill[0], info_fill[1], info_fill[2], 150)
        if "profile_exp_color" not in userinfo.keys() or not userinfo["profile_exp_color"]:
            exp_fill = (255, 255, 255, 230)
        else:
            exp_fill = tuple(userinfo["profile_exp_color"])
        if badge_fill == (128, 151, 165, 230):
            level_fill = white_color
        else:
            level_fill = self._contrast(exp_fill, rep_fill, badge_fill)

        # create image objects
        bg_image = Image
        profile_image = Image

        async with self.session.get(bg_url) as r:
            image = await r.content.read()
        with open("data/leveler/temp/{}_temp_profile_bg.png".format(str(user.id)), "wb") as f:
            f.write(image)
        try:
            async with self.session.get(profile_url) as r:
                image = await r.content.read()
        except:
            async with self.session.get(default_avatar_url) as r:
                image = await r.content.read()
        with open("data/leveler/temp/{}_temp_profile_profile.png".format(str(user.id)), "wb") as f:
            f.write(image)

        bg_image = Image.open(
            "data/leveler/temp/{}_temp_profile_bg.png".format(str(user.id))
        ).convert("RGBA")
        profile_image = Image.open(
            "data/leveler/temp/{}_temp_profile_profile.png".format(str(user.id))
        ).convert("RGBA")

        # set canvas
        bg_color = (255, 255, 255, 0)
        result = Image.new("RGBA", (340, 390), bg_color)
        process = Image.new("RGBA", (340, 390), bg_color)

        # draw
        draw = ImageDraw.Draw(process)

        # puts in background
        bg_image = bg_image.resize((340, 340), Image.ANTIALIAS)
        bg_image = bg_image.crop((0, 0, 340, 305))
        result.paste(bg_image, (0, 0))

        # draw filter
        draw.rectangle([(0, 0), (340, 340)], fill=(0, 0, 0, 10))

        # draw transparent overlay
        vert_pos = 305
        left_pos = 0
        right_pos = 340
        title_height = 30
        gap = 3

        draw.rectangle([(0, 134), (340, 325)], fill=info_fill_tx)  # general content
        # draw profile circle
        multiplier = 8
        lvl_circle_dia = 116
        circle_left = 14
        circle_top = 48
        raw_length = lvl_circle_dia * multiplier

        # create mask
        mask = Image.new("L", (raw_length, raw_length), 0)
        draw_thumb = ImageDraw.Draw(mask)
        draw_thumb.ellipse((0, 0) + (raw_length, raw_length), fill=255, outline=0)

        # border
        lvl_circle = Image.new("RGBA", (raw_length, raw_length))
        draw_lvl_circle = ImageDraw.Draw(lvl_circle)
        draw_lvl_circle.ellipse(
            [0, 0, raw_length, raw_length], fill=(255, 255, 255, 255), outline=(255, 255, 255, 250)
        )
        # put border
        lvl_circle = lvl_circle.resize((lvl_circle_dia, lvl_circle_dia), Image.ANTIALIAS)
        lvl_bar_mask = mask.resize((lvl_circle_dia, lvl_circle_dia), Image.ANTIALIAS)
        process.paste(lvl_circle, (circle_left, circle_top), lvl_bar_mask)

        # put in profile picture
        total_gap = 6
        border = int(total_gap / 2)
        profile_size = lvl_circle_dia - total_gap
        raw_length = profile_size * multiplier
        output = ImageOps.fit(profile_image, (raw_length, raw_length), centering=(0.5, 0.5))
        output = output.resize((profile_size, profile_size), Image.ANTIALIAS)
        mask = mask.resize((profile_size, profile_size), Image.ANTIALIAS)
        profile_image = profile_image.resize((profile_size, profile_size), Image.ANTIALIAS)
        process.paste(profile_image, (circle_left + border, circle_top + border), mask)

        # write label text
        white_color = (240, 240, 240, 255)
        light_color = (160, 160, 160, 255)
        dark_color = (35, 35, 35, 255)

        head_align = 140
        # determine info text color
        info_text_color = self._contrast(info_fill, white_color, dark_color)
        _write_unicode(
            self._truncate_text(user.name, 22).upper(),
            head_align,
            142,
            name_fnt,
            name_u_fnt,
            info_text_color,
        )  # NAME
        _write_unicode(
            userinfo["title"].upper(), head_align, 170, title_fnt, title_u_fnt, info_text_color
        )

        # draw divider
        draw.rectangle([(0, 323), (340, 324)], fill=(0, 0, 0, 255))  # box
        # draw text box
        draw.rectangle(
            [(0, 324), (340, 390)], fill=(info_fill[0], info_fill[1], info_fill[2], 255)
        )  # box

        # rep_text = "{} REP".format(userinfo["rep"])
        rep_text = "{}".format(userinfo["rep"])
        _write_unicode("❤", 257, 9, rep_fnt, rep_u_fnt, info_text_color)
        draw.text(
            (self._center(278, 340, rep_text, rep_fnt), 10),
            rep_text,
            font=rep_fnt,
            fill=info_text_color,
        )  # Exp Text

        lvl_left = 100
        label_align = 362  # vertical
        draw.text(
            (self._center(0, 140, "    RANK", label_fnt), label_align),
            "    RANK",
            font=label_fnt,
            fill=info_text_color,
        )  # Rank
        draw.text(
            (self._center(0, 340, "    LEVEL", label_fnt), label_align),
            "    LEVEL",
            font=label_fnt,
            fill=info_text_color,
        )  # Exp
        draw.text(
            (self._center(200, 340, "BALANCE", label_fnt), label_align),
            "BALANCE",
            font=label_fnt,
            fill=info_text_color,
        )  # Credits

        if "linux" in platform.system().lower():
            global_symbol = u"\U0001F30E "
            fine_adjust = 1
        else:
            global_symbol = "G."
            fine_adjust = 0

        _write_unicode(
            global_symbol, 36, label_align + 5, label_fnt, symbol_u_fnt, info_text_color
        )  # Symbol
        _write_unicode(
            global_symbol, 134, label_align + 5, label_fnt, symbol_u_fnt, info_text_color
        )  # Symbol

        # userinfo
        global_rank = "#{}".format(await self._find_global_rank(user))
        global_level = "{}".format(self._find_level(userinfo["total_exp"]))
        draw.text(
            (self._center(0, 140, global_rank, large_fnt), label_align - 27),
            global_rank,
            font=large_fnt,
            fill=info_text_color,
        )  # Rank
        draw.text(
            (self._center(0, 340, global_level, large_fnt), label_align - 27),
            global_level,
            font=large_fnt,
            fill=info_text_color,
        )  # Exp
        # draw level bar
        exp_font_color = self._contrast(exp_fill, light_color, dark_color)
        exp_frac = int(userinfo["total_exp"] - self._level_exp(int(global_level)))
        exp_total = self._required_exp(int(global_level) + 1)
        bar_length = int(exp_frac / exp_total * 340)
        draw.rectangle(
            [(0, 305), (340, 323)], fill=(level_fill[0], level_fill[1], level_fill[2], 245)
        )  # level box
        draw.rectangle(
            [(0, 305), (bar_length, 323)], fill=(exp_fill[0], exp_fill[1], exp_fill[2], 255)
        )  # box
        exp_text = "{}/{}".format(exp_frac, exp_total)  # Exp
        draw.text(
            (self._center(0, 340, exp_text, exp_fnt), 305),
            exp_text,
            font=exp_fnt,
            fill=exp_font_color,
        )  # Exp Text

        try:
            credits = await bank.get_balance(user)
        except:
            credits = 0
        credit_txt = "${}".format(credits)
        draw.text(
            (self._center(200, 340, credit_txt, large_fnt), label_align - 27),
            self._truncate_text(credit_txt, 18),
            font=large_fnt,
            fill=info_text_color,
        )  # Credits

        if userinfo["title"] == "":
            offset = 170
        else:
            offset = 195
        margin = 140
        txt_color = self._contrast(info_fill, white_color, dark_color)
        for line in textwrap.wrap(userinfo["info"], width=32):
            # for line in textwrap.wrap('userinfo["info"]', width=200):
            # draw.text((margin, offset), line, font=text_fnt, fill=white_color)
            _write_unicode(line, margin, offset, text_fnt, text_u_fnt, txt_color)
            offset += text_fnt.getsize(line)[1] + 2

        # sort badges
        priority_badges = []

        for badgename in userinfo["badges"].keys():
            badge = userinfo["badges"][badgename]
            priority_num = badge["priority_num"]
            if priority_num != 0 and priority_num != -1:
                priority_badges.append((badge, priority_num))
        sorted_badges = sorted(priority_badges, key=operator.itemgetter(1), reverse=True)

        # TODO: simplify this. it shouldn't be this complicated... sacrifices conciseness for customizability
        if "badge_type" not in self.settings.keys() or self.settings["badge_type"] == "circles":
            # circles require antialiasing
            vert_pos = 172
            right_shift = 0
            left = 9 + right_shift
            right = 52 + right_shift
            size = 38
            total_gap = 4  # /2
            hor_gap = 6
            vert_gap = 6
            border_width = int(total_gap / 2)
            multiplier = 6  # for antialiasing
            raw_length = size * multiplier
            mult = [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1), (0, 2), (1, 2), (2, 2)]
            for num in range(9):
                coord = (
                    left + int(mult[num][0]) * int(hor_gap + size),
                    vert_pos + int(mult[num][1]) * int(vert_gap + size),
                )
                if num < len(sorted_badges[:9]):
                    pair = sorted_badges[num]
                    badge = pair[0]
                    bg_color = badge["bg_img"]
                    border_color = badge["border_color"]
                    # draw mask circle
                    mask = Image.new("L", (raw_length, raw_length), 0)
                    draw_thumb = ImageDraw.Draw(mask)
                    draw_thumb.ellipse((0, 0) + (raw_length, raw_length), fill=255, outline=0)

                    # determine image or color for badge bg
                    if await self._valid_image_url(bg_color):
                        # get image
                        async with self.session.get(bg_color) as r:
                            image = await r.content.read()
                        with open(
                            "data/leveler/temp/{}_temp_badge.png".format(str(user.id)), "wb"
                        ) as f:
                            f.write(image)
                        badge_image = Image.open(
                            "data/leveler/temp/{}_temp_badge.png".format(str(user.id))
                        ).convert("RGBA")
                        badge_image = badge_image.resize((raw_length, raw_length), Image.ANTIALIAS)

                        # structured like this because if border = 0, still leaves outline.
                        if border_color:
                            square = Image.new("RGBA", (raw_length, raw_length), border_color)
                            # put border on ellipse/circle
                            output = ImageOps.fit(
                                square, (raw_length, raw_length), centering=(0.5, 0.5)
                            )
                            output = output.resize((size, size), Image.ANTIALIAS)
                            outer_mask = mask.resize((size, size), Image.ANTIALIAS)
                            process.paste(output, coord, outer_mask)

                            # put on ellipse/circle
                            output = ImageOps.fit(
                                badge_image, (raw_length, raw_length), centering=(0.5, 0.5)
                            )
                            output = output.resize(
                                (size - total_gap, size - total_gap), Image.ANTIALIAS
                            )
                            inner_mask = mask.resize(
                                (size - total_gap, size - total_gap), Image.ANTIALIAS
                            )
                            process.paste(
                                output,
                                (coord[0] + border_width, coord[1] + border_width),
                                inner_mask,
                            )
                        else:
                            # put on ellipse/circle
                            output = ImageOps.fit(
                                badge_image, (raw_length, raw_length), centering=(0.5, 0.5)
                            )
                            output = output.resize((size, size), Image.ANTIALIAS)
                            outer_mask = mask.resize((size, size), Image.ANTIALIAS)
                            process.paste(output, coord, outer_mask)
                else:
                    plus_fill = exp_fill
                    # put on ellipse/circle
                    plus_square = Image.new("RGBA", (raw_length, raw_length))
                    plus_draw = ImageDraw.Draw(plus_square)
                    plus_draw.rectangle(
                        [(0, 0), (raw_length, raw_length)],
                        fill=(info_fill[0], info_fill[1], info_fill[2], 245),
                    )
                    # draw plus signs
                    margin = 60
                    thickness = 40
                    v_left = int(raw_length / 2 - thickness / 2)
                    v_right = v_left + thickness
                    v_top = margin
                    v_bottom = raw_length - margin
                    plus_draw.rectangle(
                        [(v_left, v_top), (v_right, v_bottom)],
                        fill=(plus_fill[0], plus_fill[1], plus_fill[2], 245),
                    )
                    h_left = margin
                    h_right = raw_length - margin
                    h_top = int(raw_length / 2 - thickness / 2)
                    h_bottom = h_top + thickness
                    plus_draw.rectangle(
                        [(h_left, h_top), (h_right, h_bottom)],
                        fill=(plus_fill[0], plus_fill[1], plus_fill[2], 245),
                    )
                    # put border on ellipse/circle
                    output = ImageOps.fit(
                        plus_square, (raw_length, raw_length), centering=(0.5, 0.5)
                    )
                    output = output.resize((size, size), Image.ANTIALIAS)
                    outer_mask = mask.resize((size, size), Image.ANTIALIAS)
                    process.paste(output, coord, outer_mask)

                # attempt to remove badge image
                try:
                    os.remove("data/leveler/temp/{}_temp_badge.png".format(str(user.id)))
                except:
                    pass

        result = Image.alpha_composite(result, process)
        result = self._add_corners(result, 25)
        result.save("data/leveler/temp/{}_profile.png".format(str(user.id)), "PNG", quality=100)

        # remove images
        try:
            os.remove("data/leveler/temp/{}_temp_profile_bg.png".format(str(user.id)))
        except:
            pass
        try:
            os.remove("data/leveler/temp/{}_temp_profile_profile.png".format(str(user.id)))
        except:
            pass

    # returns color that contrasts better in background
    def _contrast(self, bg_color, color1, color2):
        color1_ratio = self._contrast_ratio(bg_color, color1)
        color2_ratio = self._contrast_ratio(bg_color, color2)
        if color1_ratio >= color2_ratio:
            return color1
        else:
            return color2

    def _luminance(self, color):
        # convert to greyscale
        luminance = float((0.2126 * color[0]) + (0.7152 * color[1]) + (0.0722 * color[2]))
        return luminance

    def _contrast_ratio(self, bgcolor, foreground):
        f_lum = float(self._luminance(foreground) + 0.05)
        bg_lum = float(self._luminance(bgcolor) + 0.05)

        if bg_lum > f_lum:
            return bg_lum / f_lum
        else:
            return f_lum / bg_lum

    # returns a string with possibly a nickname
    def _name(self, user, max_length):
        if user.name == user.display_name:
            return user.name
        else:
            return "{} ({})".format(
                user.name,
                self._truncate_text(user.display_name, max_length - len(user.name) - 3),
                max_length,
            )

    async def _add_dropshadow(
        self, image, offset=(4, 4), background=0x000, shadow=0x0F0, border=3, iterations=5
    ):
        totalWidth = image.size[0] + abs(offset[0]) + 2 * border
        totalHeight = image.size[1] + abs(offset[1]) + 2 * border
        back = Image.new(image.mode, (totalWidth, totalHeight), background)

        # Place the shadow, taking into account the offset from the image
        shadowLeft = border + max(offset[0], 0)
        shadowTop = border + max(offset[1], 0)
        back.paste(
            shadow, [shadowLeft, shadowTop, shadowLeft + image.size[0], shadowTop + image.size[1]]
        )

        n = 0
        while n < iterations:
            back = back.filter(ImageFilter.BLUR)
            n += 1

        # Paste the input image onto the shadow backdrop
        imageLeft = border - min(offset[0], 0)
        imageTop = border - min(offset[1], 0)
        back.paste(image, (imageLeft, imageTop))
        return back

    """
    async def draw_rank(self, user, guild):
        # fonts
        name_fnt = ImageFont.truetype(font_bold_file, 22)
        header_u_fnt = ImageFont.truetype(font_unicode_file, 18)
        sub_header_fnt = ImageFont.truetype(font_bold_file, 14)
        badge_fnt = ImageFont.truetype(font_bold_file, 12)
        large_fnt = ImageFont.truetype(font_bold_file, 33)
        level_label_fnt = ImageFont.truetype(font_bold_file, 22)
        general_info_fnt = ImageFont.truetype(font_bold_file, 15)
        general_info_u_fnt = ImageFont.truetype(font_unicode_file, 11)
        credit_fnt = ImageFont.truetype(font_bold_file, 10)

        def _write_unicode(text, init_x, y, font, unicode_font, fill):
            write_pos = init_x

            for char in text:
                if char.isalnum() or char in string.punctuation or char in string.whitespace:
                    draw.text((write_pos, y), char, font=font, fill=fill)
                    write_pos += font.getsize(char)[0]
                else:
                    draw.text((write_pos, y), u"{}".format(char), font=unicode_font, fill=fill)
                    write_pos += unicode_font.getsize(char)[0]

        userinfo = db.users.find_one({'user_id':str(str(user.id))})
        # get urls
        bg_url = userinfo["rank_background"]
        profile_url = user.avatar_url
        guild_icon_url = guild.icon_url

        # create image objects
        bg_image = Image
        profile_image = Image

        async with self.session.get(bg_url) as r:
            image = await r.content.read()
        with open('data/leveler/temp/{}_temp_rank_bg.png'.format(str(user.id)),'wb') as f:
            f.write(image)
        try:
            async with self.session.get(profile_url) as r:
                image = await r.content.read()
        except:
            async with self.session.get(default_avatar_url) as r:
                image = await r.content.read()
        with open('data/leveler/temp/{}_temp_rank_profile.png'.format(str(user.id)),'wb') as f:
            f.write(image)
        try:
            async with self.session.get(guild_icon_url) as r:
                image = await r.content.read()
        except:
            async with self.session.get(default_avatar_url) as r:
                image = await r.content.read()
        with open('data/leveler/temp/{}_temp_guild_icon.png'.format(str(user.id)),'wb') as f:
            f.write(image)

        bg_image = Image.open('data/leveler/temp/{}_temp_rank_bg.png'.format(str(user.id))).convert('RGBA')
        profile_image = Image.open('data/leveler/temp/{}_temp_rank_profile.png'.format(str(user.id))).convert('RGBA')
        guild_image = Image.open('data/leveler/temp/{}_temp_guild_icon.png'.format(str(user.id))).convert('RGBA')

        # set canvas
        width = 360
        height = 100
        bg_color = (255,255,255, 0)
        result = Image.new('RGBA', (width, height), bg_color)
        process = Image.new('RGBA', (width, height), bg_color)

        # puts in background
        bg_image = bg_image.resize((width, height), Image.ANTIALIAS)
        bg_image = bg_image.crop((0,0, width, height))
        result.paste(bg_image, (0,0))

        # draw
        draw = ImageDraw.Draw(process)

        # draw transparent overlay
        vert_pos = 5
        left_pos = 70
        right_pos = width - vert_pos
        title_height = 22
        gap = 3

        draw.rectangle([(left_pos - 20,vert_pos), (right_pos, vert_pos + title_height)], fill=(230,230,230,230)) # title box
        content_top = vert_pos + title_height + gap
        content_bottom = 100 - vert_pos

        if "rank_info_color" in userinfo.keys():
            info_color = tuple(userinfo["rank_info_color"])
            info_color = (info_color[0], info_color[1], info_color[2], 160) # increase transparency
        else:
            info_color = (30, 30 ,30, 160)
        draw.rectangle([(left_pos - 20, content_top), (right_pos, content_bottom)], fill=info_color, outline=(180, 180, 180, 180)) # content box

        # stick in credits if needed
        if bg_url in bg_credits.keys():
            credit_text = " ".join("{}".format(bg_credits[bg_url]))
            draw.text((2, 92), credit_text,  font=credit_fnt, fill=(0,0,0,190))

        # draw level circle
        multiplier = 6
        lvl_circle_dia = 94
        circle_left = 15
        circle_top = int((height- lvl_circle_dia)/2)
        raw_length = lvl_circle_dia * multiplier

        # create mask
        mask = Image.new('L', (raw_length, raw_length), 0)
        draw_thumb = ImageDraw.Draw(mask)
        draw_thumb.ellipse((0, 0) + (raw_length, raw_length), fill = 255, outline = 0)

        # drawing level bar calculate angle
        start_angle = -90 # from top instead of 3oclock
        angle = int(360 * (userinfo["servers"][str(guild.id)]["current_exp"]/self._required_exp(userinfo["servers"][str(guild.id)]["level"]))) + start_angle

        lvl_circle = Image.new("RGBA", (raw_length, raw_length))
        draw_lvl_circle = ImageDraw.Draw(lvl_circle)
        draw_lvl_circle.ellipse([0, 0, raw_length, raw_length], fill=(180, 180, 180, 180), outline = (255, 255, 255, 220))
        # determines exp bar color
        if "rank_exp_color" not in userinfo.keys() or not userinfo["rank_exp_color"]:
            exp_fill = (255, 255, 255, 230)
        else:
            exp_fill = tuple(userinfo["rank_exp_color"])
        draw_lvl_circle.pieslice([0, 0, raw_length, raw_length], start_angle, angle, fill=exp_fill, outline = (255, 255, 255, 230))
        # put on level bar circle
        lvl_circle = lvl_circle.resize((lvl_circle_dia, lvl_circle_dia), Image.ANTIALIAS)
        lvl_bar_mask = mask.resize((lvl_circle_dia, lvl_circle_dia), Image.ANTIALIAS)
        process.paste(lvl_circle, (circle_left, circle_top), lvl_bar_mask)

        # draws mask
        total_gap = 10
        border = int(total_gap/2)
        profile_size = lvl_circle_dia - total_gap
        raw_length = profile_size * multiplier
        # put in profile picture
        output = ImageOps.fit(profile_image, (raw_length, raw_length), centering=(0.5, 0.5))
        output = output.resize((profile_size, profile_size), Image.ANTIALIAS)
        mask = mask.resize((profile_size, profile_size), Image.ANTIALIAS)
        profile_image = profile_image.resize((profile_size, profile_size), Image.ANTIALIAS)
        process.paste(profile_image, (circle_left + border, circle_top + border), mask)

        # draw level box
        level_left = 274
        level_right = right_pos
        draw.rectangle([(level_left, vert_pos), (level_right, vert_pos + title_height)], fill="#AAA") # box
        lvl_text = "LEVEL {}".format(userinfo["servers"][str(guild.id)]["level"])
        draw.text((self._center(level_left, level_right, lvl_text, level_label_fnt), vert_pos + 3), lvl_text,  font=level_label_fnt, fill=(110,110,110,255)) # Level #

        # labels text colors
        white_text = (240,240,240,255)
        dark_text = (35, 35, 35, 230)
        label_text_color = self._contrast(info_color, white_text, dark_text)

        # draw text
        grey_color = (110,110,110,255)
        white_color = (230,230,230,255)

        # put in guild picture
        guild_size = content_bottom - content_top - 10
        guild_border_size = guild_size + 4
        radius = 20
        light_border = (150,150,150,180)
        dark_border = (90,90,90,180)
        border_color = self._contrast(info_color, light_border, dark_border)

        draw_guild_border = Image.new('RGBA', (guild_border_size*multiplier, guild_border_size*multiplier),border_color)
        draw_guild_border = self._add_corners(draw_guild_border, int(radius*multiplier/2))
        draw_guild_border = draw_guild_border.resize((guild_border_size, guild_border_size), Image.ANTIALIAS)
        guild_image = guild_image.resize((guild_size*multiplier, guild_size*multiplier), Image.ANTIALIAS)
        guild_image = self._add_corners(guild_image, int(radius*multiplier/2)-10)
        guild_image = guild_image.resize((guild_size, guild_size), Image.ANTIALIAS)
        process.paste(draw_guild_border, (circle_left + profile_size + 2*border + 8, content_top + 3), draw_guild_border)
        process.paste(guild_image, (circle_left + profile_size + 2*border + 10, content_top + 5), guild_image)

        # name
        left_text_align = 130
        _write_unicode(self._truncate_text(self._name(user, 20), 20), left_text_align - 12, vert_pos + 3, name_fnt, header_u_fnt, grey_color) # Name

        # divider bar
        draw.rectangle([(187, 45), (188, 85)], fill=(160,160,160,220))

        # labels
        label_align = 200
        draw.text((label_align, 38), "guild Rank:", font=general_info_fnt, fill=label_text_color) # guild Rank
        draw.text((label_align, 58), "guild Exp:", font=general_info_fnt, fill=label_text_color) # guild Exp
        draw.text((label_align, 78), "Credits:", font=general_info_fnt, fill=label_text_color) # Credit
        # info
        right_text_align = 290
        rank_txt = "#{}".format(await self._find_guild_rank(user, guild))
        draw.text((right_text_align, 38), self._truncate_text(rank_txt, 12) , font=general_info_fnt, fill=label_text_color) # Rank
        exp_txt = "{}".format(await self._find_guild_exp(user, guild))
        draw.text((right_text_align, 58), self._truncate_text(exp_txt, 12), font=general_info_fnt, fill=label_text_color) # Exp
        try:
            bank = self.bot.get_cog('Economy').bank
            if bank.account_exists(user):
                credits = bank.get_balance(user)
            else:
                credits = 0
        except:
            credits = 0
        credit_txt = "${}".format(credits)
        draw.text((right_text_align, 78), self._truncate_text(credit_txt, 12),  font=general_info_fnt, fill=label_text_color) # Credits

        result = Image.alpha_composite(result, process)
        result = await self._add_dropshadow(result)
        result.save('data/leveler/temp/{}_rank.png'.format(str(user.id)),'PNG', quality=100)
    """

    async def draw_rank(self, user, guild):
        # fonts
        font_thin_file = "data/leveler/fonts/Uni_Sans_Thin.ttf"
        font_heavy_file = "data/leveler/fonts/Uni_Sans_Heavy.ttf"
        font_file = "data/leveler/fonts/SourceSansPro-Regular.ttf"
        font_bold_file = "data/leveler/fonts/SourceSansPro-Semibold.ttf"

        name_fnt = ImageFont.truetype(font_heavy_file, 24)
        name_u_fnt = ImageFont.truetype(font_unicode_file, 24)
        label_fnt = ImageFont.truetype(font_bold_file, 16)
        exp_fnt = ImageFont.truetype(font_bold_file, 9)
        large_fnt = ImageFont.truetype(font_thin_file, 24)
        large_bold_fnt = ImageFont.truetype(font_bold_file, 24)
        symbol_u_fnt = ImageFont.truetype(font_unicode_file, 15)

        def _write_unicode(text, init_x, y, font, unicode_font, fill):
            write_pos = init_x

            for char in text:
                if char.isalnum() or char in string.punctuation or char in string.whitespace:
                    draw.text((write_pos, y), char, font=font, fill=fill)
                    write_pos += font.getsize(char)[0]
                else:
                    draw.text((write_pos, y), u"{}".format(char), font=unicode_font, fill=fill)
                    write_pos += unicode_font.getsize(char)[0]

        userinfo = db.users.find_one({"user_id": str(str(user.id))})
        # get urls
        bg_url = userinfo["rank_background"]
        profile_url = user.avatar_url
        guild_icon_url = guild.icon_url

        # create image objects
        bg_image = Image
        profile_image = Image

        async with self.session.get(bg_url) as r:
            image = await r.content.read()
        with open("data/leveler/temp/test_temp_rank_bg.png".format(str(user.id)), "wb") as f:
            f.write(image)
        try:
            async with self.session.get(profile_url) as r:
                image = await r.content.read()
        except:
            async with self.session.get(default_avatar_url) as r:
                image = await r.content.read()
        with open("data/leveler/temp/test_temp_rank_profile.png".format(str(user.id)), "wb") as f:
            f.write(image)
        try:
            async with self.session.get(guild_icon_url) as r:
                image = await r.content.read()
        except:
            async with self.session.get(default_avatar_url) as r:
                image = await r.content.read()
        with open("data/leveler/temp/test_temp_guild_icon.png".format(str(user.id)), "wb") as f:
            f.write(image)

        bg_image = Image.open(
            "data/leveler/temp/test_temp_rank_bg.png".format(str(user.id))
        ).convert("RGBA")
        profile_image = Image.open(
            "data/leveler/temp/test_temp_rank_profile.png".format(str(user.id))
        ).convert("RGBA")
        guild_image = Image.open(
            "data/leveler/temp/test_temp_guild_icon.png".format(str(user.id))
        ).convert("RGBA")

        # set canvas
        width = 390
        height = 100
        bg_color = (255, 255, 255, 0)
        bg_width = width - 50
        result = Image.new("RGBA", (width, height), bg_color)
        process = Image.new("RGBA", (width, height), bg_color)
        draw = ImageDraw.Draw(process)

        # info section
        info_section = Image.new("RGBA", (bg_width, height), bg_color)
        info_section_process = Image.new("RGBA", (bg_width, height), bg_color)
        draw_info = ImageDraw.Draw(info_section)
        # puts in background
        bg_image = bg_image.resize((width, height), Image.ANTIALIAS)
        bg_image = bg_image.crop((0, 0, width, height))
        info_section.paste(bg_image, (0, 0))

        # draw transparent overlays
        draw_overlay = ImageDraw.Draw(info_section_process)
        draw_overlay.rectangle([(0, 0), (bg_width, 20)], fill=(230, 230, 230, 200))
        draw_overlay.rectangle([(0, 20), (bg_width, 30)], fill=(120, 120, 120, 180))  # Level bar
        exp_frac = int(userinfo["servers"][str(guild.id)]["current_exp"])
        exp_total = self._required_exp(userinfo["servers"][str(guild.id)]["level"])
        exp_width = int(bg_width * (exp_frac / exp_total))
        if "rank_info_color" in userinfo.keys():
            exp_color = tuple(userinfo["rank_info_color"])
            exp_color = (exp_color[0], exp_color[1], exp_color[2], 180)  # increase transparency
        else:
            exp_color = (140, 140, 140, 230)
        draw_overlay.rectangle([(0, 20), (exp_width, 30)], fill=exp_color)  # Exp bar
        draw_overlay.rectangle([(0, 30), (bg_width, 31)], fill=(0, 0, 0, 255))  # Divider
        # draw_overlay.rectangle([(0,35), (bg_width,100)], fill=(230,230,230,0)) # title overlay
        for i in range(0, 70):
            draw_overlay.rectangle(
                [(0, height - i), (bg_width, height - i)], fill=(20, 20, 20, 255 - i * 3)
            )  # title overlay

        # draw corners and finalize
        info_section = Image.alpha_composite(info_section, info_section_process)
        info_section = self._add_corners(info_section, 25)
        process.paste(info_section, (35, 0))

        # draw level circle
        multiplier = 6
        lvl_circle_dia = 100
        circle_left = 0
        circle_top = int((height - lvl_circle_dia) / 2)
        raw_length = lvl_circle_dia * multiplier

        # create mask
        mask = Image.new("L", (raw_length, raw_length), 0)
        draw_thumb = ImageDraw.Draw(mask)
        draw_thumb.ellipse((0, 0) + (raw_length, raw_length), fill=255, outline=0)

        # drawing level border
        lvl_circle = Image.new("RGBA", (raw_length, raw_length))
        draw_lvl_circle = ImageDraw.Draw(lvl_circle)
        draw_lvl_circle.ellipse([0, 0, raw_length, raw_length], fill=(250, 250, 250, 250))
        # determines exp bar color
        """
        if "rank_exp_color" not in userinfo.keys() or not userinfo["rank_exp_color"]:
            exp_fill = (255, 255, 255, 230)
        else:
            exp_fill = tuple(userinfo["rank_exp_color"])"""
        exp_fill = (255, 255, 255, 230)

        # put on profile circle background
        lvl_circle = lvl_circle.resize((lvl_circle_dia, lvl_circle_dia), Image.ANTIALIAS)
        lvl_bar_mask = mask.resize((lvl_circle_dia, lvl_circle_dia), Image.ANTIALIAS)
        process.paste(lvl_circle, (circle_left, circle_top), lvl_bar_mask)

        # draws mask
        total_gap = 6
        border = int(total_gap / 2)
        profile_size = lvl_circle_dia - total_gap
        raw_length = profile_size * multiplier
        # put in profile picture
        output = ImageOps.fit(profile_image, (raw_length, raw_length), centering=(0.5, 0.5))
        output = output.resize((profile_size, profile_size), Image.ANTIALIAS)
        mask = mask.resize((profile_size, profile_size), Image.ANTIALIAS)
        profile_image = profile_image.resize((profile_size, profile_size), Image.ANTIALIAS)
        process.paste(profile_image, (circle_left + border, circle_top + border), mask)

        # draw text
        grey_color = (100, 100, 100, 255)
        white_color = (220, 220, 220, 255)

        # name
        left_text_align = 130
        name_color = 0
        _write_unicode(
            self._truncate_text(self._name(user, 20), 20), 100, 0, name_fnt, name_u_fnt, grey_color
        )  # Name

        # labels
        v_label_align = 75
        info_text_color = white_color
        draw.text(
            (self._center(100, 200, "  RANK", label_fnt), v_label_align),
            "  RANK",
            font=label_fnt,
            fill=info_text_color,
        )  # Rank
        draw.text(
            (self._center(100, 360, "  LEVEL", label_fnt), v_label_align),
            "  LEVEL",
            font=label_fnt,
            fill=info_text_color,
        )  # Rank
        draw.text(
            (self._center(260, 360, "BALANCE", label_fnt), v_label_align),
            "BALANCE",
            font=label_fnt,
            fill=info_text_color,
        )  # Rank
        local_symbol = u"\U0001F3E0 "
        if "linux" in platform.system().lower():
            local_symbol = u"\U0001F3E0 "
        else:
            local_symbol = "S. "
        _write_unicode(
            local_symbol, 117, v_label_align + 4, label_fnt, symbol_u_fnt, info_text_color
        )  # Symbol
        _write_unicode(
            local_symbol, 195, v_label_align + 4, label_fnt, symbol_u_fnt, info_text_color
        )  # Symbol

        # userinfo
        guild_rank = "#{}".format(await self._find_guild_rank(user, guild))
        draw.text(
            (self._center(100, 200, guild_rank, large_fnt), v_label_align - 30),
            guild_rank,
            font=large_fnt,
            fill=info_text_color,
        )  # Rank
        level_text = "{}".format(userinfo["servers"][str(guild.id)]["level"])
        draw.text(
            (self._center(95, 360, level_text, large_fnt), v_label_align - 30),
            level_text,
            font=large_fnt,
            fill=info_text_color,
        )  # Level
        try:
            credits = await bank.get_balance(user)
        except:
            credits = 0
        credit_txt = "${}".format(credits)
        draw.text(
            (self._center(260, 360, credit_txt, large_fnt), v_label_align - 30),
            credit_txt,
            font=large_fnt,
            fill=info_text_color,
        )  # Balance
        exp_text = "{}/{}".format(exp_frac, exp_total)
        draw.text(
            (self._center(80, 360, exp_text, exp_fnt), 19),
            exp_text,
            font=exp_fnt,
            fill=info_text_color,
        )  # Rank

        result = Image.alpha_composite(result, process)
        result.save("data/leveler/temp/{}_rank.png".format(str(user.id)), "PNG", quality=100)

    def _add_corners(self, im, rad, multiplier=6):
        raw_length = rad * 2 * multiplier
        circle = Image.new("L", (raw_length, raw_length), 0)
        draw = ImageDraw.Draw(circle)
        draw.ellipse((0, 0, raw_length, raw_length), fill=255)
        circle = circle.resize((rad * 2, rad * 2), Image.ANTIALIAS)

        alpha = Image.new("L", im.size, 255)
        w, h = im.size
        alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
        alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
        alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
        alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))
        im.putalpha(alpha)
        return im

    """
    async def draw_levelup(self, user, guild):
        userinfo = db.users.find_one({'user_id':str(str(user.id))})
        # get urls
        bg_url = userinfo["levelup_background"]
        profile_url = user.avatar_url

        # create image objects
        bg_image = Image
        profile_image = Image

        async with self.session.get(bg_url) as r:
            image = await r.content.read()
        with open('data/leveler/temp/{}_temp_level_bg.png'.format(str(user.id)),'wb') as f:
            f.write(image)
        try:
            async with self.session.get(profile_url) as r:
                image = await r.content.read()
        except:
            async with self.session.get(default_avatar_url) as r:
                image = await r.content.read()
        with open('data/leveler/temp/{}_temp_level_profile.png'.format(str(user.id)),'wb') as f:
            f.write(image)

        bg_image = Image.open('data/leveler/temp/{}_temp_level_bg.png'.format(str(user.id))).convert('RGBA')
        profile_image = Image.open('data/leveler/temp/{}_temp_level_profile.png'.format(str(user.id))).convert('RGBA')

        # set canvas
        width = 175
        height = 65
        bg_color = (255,255,255, 0)
        result = Image.new('RGBA', (width, height), bg_color)
        process = Image.new('RGBA', (width, height), bg_color)

        # draw
        draw = ImageDraw.Draw(process)

        # puts in background
        bg_image = bg_image.resize((width, height), Image.ANTIALIAS)
        bg_image = bg_image.crop((0,0, width, height))
        result.paste(bg_image, (0,0))

        # draw transparent overlay
        if "levelup_info_color" in userinfo.keys():
            info_color = tuple(userinfo["levelup_info_color"])
            info_color = (info_color[0], info_color[1], info_color[2], 150) # increase transparency
        else:
            info_color = (30, 30 ,30, 150)
        draw.rectangle([(38, 5), (170, 60)], fill=info_color) # info portion

        # draw level circle
        multiplier = 6
        lvl_circle_dia = 60
        circle_left = 4
        circle_top = int((height- lvl_circle_dia)/2)
        raw_length = lvl_circle_dia * multiplier

        # create mask
        mask = Image.new('L', (raw_length, raw_length), 0)
        draw_thumb = ImageDraw.Draw(mask)
        draw_thumb.ellipse((0, 0) + (raw_length, raw_length), fill = 255, outline = 0)

        # drawing level bar calculate angle
        start_angle = -90 # from top instead of 3oclock

        lvl_circle = Image.new("RGBA", (raw_length, raw_length))
        draw_lvl_circle = ImageDraw.Draw(lvl_circle)
        draw_lvl_circle.ellipse([0, 0, raw_length, raw_length], fill=(255, 255, 255, 220), outline = (255, 255, 255, 220))

        # put on level bar circle
        lvl_circle = lvl_circle.resize((lvl_circle_dia, lvl_circle_dia), Image.ANTIALIAS)
        lvl_bar_mask = mask.resize((lvl_circle_dia, lvl_circle_dia), Image.ANTIALIAS)
        process.paste(lvl_circle, (circle_left, circle_top), lvl_bar_mask)

        # draws mask
        total_gap = 6
        border = int(total_gap/2)
        profile_size = lvl_circle_dia - total_gap
        raw_length = profile_size * multiplier
        # put in profile picture
        output = ImageOps.fit(profile_image, (raw_length, raw_length), centering=(0.5, 0.5))
        output = output.resize((profile_size, profile_size), Image.ANTIALIAS)
        mask = mask.resize((profile_size, profile_size), Image.ANTIALIAS)
        profile_image = profile_image.resize((profile_size, profile_size), Image.ANTIALIAS)
        process.paste(profile_image, (circle_left + border, circle_top + border), mask)

        # fonts
        level_fnt2 = ImageFont.truetype('data/leveler/fonts/font_bold.ttf', 19)
        level_fnt = ImageFont.truetype('data/leveler/fonts/font_bold.ttf', 26)

        # write label text
        white_text = (240,240,240,255)
        dark_text = (35, 35, 35, 230)
        level_up_text = self._contrast(info_color, white_text, dark_text)
        lvl_text = "LEVEL {}".format(userinfo["servers"][str(guild.id)]["level"])
        draw.text((self._center(50, 170, lvl_text, level_fnt), 22), lvl_text, font=level_fnt, fill=level_up_text) # Level Number

        result = Image.alpha_composite(result, process)
        result = await self._add_dropshadow(result)
        filename = 'data/leveler/temp/{}_level.png'.format(str(user.id))
        result.save(filename,'PNG', quality=100)"""

    async def draw_levelup(self, user, guild):
        # fonts
        font_thin_file = "data/leveler/fonts/Uni_Sans_Thin.ttf"
        level_fnt = ImageFont.truetype(font_thin_file, 23)

        userinfo = db.users.find_one({"user_id": str(str(user.id))})

        # get urls
        bg_url = userinfo["levelup_background"]
        profile_url = user.avatar_url

        # create image objects
        bg_image = Image
        profile_image = Image

        async with self.session.get(bg_url) as r:
            image = await r.content.read()
        with open("data/leveler/temp/{}_temp_level_bg.png".format(str(user.id)), "wb") as f:
            f.write(image)
        try:
            async with self.session.get(profile_url) as r:
                image = await r.content.read()
        except:
            async with self.session.get(default_avatar_url) as r:
                image = await r.content.read()
        with open("data/leveler/temp/{}_temp_level_profile.png".format(str(user.id)), "wb") as f:
            f.write(image)

        bg_image = Image.open(
            "data/leveler/temp/{}_temp_level_bg.png".format(str(user.id))
        ).convert("RGBA")
        profile_image = Image.open(
            "data/leveler/temp/{}_temp_level_profile.png".format(str(user.id))
        ).convert("RGBA")

        # set canvas
        width = 176
        height = 67
        bg_color = (255, 255, 255, 0)
        result = Image.new("RGBA", (width, height), bg_color)
        process = Image.new("RGBA", (width, height), bg_color)
        draw = ImageDraw.Draw(process)

        # puts in background
        bg_image = bg_image.resize((width, height), Image.ANTIALIAS)
        bg_image = bg_image.crop((0, 0, width, height))
        result.paste(bg_image, (0, 0))

        # info section
        lvl_circle_dia = 60
        total_gap = 2
        border = int(total_gap / 2)
        info_section = Image.new("RGBA", (165, 55), (230, 230, 230, 20))
        info_section = self._add_corners(info_section, int(lvl_circle_dia / 2))
        process.paste(info_section, (border, border))

        # draw transparent overlay
        if "levelup_info_color" in userinfo.keys():
            info_color = tuple(userinfo["levelup_info_color"])
            info_color = (
                info_color[0],
                info_color[1],
                info_color[2],
                150,
            )  # increase transparency
        else:
            info_color = (30, 30, 30, 150)

        for i in range(0, height):
            draw.rectangle(
                [(0, height - i), (width, height - i)],
                fill=(info_color[0], info_color[1], info_color[2], 255 - i * 3),
            )  # title overlay

        # draw circle
        multiplier = 6
        circle_left = 4
        circle_top = int((height - lvl_circle_dia) / 2)
        raw_length = lvl_circle_dia * multiplier
        # create mask
        mask = Image.new("L", (raw_length, raw_length), 0)
        draw_thumb = ImageDraw.Draw(mask)
        draw_thumb.ellipse((0, 0) + (raw_length, raw_length), fill=255, outline=0)

        # border
        lvl_circle = Image.new("RGBA", (raw_length, raw_length))
        draw_lvl_circle = ImageDraw.Draw(lvl_circle)
        draw_lvl_circle.ellipse([0, 0, raw_length, raw_length], fill=(250, 250, 250, 180))
        lvl_circle = lvl_circle.resize((lvl_circle_dia, lvl_circle_dia), Image.ANTIALIAS)
        lvl_bar_mask = mask.resize((lvl_circle_dia, lvl_circle_dia), Image.ANTIALIAS)
        process.paste(lvl_circle, (circle_left, circle_top), lvl_bar_mask)

        profile_size = lvl_circle_dia - total_gap
        raw_length = profile_size * multiplier
        # put in profile picture
        output = ImageOps.fit(profile_image, (raw_length, raw_length), centering=(0.5, 0.5))
        output = output.resize((profile_size, profile_size), Image.ANTIALIAS)
        mask = mask.resize((profile_size, profile_size), Image.ANTIALIAS)
        profile_image = profile_image.resize((profile_size, profile_size), Image.ANTIALIAS)
        process.paste(profile_image, (circle_left + border, circle_top + border), mask)

        # write label text
        white_text = (250, 250, 250, 255)
        dark_text = (35, 35, 35, 230)
        level_up_text = self._contrast(info_color, white_text, dark_text)
        lvl_text = "LEVEL {}".format(userinfo["servers"][str(guild.id)]["level"])
        draw.text(
            (self._center(60, 170, lvl_text, level_fnt), 23),
            lvl_text,
            font=level_fnt,
            fill=level_up_text,
        )  # Level Number

        result = Image.alpha_composite(result, process)
        result = self._add_corners(result, int(height / 2))
        filename = "data/leveler/temp/{}_level.png".format(str(user.id))
        result.save(filename, "PNG", quality=100)

    async def _handle_on_message(self, message):
        # try:
        text = message.content
        channel = message.channel
        guild = message.guild
        user = message.author
        # creates user if doesn't exist, bots are not logged.
        await self._create_user(user, guild)
        curr_time = time.time()
        userinfo = db.users.find_one({"user_id": str(str(user.id))})

        if not guild or str(guild.id) in self.settings["disabled_guilds"]:
            return
        if user.bot:
            return

        # check if chat_block exists
        if "chat_block" not in userinfo:
            userinfo["chat_block"] = 0

        if float(curr_time) - float(userinfo["chat_block"]) >= 120 and not any(
            text.startswith(x) for x in prefix
        ):
            await self._process_exp(message, userinfo, random.randint(15, 20))
            await self._give_chat_credit(user, guild)
        # except AttributeError as e:
        # pass

    async def _process_exp(self, message, userinfo, exp: int):
        guild = message.author.guild
        channel = message.channel
        user = message.author

        # add to total exp
        try:
            required = self._required_exp(userinfo["servers"][str(guild.id)]["level"])
            db.users.update_one(
                {"user_id": str(str(user.id))},
                {"$set": {"total_exp": userinfo["total_exp"] + exp}},
            )
        except:
            pass
        print(userinfo["total_exp"] + exp)
        if userinfo["servers"][str(guild.id)]["current_exp"] + exp >= required:
            userinfo["servers"][str(guild.id)]["level"] += 1
            db.users.update_one(
                {"user_id": str(str(user.id))},
                {
                    "$set": {
                        "servers.{}.level".format(str(guild.id)): userinfo["servers"][
                            str(guild.id)
                        ]["level"],
                        "servers.{}.current_exp".format(str(guild.id)): userinfo["servers"][
                            str(guild.id)
                        ]["current_exp"]
                        + exp
                        - required,
                        "chat_block": time.time(),
                    }
                },
            )
            await self._handle_levelup(user, userinfo, guild, channel)
        else:
            db.users.update_one(
                {"user_id": str(str(user.id))},
                {
                    "$set": {
                        "servers.{}.current_exp".format(str(guild.id)): userinfo["servers"][
                            str(guild.id)
                        ]["current_exp"]
                        + exp,
                        "chat_block": time.time(),
                    }
                },
            )

    async def _handle_levelup(self, user, userinfo, guild, channel):
        if not isinstance(self.settings["lvl_msg"], list):
            self.settings["lvl_msg"] = []
            fileIO("data/leveler/settings.json", "save", self.settings)
        guild_identifier = ""  # super hacky
        name = self._is_mention(user)  # also super hacky
        new_level = str(userinfo["servers"][str(guild.id)]["level"])
        if str(guild.id) in self.settings["lvl_msg"]:  # if lvl msg is enabled
            # channel lock implementation
            if (
                "lvl_msg_lock" in self.settings.keys()
                and str(guild.id) in self.settings["lvl_msg_lock"].keys()
            ):
                channel_id = self.settings["lvl_msg_lock"][str(guild.id)]
                channel = find(lambda m: m.id == channel_id, guild.channels)

            # private message takes precedent, of course
            if (
                "private_lvl_msg" in self.settings
                and str(guild.id) in self.settings["private_lvl_msg"]
            ):
                guild_identifier = " on {}".format(guild.name)
                channel = user
                name = "You"

            if "text_only" in self.settings and str(guild.id) in self.settings["text_only"]:

                em = discord.Embed(
                    description="**{} just gained a level{}! (LEVEL {})**".format(
                        name, guild_identifier, new_level
                    ),
                    colour=user.colour,
                )
                await channel.send("", embed=em)
            else:
                await self.draw_levelup(user, guild)

                await channel.send(
                    "**{} just gained a level{}!**".format(name, guild_identifier),
                    file=discord.File("data/leveler/temp/{}_level.png".format(str(user.id))),
                )

        # add to appropriate role if necessary
        try:
            guild_roles = db.roles.find_one({"guild_id": str(guild.id)})
            if guild_roles != None:
                for role in guild_roles["roles"].keys():
                    if int(guild_roles["roles"][role]["level"]) == int(new_level):
                        role_obj = discord.utils.find(lambda r: r.name == role, guild.roles)
                        await user.add_roles(role_obj)

                        if guild_roles["roles"][role]["remove_role"] != None:
                            remove_role_obj = discord.utils.find(
                                lambda r: r.name == guild_roles["roles"][role]["remove_role"],
                                guild.roles,
                            )
                            if remove_role_obj != None:
                                await user.remove_roles(remove_role_obj)
        except:
            await channel.send("Role was not set. Missing Permissions!")

        # add appropriate badge if necessary
        try:
            guild_linked_badges = db.badgelinks.find_one({"guild_id": str(guild.id)})
            if guild_linked_badges != None:
                for badge_name in guild_linked_badges["badges"]:
                    if int(guild_linked_badges["badges"][badge_name]) == int(new_level):
                        guild_badges = db.badges.find_one({"guild_id": str(guild.id)})
                        if guild_badges != None and badge_name in guild_badges["badges"].keys():
                            userinfo_db = db.users.find_one({"user_id": str(str(user.id))})
                            new_badge_name = "{}_{}".format(badge_name, str(guild.id))
                            userinfo_db["badges"][new_badge_name] = guild_badges["badges"][
                                badge_name
                            ]
                            db.users.update_one(
                                {"user_id": str(str(user.id))},
                                {"$set": {"badges": userinfo_db["badges"]}},
                            )
        except:
            await channel.send("Error. Badge was not given!")

    async def _find_guild_rank(self, user, guild):
        targetid = str(user.id)
        users = []

        for userinfo in db.users.find({}):
            try:
                guild_exp = 0
                userid = userinfo["user_id"]
                for i in range(userinfo["servers"][str(guild.id)]["level"]):
                    guild_exp += self._required_exp(i)
                guild_exp += userinfo["servers"][str(guild.id)]["current_exp"]
                users.append((str(userid), guild_exp))
            except:
                pass

        sorted_list = sorted(users, key=operator.itemgetter(1), reverse=True)

        rank = 1
        for a_user in sorted_list:
            if a_user[0] == targetid:
                return rank
            rank += 1

    async def _find_guild_rep_rank(self, user, guild):
        targetid = str(user.id)
        users = []
        for userinfo in db.users.find({}):
            userid = userinfo["user_id"]
            if "servers" in userinfo and str(guild.id) in userinfo["servers"]:
                users.append((userinfo["user_id"], userinfo["rep"]))

        sorted_list = sorted(users, key=operator.itemgetter(1), reverse=True)

        rank = 1
        for a_user in sorted_list:
            if a_user[0] == targetid:
                return rank
            rank += 1

    async def _find_guild_level_rank(self, user, guild):
        targetid = str(user.id)
        users = []
        for userinfo in db.users.find({}):
            userid = userinfo["user_id"]
            if "servers" in userinfo and str(guild.id) in userinfo["servers"]:
                users.append((userinfo["user_id"], userinfo["servers"][str(guild.id)]["level"]))
            sorted_list = sorted(users, key=operator.itemgetter(1), reverse=True)

            rank = 1
            for a_user in sorted_list:
                if a_user[0] == targetid:
                    return rank
                rank += 1

    async def _find_guild_exp(self, user, guild):
        guild_exp = 0
        userinfo = db.users.find_one({"user_id": str(str(user.id))})

        try:
            for i in range(userinfo["servers"][str(guild.id)]["level"]):
                guild_exp += self._required_exp(i)
            guild_exp += userinfo["servers"][str(guild.id)]["current_exp"]
            return guild_exp
        except:
            return guild_exp

    async def _find_global_rank(self, user):
        users = []

        for userinfo in db.users.find({}):
            try:
                userid = userinfo["user_id"]
                users.append((str(userid), userinfo["total_exp"]))
            except KeyError:
                pass
        sorted_list = sorted(users, key=operator.itemgetter(1), reverse=True)

        rank = 1
        for stats in sorted_list:
            if stats[0] == str(user.id):
                return rank
            rank += 1

    async def _find_global_rep_rank(self, user):
        users = []

        for userinfo in db.users.find({}):
            try:
                userid = userinfo["user_id"]
                users.append((str(userid), userinfo["rep"]))
            except KeyError:
                pass
        sorted_list = sorted(users, key=operator.itemgetter(1), reverse=True)

        rank = 1
        for stats in sorted_list:
            if stats[0] == str(user.id):
                return rank
            rank += 1

    # handles user creation, adding new guild, blocking
    async def _create_user(self, user, guild):
        try:
            userinfo = db.users.find_one({"user_id": str(str(user.id))})
            if not userinfo:
                new_account = {
                    "user_id": str(user.id),
                    "username": user.name,
                    "servers": {},
                    "total_exp": 0,
                    "profile_background": self.backgrounds["profile"]["default"],
                    "rank_background": self.backgrounds["rank"]["default"],
                    "levelup_background": self.backgrounds["levelup"]["default"],
                    "title": "",
                    "info": "I am a mysterious person.",
                    "rep": 0,
                    "badges": {},
                    "active_badges": {},
                    "rep_color": [],
                    "badge_col_color": [],
                    "rep_block": 0,
                    "chat_block": 0,
                    "profile_block": 0,
                    "rank_block": 0,
                }
                db.users.insert_one(new_account)

            userinfo = db.users.find_one({"user_id": str(str(user.id))})

            if "username" not in userinfo or userinfo["username"] != user.name:
                db.users.update_one(
                    {"user_id": str(str(user.id))}, {"$set": {"username": user.name}}, upsert=True
                )

            if "servers" not in userinfo or str(guild.id) not in userinfo["servers"]:
                db.users.update_one(
                    {"user_id": str(str(user.id))},
                    {
                        "$set": {
                            "servers.{}.level".format(str(guild.id)): 0,
                            "servers.{}.current_exp".format(str(guild.id)): 0,
                        }
                    },
                    upsert=True,
                )
        except AttributeError as e:
            pass

    def _truncate_text(self, text, max_length):
        if len(text) > max_length:
            if text.strip("$").isdigit():
                text = int(text.strip("$"))
                return "${:.2E}".format(text)
            return text[: max_length - 3] + "..."
        return text

    # finds the the pixel to center the text
    def _center(self, start, end, text, font):
        dist = end - start
        width = font.getsize(text)[0]
        start_pos = start + ((dist - width) / 2)
        return int(start_pos)

    # calculates required exp for next level
    def _required_exp(self, level: int):
        if level < 0:
            return 0
        return 139 * level + 65

    def _level_exp(self, level: int):
        return level * 65 + 139 * level * (level - 1) // 2

    def _find_level(self, total_exp):
        # this is specific to the function above
        return int((1 / 278) * (9 + math.sqrt(81 + 1112 * (total_exp))))


# ------------------------------ setup ----------------------------------------
def check_folders():
    if not os.path.exists("data/leveler"):
        print("Creating data/leveler folder...")
        os.makedirs("data/leveler")

    if not os.path.exists("data/leveler/temp"):
        print("Creating data/leveler/temp folder...")
        os.makedirs("data/leveler/temp")


def transfer_info():
    try:
        users = fileIO("data/leveler/users.json", "load")
        for user_id in users:
            os.makedirs("data/leveler/users/{}".format(user_id))
            # create info.json
            f = "data/leveler/users/{}/info.json".format(user_id)
            if not fileIO(f, "check"):
                fileIO(f, "save", users[user_id])
    except:
        pass


def check_files():
    default = {
        "bg_price": 0,
        "lvl_msg": [],  # enabled lvl msg guilds
        "disabled_guilds": [],
        "badge_type": "circles",
        "mention": True,
        "text_only": [],
        "guild_roles": {},
        "rep_cooldown": 43200,
        "chat_cooldown": 120,
    }

    settings_path = "data/leveler/settings.json"
    if not os.path.isfile(settings_path):
        print("Creating default leveler settings.json...")
        fileIO(settings_path, "save", default)

    bgs = {
        "profile": {
            "alice": "http://i.imgur.com/MUSuMao.png",
            "bluestairs": "http://i.imgur.com/EjuvxjT.png",
            "lamp": "http://i.imgur.com/0nQSmKX.jpg",
            "coastline": "http://i.imgur.com/XzUtY47.jpg",
            "redblack": "http://i.imgur.com/74J2zZn.jpg",
            "default": "http://i.imgur.com/8T1FUP5.jpg",
            "iceberg": "http://i.imgur.com/8KowiMh.png",
            "miraiglasses": "http://i.imgur.com/2Ak5VG3.png",
            "miraikuriyama": "http://i.imgur.com/jQ4s4jj.png",
            "mountaindawn": "http://i.imgur.com/kJ1yYY6.jpg",
            "waterlilies": "http://i.imgur.com/qwdcJjI.jpg",
            "greenery": "http://i.imgur.com/70ZH6LX.png",
        },
        "rank": {
            "aurora": "http://i.imgur.com/gVSbmYj.jpg",
            "default": "http://i.imgur.com/SorwIrc.jpg",
            "nebula": "http://i.imgur.com/V5zSCmO.jpg",
            "mountain": "http://i.imgur.com/qYqEUYp.jpg",
            "abstract": "http://i.imgur.com/70ZH6LX.png",
            "city": "http://i.imgur.com/yr2cUM9.jpg",
        },
        "levelup": {"default": "http://i.imgur.com/eEFfKqa.jpg"},
    }

    bgs_path = "data/leveler/backgrounds.json"
    if not os.path.isfile(bgs_path):
        print("Creating default leveler backgrounds.json...")
        fileIO(bgs_path, "save", bgs)

    f = "data/leveler/badges.json"
    if not fileIO(f, "check"):
        print("Creating badges.json...")
        fileIO(f, "save", {})


def setup(bot):
    check_folders()
    check_files()
    n = Leveler(bot)
    bot.add_listener(n._handle_on_message, "on_message")
    bot.add_cog(n)
