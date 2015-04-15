.. image:: https://img.shields.io/travis/erikrose/blessings.svg
    :alt: Travis Continous Integration
    :target: https://travis-ci.orgerikrose/blessings/

.. image:: https://img.shields.io/teamcity/http/teamcity-master.pexpect.org/s/Blessings_BuildHead.png
    :alt: TeamCity Build status
    :target: https://teamcity-master.pexpect.org/viewType.html?buildTypeId=Blessings_BuildHead&branch_Blessings=%3Cdefault%3E&tab=buildTypeStatusDiv

.. image:: https://coveralls.io/repos/erikrose/blessings/badge.png?branch=master
    :alt: Coveralls Code Coverage
    :target: https://coveralls.io/r/erikrose/blessings?branch=master

.. image:: https://img.shields.io/pypi/v/blessings.svg
    :alt: Latest Version
    :target: https://pypi.python.org/pypi/blessings

.. image:: https://pypip.in/license/blessings/badge.svg
    :alt: License
    :target: http://opensource.org/licenses/MIT

.. image:: https://img.shields.io/pypi/dm/blessings.svg
    :alt: Downloads
    :target: https://pypi.python.org/pypi/blessings

Introduction
============

Blessings is a thin, practical wrapper around terminal capabilities in Python.

Coding with *Blessings* looks like this... ::

    from blessings import Terminal

    t = Terminal()

    print(t.bold('Hi there!'))
    print(t.bold_red_on_bright_green('It hurts my eyes!'))

    with t.location(0, t.height - 1):
        print(t.center(t.blink('press any key to continue.')))

    with t.keystroke_input():
        inp = t.keystroke()
    print('You pressed ' + repr(inp))


The Pitch
---------

*Blessings* is a more simplified wrapper around curses_, providing :

* Styles, color, and maybe a little positioning without necessarily
  clearing the whole screen first.
* Leave more than one screenful of scrollback in the buffer after your program
  exits, like a well-behaved command-line application should.
* No more C-like calls to tigetstr_ and tparm_.
* Act intelligently when somebody redirects your output to a file, omitting
  all of the terminal sequences such as styling, colors, or positioning.
* Dead-simple keyboard handling, modeled after the Basic language's *INKEY$*


Before And After
----------------

With the built-in curses_ module, this is how you would typically
print some underlined text at the bottom of the screen::

    from curses import tigetstr, setupterm, tparm
    from fcntl import ioctl
    from os import isatty
    import struct
    import sys
    from termios import TIOCGWINSZ

    # If we want to tolerate having our output piped to other commands or
    # files without crashing, we need to do all this branching:
    if hasattr(sys.stdout, 'fileno') and isatty(sys.stdout.fileno()):
        setupterm()
        sc = tigetstr('sc')
        cup = tigetstr('cup')
        rc = tigetstr('rc')
        underline = tigetstr('smul')
        normal = tigetstr('sgr0')
    else:
        sc = cup = rc = underline = normal = ''
    print(sc)  # Save cursor position.
    if cup:
        # tigetnum('lines') doesn't always update promptly, hence this:
        height = struct.unpack('hhhh', ioctl(0, TIOCGWINSZ, '\000' * 8))[0]
        print(tparm(cup, height - 1, 0))  # Move cursor to bottom.
    print('This is {under}underlined{normal}!'.format(under=underline,
                                                      normal=normal))
    print(rc)  # Restore cursor position.

The same program with *Blessings* is simply::

    from blessings import Terminal

    term = Terminal()
    with term.location(0, term.height - 1):
        print('This is' + term.underline('pretty!'))


Brief Overview
--------------

There are decades of legacy tied up in terminal interaction, so attention to
detail and behavior in edge cases make a difference. Here are some ways
*Blessings* has your back:

* Uses the `terminfo(5)`_ database so it works with any terminal type.
* Provides up-to-the-moment terminal height and width, so you can respond to
  terminal size changes (*SIGWINCH* signals): Most other libraries query the
  ``COLUMNS`` and ``LINES`` environment variables or the ``cols`` or ``lines``
  terminal capabilities, which don't update promptly, if at all.
* Avoids making a mess if the output gets piped to a non-terminal.
* Works great with standard Python string formatting.
* Provides convenient access to **all** terminal capabilities.
* Outputs to any file-like object (*StringIO*, file), not just *stdout*.
* Keeps a minimum of internal state, so you can feel free to mix and match with
  calls to curses or whatever other terminal libraries you like.
* Safely decodes internationalization keyboard input to their unicod e
  equivalents.
* Safely decodes multibyte sequences for application/arrow keys.
* Allows the printable length of strings containing sequences to be determined.
* Provides plenty of context managers to safely express various terminal modes,
  restoring to a safe state upon exit.

Blessings does not provide...

* Native color support on the Windows command prompt.  A PDCurses_ build
  of python for windows provides only partial support at this time -- there
  are plans to merge with the ansi_ module in concert with colorama_ to
  resolve this.  `Patches welcome
  <https://github.com/erikrose/blessings/issues/21>`_!

Further Documentation
---------------------

More documentation can be found at http://blessings.readthedocs.org/

Developers, Bugs
----------------

Bugs or suggestions? Visit the `issue tracker`_.

Pull requests require test coverage, we aim for 100% test coverage.

License
-------

Blessings is under the MIT License. See the LICENSE file.

.. _`issue tracker`: https://github.com/erikrose/blessings/issues/
.. _curses: https://docs.python.org/library/curses.html
.. _tigetstr: http://www.openbsd.org/cgi-bin/man.cgi?query=tigetstr&sektion=3
.. _tparm: http://www.openbsd.org/cgi-bin/man.cgi?query=tparm&sektion=3
.. _ansi: https://github.com/tehmaze/ansi
.. _colorama: https://pypi.python.org/pypi/colorama
.. _PDCurses: http://www.lfd.uci.edu/~gohlke/pythonlibs/#curses
.. _`terminfo(5)`: http://invisible-island.net/ncurses/man/terminfo.5.html
