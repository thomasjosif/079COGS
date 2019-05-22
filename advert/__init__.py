from .advert import AdvertCog


def setup(bot):
    bot.add_cog(AdvertCog(bot))
