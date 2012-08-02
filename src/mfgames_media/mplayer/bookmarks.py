"""Contains the common functionality for starting MPlayer using bookmarks to remember where the video was last positioned."""


from datetime import datetime
import argparse
import logging
import mfgames_tools.process
import os
import re
import sqlite3
import subprocess
import time


# Schema used to identify the current file structure.
DATABASE_SCHEMA = 4

# Regex used to identify a status line from the mplayer output.
STATUS_REGEX = 'STATUSLINE: A:\s*([\d+\.]+)\s+V:\s*([\d+\.]+)\s+A-V:'

# Format of the log messages.
LOG_FORMAT = "%(asctime)-15s %(name)-8s %(levelname)-5s %(message)s"

# Format of the data stored in the file.
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'


class BookmarkProcess(mfgames_tools.process.Process):
    """Base class that handles the database management and setup for
    bookmarking MPlayer videos."""

    def __init__(self):
        super(BookmarkProcess, self).__init__()

    def process(self, args):
        # Handle the base class' processing which verifies the file
        # already exists.
        super(BookmarkProcess, self).process(args)

        # Logging
        logging.basicConfig(format=LOG_FORMAT, level=logging.DEBUG)

        # Database
        db = self.database_connect()

#    # Cleanup and shutdown
#    db.close()

    def database_connect(self):
        """
        Ensures that the database exists and it contains the proper
        structure. If the database does not, then it creates the
        database at version 0. For schema out of data, including a new
        one, it replays all the schema changes to bring it up to the
        newest version. If the schema is further than this
        application, the application quits with an error.
        """
        
        # Logging to report the status.
        log = logging.getLogger("database")

        # Build up the SQL filename. For Unix machines, this will be under
        # $HOME/.config/mfgames/mfgames-mplayer/. For Windows... no clue.
        config_directory = os.path.join(
            os.path.expanduser("~"),
            '.config',
            'mfgames',
            'mfgames-mplayer')
        log.info('Using configuration directory: ' + config_directory)
        
        # Make sure the directory exists.
        if not os.path.isdir(config_directory):
            log.info('Creating configuration directory')
            os.makedirs(config_directory)
            
        # Open a connection to the sqlite3 database, creating if needed.
        db_path = os.path.join(config_directory, 'history.sqlite3')
        is_new = False
            
        if not os.path.isfile(db_path):
            log.info('Creating initial database file')
            is_new = True

        self.db = sqlite3.connect(db_path)
        self.db.isolation_level = None

        # Create the initial database, if needed
        if is_new:
            self.create_database_structure()

        # Check the database schema for needed updates
        schema_version = self.get_database_schema()
        log.info('Current database schema version: ' + format(schema_version))

        if schema_version > DATABASE_SCHEMA:
            log.error("Current file schema exceeds the program's schema of "
                      + format(DATABASE_SCHEMA) + "!")
            exit(1)

        if schema_version < DATABASE_SCHEMA:
            self.upgrade_schema(schema_version)

    def create_database_structure(self):
        """Creates the initial table structure for the database."""

        # Create the schema table
        self.db.execute('CREATE TABLE schema (version INTEGER);')
        self.db.execute('INSERT INTO schema VALUES(1);')
        
        # Create the bookmark table
        self.db.execute('CREATE TABLE bookmark ('
                        + 'path TEXT, position REAL, duration REAL,'
                        + 'timestamp TEXT);')

    def upgrade_schema(self, schema_version):
        """
        Upgrades the schema of the settings file to the current version. This
        runs the various upgrades sequentially until the system is brought up
        to the proper version.
        """

        log = logging.getLogger("schema")

        # Version 2 adds a settings/configuration table.
        if schema_version < 2:
            # Perform the steps to upgrade the schema.
            log.info("Upgrading schema to version 2")
            self.db.execute("CREATE TABLE settings (name TEXT, value TEXT);")
            self.db.execute("INSERT INTO settings VALUES('rewind_seconds', 5);")
            self.db.execute("INSERT INTO settings VALUES('end_of_buffer_reset', 60);")
            self.db.execute(
                "INSERT INTO settings VALUES('program', '/usr/bin/mplayer');")

            # Update the current version of the schema.
            self.db.execute("UPDATE schema SET version = 2;")
            schema_version = 2

        # Version 3 moves a missing field into the configuration.
        if schema_version < 3:
            # Perform the steps for the upgrade.
            log.info("Upgrading schema to version 3")
            self.db.execute("INSERT INTO settings VALUES('expire_days', 30);")

            # Update the current version of the schema.
            self.db.execute("UPDATE schema SET version = 3;")
            schema_version = 3

        # Version 4 adds configuration options for mfgames-mplayer-mythtv.
        if schema_version < 4:
            # Perform the steps for the upgrade.
            log.info("Upgrading schema to version 4")
            insert = "INSERT INTO settings VALUES"
            self.db.execute(insert + "('directory_roots', '');")
            self.db.execute(insert + "('splash_error_pause', '5000');")
            self.db.execute(insert + "('splash_play_pause', '1000');")
            self.db.execute(insert + "('splash_font_name', 'Verdana');")
            self.db.execute(insert + "('splash_font_size', '24');")

            # Update the current version of the schema.
            self.db.execute("UPDATE schema SET version = 4;")
            schema_version = 4

    def get_database_schema(self):
        """Retrieves the database schema version."""

        cursor = self.db.cursor()
        cursor.execute('SELECT version FROM schema')
        results = cursor.fetchone()
        cursor.close()
        return results[0]

    def get_setting(self, name):
        """Retrieves a settings value from the database."""

        cursor = self.db.cursor()
        cursor.execute("SELECT value FROM settings WHERE name='" + name + "';")
        results = cursor.fetchone()
        cursor.close()
        return results[0]

    def get_setting_float(self, name):
        """Retrieves a setting as a float value."""

        return float(self.get_setting(name))

    def has_record_expired(self, dbrow):
        # Pull out the fields from the row.
        seconds = dbrow[0]
        duration = dbrow[1]
        last = dbrow[2]

        # If we are at the beginning, it is effectively expired.
        if seconds < 0.1:
            return "At Start"

        # Ignore bookmarks near the end of the file.
        end_of_buffer_reset = self.get_setting_float('end_of_buffer_reset')
    
        if duration > 0.0 and (seconds + end_of_buffer_reset) > duration:
            return "At End"

        # Ignore records that are over a month long.
        then = datetime.strptime(last, DATETIME_FORMAT)
        how_long = datetime.utcnow() - then

        if how_long.days > self.get_setting_float('expire_days'):
            return format(how_long.days) + " days"

        # The record has not expired.
        return None


class BookmarkConfigProcess(BookmarkProcess):
    def __init__(self):
        super(BookmarkConfigProcess, self).__init__()

    def process(self, args):
        """
        Lists all configuration settings within the file.
        """

        # Handle the base class' processing.
        super(BookmarkConfigProcess, self).process(args)

        # If we have a first parameter, then we just filter for that one.
        where = ''

        if args.config != None:
            where = " WHERE name='" + args.config + "'"

        # If we have the second parameter, we want to set the value first.
        if args.value != None:
            self.db.execute(
                "UPDATE settings SET value='" + args.value
                + "' WHERE name='" + args.config + "';")

        # Create the SQL statement to retrieve the data.
        cursor = self.db.cursor()
        cursor.execute('SELECT name, value FROM settings'
                       + where + ' ORDER BY name;')

        # Loop through the rows and format it as output.
        print 'Name                  Value'
        print '===================== ============================'

        for row in cursor:
            print('{0:>21s} {1}'.format(row[0], row[1]))
            
        # Close the cursor and give a line to indicate we are done.
        cursor.close()

    def setup_arguments(self, parser):
        # Add in the argument from the base class.
        super(BookmarkConfigProcess, self).setup_arguments(parser)

        # Add in the text-specific generations.
        parser.add_argument(
            'config',
            type=str,
            nargs='?',
            default=None,
            help='Name of configuration setting to display or set.')
        parser.add_argument(
            'value',
            type=str,
            nargs='?',
            default=None,
            help='Value to set the configuration.')

    def get_help(self):
        return "Displays and sets configuration options."


class BookmarkListProcess(BookmarkProcess):
    def get_help(self):
        return "Lists all known bookmarks."

    def process(self, args):
        """
        Lists all files and their position and last access timestamp.
        """

        # Handle the base class' processing.
        super(BookmarkListProcess, self).process(args)

        # Create the SQL statement to retrieve the data.
        count = 0

        cursor = self.db.cursor()
        cursor.execute('SELECT position, duration, timestamp, path'
            + ' FROM bookmark'
            + ' ORDER BY path')

        # Loop through the rows and format it as output.
        print 'Position Duration Last Access         State      Filename'
        print '======== ======== =================== ========== ========'

        for row in cursor:
            # Keep track of the number of records we have.
            count = count + 1

            # Figure out the formatted state.
            state = self.has_record_expired(row)

            if state == None:
                state = ''

            # Print the results.
            print(
                '{1:>8.1f} {2:>8.1f} {3} {4:<10} {0}'.
                format(row[3], row[0], row[1], row[2], state))

        # Close the cursor and give a line to indicate we are done.
        cursor.close()
    
        if count == 1:
            print("Found 1 entry.")
        else:
            print("Found " + format(count) + " entries.")


class BookmarkClearProcess(BookmarkProcess):
    def get_help(self):
        return "Clears all known bookmarks."

    def process(self, args):
        """
        Clears all the records.
        """

        # Handle the base class' processing.
        super(BookmarkClearProcess, self).process(args)

        # Create the SQL statement to retrieve the data.
        count = 0

        cursor = self.db.cursor()
        cursor.execute('SELECT position, duration, timestamp, path'
            + ' FROM bookmark'
            + ' ORDER BY path')

        # Loop through the rows and get a list of files that need to be removed.
        filenames = list()

        for row in cursor:
            filenames.append(row[3])

        cursor.close()

        # Loop through all the files and delete them from the database.
        for filename in filenames:
            # Print out the filename
            print(filename)

            # Delete it from the database.
            self.db.execute(
                "DELETE FROM bookmark WHERE path = '" + filename + "'")


class BookmarkExpireProcess(BookmarkProcess):
    def get_help(self):
        return "Removes bookmarks that have expired."

    def process(self, args):
        """
        Removes all the records that have been expired.
        """

        # Handle the base class' processing.
        super(BookmarkExpireProcess, self).process(args)

        # Create the SQL statement to retrieve the data.
        count = 0

        cursor = self.db.cursor()
        cursor.execute('SELECT position, duration, timestamp, path'
            + ' FROM bookmark'
            + ' ORDER BY path')

        # Loop through the rows and get a list of files that need to be removed.
        filenames = list()

        for row in cursor:
            if self.has_record_expired(row) != None:
                filenames.append(row[3])

        cursor.close()

        # Loop through all the files and delete them from the database.
        for filename in filenames:
            # Print out the filename
            print(filename)

            # Delete it from the database.
            self.db.execute(
                "DELETE FROM bookmark WHERE path = '" + filename + "'")
    

class BookmarkPlayProcess(BookmarkProcess):
    def get_help(self):
        return "Play a video, using a bookmark if possible."

    def process(self, args):
        """
        Plays the given media file, potentially resuming at the last position.
        """

        # Handle the base class' processing.
        super(BookmarkPlayProcess, self).process(args)

        # Logging to report the status.
        log = logging.getLogger("play")

        # Keep track of the absolute path since we use that for storing
        # the bookmark information, with a bit of SQL protection.
        filename = os.path.abspath(args.file)
        lookup = filename.replace("'", '')

        # Determine if we have a bookmark already in the file.
        cursor = self.db.cursor()
        cursor.execute('SELECT position, duration, timestamp'
            + ' FROM bookmark'
            + " WHERE path='" + lookup + "'")
        dbrow = cursor.fetchone()
        cursor.close()

        # Get the position from the sqlite3 database.
        seconds = 0.0
        duration = 0.0

        if dbrow != None:
            # Pull the positional data for this file.
            seconds = dbrow[0]
            last = dbrow[2]
            log.info("Loaded position: " + format(seconds)
                + 's of ' + format(duration)
                + 's from ' + last)

            # Determine if we need to expire this record.
            reason = self.has_record_expired(dbrow)

            if reason != None:
                # We need to ignore the contents of this record.
                log.info('Resetting to beginning: ' + reason)
                seconds = 0

        # Build up the basic commands in a list. We include the -msgmodule
        # line so each status line shows up on its own line. We also
        # increase the verbosity of everything so it forces the status
        # line to break into a new line.
        commands = [self.get_setting('program')]
        commands.append('-identify')
        commands.append('-msgmodule')
        commands.append('-msglevel')
        commands.append('all=8')

        # If we have a position, use it.
        if seconds > 0:
            commands.append('-ss')
            commands.append(format(seconds))

        # Start the MPlayer process with the gathered commands. We open a
        # pipe to the output since we use that to scan for the current
        # position inside the file.
        log.info('Playing ' + filename)
        commands.append(filename)
        process = subprocess.Popen(
            commands,
            shell=False,
            close_fds=True,
            bufsize=0,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)

        # Loop through the output of the MPlayer, looking for position
        # data. This is the status line, which looks like this:
        #   A: (\d+.\d+) V: (\d+.\d+)...
        # The status line will only be displayed once at quitting when running
        # in this mode (without shell).
        for line in process.stdout:
            # Debugging to show the line.
            #log.debug(line.strip())

            # See if we have a duration line. We need search since this
            # isn't the starting point of the line.
            match = re.search("IDENTIFY: ID_LENGTH=([\d\.]+)", line, re.MULTILINE)

            if match != None:
                log.info("Found duration: " + match.group(1))
                duration = max(duration, float(match.group(1)))

            # Use the regex to see if we have a match on this line.
            match = re.match(STATUS_REGEX, line, re.MULTILINE)

            if match != None:
                # We have a match on the line, so pull out the groups and
                # convert them into floats of seconds. We take the lowest
                # offset as our new position.
                seconds = min(float(match.group(1)), float(match.group(2)))

                # Adjust the duration if we exceed it for some reason.
                duration = max(duration, seconds)

                # Report the results to the log.
                #log.info('New position: ' + format(seconds))

        process.stdout.close()

        # Figure out the position in the file. This is parsed from the
        # statusline messages. We also shift back slightly to handle the
        # fact that MPlayer doesn't have good seeking.
        rewind_seconds = self.get_setting_float('rewind_seconds')
        seconds = max(0, seconds - rewind_seconds)
        log.info(
            "Saved position: "
            + format(seconds)
            + " of "
            + format(duration))

        # Save or update the position into the database.
        now = datetime.utcnow().strftime(DATETIME_FORMAT)

        if dbrow != None:
            self.db.execute("UPDATE bookmark SET "
                + "position = " + format(seconds) + ","
                + "duration = " + format(duration) + ","
                + "timestamp = '" + now + "'"
                + " WHERE path = '" + lookup + "'");
        else:
            self.db.execute("INSERT INTO bookmark VALUES ("
                + "'" + lookup + "',"
                + format(seconds) + ","
                + format(duration) + ","
                + "'" + now + "'" + ")")

    def setup_arguments(self, parser):
        # Add in the argument from the base class.
        super(BookmarkPlayProcess, self).setup_arguments(parser)

        # Add in the text-specific generations.
        parser.add_argument(
            'file',
            type=str,
            help='Movie file to play.')
