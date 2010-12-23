#!/usr/bin/env python


from distutils.core import setup


setup(
    name='mfgames-media',
    version='0.0.0.0',
    description='Utilities for media libraries and programs.',
    author='D. Moonfire',
    url='http://mfgames.com/mfgames-media',
    scripts=[
        'src/mfgames-mplayer',
        'src/mfgames-mplayer-mythtv',
#        'src/mfgames-mythtv',
#        'src/mfgames-tellico',
        ],
    data_files=[
        ('share/mfgames-media/mfgames',
         ['src/mfgames/__init__.py',
         ]),
        ('share/mfgames-media/mfgames/media',
         ['src/mfgames/media/__init__.py',
          'src/mfgames/media/mplayer.py',
         ]),
        ]
    )
