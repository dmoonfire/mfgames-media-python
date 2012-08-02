"""Common functionality for MPlayer functionality."""


import subprocess
import logging
import mfgames_tools.process
import os
import simplejson


class JsonProcess(mfgames_tools.process.Process):
    def __init__(self):
        super(JsonProcess, self).__init__()

    def get_help(self):
        return "Update a JSON file with metadata from MPlayer."

    def process(self, args):
        # Handle the base class' processing.
        super(JsonProcess, self).process(args)

        # Logging to report the status.
        log = logging.getLogger("json")

        # Make sure the file exists.
        if not os.path.isfile(args.video):
            log.error("Video file does not exist: {0}".format(args.video))
            exit(1)

        log.info("Parsing video file: " + args.video)

        # Figure out the JSON file if it wasn't included in the arguments.
        if not args.json:
            basename=os.path.splitext(args.video)[0]
            args.json = basename + ".json"

        # Check to see if the JSON file exists.
        if args.json == "-":
            json = {}
        elif os.path.isfile(args.json):
            log.info("Using JSON file: " + args.json)
            stream = open(args.json, 'r')
            json = simplejson.load(stream)
            stream.close()
        else:
            log.info("Creating JSON file: " + args.json)
            json = {}

        # If the file exists, we need to check for forcing.
        if "enable-mplayer" in json and not args.force:
            log.info("Information already cached, skipping")
            return False

        # Put in the enable flag.
        json["enable-mplayer"] = True
        json["mplayer"] = {}

        # Figure out the command we'll be running.
        commands = [
            "mplayer",
            "-identify",
            "-frames", "0",
            "-vc", "null",
            "-vo", "null",
            "-ao", "null",
            "-msglevel", "all=-1",
            args.video];

        process = subprocess.Popen(
            commands,
            shell=False,
            close_fds=True,
            bufsize=0,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)

        for line in process.stdout:
            # Ignore non-ID lines.
            if not line.startswith("ID_"):
                continue

            # Split out the two parts of the line.
            [key, value] = line.split('=')

            # Clean out the white space, remove the "ID_" in front of
            # it, convert everything to lowercase and change "_" to
            # "-".
            key = key.strip()
            key = key[3:]
            key = key.lower()
            key = key.replace("_", "-")

            value = value.strip()

            # Ignore filenames since we can move the file.
            if key.endswith("filename"):
                continue
            
            # Put the key into the value.
            json["mplayer"][key] = value

        process.stdout.close()

        # Now that we are done, get the formatted JSON file.
        formatted = simplejson.dumps(json, indent=4, sort_keys=True)

        # Figure out how to output the file.
        if not args.output:
            args.output = args.json

        if args.output == "-":
            # Just print it to the output.
            print formatted
        else:
            # Open the stream for writing.
            stream = open(args.output, "w")
            simplejson.dump(json, stream, sort_keys=True, indent=4)
            stream.close()

    def setup_arguments(self, parser):
        # Add in the argument from the base class.
        super(JsonProcess, self).setup_arguments(parser)

        # Add in the text-specific generations.
        parser.add_argument(
            'video',
            type=str,
            help='Movie file to play.')
        parser.add_argument(
            'json',
            type=str,
            nargs="?",
            help='Movie file to play.')
        parser.add_argument(
            '--output', '-o',
            default=None,
            type=str,
            help='Optional output file for JSON.')
        parser.add_argument(
            '--force', '-f',
            default=False,
            action="store_true",
            help='If set, then overwrite the JSON file.')
