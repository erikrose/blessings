Contributing
============

We welcome contributions via GitHub pull requests:

- `Fork a Repo <https://help.github.com/articles/fork-a-repo/>`_
- `Creating a pull request
  <https://help.github.com/articles/creating-a-pull-request/>`_

Developing
----------

Prepare a developer environment.  Then, from the blessed code folder::

    pip install --editable .

Any changes made in this project folder are then made available to the python
interpreter as the 'blessed' package from any working directory.

Running Tests
~~~~~~~~~~~~~

Install and run tox

::

    pip install --upgrade tox
    tox

Py.test is used as the test runner, supporting positional arguments, you may
for example use `looponfailing
<https://pytest.org/latest/xdist.html#running-tests-in-looponfailing-mode>`_
with python 3.5, stopping at the first failing test case, and looping
(retrying) after a filesystem save is detected::

    tox -epy35 -- -fx


Test Coverage
~~~~~~~~~~~~~

When you contribute a new feature, make sure it is covered by tests.
Likewise, a bug fix should include a test demonstrating the bug.  Blessed has
nearly 100% line coverage, with roughly 1/2 of the codebase in the form of
tests, which are further combined by a matrix of varying ``TERM`` types,
providing plenty of existing test cases to augment or duplicate in your
favor.

Style and Static Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~

The test runner (``tox``) ensures all code and documentation complies
with standard python style guides, pep8 and pep257, as well as various
static analysis tools through the **sa** target, invoked using::

    tox -esa

All standards enforced by the underlying style checker tools are adhered to,
with the declarative exception of those found in `landscape.yml
<https://github.com/jquast/blessed/blob/master/.landscape.yml>`_, or inline
using ``pylint: disable=`` directives.
