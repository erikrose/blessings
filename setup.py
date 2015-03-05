# Prevent spurious errors during `python setup.py test` in 2.6 and 2.7, a la
# http://www.eby-sarna.com/pipermail/peak/2010-May/003357.html:
try:
    import multiprocessing
except ImportError:
    pass
from os.path import dirname, join
from sys import exit, version_info

from setuptools.command.test import test as TestCommand
from setuptools import setup


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = ['blessings/tests']
        self.test_suite = True

    def run_tests(self):
        import pytest
        exit(pytest.main(self.test_args))


conditional_requirements = (['ordereddict>=1.1']
                            if version_info < (2, 7) else [])


setup(
    name='blessings',
    version='1.9.5',
    description='A thin, practical wrapper around terminal coloring, '
                'styling, positioning, and keyboard input.',
    long_description=open(join(dirname(__file__), 'README.rst')).read(),
    author='Erik Rose, Jeff Quast',
    author_email='erikrose@grinchcentral.com',
    license='MIT',
    packages=['blessings', 'blessings.tests'],
    url='https://github.com/erikrose/blessings',
    include_package_data=True,
    test_suite='blessings.tests',
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
    keywords=['terminal', 'sequences', 'tty', 'curses', 'ncurses', 'xterm',
              'formatting', 'style', 'color', 'console', 'keyboard', 'ansi'],
    cmdclass={'test': PyTest},
    install_requires=['wcwidth>=0.1.0'] + conditional_requirements,
    tests_require=['mock', 'pytest']
)
