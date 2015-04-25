#!/usr/bin/env python
import subprocess
import sys
from os import getenv
from os.path import dirname, join

import setuptools
import setuptools.command.develop
import setuptools.command.test


class SetupDevelop(setuptools.command.develop.develop):
    """Docstring is overwritten."""

    def run(self):
        """
        Prepare environment for development.

        - Ensures a virtualenv environmnt is used.
        - Ensures tox, ipython, wheel is installed for convenience and testing.
        - Call super()'s run method.
        """
        assert getenv('VIRTUAL_ENV'), 'You should be in a virtualenv'
        subprocess.check_call(('pip', 'install', 'tox', 'ipython', 'wheel'))

        # Call super() (except develop is an old-style class, so we must call
        # directly). The effect is that the development egg-link is installed.
        setuptools.command.develop.develop.run(self)

SetupDevelop.__doc__ = setuptools.command.develop.develop.__doc__


class SetupTest(setuptools.command.test.test):
    """Docstring is overwritten."""

    def run(self):
        """Spawn tox."""
        self.spawn(('tox',))

SetupTest.__doc__ = setuptools.command.test.test.__doc__

kwargs = {
    'install_requires': [
        'wcwidth>=0.1.4',
        'six>=1.9.0',
    ]
}

if sys.version_info < (2, 7):
    # we make use of collections.ordereddict: for python 2.6 we require the
    # assistance of the 'orderddict' module which backports the same.
    kwargs['install_requires'].extend(['ordereddict>=1.1'])

setuptools.setup(
    name='blessings',
    version='1.9.5',
    description=('A thin, practical wrapper around terminal coloring, '
                 'styling, positioning, and keyboard input.'),
    long_description=open(join(dirname(__file__),
                               'docs', 'intro.rst')).read(),
    author='Erik Rose, Jeff Quast',
    author_email='erikrose@grinchcentral.com',
    license='MIT',
    packages=['blessings', 'blessings.tests'],
    url='https://github.com/erikrose/blessings',
    include_package_data=True,
    test_suite='blessings.tests',
    zip_safe=True,
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
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: User Interfaces',
        'Topic :: Terminals'
    ],
    keywords=['terminal', 'sequences', 'tty', 'curses', 'ncurses',
              'formatting', 'style', 'color', 'console', 'keyboard',
              'ansi', 'xterm'],
    cmdclass={'develop': SetupDevelop,
              'test': SetupTest},
    **kwargs
)
