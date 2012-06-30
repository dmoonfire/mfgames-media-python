"""Process classes for working with themoviedb.com."""


import StringIO
import logging
import mfgames_tools.process
import os
import pycurl
import re
import sys
import tmdb


class TmdbProcess(mfgames_tools.process.Process):
    """Common base class for TMDB processes that handles handling of
    the API key and common configuration."""

    def __init__(self):
        super(TmdbProcess, self).__init__()

        # Set up logging for this proces.
        self.log = logging.getLogger('tmdb')

    def process(self, args):
        """Loads the TMDB configuration and ensures the API is
        properly set."""

        # Perform any base class processing.
        super(TmdbProcess, self).process(args)

        # Get the API key or blow up if we can't figure it out.
        if not args.api_key:
            self.log.error("Cannot find API key from command line "
                           + "or configuration file.")
            return False

        tmdb.configure(args.api_key)

        # We were successful, so return true.
        return True

    def setup_arguments(self, parser):
        # Add in the argument from the base class.
        super(TmdbProcess, self).setup_arguments(parser)

        # Add the Creole-conversion specific processes.
        parser.add_argument(
            '--api-key', '-a',
            type=str,
            nargs=1,
            help='API key from themoviedb.com, required.')

class IdProcess(TmdbProcess):
    """Searches themoviedb.com for the ID for a given movie."""

    def process(self, args):
        # Perform any base class processing.
        if not super(IdProcess, self).process(args):
            return

        # Combine the title elements together since we allow both a
        # single variable or combined together. Once we have that,
        # normalize the name.
        title = " ".join(args.title)
        title = self.normalize_title(title)
        
        # Do a search for the title using the TMDB library.
        movie = tmdb.tmdb(title)

        if movie:
            print args.format % {
                "id": movie.getId(0),
                "title": movie.getName(0),
                }

    def setup_arguments(self, parser):
        # Add in the argument from the base class.
        super(IdProcess, self).setup_arguments(parser)

        # Add the Creole-conversion specific processes.
        parser.add_argument(
            'title',
            type=str,
            nargs='+',
            help='One or more names to search for the ID.')
        parser.add_argument(
            '--format', '-f',
            type=str,
            default="%(id)s",
            help='Output format: %(id)s, %(title)s')

    def get_help(self):
        return "Searches TMDB for a movie with the given title and optional attributes."

    def normalize_title(self, title):
        """Normalizes the title by handling articles at the end of the
        title while excluding any search keys in parentheses."""

        # Check to see if we need to remove the "()" characters and
        # contents.
        year = None
        result = re.search(r'^(.*?)\s*\(\s*(\d+)\s*\)\s*$', title)

        if result:
            year = result.group(2)
            title = result.group(1)

        # Move the articles to the beginning.
        title = re.sub(r'(.*?), (The|A|An)$', r'\2 \1', title)

        # If we have a year, put it back.
        #if year:
        #    title += " (" + year + ")"

        # Return the resulting title.
        return title


class JsonProcess(TmdbProcess):
    """Downloads the Json file for a given TMDB ID movie."""

    def process(self, args):
        # Perform any base class processing.
        if not super(JsonProcess, self).process(args):
            return

        # Set up the PyCurl process so we can download the results
        # directly. We do this so it is easier to pull out the data
        # later (e.g., cache it).
        pycurl.global_init(pycurl.GLOBAL_DEFAULT)

        # Retrieve the JSON for that specific movie.
        curl = pycurl.Curl()
        curl.setopt(
            pycurl.URL,
            "http://api.themoviedb.org/3/movie/{0}?api_key={1}".format(
                args.id,
                args.api_key))
        curl.setopt(pycurl.HTTPHEADER, ["Accept: application/json"])

        # Figure out where we're downloading to.
        if args.output == "-":
            stream = sys.stdout
        else:
            # If the file exists, we need to check for forcing.
            if os.path.isfile(args.output) and not args.force:
                print "Cannot overwrite file: " + args.output
                return False

            # Open the stream for writing.
            stream = open(args.output, 'w')

        # Download into a string.
        buf = StringIO.StringIO()
        curl.setopt(pycurl.WRITEFUNCTION, stream.write)
        curl.setopt(pycurl.FOLLOWLOCATION, 1)
        curl.setopt(pycurl.MAXREDIRS, 5)
        curl.perform()
        
        # Close the stream if we're done.
        if not args.output == "-":
            stream.close()

        # Finish up the PyCurl library.
        pycurl.global_cleanup()

    def setup_arguments(self, parser):
        # Add in the argument from the base class.
        super(JsonProcess, self).setup_arguments(parser)

        # Add the Creole-conversion specific processes.
        parser.add_argument(
            'id',
            type=int,
            help='The TMDB ID for the movie to retrieve.')
        parser.add_argument(
            '--output', '-o',
            type=str,
            default='-',
            help='The output file to write the results. If - or missing, it will write to standard output.')
        parser.add_argument(
            '--force', '-f',
            action='store_true',
            help="If used, then the output will overwrite the file.")

    def get_help(self):
        return "Downloads the JSON file for a given ID and write it to a file or standard out."
