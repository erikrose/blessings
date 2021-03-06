=========
Blessings
=========

Coding with Blessings looks like this...

.. code:: python

    from blessings import Terminal

    t = Terminal()

    print(t.bold('Hi there!'))
    print(t.bold_red_on_bright_green('It hurts my eyes!'))

    with t.location(0, t.height - 1):
        print('This is at the bottom.')

Or, for byte-level control, you can drop down and play with raw terminal
capabilities:

.. code:: python

    print('{t.bold}All your {t.red}bold and red base{t.normal}'.format(t=t))
    print(t.wingo(2))

`Full API Reference <https://blessings.readthedocs.io/>`_

The Pitch
=========

Blessings lifts several of curses_' limiting assumptions, and it makes your
code pretty, too:

* Use styles, color, and maybe a little positioning without necessarily
  clearing the whole
  screen first.
* Leave more than one screenful of scrollback in the buffer after your program
  exits, like a well-behaved command-line app should.
* Get rid of all those noisy, C-like calls to ``tigetstr`` and ``tparm``, so
  your code doesn't get crowded out by terminal bookkeeping.
* Act intelligently when somebody redirects your output to a file, omitting the
  terminal control codes the user doesn't want to see (optional).

.. _curses: http://docs.python.org/library/curses.html

Before And After
----------------

Without Blessings, this is how you'd print some underlined text at the bottom
of the screen:

.. code:: python

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

That was long and full of incomprehensible trash! Let's try it again, this time
with Blessings:

.. code:: python

    from blessings import Terminal

    term = Terminal()
    with term.location(0, term.height - 1):
        print('This is', term.underline('pretty!'))

Much better.

What It Provides
================

Blessings provides just one top-level object: ``Terminal``. Instantiating a
``Terminal`` figures out whether you're on a terminal at all and, if so, does
any necessary terminal setup. After that, you can proceed to ask it all sorts
of things about the terminal. Terminal terminal terminal.

Simple Formatting
-----------------

Lots of handy formatting codes ("capabilities" in low-level parlance) are
available as attributes on a ``Terminal``. For example...

.. code:: python

    from blessings import Terminal

    term = Terminal()
    print('I am ' + term.bold + 'bold' + term.normal + '!')

Though they are strings at heart, you can also use them as callable wrappers so
you don't have to say ``normal`` afterward:

.. code:: python

    print('I am', term.bold('bold') + '!')

Or, if you want fine-grained control while maintaining some semblance of
brevity, you can combine it with Python's string formatting, which makes
attributes easy to access:

.. code:: python

    print('All your {t.red}base {t.underline}are belong to us{t.normal}'.format(t=term))

Simple capabilities of interest include...

* ``bold``
* ``reverse``
* ``underline``
* ``no_underline`` (which turns off underlining)
* ``blink``
* ``normal`` (which turns off everything, even colors)

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
custom colors. This is because there's no portable way to tell the terminal to
undo certain pieces of formatting, even at the lowest level.

You might also notice that the above aren't the typical incomprehensible
terminfo capability names; we alias a few of the harder-to-remember ones for
readability. However, you aren't limited to these: you can reference any
string-returning capability listed on the `terminfo man page`_ by the name
under the "Cap-name" column: for example, ``term.rum``.

.. _`terminfo man page`: http://www.manpagez.com/man/5/terminfo/

Color
-----

16 colors, both foreground and background, are available as easy-to-remember
attributes:

.. code:: python

    from blessings import Terminal

    term = Terminal()
    print(term.red + term.on_green + 'Red on green? Ick!' + term.normal)
    print(term.bright_red + term.on_bright_blue + 'This is even worse!' + term.normal)

You can also call them as wrappers, which sets everything back to normal at the
end:

.. code:: python

    print(term.red_on_green('Red on green? Ick!'))
    print(term.yellow('I can barely see it.'))

The available colors are...

* ``black``
* ``red``
* ``green``
* ``yellow``
* ``blue``
* ``magenta``
* ``cyan``
* ``white``

You can set the background color instead of the foreground by prepending
``on_``, as in ``on_blue``. There is also a ``bright`` version of each color:
for example, ``on_bright_blue``.

There is also a numerical interface to colors, which takes an integer from
0-15:

.. code:: python

    term.color(5) + 'Hello' + term.normal
    term.on_color(3) + 'Hello' + term.normal

    term.color(5)('Hello')
    term.on_color(3)('Hello')

If some color is unsupported (for instance, if only the normal colors are
available, not the bright ones), trying to use it will, on most terminals, have
no effect: the foreground and background colors will stay as they were. You can
get fancy and do different things depending on the supported colors by checking
`number_of_colors`_.

.. _`number_of_colors`: https://blessings.readthedocs.io/en/latest/#blessings.Terminal.number_of_colors

Compound Formatting
-------------------

If you want to do lots of crazy formatting all at once, you can just mash it
all together:

.. code:: python

    from blessings import Terminal

    term = Terminal()
    print(term.bold_underline_green_on_yellow + 'Woo' + term.normal)

Or you can use your newly coined attribute as a wrapper, which implicitly sets
everything back to normal afterward:

.. code:: python

    print(term.bold_underline_green_on_yellow('Woo'))

This compound notation comes in handy if you want to allow users to customize
the formatting of your app: just have them pass in a format specifier like
"bold_green" on the command line, and do a quick ``getattr(term,
that_option)('Your text')`` when you do your formatting.

I'd be remiss if I didn't credit couleur_, where I probably got the idea for
all this mashing.

.. _couleur: http://pypi.python.org/pypi/couleur

Moving The Cursor
-----------------

When you want to move the cursor to output text at a specific spot, you have
a few choices.

Moving Temporarily
~~~~~~~~~~~~~~~~~~

Most often, you'll need to flit to a certain location, print something, and
then return: for example, when updating a progress bar at the bottom of the
screen. ``Terminal`` provides a context manager for doing this concisely:

.. code:: python

    from blessings import Terminal

    term = Terminal()
    with term.location(0, term.height - 1):
        print('Here is the bottom.')
    print('This is back where I came from.')

Parameters to ``location()`` are ``x`` and then ``y``, but you can also pass
just one of them, leaving the other alone. For example...

.. code:: python

    with term.location(y=10):
        print('We changed just the row.')

If you're doing a series of ``move`` calls (see below) and want to return the
cursor to its original position afterward, call ``location()`` with no
arguments, and it will do only the position restoring:

.. code:: python

    with term.location():
        print(term.move(1, 1) + 'Hi')
        print(term.move(9, 9) + 'Mom')

Note that, since ``location()`` uses the terminal's built-in
position-remembering machinery, you can't usefully nest multiple calls. Use
``location()`` at the outermost spot, and use simpler things like ``move``
inside.

Moving Permanently
~~~~~~~~~~~~~~~~~~

If you just want to move and aren't worried about returning, do something like
this:

.. code:: python

    from blessings import Terminal

    term = Terminal()
    print(term.move(10, 1) + 'Hi, mom!')

``move``
  Position the cursor elsewhere. Parameters are y coordinate, then x
  coordinate.
``move_x``
  Move the cursor to the given column.
``move_y``
  Move the cursor to the given row.

How does all this work? These are simply more terminal capabilities, wrapped to
give them nicer names. The added wrinkle--that they take parameters--is also
given a pleasant treatment: rather than making you dig up ``tparm()`` all the
time, we simply make these capabilities into callable strings. You'd get the
raw capability strings if you were to just print them, but they're fully
parametrized if you pass params to them as if they were functions.

Consequently, you can also reference any other string-returning capability
listed on the `terminfo man page`_ by its name under the "Cap-name" column.

.. _`terminfo man page`: http://www.manpagez.com/man/5/terminfo/

One-Notch Movement
~~~~~~~~~~~~~~~~~~

Finally, there are some parameterless movement capabilities that move the
cursor one character in various directions:

* ``move_left``
* ``move_right``
* ``move_up``
* ``move_down``

For example...

.. code:: python

    print(term.move_up + 'Howdy!')

Height And Width
----------------

It's simple to get the height and width of the terminal, in characters:

.. code:: python

    from blessings import Terminal

    term = Terminal()
    height = term.height
    width = term.width

These are newly updated each time you ask for them, so they're safe to use from
SIGWINCH handlers.

Clearing The Screen
-------------------

Blessings provides syntactic sugar over some screen-clearing capabilities:

``clear``
  Clear the whole screen.
``clear_eol``
  Clear to the end of the line.
``clear_bol``
  Clear backward to the beginning of the line.
``clear_eos``
  Clear to the end of screen.

For example:

.. code:: python

    print(term.clear())



Full-Screen Mode
----------------

Perhaps you have seen a full-screen program, such as an editor, restore the
exact previous state of the terminal upon exiting, including, for example, the
command-line prompt from which it was launched. Curses pretty much forces you
into this behavior, but Blessings makes it optional. If you want to do the
state-restoration thing, use these capabilities:

``enter_fullscreen``
    Switch to the terminal mode where full-screen output is sanctioned. Print
    this before you do any output.
``exit_fullscreen``
    Switch back to normal mode, restoring the exact state from before
    ``enter_fullscreen`` was used.

Using ``exit_fullscreen`` will wipe away any trace of your program's output, so
reserve it for when you don't want to leave anything behind in the scrollback.

There's also a context manager you can use as a shortcut:

.. code:: python

    from blessings import Terminal

    term = Terminal()
    with term.fullscreen():
        # Print some stuff.

Besides brevity, another advantage is that it switches back to normal mode even
if an exception is raised in the ``with`` block.

Pipe Savvy
----------

If your program isn't attached to a terminal, like if it's being piped to
another command or redirected to a file, all the capability attributes on
``Terminal`` will return empty strings. You'll get a nice-looking file without
any formatting codes gumming up the works.

If you want to override this--like if you anticipate your program being piped
through ``less -r``, which handles terminal escapes just fine--pass
``force_styling=True`` to the ``Terminal`` constructor.

In any case, there is a ``does_styling`` attribute on ``Terminal`` that lets
you see whether your capabilities will return actual, working formatting codes.
If it's false, you should refrain from drawing progress bars and other frippery
and just stick to content, since you're apparently headed into a pipe:

.. code:: python

    from blessings import Terminal

    term = Terminal()
    if term.does_styling:
        with term.location(0, term.height - 1):
            print('Progress: [=======>   ]')
    print(term.bold('Important stuff'))

Shopping List
=============

There are decades of legacy tied up in terminal interaction, so attention to
detail and behavior in edge cases make a difference. Here are some ways
Blessings has your back:

* Uses the terminfo database so it works with any terminal type
* Provides up-to-the-moment terminal height and width, so you can respond to
  terminal size changes (SIGWINCH signals). (Most other libraries query the
  ``COLUMNS`` and ``LINES`` environment variables or the ``cols`` or ``lines``
  terminal capabilities, which don't update promptly, if at all.)
* Avoids making a mess if the output gets piped to a non-terminal
* Works great with standard Python string templating
* Provides convenient access to all terminal capabilities, not just a sugared
  few
* Outputs to any file-like object, not just stdout
* Keeps a minimum of internal state, so you can feel free to mix and match with
  calls to curses or whatever other terminal libraries you like

Blessings does not provide...

* Native color support on the Windows command prompt. However, it should work
  when used in concert with colorama_.

.. _colorama: http://pypi.python.org/pypi/colorama/0.2.4

Bugs
====

Bugs or suggestions? Visit the `issue tracker`_.

.. _`issue tracker`: https://github.com/erikrose/blessings/issues/

Blessings tests are run automatically by `Travis CI`_.

.. _`Travis CI`: https://travis-ci.org/erikrose/blessings/

.. image:: https://travis-ci.org/erikrose/blessings.svg?branch=master
    :target: https://travis-ci.org/erikrose/blessings


License
=======

Blessings is under the MIT License. See the LICENSE file.

Version History
===============

1.7
  * Drop support for Python 2.6 and 3.3, which are end-of-lifed.
  * Switch from 2to3 to the ``six`` library.

1.6.1
  * Don't crash if ``number_of_colors()`` is called when run in a non-terminal
    or when ``does_styling`` is otherwise false.

1.6
  * Add ``does_styling`` property. This takes ``force_styling`` into account
    and should replace most uses of ``is_a_tty``.
  * Make ``is_a_tty`` a read-only property, like ``does_styling``. Writing to
    it never would have done anything constructive.
  * Add ``fullscreen()`` and ``hidden_cursor()`` to the auto-generated docs.
  * Fall back to ``LINES`` and ``COLUMNS`` environment vars to find height and
    width. (jquast)
  * Support terminal types, such as kermit and avatar, that use bytes 127-255
    in their escape sequences. (jquast)

1.5.1
  * Clean up fabfile, removing the redundant ``test`` command.
  * Add Travis support.
  * Make ``python setup.py test`` work without spurious errors on 2.6.
  * Work around a tox parsing bug in its config file.
  * Make context managers clean up after themselves even if there's an
    exception. (Vitja Makarov)
  * Parametrizing a capability no longer crashes when there is no tty. (Vitja
    Makarov)

1.5
  * Add syntactic sugar and documentation for ``enter_fullscreen`` and
    ``exit_fullscreen``.
  * Add context managers ``fullscreen()`` and ``hidden_cursor()``.
  * Now you can force a ``Terminal`` never to emit styles by passing
    ``force_styling=None``.

1.4
  * Add syntactic sugar for cursor visibility control and single-space-movement
    capabilities.
  * Endorse the ``location()`` idiom for restoring cursor position after a
    series of manual movements.
  * Fix a bug in which ``location()`` wouldn't do anything when passed zeroes.
  * Allow tests to be run with ``python setup.py test``.

1.3
  * Added ``number_of_colors``, which tells you how many colors the terminal
    supports.
  * Made ``color(n)`` and ``on_color(n)`` callable to wrap a string, like the
    named colors can. Also, make them both fall back to the ``setf`` and
    ``setb`` capabilities (like the named colors do) if the ANSI ``setaf`` and
    ``setab`` aren't available.
  * Allowed ``color`` attr to act as an unparametrized string, not just a
    callable.
  * Made ``height`` and ``width`` examine any passed-in stream before falling
    back to stdout. (This rarely if ever affects actual behavior; it's mostly
    philosophical.)
  * Made caching simpler and slightly more efficient.
  * Got rid of a reference cycle between Terminals and FormattingStrings.
  * Updated docs to reflect that terminal addressing (as in ``location()``) is
    0-based.

1.2
  * Added support for Python 3! We need 3.2.3 or greater, because the curses
    library couldn't decide whether to accept strs or bytes before that
    (http://bugs.python.org/issue10570).
  * Everything that comes out of the library is now unicode. This lets us
    support Python 3 without making a mess of the code, and Python 2 should
    continue to work unless you were testing types (and badly). Please file a
    bug if this causes trouble for you.
  * Changed to the MIT License for better world domination.
  * Added Sphinx docs.

1.1
  * Added nicely named attributes for colors.
  * Introduced compound formatting.
  * Added wrapper behavior for styling and colors.
  * Let you force capabilities to be non-empty, even if the output stream is
    not a terminal.
  * Added the ``is_a_tty`` attribute for telling whether the output stream is a
    terminal.
  * Sugared the remaining interesting string capabilities.
  * Let ``location()`` operate on just an x *or* y coordinate.

1.0
  * Extracted Blessings from nose-progressive, my `progress-bar-having,
    traceback-shortcutting, rootin', tootin' testrunner`_. It provided the
    tootin' functionality.

.. _`progress-bar-having, traceback-shortcutting, rootin', tootin' testrunner`: http://pypi.python.org/pypi/nose-progressive/
