"""Run this using ``fabric``.

I can't remember any of this syntax on my own.

"""
import functools
import os

from fabric.api import local, cd


local = functools.partial(local, capture=False)

NAME = os.path.basename(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.dirname(__file__))

os.environ['PYTHONPATH'] = (((os.environ['PYTHONPATH'] + ':') if
    os.environ.get('PYTHONPATH') else '') + ROOT)


def doc(kind='html'):
    """Build Sphinx docs.

    Requires Sphinx to be installed.

    """
    with cd('docs'):
        local('make clean %s' % kind)

def test():
    # Just calling nosetests results in SUPPORTS_TRANSACTIONS KeyErrors.
    local('nosetests')

def updoc():
    """Build Sphinx docs and upload them to packages.python.org.

    Requires Sphinx-PyPI-upload to be installed.

    """
    doc('html')
    local('python setup.py upload_sphinx --upload-dir=docs/_build/html')
