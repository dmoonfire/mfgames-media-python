"""Contains the various Lirc processing classes."""


import logging
import os

import mfgames.tools.process


class ConvertToTabSeparatedValues(mfgames.tools.process.Process):
    """Converts the given input file into a tab separated values."""

    def __init__(self):
        super(ConvertToTabSeparatedValues, self).__init__()
        self.archive = None

    def process(self, args):
        """Converts the input Lirc file into tab values."""

        # Call the parent to process the arguments first.
        super(ConvertToTabSeparatedValues, self).process(args)

        # Set up logging to report usage.
        log = logging.getLogger('tabs')
        log.info('Processing Lirc input: ' + args.input.name)

        # Open up the file which is a formatted text file. Since
        # we don't expect the file to be huge, we just load
        # everything up into memory.
        contents = args.input.readlines()

        # Create a header with the standard fields we use.
        header = []
        header.append("prog")
        header.append("button")
        header.append("config")

        # Create a list of lines we are writing out since we want
        # to output the generated header first.
        lines = []
        
        # Loop through the lines in the file.
        records = []
        record = {}

        for block in contents:
            # Trim the newlines at the beginning and end of
            # each line.
            block = block.strip()
            
            # Skip blank lines.
            if block == "" or block[0] == "#":
                continue
            
            # We don't worry about begins, only end.
            if block == "begin":
                continue
            
            # If we hit the end, then we want to move to the
            # next line in the file.
            if block == "end":
                records.append(record)
                record = {}
                continue

            # Otherwise, split this on the equal sign.
            parts = block.split("=", 2)
            key = parts[0].strip()
            value = parts[1].strip()

            # If we don't have the header in the list, then we
            # need to append it.
            if key not in header:
                header.append(key)

            # Add the value into the record at the right location.
            index = header.index(key)
            record[index] = value

        # Write out the contents of the file.
        with open(args.output, 'w+') as output:
            # Write out the header.
            output.write("\t".join(header) + "\n")

            # Go through each of the records.
            for record in records:
                # Write out the fields in the same orders.
                for index in range(len(header)):
                    # Check to see if we have data in the record.
                    # If we do, write it out to the output.
                    if index in record:
                        output.write(record[index])

                    # Add a tab or newline depending if we are at
                    # the last header record.
                    if index == len(header) - 1:
                        output.write("\n")
                    else:
                        output.write("\t")
                    
    def setup_arguments(self, parser):
        """
        Sets up the command-line arguments for the tab
        conversion process.
        """

        super(ConvertToTabSeparatedValues, self).setup_arguments(parser)

        # Add the Tellico file options.
        parser.add_argument(
            'input',
            type=file,
            help='Contains the input Lirc file to process or manipulate.')
        parser.add_argument(
            'output',
            type=str,
            help='The destination file for the resulting file.')

    def get_help(self):
        """Returns the help line for the process."""
        return 'Converts Lirc files into tab seperated values.'


class ConvertToLirc(mfgames.tools.process.Process):
    """Converts the given tab-separated values into a Lirc configuration file."""

    def __init__(self):
        super(ConvertToLirc, self).__init__()
        self.archive = None

    def process(self, args):
        """Converts the input Lirc file into tab values."""

        # Call the parent to process the arguments first.
        super(ConvertToLirc, self).process(args)

        # Set up logging to report usage.
        log = logging.getLogger('tabs')
        log.info('Processing TSV input: ' + args.input.name)

        # Open up the file which is a formatted text file. Since
        # we don't expect the file to be huge, we just load
        # everything up into memory.
        contents = args.input.readlines()

        # Pull off the first record and parse it for key values.
        header = contents.pop(0).split("\t")

        # Open up a handle to the output file.
        with open(args.output, 'w+') as output:
            # Go through the contents and write out each field
            # on its own separate line.
            for line in contents:
                # Write out the begin record.
                output.write("begin\n")

                # Go through all the fields.
                record = line.split("\t")

                for index in range(len(record)):
                    key = header[index].strip()
                    value = record[index].strip()

                    if not value == '':
                        output.write(
                            "\t" + key + " = " + value + "\n")

                # Finish up the record.
                output.write("end\n")
                    
    def setup_arguments(self, parser):
        """
        Sets up the command-line arguments for the tab
        conversion process.
        """

        super(ConvertToLirc, self).setup_arguments(parser)

        # Add the Tellico file options.
        parser.add_argument(
            'input',
            type=file,
            help='Contains the input tab file to process or manipulate.')
        parser.add_argument(
            'output',
            type=str,
            help='The destination file for the resulting file.')

    def get_help(self):
        """Returns the help line for the process."""
        return 'Converts tab-separated values into a Lirc configuration.'
