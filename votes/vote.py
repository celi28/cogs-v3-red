from redbot.core import data_manager, checks, commands
import sqlite3
import os

class Votes(commands.Cog):
    def __init__(self, bot):
        if not hasattr(self.bot, 'cogs_messages'):
            raise Exception("Cog message needed")

        self.bot = bot
        directory = str(data_manager.cog_data_path()) + "/{}".format(self.__class__.__name__)
        # let's initiate the storage
        if not os.path.exists(directory):
            os.makedirs(directory)
            
        sqlite3.enable_callback_tracebacks(True)
        sqlite3.register_adapter(bool, int)
        sqlite3.register_converter("BOOLEAN", lambda v: bool(int(v)))
        self.conn = sqlite3.connect(directory + '/votes.db')
        c = self.conn.cursor()
        scheme_votes = ", ".join(['id INTEGER PRIMARY KEY', 'member_id INTEGER', 'picture_url TEXT',
                                  'created_at TIMESTAMP', 'end_at TIMESTAMP', 'closed BOOLEAN DEFAULT 0'])
        scheme_voices = ", ".join(['id INTERGER PRIMARY KEY', 'vote_id INTEGER', 'value INTEGER', 'reason TEXT',
                         'valid BOOLEAN DEFAULT 0', 'created_at TIMESTAMP', 'FOREIGN KEY(vote_id) REFERENCES votes(id)'])
        
        if c.execute("SELECT name FROM sqlite_master WHERE type='table'\
                     AND name='votes'").fetchone() is None:
            c.execute('''CREATE TABLE 'votes' ({})'''.format(scheme_votes))
            c.execute('''CREATE TABLE 'voices' ({})'''.format(scheme_voices))
                
        self.conn.commit()
        c.close()
    
    def db_addvote(self, member_id, picture_url, created_at, end_at):
        c = self.conn.cursor()
        c.execute("INSERT INTO votes(member_id, picture_url, created_at, end_at)\
          VALUES (?, ?, ?, ?)", (member_id, picture_url, created_at, end_at))
        self.conn.commit()
        c.close()
        
    def db_addvoice(self, vote_id, value, reason, created_at):
        c = self.conn.cursor()
        c.execute("INSERT INTO voices(vote_id, value, reason, created_at)\
          VALUES (?, ?, ?, ?)", (vote_id, value, reason, created_at))
        self.conn.commit()
        c.close()
    
        