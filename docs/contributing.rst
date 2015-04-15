Contributing
============

Contributors should create a GitHub account if they do not have one.
If you are opposed to having a GitHub account, you may e-mail the
maintainers a patch, though it reduces the chance of being accepted).

How to make a pull request
--------------------------

All aspects of using git and GitHub is well-documented by GitHub:

- `Fork a Repo <https://help.github.com/articles/fork-a-repo/>`_
- `Creating a pull request
  <https://help.github.com/articles/creating-a-pull-request/>`_

Preparing a Developer Environment
---------------------------------

Install git, python2, python3, pip, then virtualenvwrapper::

    pip install virtualenvwrapper

Then, Load virtualenvwrapper and prepare a developer environment
for blessings.  From the blessings code folder::

    . `which virtualenvwrapper.sh`
    mkvirtualenv blessings
    pip install --editable .

Running tests
-------------

::
        tox

Test Coverage
-------------

Blessings has 99% code coverage.  New features will not be accepted
without coverage. Bugfixes will not be accepted without a complimentary
test that demonstrates the bug.

Style, static analysis
----------------------

The test runner (``tox``) ensures all code and documentation complies
with standard python style guides, pep8 and pep257, as well as various
static analysis tools.
