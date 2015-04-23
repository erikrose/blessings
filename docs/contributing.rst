Contributing
============

We welcome contributions via GitHub pull requests:

- `Fork a Repo <https://help.github.com/articles/fork-a-repo/>`_
- `Creating a pull request
  <https://help.github.com/articles/creating-a-pull-request/>`_

Developing
----------

Install git, Python 2, Python 3, pip.

Then, from the blessings code folder::

    pip install virtualenvwrapper
    . `which virtualenvwrapper.sh`
    mkvirtualenv blessings
    pip install --editable .

Running Tests
~~~~~~~~~~~~~

::

    tox

Test Coverage
~~~~~~~~~~~~~

Blessings has 99% code coverage, and we'd like to keep it that way, as
terminals are fiddly beasts. Thus, when you contribute a new feature, make sure
it is covered by tests. Likewise, a bug fix should include a test demonstrating
the bug.

Style and Static Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~

The test runner (``tox``) ensures all code and documentation complies
with standard python style guides, pep8 and pep257, as well as various
static analysis tools.
