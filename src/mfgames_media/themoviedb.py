"""Process classes for working with themoviedb.com."""


from elementtree.SimpleXMLWriter import XMLWriter
import urllib
import StringIO
import simplejson
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

    def configure(self):
        # Configure the TMDB database.
        tmdb.configure(self.args.api_key)

        # Get the v3 API stuff directly through JSON.
        url = "http://api.themoviedb.org/3/configuration?api_key={0}".format(
            self.args.api_key)
        self.configuration = self.get_json(url)

    def get_images_base_url(self):
        return self.configuration['images']['base_url']

    def get_json(self, url):
        # Set up the PyCurl process so we can download the results
        # directly. We do this so it is easier to pull out the data
        # later (e.g., cache it).
        pycurl.global_init(pycurl.GLOBAL_DEFAULT)

        # Retrieve the JSON for that specific movie.
        curl = pycurl.Curl()
        curl.setopt(pycurl.URL, url)
        curl.setopt(pycurl.HTTPHEADER, ["Accept: application/json"])

        # Download into a string.
        buf = StringIO.StringIO()
        curl.setopt(pycurl.WRITEFUNCTION, buf.write)
        curl.setopt(pycurl.FOLLOWLOCATION, 1)
        curl.setopt(pycurl.MAXREDIRS, 5)
        curl.perform()
        
        # Return the resulting JSON file.
        json = simplejson.loads(buf.getvalue())
        return json


class TmdbMovieProcess(TmdbProcess):
    """Common base class for processes that operate on a single
    movie. This takes a JSON file with information as the first
    parameter."""

    def __init__(self):
        super(TmdbMovieProcess, self).__init__()

    def process(self, args):
        # Perform any base class processing.
        if not super(TmdbMovieProcess, self).process(args):
            return False

        # Load the movie information into memory.
        if not os.path.isfile(args.tmdb):
            self.log("Cannot find JSON file: " + args.tmdb)
            return False

        stream = open(args.tmdb, 'r')
        self.movie = simplejson.load(stream)
        stream.close()

        # We were successful, so return true.
        return True

    def setup_arguments(self, parser):
        # Add in the argument from the base class.
        super(TmdbProcess, self).setup_arguments(parser)

        # Add the Creole-conversion specific processes.
        parser.add_argument(
            'tmdb',
            type=str,
            help='JSON file with the information about a TMDB movie.')


class IdProcess(TmdbProcess):
    """Searches themoviedb.com for the ID for a given movie."""

    def process(self, args):
        # Perform any base class processing.
        if not super(IdProcess, self).process(args):
            return

        # Set up the configuration.
        self.configure()

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

        # Set up the configuration.
        self.configure()

        url = "http://api.themoviedb.org/3/movie/{0}?api_key={1}".format(
            args.id,
            args.api_key)
        json = self.get_json(url)
        formatted = simplejson.dumps(json, indent=4, sort_keys=True)
        
        # Write out the results to either stdout or the file.
        if args.output == "-":
            print formatted
        else:
            # If the file exists, we need to check for forcing.
            if os.path.isfile(args.output) and not args.force:
                print "Cannot overwrite file: " + args.output
                return False

            # Open the stream for writing.
            stream = open(args.output, "w")
            simplejson.dump(json, stream, sort_keys=True, indent=4)
            stream.close()

        # Close the file.
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


class PosterProcess(TmdbMovieProcess):
    """Downloads the poster of for a given movie."""

    def process(self, args):
        # Perform any base class processing.
        if not super(PosterProcess, self).process(args):
            return

        # Configure the process.
        self.configure()

        # If we don't have an output parameter, we figure it out from
        # the input filename.
        output = args.output

        if not output:
            output = os.path.splitext(args.tmdb)[0] + ".jpg"

        # Check to see if the file exists.
        if os.path.isfile(output) and not args.force:
            print "Cannot overwrite file: " + output
            return False

        # Build up the path to get the image. This is described in
        # http://help.themoviedb.org/kb/api/configuration
        # http://cf2.imgobject.com/t/p/w500/mOTtuakUTb1qY6jG6lzMfjdhLwc.jpg
        url = "{0}/{1}/{2}".format(
            self.get_images_base_url(),
            args.width,
            self.movie['poster_path'])

        urllib.urlretrieve(url, output)

        self.log.info("Downloaded " + output)

    def setup_arguments(self, parser):
        # Add in the argument from the base class.
        super(PosterProcess, self).setup_arguments(parser)

        # Add the Creole-conversion specific processes.
        parser.add_argument(
            '--output', '-o',
            type=str,
            help='The filename of the image file to write. If missing, then it will be based on the input file.')
        parser.add_argument(
            '--width', '-w',
            type=str,
            default='w342',
            help='The width code for TMDB: "w92", "w154", "w185", "w342", "w500", "original"')
        parser.add_argument(
            '--force', '-f',
            action='store_true',
            help="If used, then the output will overwrite the file.")

    def get_help(self):
        return "Downloads the JSON file for a given ID and write it to a file or standard out."


class NfoProcess(TmdbMovieProcess):
    """Creates an NFO file from the cached TMDB."""

    def process(self, args):
        # Perform any base class processing.
        if not super(NfoProcess, self).process(args):
            return

        # If we don't have an output parameter, we figure it out from
        # the input filename.
        output = args.output

        if not output:
            output = os.path.splitext(args.tmdb)[0] + ".nfo"

        # Check to see if the file exists.
        if os.path.isfile(output) and not args.force:
            print "Cannot overwrite file: " + output
            return False

        # Open up the output file.
        xml = open(output, 'w')
        xml.write("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n")

        w = XMLWriter(xml, 'utf-8')
        tag = w.start("movie", ThumbGen="1")
        w.element("hasrighttoleftdirection", "false")
        w.element("title", self.movie['title'])
        w.element("originaltitle", self.movie['original_title'])
        w.element("filename", os.path.splitext(args.tmdb)[0] + ".mp4")
        w.element("tagline", self.movie['tagline'])
        w.element("releasedate", self.movie['release_date'])
        w.element("id", self.movie['imdb_id'])
        w.element("runtime", format(self.movie['runtime']))
        w.element("plot", self.movie['overview'])

        # Write out the genres.
        w.start("genre")

        for genre in self.movie['genres']:
            w.element("name", genre['name'])

        w.end()

        # Media information
        w.start("mediainfo")
        w.start("Resolution")
        w.element("Flag", "Resolution_480p")
        w.end()
        w.element("resolution", "480P")
        w.end()

        # Finish up the document.
        w.end()
        w.close(tag)
        xml.close()

        # Report that we created the file.
        self.log.info("Created " + output)

    def setup_arguments(self, parser):
        # Add in the argument from the base class.
        super(NfoProcess, self).setup_arguments(parser)

        # Add the Creole-conversion specific processes.
        parser.add_argument(
            '--output', '-o',
            type=str,
            help='The filename of the image file to write. If missing, then it will be based on the input file.')
        parser.add_argument(
            '--force', '-f',
            action='store_true',
            help="If used, then the output will overwrite the file.")

    def get_help(self):
        return "Creates a NFO file from the cached JSON file."
