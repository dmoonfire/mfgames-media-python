"""Contains the common functionality for starting MPlayer using the
various boomarking settings."""


from datetime import datetime
import argparse
import logging
import os
import re
import subprocess
import time

import sqlite3


# Schema used to identify the current file structure.
DATABASE_SCHEMA = 3

# Regex used to identify a status line from the mplayer output.
STATUS_REGEX = 'STATUSLINE: A:\s*([\d+\.]+)\s+V:\s*([\d+\.]+)\s+A-V:'

# Format of the log messages.
LOG_FORMAT = "%(asctime)-15s %(name)-8s %(levelname)-5s %(message)s"

# Format of the data stored in the file.
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'


def do_mplayer_tool(arguments):
    """Starts MPlayer using the given arguments."""
    parser = argparse.ArgumentParser(
        description='Wraps mplayer with various options.')
    subparsers = parser.add_subparsers()

    config_parser = subparsers.add_parser('config')
    config_parser.set_defaults(function = do_config)
    config_parser.add_argument(
        'name',
        type=str,
        nargs='?',
        default=None,
        help='Name of configuration setting to display or set.')
    config_parser.add_argument(
        'value',
        type=str,
        nargs='?',
        default=None,
        help='Value to set the configuration.')
    
    list_parser = subparsers.add_parser('list')
    list_parser.set_defaults(function = do_list)
    
    clear_parser = subparsers.add_parser('clear')
    clear_parser.set_defaults(function = do_clear)
    
    expire_parser = subparsers.add_parser('expire')
    expire_parser.set_defaults(function = do_expire)
    
    play_parser = subparsers.add_parser('play')
    play_parser.set_defaults(function = do_play)
    play_parser.add_argument(
        'file',
        type=str,
        help='Media path to play in mplayer')

    args = parser.parse_args()
    
    # Logging
    logging.basicConfig(format=LOG_FORMAT, level=logging.DEBUG)
    #level=logging.DEBUG, INFO, etc
    #filename=LOG_FILENAME

    # Database
    db = database_connect()

    # Execute the commands selected by the parser.
    results = args.function(args, db)

    # Cleanup and shutdown
    db.close()

def database_connect():
    """
    Ensures that the database exists and it contains the proper
    structure. If the database does not, then it creates the database
    at version 0. For schema out of data, including a new one, it
    replays all the schema changes to bring it up to the newest
    version. If the schema is further than this application, the
    application quits with an error.
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

    db = sqlite3.connect(db_path)
    db.isolation_level = None

    # Create the initial database, if needed
    if is_new:
        create_database_structure(db)

    # Check the database schema for needed updates
    schema_version = get_database_schema(db)
    log.info('Current database schema version: ' + format(schema_version))

    if schema_version > DATABASE_SCHEMA:
        log.error("Current file schema exceeds the program's schema of "
            + format(DATABASE_SCHEMA) + "!")
        exit(1)

    if schema_version < DATABASE_SCHEMA:
        upgrade_schema(db, schema_version)

    # Return the resulting database
    return db

def create_database_structure(db):
    """Creates the initial table structure for the database."""

    # Create the schema table
    db.execute('CREATE TABLE schema (version INTEGER);')
    db.execute('INSERT INTO schema VALUES(1);')

    # Create the bookmark table
    db.execute('CREATE TABLE bookmark ('
        + 'path TEXT, position REAL, duration REAL, timestamp TEXT);')

def upgrade_schema(db, schema_version):
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
        db.execute("CREATE TABLE settings (name TEXT, value TEXT);")
        db.execute("INSERT INTO settings VALUES('rewind_seconds', 5);")
        db.execute("INSERT INTO settings VALUES('end_of_buffer_reset', 60);")
        db.execute(
            "INSERT INTO settings VALUES('program', '/usr/bin/mplayer');")

        # Update the current version of the schema.
        db.execute("UPDATE schema SET version = 2;")
        schema_version = 2

    # Version 3 moves a missing field into the configuration.
    if schema_version < 3:
        # Perform the steps for the upgrade.
        log.info("Upgrading schema to version 3")
        db.execute("INSERT INTO settings VALUES('expire_days', 30);")

        # update the current version of the schema.
        db.execute("UPDATE schema SET version = 3;")
        schema_version = 3

def get_database_schema(db):
    """Retrieves the database schema version."""

    cursor = db.cursor()
    cursor.execute('SELECT version FROM schema')
    results = cursor.fetchone()
    cursor.close()
    return results[0]

def get_setting(db, name):
    """Retrieves a settings value from the database."""

    cursor = db.cursor()
    cursor.execute("SELECT value FROM settings WHERE name='" + name + "';")
    results = cursor.fetchone()
    cursor.close()
    return results[0]

def get_setting_float(db, name):
    """Retrieves a setting as a float value."""

    return float(get_setting(db, name))

#
# Clear
#

def do_clear(args, db):
    """
    Clears all the records.
    """

    # Create the SQL statement to retrieve the data.
    count = 0

    cursor = db.cursor()
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
        db.execute("DELETE FROM bookmark WHERE path = '" + filename + "'")

#
# Listing
#

def do_config(args, db):
    """
    Lists all configuration settings within the file.
    """

    # If we have a first parameter, then we just filter for that one.
    where = ''

    if args.name != None:
        where = " WHERE name='" + args.name + "'"

    # If we have the second parameter, we want to set the value first.
    if args.value != None:
        db.execute("UPDATE settings SET value='" + args.value
            + "' WHERE name='" + args.name + "';")

    # Create the SQL statement to retrieve the data.
    cursor = db.cursor()
    cursor.execute('SELECT name, value FROM settings'
        + where + ' ORDER BY name;')

    # Loop through the rows and format it as output.
    print 'Name                  Value'
    print '===================== ============================'

    for row in cursor:
        print(
            '{0:>21s} {1}'.
            format(row[0], row[1]))

    # Close the cursor and give a line to indicate we are done.
    cursor.close()

#
# Expiring
#

def do_expire(args, db):
    """
    Removes all the records that have been expired.
    """

    # Create the SQL statement to retrieve the data.
    count = 0

    cursor = db.cursor()
    cursor.execute('SELECT position, duration, timestamp, path'
        + ' FROM bookmark'
        + ' ORDER BY path')

    # Loop through the rows and get a list of files that need to be removed.
    filenames = list()

    for row in cursor:
        if has_record_expired(db, row):
            filenames.append(row[3])

    cursor.close()

    # Loop through all the files and delete them from the database.
    for filename in filenames:
        # Print out the filename
        print(filename)

        # Delete it from the database.
        db.execute("DELETE FROM bookmark WHERE path = '" + filename + "'")

#
# Listing
#

def do_list(args, db):
    """
    Lists all files and their position and last access timestamp.
    """

    # Create the SQL statement to retrieve the data.
    count = 0

    cursor = db.cursor()
    cursor.execute('SELECT position, duration, timestamp, path'
        + ' FROM bookmark'
        + ' ORDER BY path')

    # Loop through the rows and format it as output.
    print 'Position Duration Last Access         State   Filename'
    print '======== ======== =================== ======= ========'

    for row in cursor:
        # Keep track of the number of records we have.
        count = count + 1

        # Figure out the formatted state.
        state = ''

        if has_record_expired(db, row):
            state = 'Expired'

        # Print the results.
        print(
            '{1:>8.1f} {2:>8.1f} {3} {4:<7} {0}'.
            format(row[3], row[0], row[1], row[2], state))

    # Close the cursor and give a line to indicate we are done.
    cursor.close()
    
    if count == 1:
        print("Found 1 entry.")
    else:
        print("Found " + format(count) + " entries.")

#
# Playback
#

def do_play(args, db):
    """
    Plays the given media file, potentially resuming at the last position.
    """

    # Logging to report the status.
    log = logging.getLogger("play")

    # Keep track of the absolute path since we use that for storing
    # the bookmark information, with a bit of SQL protection.
    filename = os.path.abspath(args.file)
    lookup = filename.replace("'", '')

    # Determine if we have a bookmark already in the file.
    cursor = db.cursor()
    cursor.execute('SELECT position, duration, timestamp'
        + ' FROM bookmark'
        + " WHERE path='" + lookup + "'")
    dbrow = cursor.fetchone()
    cursor.close()

    seconds = 0.0
    duration = 0.0

    if dbrow != None:
        # Pull the positional data for this file.
        seconds = dbrow[0]
        duration = dbrow[1]
        last = dbrow[2]
        log.info("Loaded position: " + format(seconds)
            + 's of ' + format(duration)
            + 's from ' + last)

        # Determine if we need to expire this record.
        if has_record_expired(db, dbrow):
            # We need to ignore the contents of this record.
            log.info('Resetting to beginning')
            seconds = 0
    # end if

    # Build up the basic commands in a list. We include the -msgmodule
    # line so each status line shows up on its own line. We also
    # increase the verbosity of everything so it forces the status
    # line to break into a new line.
    commands = [get_setting(db, 'program')]
    commands.append('-msgmodule')
    commands.append('-msglevel')
    commands.append('all=8')

    # If we have a position, use it.
    if seconds > 0:
        commands.append('-ss')
        commands.append(format(seconds))
    # end if

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
        match = re.search("duration: ([\d\.]+)s", line, re.MULTILINE)

        if match != None:
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
        # end if
    # end for

    process.stdout.close()

    # Figure out the position in the file. This is parsed from the
    # statusline messages. We also shift back slightly to handle the
    # fact that MPlayer doesn't have good seeking.
    rewind_seconds = get_setting_float(db, 'rewind_seconds')
    seconds = max(0, seconds - rewind_seconds)
    log.info(
        "Saved position: "
        + format(seconds)
        + " of "
        + format(duration))

    # Save or update the position into the database.
    now = datetime.utcnow().strftime(DATETIME_FORMAT)

    if dbrow != None:
        db.execute("UPDATE bookmark SET "
            + "position = " + format(seconds) + ","
            + "duration = " + format(duration) + ","
            + "timestamp = '" + now + "'"
            + " WHERE path = '" + lookup + "'");
    else:
        db.execute("INSERT INTO bookmark VALUES ("
            + "'" + lookup + "',"
            + format(seconds) + ","
            + format(duration) + ","
            + "'" + now + "'" + ")")

def has_record_expired(db, dbrow):
    # Pull out the fields from the row.
    seconds = dbrow[0]
    duration = dbrow[1]
    last = dbrow[2]

    # If we are at the beginning, it is effectively expired.
    if seconds < 0.1:
        return True

    # Ignore bookmarks near the end of the file.
    end_of_buffer_reset = get_setting_float(db, 'end_of_buffer_reset')
    
    if duration > 0.0 and (seconds + end_of_buffer_reset) > duration:
        return True

    # Ignore records that are over a month long.
    then = datetime.strptime(last, DATETIME_FORMAT)
    how_long = datetime.utcnow() - then

    if how_long.days > get_setting_float(db, 'expire_days'):
        return True

    # The record has not expired.
    return False