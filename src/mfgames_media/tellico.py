"""Contains the various Tellico processing classes."""


import logging
import xml.sax
import zipfile

import mfgames_tools.process


class TellicoArchiveProcess(mfgames_tools.process.Process):
    """Extends the basic Process class to handle a single Tellico archive."""

    def __init__(self):
        super(TellicoArchiveProcess, self).__init__()
        self.archive = None

    def process(self, args):
        """Performs processing on a single Tellico file."""

        # Call the parent to process the arguments first.
        super(TellicoArchiveProcess, self).process(args)

        # Set up logging to report usage.
        log = logging.getLogger('tellico')
        log.info('Processing Tellico input: ' + args.tellico)

        # Attempt to open up the Tellico file which is a Zip-archive with
        # the tellico file inside.
        if not zipfile.is_zipfile(args.tellico):
            raise ProcessException('Cannot open Tellico input: ' + args.tellico)

        self.archive = zipfile.ZipFile(args.tellico, 'r')

        # Make sure we have a 'tellico.xml' file inside the archive.
        found = False

        for contents in self.archive.namelist():
            if contents == 'tellico.xml':
                found = True
                break

        if not found:
            raise ProcessException(
                "Could not find tellico.xml in input: " + args.tellico)

    def setup_arguments(self, parser):
        """
        Sets up the command-line arguments for the Creole to Docbook
        conversion.
        """

        super(TellicoArchiveProcess, self).setup_arguments(parser)

        # Add the Tellico file options.
        parser.add_argument(
            'tellico',
            type=str,
            help='Contains the Tellico file to process or manipulate.')


class TellicoFileProcess(
    TellicoArchiveProcess,
    xml.sax.ContentHandler):
    """
    Extends the basic Process class to handle a single Tellico XML
    inside the archive.
    """

    def __init__(self):
        super(TellicoFileProcess, self).__init__()

    def process(self, args):
        """Performs processing on a single Tellico file."""

        # Call the parent to process the arguments first.
        super(TellicoFileProcess, self).process(args)
        tellico_xml = self.archive.open('tellico.xml', 'r')

        # Set up logging to report usage.
        log = logging.getLogger('tellico')
        log.info('Processing Tellico XML')

        # Open the tellico.xml file inside the archive and process it
        # using SAX callbacks. Extending classes need to override the
        # various SAX processing methods.
        parser = xml.sax.make_parser()
        parser.setContentHandler(self)
        parser.parse(tellico_xml)

        # Finish up the XML processing.
        log.info('Finished processing Tellico XML')
        

class StatsProcess(TellicoFileProcess):
    """Parses the Tellico file and generates various statistics."""

    def __init__(self):
        super(StatsProcess, self).__init__()
        self.field_count = 0
        self.entry_count = 0

    def process(self, args):
        """Analyzes the Tellico archive and returns some statistics."""

        # Call the parent to process the arguments first.
        super(StatsProcess, self).process(args)

        # Report the results of the parsing.
        print(' Fields: {0}'.format(self.field_count))
        print('Entries: {0}'.format(self.entry_count))

    def get_help(self):
        """Returns the help line for the process."""
        return 'Converts Creole files into Docbook 5.'

    def startElement(self, name, attrs):
        """Processes the start of the XML element."""

        if name == "field":
            self.field_count = self.field_count + 1

        if name == "entry":
            self.entry_count = self.entry_count + 1
