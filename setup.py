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
    # Metadata
    name='mfgames-media',
    version='0.1.0.0',
    description='Utilities for manipulating and working with various media-related files, programs, and formats.',
    author='Dylan R. E. Moonfire',
    author_email="contact@mfgames.com",
    url='http://mfgames.com/mfgames-media',
    classifiers=[
        "Development Status :: 1 - Planning",
        "Development Status :: 2 - Pre-Alpha",
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Topic :: Artistic Software",
    ],

    # Scripts
    scripts=[
        'src/mfgames-mplayer',
        'src/mfgames-tellico',
        'src/mfgames-tmdb',
        ],

    # Packages
    packages=[
        "mfgames_media",
        "mfgames_media.mplayer",
        ],
    package_dir = {'': 'src'}
    )
