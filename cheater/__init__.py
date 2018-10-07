"""SCP SL Cheater Report cog."""

from .cheater import Cheater

def setup(bot):
    """Load Report."""
    bot.add_cog(Cheater(bot))
