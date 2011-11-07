import sys

from setuptools import setup, find_packages


extra_setup = {}
if sys.version_info >= (3,):
    extra_setup['use_2to3'] = True

setup(
    name='terminator',
    version='1.0.1',
    description='A thin, practical wrapper around terminal formatting, positioning, and more',
    long_description=open('README.rst').read(),
    author='Erik Rose',
    author_email='erikrose@grinchcentral.com',
    license='GPL',
    packages=find_packages(exclude=['ez_setup']),
    tests_require=['Nose'],
    url='http://pypi.python.org/pypi/terminator/',
    include_package_data=True,
    classifiers = [
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Environment :: Console',
        'Operating System :: POSIX',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: User Interfaces',
        'Topic :: Terminals'
        ],
    **extra_setup
)
