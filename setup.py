#!/usr/bin/env python

#
# Imports
#

# System Imports
from distutils.core import setup

#
# Setup
#

setup(
    name='mfgames-media',
    version='0.0.0.0',
    description='Utilities for media libraries and programs.',
    author='D. Moonfire',
    url='http://mfgames.com/mfgames-media',
    scripts=[
        'src/mfgames-mplayer',
        'src/mfgames-mythtv',
        ],
#    data_files=[
#        ('share/mfgames-media/media', [
#            'src/media/__init__.py',
#            'src/media/some_file.py',
#            ]),
#        ],
    )
