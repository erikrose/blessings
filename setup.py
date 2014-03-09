#!/usr/bin/env python
from setuptools import setup, find_packages, Command
from setuptools.command.develop import develop
import sys
import os

extra_setup = {}
if sys.version_info >= (3,):
    extra_setup['use_2to3'] = True
if sys.version_info <= (2, 7,):
    extra_setup['requires'] = ['ordereddict']

here = os.path.dirname(__file__)
dev_requirements = ['pytest', 'pytest-cov', 'pytest-pep8',
                    'pytest-flakes', 'pytest-sugar', 'mock']


class PyTest(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import subprocess
        test_files = os.path.join(here, 'tests')
        errno = subprocess.call(['py.test', '-x', '--strict',
                                 '--pep8', '--flakes',
                                 '--cov', 'blessed',
                                 '--cov-report', 'html',
                                 test_files])
        raise SystemExit(errno)

class SetupDevelop(develop):
    """Setup development environment suitable for testing."""

    def finalize_options(self):
        assert os.getenv('VIRTUAL_ENV'), "Use a virtualenv for this option."
        develop.finalize_options(self)

    def run(self):
        import subprocess
        subprocess.check_call('pip install {reqs}'
                              .format(reqs=u' '.join(dev_requirements)),
                              shell=True)
        develop.run(self)

setup(
    name='blessed',
    version='1.7',
    description="A feature-filled fork of Erik Rose's blessings project",
    long_description=open('README.rst').read(),
    author='Jeff Quast',
    author_email='contact@jeffquast.com',
    license='MIT',
    packages=find_packages(exclude=['ez_setup']),
    tests_require=dev_requirements,
    cmdclass={'test': PyTest, 'develop': SetupDevelop},
    url='https://github.com/jquast/blessed',
    include_package_data=True,
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Environment :: Console :: Curses',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.5',
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
    **extra_setup
)
