from .serverstatus import SteamReminder


def setup(bot):
	bot.add_cog(SteamReminder(bot))
