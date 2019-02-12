from .suggestioncounter import SuggestionCounterCog

def setup(bot):
    bot.add_cog(SuggestionCounterCog(bot))
    