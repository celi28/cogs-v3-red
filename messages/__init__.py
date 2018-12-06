from .message import Messages


def setup(bot):
    bot.add_cog(Messages(bot))
