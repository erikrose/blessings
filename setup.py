#!/usr/bin/env python
from setuptools import setup
import sys
import os

extra = {}

if sys.version_info < (2, 7,):
    extra.update({'install_requires': 'ordereddict'})

elif sys.version_info >= (3,):
    extra.update({'use_2to3': True})

here = os.path.dirname(__file__)
setup(
    name='blessed',
    version='1.8.5',
    description="A feature-filled fork of Erik Rose's blessings project",
    long_description=open(os.path.join(here, 'README.rst')).read(),
    author='Jeff Quast',
    author_email='contact@jeffquast.com',
    license='MIT',
    packages=['blessed', 'blessed.tests'],
    url='https://github.com/jquast/blessed',
    include_package_data=True,
    test_suite='blessed.tests',
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Environment :: Console :: Curses',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: User Interfaces',
        'Topic :: Terminals'
        ],
    keywords=['terminal', 'sequences', 'tty', 'curses', 'ncurses',
              'formatting', 'style', 'color', 'console', 'keyboard',
              'ansi', 'xterm'],
    **extra
)
