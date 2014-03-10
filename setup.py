#!/usr/bin/env python
from setuptools import setup, find_packages, Command
from setuptools.command.develop import develop
from setuptools.command.test import test
import sys
import os

extra = {}

if sys.version_info < (2, 7,):
    extra.update({'install_requires': 'ordereddict'})

elif sys.version_info >= (3,):
    extra.update({'use_2to3': True})

#    try:
#        import setuptools
#    except ImportError:
#        from distribute_setup import use_setuptools
#        use_setuptools()
#
#
#
#dev_requirements = ['pytest', 'pytest-cov', 'pytest-pep8',
#                    'pytest-flakes', 'pytest-sugar', 'mock']
#

#class PyTest(test):
#
#    def initialize_options(self):
#        test.initialize_options(self)
#        test_suite = True
#
#    def finalize_options(self):
#        test.finalize_options(self)
#        self.test_args = ['-x', '--strict', '--pep8', '--flakes',
#                          '--cov', 'blessed', '--cov-report', 'html',
#                          '--pyargs', 'blessed.tests']
#
#    def run(self):
#        import pytest
##        import blessed.tests
##        print ('*')
##        print(blessed.tests.__file__)
##        print ('*')
#        raise SystemExit(pytest.main(self.test_args))


#class SetupDevelop(develop):
#    """Setup development environment suitable for testing."""
#
#    def finalize_options(self):
#        assert os.getenv('VIRTUAL_ENV'), "Please use virtualenv."
#        develop.finalize_options(self)
#
#    def run(self):
#        import subprocess
#        reqs = dev_requirements
#        reqs.extend(extra_setup['requires'])
#        if extra_setup.get('use_2to3', False):
#            # install in virtualenv, via 2to3 mechanism
#            reqs.append(self.distribution.get_name())
#        subprocess.check_call('pip install {reqs}'
#                              .format(reqs=u' '.join(reqs)),
#                              shell=True)
#        develop.run(self)

here = os.path.dirname(__file__)
setup(
    name='blessed',
    version='1.7',
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
    **extra
)
