from .vote import Votes


def setup(bot):
    bot.add_cog(Votes(bot))
