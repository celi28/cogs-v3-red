from .validation import Validation


def setup(bot):
    bot.add_cog(Validation(bot))
