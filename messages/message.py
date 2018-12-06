from redbot.core import data_manager, checks, commands
import datetime as dt
import discord
import sqlite3
import os

class Messages(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        directory = str(data_manager.cog_data_path()) + "/{}".format(self.__class__.__name__)
        
        # let's initiate the storage
        if not os.path.exists(directory):
            os.makedirs(directory)
        sqlite3.enable_callback_tracebacks(True)
        sqlite3.register_adapter(bool, int)
        sqlite3.register_converter("BOOLEAN", lambda v: bool(int(v)))
        self.conn = sqlite3.connect(directory + '/messages.db', detect_types=sqlite3.PARSE_DECLTYPES)
        scheme = ", ".join(['channel_id INTEGER', 'message_id INTEGER', 'author_id INTEGER',
                            'date TIMESTAMP', 'content TEXT', 'deleted BOOLEAN DEFAULT 0',
                            'edited BOOLEAN DEFAULT 0', 'revision_count INTEGER DEFAULT 0',
                            'PRIMARY KEY (message_id, revision_count)'])
        c = self.conn.cursor()
        
        # for each guild let's check if table exist
        for guild in self.bot.guilds:
            # if the table doesn't exist
            if c.execute("SELECT name FROM sqlite_master WHERE type='table'\
                         AND name={}".format(guild.id)).fetchone() is None:
                c.execute('''CREATE TABLE '{}' ({})'''.format(guild.id, scheme))
                c.execute("CREATE INDEX `author_index` ON `{}` ( `author_id` )".format(guild.id))
        self.conn.commit()
        c.close()
        
        self.bot.cogs_messages = True
        
    def __unload(self):
        del self.bot.cogs_messages
        self.conn.close()
        
    def db_insert(self, message):
        c = self.conn.cursor()
        print((message.channel.id, message.id, message.author.id,message.created_at, message.clean_content))
        c.execute("INSERT INTO '{}'(channel_id, message_id, author_id, date, content)\
                  VALUES (?, ?, ?, ?, ?)".format(message.guild.id),
                  (message.channel.id, message.id, message.author.id,
                   dt.datetime.now(), message.clean_content))
       
        self.conn.commit()
        c.close()
        
    def db_update(self, message):
        c = self.conn.cursor()
        last_rev = c.execute("SELECT max(revision_count) FROM '{}'\
                             WHERE message_id={}".format(message.guild.id, message.id)).fetchone()[0]
        c.execute("UPDATE '{}' SET edited=1 WHERE message_id=?\
                  AND revision_count=?".format(message.guild.id), (message.id, last_rev))
        c.execute("INSERT INTO '{}'(channel_id, message_id, author_id, date, content, revision_count)\
                  VALUES (?, ?, ?, ?, ?, ?)".format(message.guild.id),
                  (message.channel.id, message.id, message.author.id,
                   message.edited_at, message.clean_content, last_rev+1))
        self.conn.commit()
        c.close()
        
    def db_delete(self, message):
        c = self.conn.cursor()
        last_rev = c.execute("SELECT max(revision_count) FROM '{}'\
                             WHERE message_id={}".format(message.guild.id, message.id)).fetchone()[0]
        c.execute("UPDATE '{}' SET deleted=1 WHERE message_id=?\
                  AND revision_count=?".format(message.guild.id), (message.id, last_rev))
        self.conn.commit()
        c.close()
        
    async def on_message(self, message):
        if not message.author.bot and isinstance(message.channel, discord.TextChannel):
            self.db_insert(message)
            
    async def on_message_edit(self, before, after):
        if not after.author.bot and isinstance(after.channel, discord.TextChannel):
            self.db_update(after)
            
    async def on_message_delete(self, message):
        if not message.author.bot and isinstance(message.channel, discord.TextChannel):
            self.db_delete(message)
