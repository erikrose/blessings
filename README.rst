==========
Blessings
==========

by Erik Rose

The Pitch
=========

curses is a fine library, but there are a couple situations where it doesn't
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
        normal = tigetstr('sgr0')
    else:
        sc = cup = rc = underline = normal = ''
    print sc  # Save cursor position.
    if cup:
        # tigetnum('lines') doesn't always update promptly, hence this:
        height = struct.unpack('hhhh', ioctl(0, TIOCGWINSZ, '\000' * 8))[0]
        print tparm(cup, height, 0)  # Move cursor to bottom.
    print 'This is {under}underlined{normal}!'.format(under=underline,
                                                      normal=normal)
    print rc  # Restore cursor position.

Phew! That was long and full of incomprehensible trash! Let's try it again,
this time with Blessings::

    from blessings import Terminal

    term = Terminal()
    with term.location(0, term.height):
        print 'This is {t.underline}underlined{t.no_underline}!'.format(t=term)

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

    from blessings import Terminal

    term = Terminal()
    print 'I am ' + term.bold + 'bold' + term.normal + '!'

Simple capabilities of interest include...

* ``bold``
* ``reverse``
* ``underline``
* ``no_underline`` (which turns off underlining)
* ``blink``
* ``normal`` (which turns off everything, even colors)
* ``clear_eol`` (clear to the end of the line)
* ``clear_bol`` (clear to beginning of line)
* ``clear_eos`` (clear to end of screen)

Here are a few more which are less likely to work on all terminals:

* ``dim``
* ``italic`` and ``no_italic``
* ``shadow`` and ``no_shadow``
* ``standout`` and ``no_standout``
* ``subscript`` and ``no_subscript``
* ``superscript`` and ``no_superscript``
* ``flash`` (which flashes the screen once)

Note that, while the inverse of ``underline`` is ``no_underline``, the only way
to turn off ``bold`` or ``reverse`` is ``normal``, which also cancels any
custom colors. This is because there's no way to tell the terminal to undo
certain pieces of formatting, even at the lowest level.

You might notice that the above aren't the typical incomprehensible terminfo
capability names; we alias a few of the harder-to-remember ones for
readability. However, you aren't limited to these: you can reference any
string-returning capability listed on the `terminfo man page`_ by the name
under the "Cap-name" column: for example, ``rum``.

.. _`terminfo man page`: http://www.manpagez.com/man/5/terminfo/

Color
-----

16 colors, both foreground and background, are available as easy-to-remember
attributes::

    from blessings import Terminal

    term = Terminal()
    print term.red + term.bg_green + 'Red on green? Ick!' + term.normal
    print term.bright_red + term.bg_bright_blue + 'This is even worse!' + term.normal

The available colors are...

* ``black``
* ``red``
* ``green``
* ``yellow``
* ``blue``
* ``magenta``
* ``cyan``
* ``white``

In addition, there is a ``bright`` version of each. If your terminal does not
support the bright palette, it will usually render them as black.

You can set the background color instead of the foreground by prepending
``bg_``, as in ``bg_blue`` or ``bg_bright_white``.

Parametrized Capabilities
-------------------------

Some capabilities take parameters. Rather than making you dig up ``tparm()``
all the time, we simply make such capabilities into callable strings. You can
pass the parameters right in::

    from blessings import Terminal

    term = Terminal()
    print term.move(10, 1)

Here are some of interest:

``move``
  Position the cursor elsewhere. Parameters are y coordinate, then x
  coordinate.
``move_x``
  Move the cursor to the given column.
``move_y``
  Move the cursor to the given row.

You can also reference any other string-returning capability listed on the
`terminfo man page`_ by its name under the "Cap-name" column.

.. _`terminfo man page`: http://www.manpagez.com/man/5/terminfo/

Height and Width
----------------

It's simple to get the height and width of the terminal, in characters::

    from blessings import Terminal

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

    from blessings import Terminal

    term = Terminal()
    with term.location(0, term.height):
        print 'Here is the bottom.'
    print 'This is back where I came from.'

Parameters to ``location()`` are ``x`` and then ``y``, but you can also pass
just one of them, leaving the other alone. For example... ::

    with term.location(y=10):
        print 'We changed just the row.'

Pipe Savvy
----------

If your program isn't attached to a terminal, like if it's being piped to
another command or redirected to a file, all the capability attributes on
``Terminal`` will return empty strings. You'll get a nice-looking file without
any formatting codes gumming up the works.

If you want to override this--like if you anticipate your program being piped
through ``less -r``, which handles terminal escapes just fine--pass
``force_styling=True`` to the ``Terminal`` constructor.

In any case, there is an ``is_a_tty`` attribute on ``Terminal`` that lets you
see whether the attached stream seems to be a terminal. If it's false, you
might refrain from drawing progress bars and other frippery, since you're
apparently headed into a pipe::

    from blessings import Terminal

    term = Terminal()
    if term.is_a_tty:
        with term.location(0, term.height):
            print 'Progress: [=======>   ]'
    print term.bold + 'Important stuff' + term.normal

Shopping List
=============

There are decades of legacy tied up in terminal interaction, so attention to
detail and behavior in edge cases make a difference. Consider which of these
features matter to you as you shop for a terminal library. Blessings has them
all.

* Output to any file-like object, not just stdout.
* Use the terminfo database so it works with any terminal type.
* Provide up-to-the-moment terminal height and width, so you can respond to
  terminal size changes (SIGWINCH signals). (Most other libraries query the
  ``COLUMNS`` and ``LINES`` environment variables or the ``cols`` or ``lines``
  terminal capabilities, which don't update promptly, if at all.)
* Avoid making a mess if the output gets piped to a non-terminal.
* Avoid introducing a new templating syntax.
* Provide convenient access to all terminal capabilities, not just a sugared
  few.
* Keep a minimum of internal state, so you can feel free to mix and match with
  calls to curses or whatever other terminal libraries you like.

Blessings does not provide...

* Native color support on the Windows command prompt. However, it should work
  when used in concert with colorama_.

.. _colorama: http://pypi.python.org/pypi/colorama/0.2.4

Bugs
====

Bugs or suggestions? Visit the `issue tracker`_.

.. _`issue tracker`: https://github.com/erikrose/blessings/issues/new

Version History
===============

1.1
  * Added nicely named attributes for colors.
  * Added ability to make capabilities non-empty, even if the output stream is
    not a terminal.
  * Added the ``is_a_tty`` attribute for telling whether the output stream is a
    terminal.
  * Added sugar for the remaining interesting string capabilities.
  * Let ``location()`` operate on just an x *or* y coordinate.

1.0
  * Extracted Blessings from nose-progressive, my `progress-bar-having,
    traceback-shortcutting, rootin', tootin' testrunner`_. It provided the
    tootin' functionality.

.. _`progress-bar-having, traceback-shortcutting, rootin', tootin' testrunner`: http://pypi.python.org/pypi/nose-progressive/
