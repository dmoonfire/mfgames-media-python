"""Contains the various Amarok processing classes."""


import logging
import os
import shutil
import re

import MySQLdb

import mfgames.tools.process


class AmarokProcess(mfgames.tools.process.Process):
    """Extends the basic Process class to handle Amarok databases."""

    def __init__(self):
        super(AmarokProcess, self).__init__()
        self.db = None

    def process(self, args):
        """Performs processing on a single Amarok database."""

        # Call the parent to process the arguments first.
        super(AmarokProcess, self).process(args)

        # Set up logging to report usage.
        log = logging.getLogger('amarok')

        self.db = MySQLdb.connect (
            host = args.db_host,
            user = args.db_user,
            passwd = args.db_pass,
            db = args.db_name)

        log.info("Connected to Amarok database: " + args.db_name)

    def setup_arguments(self, parser):
        """Sets up the command-line arguments connecting to the Amarok
        database."""

        super(AmarokProcess, self).setup_arguments(parser)

        # Add the Amarok file options.
        parser.add_argument(
            '--db-user',
            type=str,
            default='',
            help='The database username to use.')
        parser.add_argument(
            '--db-host',
            type=str,
            default='localhost',
            help='The database host to use.')
        parser.add_argument(
            '--db-pass',
            type=str,
            default='',
            help='The database password to use.')
        parser.add_argument(
            '--db-name',
            type=str,
            default='amarok',
            help='The database name to use.')


class PackProcess(AmarokProcess):
    """Takes the files referred to by the Amarok database and packs
    them into a directory, taking into account disk limits."""

    def __init__(self):
        super(PackProcess, self).__init__()

    def process(self, args):
        """Packs files into a given directory."""

        # Call the parent to process the arguments first.
        super(PackProcess, self).process(args)

        # Set up logging to report usage.
        log = logging.getLogger('pack')

        # Verify and report the incoming values.
        if not os.path.exists(args.path):
            raise ProcessException("Cannot find directory: " + args.path)

        log.info("Scanning directory: " + args.path)

        # The basic structure for handling sizes is a nested
        # dictionary. The top level are the rating of the individual
        # files, with the second level being the relative filename and
        # its size. A rating of -1 is an unknown value to represent
        # the files that already in the destination location. Amarok
        # has ten ratings (5 stars allowing for half stars).
        files = {
            -1: {},
             0: {},
             1: {},
             2: {},
             3: {},
             4: {},
             5: {},
             6: {},
             7: {},
             8: {},
             9: {},
             10: {},
             }

        # Start by scanning the directory and getting the names of all
        # the files and their respective sizes and put them into the
        # -1 rating category.
        directory_tree = os.walk(args.path)
        
        total_bytes = 0

        for directory in directory_tree:
            for file in directory[2]:
                # Get a relative filename. This assumes / as a
                # directory separator, which is not a good thing. FIX.
                filename = os.path.join(directory[0], file)
                relativename = str.replace(
                    os.path.join(directory[0], file),
                    args.path + '/',
                    '')
                bytes = os.path.getsize(filename)

                # Add the relative filename and the size into a dictionary.
                #log.debug("  {0}".format(relativename))
                files[-1][relativename.lower()] = bytes
                total_bytes = total_bytes + bytes

        # Calculate how much space we have left to fill in.
        max_size = self.from_human(args.max_size)
        remaining_bytes = max_size - total_bytes

        if remaining_bytes < 0:
            log.error(
                "No more remaining space using {1} of {0}".format(
                    self.to_human(max_size),
                    self.to_human(total_bytes)))
            return

        log.info(
            "Can copy {0} of {1} bytes".format(
                self.to_human(remaining_bytes),
                self.to_human(max_size)))

        # Go through all the files in the database to identify the
        # file we already have and also to categorize all the music.
        source_files = {}
        dest_files = {}

        log.info("Using database to identify files")

        cursor = self.db.cursor()
        cursor.execute("SELECT "
                       + "s.id, "
                       + "s.score, "
                       + "s.rating, "
                       + "u.rpath "
                       + "FROM statistics s "
                       + "JOIN urls u "
                       + "ON s.url = u.id "
                       + "WHERE rating >= " + format(args.min_rating))

        while (1):
            # Fetch the next row from the cursor.
            row = cursor.fetchone()

            if row == None:
                break

            # Pull out the fields and remove the common prefixes from
            # the path. Amarok always put . in front of the path. We also
            # have to handle some characters that are not valid in VFAT
            # filesystems.
            fid = row[0]
            score = row[1]
            rating = row[2]
            rpath = row[3]

            rpath = str.replace(rpath, "." + args.source_directory, '')
            spath = rpath

            rpath = str.replace(rpath, ":", " -")
            rpath = str.replace(rpath, "?", "")
            rpath = str.replace(rpath, "./", "/")

            dpath = rpath
            rpath = rpath.lower()

            source_files[rpath] = spath
            dest_files[rpath] = dpath

            # Check to see if the rpath exists already there and we aren't
            # trying to keep a file with a lower rating than our minimum.
            if rpath in files[-1] and rating >= args.min_rating:
                # The file exists already in the destination, so move
                # it into the proper rating location. Also remove it
                # from the -1 so we don't remove it.
                files[rating][rpath] = files[-1][rpath]
                del files[-1][rpath]
            else:
                # Add the file into the files with a zero size.
                files[rating][rpath] = 0

        cursor.close()

        # Any remaining files at rating -1 need to be deleted and their
        # size subtracted from the remaining bytes.
        log.info("Removing any files not in DB or too low rating")
        files_removed = 0

        for rpath in files[-1].keys():
            # Delete the file from the destination.
            log.info("  {0}".format(rpath))
            os.remove(os.path.join(args.path, rpath))
            remaining_bytes = remaining_bytes + files[-1][rpath]
            files_removed = files_removed + 1
 
        log.info(
            "Removed {2} files and have {0} remaining".format(
                self.to_human(remaining_bytes),
                max_size,
                files_removed))

        # Starting at the highest rating (10), we move down until we
        # have filled the space as completely as possible.
        for rating in range(10, args.min_rating -1, -1):
            log.info("Checking for rating {0} files remaining".format(rating))

            # Go through all the files of this rating.
            for rpath in files[rating]:
                # If we already have it copied, we'll have the file
                # size in the rating path.
                size = files[rating][rpath]

                if size > 0:
                    # We already have it
                    continue

                # Determine if we can copy the file into the destination
                source_path = os.path.join(
                    args.source_directory,
                    source_files[rpath])

                if not os.path.exists(source_path):
                    # Cannot find the file in the filesystm
                    continue

                size = os.path.getsize(source_path)

                if size == 0:
                    # Invalid size, get rid of it.
                    continue

                # If the size is greater than remaining bytes, then we
                # need to make more space by deleting lower rating
                # files. If we can't do that, then we can't copy the file
                # over to the destination.
                if size > remaining_bytes:
                    # TODO Cannot purge yet
                    #log.info("Too big {0} {1}".format(size, remaining_bytes))
                    continue

                # We have enough space to copy the file, so copy it.
                dest_path = os.path.join(args.path, dest_files[rpath])
                dest_dir = os.path.dirname(dest_path)

                if not os.path.exists(dest_dir):
                    # Create the directories so we can copy it.
                    os.makedirs(dest_dir)

                log.info("  Copying {0}".format(dest_files[rpath]))
                shutil.copy(source_path, dest_path)

                remaining_bytes = remaining_bytes - size

    def from_human(self, format):
        """Converts a formatted string, like 10KB or 10 into an
        integer value."""

        # Look for straight numbers which don't need anything.
        if re.match('^\d+$', format) != None:
            # This is a straight number, so just return it.
            return int(format)

        # Look for a standard format.
        match = re.match('^(\d+)([KMG])B?$', format)

        if match == None:
            raise ProcessException("Cannot parse " + format)
        
        # Pull out the number and the multiplier.
        value = int(match.group(1))

        suffix = match.group(2)

        if suffix == 'K':
            return value * 1000

        if suffix == 'M':
            return value * 1000 * 1000

        if suffix == 'G':
            return value * 1000 * 1000 * 1000

    def to_human(self, value):
        """Converts a value string into a formatted string."""

        if value > 1000 * 1000 * 1000:
            return "{0:.2f} GB".format(value / 1000.0 / 1000.0 / 1000.0)

        if value > 1000 * 1000:
            return "{0:.2f} MB".format(value / 1000.0 / 1000.0)

        if value > 1000:
            return "{0:.2f} KB".format(value / 1000.0)

        return value

    def setup_arguments(self, parser):
        """Sets up the command-line arguments connecting to the Amarok
        database."""

        super(PackProcess, self).setup_arguments(parser)

        # Add the Amarok file options.
        parser.add_argument(
            '--max-size',
            type=str,
            help='The maximum size to allow for copied files.')
        parser.add_argument(
            '--min-rating',
            type=int,
            default=7, # 4 stars
            help='The minimum rating to copy into the destination.')
        parser.add_argument(
            '--source-directory',
            type=str,
            help="Contains the directory roots that need to be removed to determine relative paths.")
        parser.add_argument(
            'path',
            type=str,
            help='The path to pack the files into.')

    def get_help(self):
        """Returns the help line for the process."""
        return 'Packs files from Amarok into a directory.'
