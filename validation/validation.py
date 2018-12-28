import asyncio
import datetime as dt
import json

import discord
from redbot.core import Config, checks, commands, utils


class Abort(Exception):
    pass


class Validation(commands.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=20181201)
        default_guild = {
            "entrance_channel": None,
            "archive_channel": None,
            "welcome_channel": None,
            "mod_channel": None,
            "message_validation": None,
            "message_welcome": None,
            "setup_role": None,
            "optional_roles": {},
            "time_before_kick": {"days": 1},
            "optionnal_roles_description": {}
        }
        self.config.register_guild(**default_guild)
        self.background_task = self.bot.loop.create_task(self._daemon())

    def __unload(self):
        if self.background_task:
            self.background_task.cancel()

    async def _daemon(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            guilds = self.bot.guilds
            for guild in guilds:

                time_limit = dt.datetime.utcnow() - dt.timedelta(**(await self.config.guild(guild).time_before_kick()))
                channel = self.bot.get_channel(await self.config.guild(guild).entrance_channel())
                members = channel.members
                for member in members:
                    # Si il a un rôle, alors c'est un pas un nouveau
                    if len(member.roles) > 1:
                        continue
                    # Si il est arrivé depuis - 24h alors on kick pas
                    if member.joined_at > time_limit:
                        continue
                    # Si il a posté depuis -24h alors on kick pas
                    active_bool = False
                    messages = await channel.history(after=time_limit).flatten()
                    for message in messages:
                        if message.author == member:
                            active_bool = True
                            break
                    if active_bool:
                        continue

                    # Sinon, ben on le kick
                    # Mais first on clean les messages qui se rapportes a lui
                    msg = await self._find_related_msg(member)
                    await channel.delete_messages(msg)
                    await member.kick(reason="Autokick for non validation")
                    mod_message = "{} kick automatique pour non validation".format(
                        member)
                    await self.bot.get_channel(await self.config.guild(guild).mod_channel()).send(mod_message)

            await asyncio.sleep(600)

    async def on_member_join(self, member):
        keywords = {"SERVER": member.guild, "MEMBER": member.mention}
        message = (await self.config.guild(member.guild).message_validation()).format(**keywords)
        message += " ({})".format((dt.datetime.now() - member.created_at).days)
        await self.bot.get_channel(await self.config.guild(member.guild).entrance_channel()).send(message)

    async def on_member_remove(self, member):
        if len(member.roles) > 1:  # The member always have @everyone role. So 2 not 1
            return
        messages = await self._find_related_msg(member)
        if len(messages) > 0:
            if len([m for m in messages if m.author == member]) > 0:
                await self._backup_msg(messages, "Kick/Leave", member, self.bot.user)
            await self.bot.get_channel(await self.config.guild(member.guild).entrance_channel()).delete_messages(
                messages)

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions(administrator=True)
    async def val_setup(self, ctx):
        pass

    @val_setup.group()
    async def channel(self, ctx):
        pass

    @val_setup.group()
    async def message(self, ctx):
        pass

    @val_setup.group()
    async def role(self, ctx):
        pass

    @channel.command(name="entrance", aliases=['entry'])
    async def val_setup_channel_entry(self, ctx, channel: discord.TextChannel):
        """Setup the entrance channel."""
        await self.config.guild(ctx.guild).entrance_channel.set(channel.id)

        message = "Entrance channel configured on {}".format(channel.mention)
        await ctx.send(message)

    @channel.command(name="archive")
    async def val_setup_channel_archive(self, ctx, channel: discord.TextChannel):
        """Setup the archive channel."""
        await self.config.guild(ctx.guild).archive_channel.set(channel.id)

        message = "Archive channel configured on {}".format(channel.mention)
        await ctx.send(message)

    @channel.command(name="general", aliases=['welcome'])
    async def val_setup_channel_welcome(self, ctx, channel: discord.TextChannel):
        """Setup the welcome channel."""
        await self.config.guild(ctx.guild).welcome_channel.set(channel.id)

        message = "Welcome channel configured on {}".format(channel.mention)
        await ctx.send(message)

    @channel.command(name="moderation", aliases=['mod'])
    async def val_setup_channel_mod(self, ctx, channel: discord.TextChannel):
        """Setup the mod channel."""
        await self.config.guild(ctx.guild).mod_channel.set(channel.id)

        message = "Welcome channel configured on {}".format(channel.mention)
        await ctx.send(message)

    @message.command(name="validation")
    async def val_setup_message_validation(self, ctx):
        """Setup the validation message."""

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        instructions = "You have 2 minutes to post in the next message the content of the validation message.\n" \
                       + "You can enter `{SERVER}` for server name, `{MEMBER}` for member name, or `abort` to abort"
        instructions_msg = await ctx.send(instructions)
        try:
            message = await self.bot.wait_for('message', check=check, timeout=120)
            if message.content.strip() == "abort":
                raise Abort()
        except asyncio.TimeoutError:
            await ctx.send("{} Too late, please be quicker next time".format(ctx.author.mention))
        except Abort:
            await ctx.send("Edit aborted".format(ctx.author.mention))
        else:
            await self.config.guild(ctx.guild).message_validation.set(message.content)
            confirmation = "Validation message configured on ```{}```".format(
                message.content)
            await ctx.send(confirmation)
            await message.add_reaction('✅')
        finally:
            await instructions_msg.delete()

    @message.command(name="welcome")
    async def val_setup_message_welcome(self, ctx):
        """Setup the welcome message."""

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        instructions = "You have 2 minutes to post in the next message the content of the welcome message"
        instructions_msg = await ctx.send(instructions)
        try:
            message = await self.bot.wait_for('message', check=check, timeout=120)
            if message.content.strip() == "abort":
                raise Abort()
        except asyncio.TimeoutError:
            await ctx.send("{} Too late, please be quicker next time".format(ctx.author.mention))
        except Abort:
            await ctx.send("Edit aborted".format(ctx.author.mention))
        else:
            await self.config.guild(ctx.guild).message_welcome.set(message.content)
            confirmation = "Welcome message configured on ```{}```".format(
                message.content)
            await ctx.send(confirmation)
            await message.add_reaction('✅')
        finally:
            await instructions_msg.delete()

    @role.command(name="setup")
    async def val_setup_role_setup(self, ctx, role: discord.Role):
        """Setup the role after validation."""
        await self.config.guild(ctx.guild).setup_role.set(role.id)

        message = "Setup role configured on {}".format(role)
        await ctx.send(message)

    @role.group(name="optional")
    async def val_setup_role_optional(self, ctx):
        pass

    @val_setup_role_optional.command(name="set")
    async def val_setup_role_optional_set(self, ctx, role: discord.Role, *tags):
        for tag in tags:
            await self.config.guild(ctx.guild).set_raw('optional_roles', tag, value=role.id)
        await ctx.send("Mapped {} role on tags {}".format(role, " ".join(tags)))

    @val_setup_role_optional.command(name="del")
    async def val_setup_role_optional_del(self, ctx, *tags):
        for tag in tags:
            await self.config.guild(ctx.guild).clear_raw('optional_roles', tag)
        await ctx.send("Del tags: {}".format(" ".join(tags)))

    @val_setup_role_optional.command(name="get")
    async def val_setup_role_optional_get(self, ctx, *tags):
        data = await self.config.guild(ctx.guild).get_raw('optional_roles', *tags)
        data_str = str(json.dumps(data, indent=4, sort_keys=True))
        for role in ctx.guild.roles:
            data_str = data_str.replace(str(role.id), role.name)
        message = '```json\n{}```'.format(data_str)
        await ctx.send(message)

    @commands.command()
    @checks.mod_or_permissions(administrator=True)
    async def aval(self, ctx, member: discord.Member, *roles):
        """Accept a member in entrance channel."""
        if await self._is_mod(member):
            message_usr = '{} : Action non valide (membre du staff)'.format(
                ctx.message.author.mention)
            await ctx.send(message_usr, delete_after=2)
            await ctx.message.delete()
            return

        roles_to_setup = [ctx.guild.get_role(await self.config.guild(ctx.guild).setup_role())]
        list_roles = await self.config.guild(ctx.guild).optional_roles()
        for role in roles:
            try:
                roles_to_setup.append(ctx.guild.get_role(list_roles[role]))
            except:
                continue

        # Trouvons les messages relatifs
        messages_related = await self._find_related_msg(member)
        # Faisons une backup
        await self._backup_msg(messages_related, 'Validation', member, ctx.author)
        # Supprimons les
        await ctx.channel.delete_messages(messages_related)

        # Ajoutons les droits au nouveau
        for role in roles_to_setup:
            await member.add_roles(role, reason="Ajout d'un nouveau")

        mod_message = "{} vient d'être ajouté au serveur par {}".format(
            member, ctx.message.author)
        await self.bot.get_channel(await self.config.guild(ctx.guild).mod_channel()).send(mod_message)

        keywords = {"SERVER": ctx.guild, "MEMBER": member.mention}
        message = (await self.config.guild(ctx.guild).message_welcome()).format(**keywords)
        await self.bot.get_channel(await self.config.guild(ctx.guild).welcome_channel()).send(message)

    @commands.command()
    @checks.mod_or_permissions(administrator=True)
    async def aban(self, ctx, member: discord.Member, reason: str = None):
        """Ban a member in entrance channel."""
        if await self._is_mod(member):
            message_usr = '{} : Action non valide (membre du staff)'.format(
                ctx.message.author.mention)
            await ctx.send(message_usr, delete_after=2)
            await ctx.message.delete()
            return

        # Trouvons les messages relatifs
        messages_related = await self._find_related_msg(member)
        # Faisons une backup
        await self._backup_msg(messages_related, "Banissement", member, ctx.author)
        # Supprimons les
        await ctx.channel.delete_messages(messages_related)

        # Let's ban the user
        await ctx.guild.ban(member, reason=reason)

        mod_message = "{} vient d'être banni par {} - Raison: {}".format(
            member, ctx.message.author, reason)
        await self.bot.get_channel(await self.config.guild(ctx.guild).mod_channel()).send(mod_message)

    async def _find_related_msg(self, member):
        bool_firstmsg, only_user = True, True
        related_msg = []
        async for msg in self.bot.get_channel(await self.config.guild(member.guild).entrance_channel()).history(
                reverse=True):
            if bool_firstmsg:
                if msg.author == self.bot.user:
                    if member.id in msg.raw_mentions:
                        #                    if member in msg.mentions:
                        related_msg.append(msg)
                        bool_firstmsg = False
                elif msg.author == member:
                    related_msg.append(msg)
                    bool_firstmsg = False
            else:
                if msg.author == member:
                    related_msg.append(msg)
                elif msg.author == self.bot.user and len(msg.mentions) == 0:
                    continue
                elif only_user:
                    if await self._is_mod(msg.author):
                        related_msg.append(msg)
                    else:
                        only_user = False
                else:
                    if await self._is_mod(msg.author):
                        if member.id in msg.raw_mentions:
                            #                        if member in msg.mentions:
                            related_msg.append(msg)
        return related_msg

    async def _backup_msg(self, messages, action: str, member: discord.Member, staff):
        message_to_post = '# DEBUT - Action: ' + action + ' - Membre: {} ({})'.format(member, member.id) \
                          + ' - Modérateur: {} ({})\n\n'.format(staff, staff.id)

        for msg in messages:
            if await self._is_mod(msg.author):
                tmp = '< ' + str(msg.author)[:-5] + ' > :\n'
            else:
                tmp = '<' + str(msg.author)[:-5] + '> :\n'
            tmp += msg.clean_content + '\n\n'

            message_to_post += tmp
        message_to_post += '# FIN'

        messages_to_post = utils.chat_formatting.pagify(message_to_post, "\n<", shorten_by=10)

        for message in messages_to_post:
            message = f"```md\n{message}```"
            await self.bot.get_channel(await self.config.guild(member.guild).archive_channel()).send(message)

    async def _is_mod(self, member: discord.Member):
        try:
            if len(member.roles) > 1:
                return True
            else:
                return False
        except AttributeError:
            return False