import sys

from setuptools import setup, find_packages


extra_setup = {}
if sys.version_info >= (3,):
    extra_setup['use_2to3'] = True

setup(
    name='blessings',
    version='1.2',
    description='A thin, practical wrapper around terminal formatting, positioning, and more',
    long_description=open('README.rst').read(),
    author='Erik Rose',
    author_email='erikrose@grinchcentral.com',
    license='GPL',
    packages=find_packages(exclude=['ez_setup']),
    tests_require=['Nose'],
    url='https://github.com/erikrose/blessings',
    include_package_data=True,
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Environment :: Console',
        'Environment :: Console :: Curses',
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
    keywords=['terminal', 'tty', 'curses', 'ncurses', 'formatting', 'color', 'console'],
    **extra_setup
)
