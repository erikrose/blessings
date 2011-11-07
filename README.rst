==========
Blessings
==========

by Erik Rose

The Pitch
=========

curses is a great library, but there are a couple situations where it doesn't
fit:

* You want to use bold, color, and maybe a little positioning without clearing
  the whole screen first.
* You want to leave more than one screenful of scrollback in the buffer after
  your program exits.

In essence, you want to act like a well-behaved command-line app, not a
full-screen pseudo-GUI one.

If that's your use case--or even if you just want to get the noise out of your
code--Blessings is for you. Without it, this is how you'd print some
underlined text at the bottom of the screen::

    from curses import tigetstr, tigetnum, setupterm, tparm
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
        plain = tigetstr('sgr0')
    else:
        sc = cup = rc = underline = plain = ''
    print sc  # Save cursor position.
    if cup:
        # tigetnum('lines') doesn't always update promptly, hence this:
        height = struct.unpack('hhhh', ioctl(0, TIOCGWINSZ, '\000' * 8))[0]
        print tparm(cup, height, 0)  # Move cursor to bottom.
    print 'This is {under}underlined{plain}!'.format(under=underline,
                                                     plain=plain)
    print rc  # Restore cursor position.

Phew! That was long and full of incomprehensible trash! Let's try it again,
this time with Blessings::

    from terminator import Terminal

    term = Terminal()
    with term.location(0, term.height):
        print 'This is {under}underlined{plain}!'.format(under=term.underline,
                                                         plain=term.no_underline)

It's short, it's obvious, and it keeps all those nasty ``tigetstr()`` and
``tparm()`` calls out of your code. It also acts intelligently when somebody
redirects your output to a file, omitting the terminal control codes you don't
want to see.

What It Provides
================

Blessings provides just one top-level object: ``Terminal``. Instantiating a
``Terminal`` figures out whether you're on a terminal at all and, if so, does
any necessary terminal setup. After that, you can proceed to ask it all sorts
of things about the terminal. Terminal terminal terminal.

Simple Formatting
-----------------

Lots of handy formatting codes ("capabilities" in low-level parlance) are
available as attributes on ``Terminal`` instances. For example::

    from terminator import Terminal

    term = Terminal()
    print 'I am ' + term.bold + 'bold' + term.normal + '!'

Other simple capabilities of interest include...

* ``clear_eol`` (clear to the end of the line)
* ``reverse``
* ``underline``
* ``no_underline`` (which turns off underlining)
* ``normal`` (which turns off everything)

At the lowest level, there's no specific code for undoing most formatting.
Though the inverse of ``underline`` is ``no_underline``, the only way to turn
off ``bold`` or ``reverse`` is ``normal``, which also cancels any custom
colors.

Some other terminal libraries implement fancy state machines to hide this
detail, but I elected to keep Blessings easy to integrate and quick to learn.

.. note:: You might notice that these aren't the typical incomprehensible
  terminfo capability names; we alias a few (and soon more) of the
  harder-to-remember ones for readability. However, **all** capabilities are
  available: you can reference any string-returning capability listed on the
  `terminfo man page`_ by the name under the "Cap-name" column: for example,
  ``rsubm``.

  .. _`terminfo man page`: http://www.manpagez.com/man/5/terminfo/

Parametrized Capabilities
-------------------------

Some capabilities take parameters. Rather than making you dig up ``tparm()``
all the time, we simply make such capabilities into callable strings. You can
pass the parameters right in::

    from terminator import Terminal

    term = Terminal()
    print 'I am ' + term.color(2) + 'green' + term.normal + '!'

Parametrized capabilities of interest include...

* ``color`` (takes a number 0-15)
* ``bg_color`` (background color, also takes a number 0-15)

If you need more, you can also reference any string-returning capability listed
on the `terminfo man page`_ by the name under the "Cap-name" column.

.. _`terminfo man page`: http://www.manpagez.com/man/5/terminfo/

Height and Width
----------------

It's simple to get the height and width of the terminal, in characters::

    from terminator import Terminal

    term = Terminal()
    height = term.height
    width = term.width

These are newly updated each time you ask for them, so they're safe to use from
SIGWINCH handlers.

Temporary Repositioning
-----------------------

Sometimes you need to flit to a certain location, print something, and then
return: for example, when updating a progress bar at the bottom of the screen.
``Terminal`` provides a context manager for doing this concisely::

    from terminator import Terminal

    term = Terminal()
    with term.location(0, term.height):
        print 'Here is the bottom.'
    print 'This is back where I came from.'

Pipe Savvy
----------

If your program isn't attached to a terminal, like if it's being piped to
another command or redirected to a file, all the capability attributes on
``Terminal`` will return empty strings. You'll get a nice-looking file without
any formatting codes gumming up the works.

Future Plans
============

* Comb through the terminfo man page for useful capabilities with confounding
  names, and add sugary attribute names for them.
* A more mnemonic way of specifying colors. Remember that ``setaf`` and
  ``setf`` take subtly different color mappings, so maybe ``term.red`` would be
  a good idea.
* An ``is_terminal`` attr on ``Terminal`` that you can check before drawing
  progress bars and other such things that are interesting only in a terminal
  context
* A relative-positioning version of ``location()``

Bugs or suggestions? Visit the `issue tracker`_.

.. _`issue tracker`: https://github.com/erikrose/terminator/issues/new

Version History
===============

1.0
  * Extracted Blessings from nose-progressive, my `progress-bar-having,
    traceback-shortcutting, rootin', tootin' testrunner`_. It provided the
    tootin' functionality.

.. _`progress-bar-having, traceback-shortcutting, rootin', tootin' testrunner`: http://pypi.python.org/pypi/nose-progressive/
