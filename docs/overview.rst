Overview
========

Blessings provides just **one** top-level object: *Terminal*. Instantiating a
*Terminal* figures out whether you're on a terminal at all and, if so, does
any necessary setup. After that, you can proceed to ask it all sorts of things
about the terminal, such as its size and color support, and use its styling
to construct strings containing color and styling. Also, the special sequences
inserted with application keys (arrow and function keys) are understood and
decoded, as well as your locale-specific encoded multibyte input, such as
utf-8 characters.


Simple Formatting
-----------------

Lots of handy formatting codes are available as attributes on a *Terminal* class
instance. For example::

    from blessings import Terminal

    term = Terminal()
    print('I am ' + term.bold + 'bold' + term.normal + '!')

These capabilities (*bold*, *normal*) are translated to their sequences, which
when displayed simply change the video attributes.  And, when used as a callable,
automatically wraps the given string with this sequence, and terminates it with
*normal*.

The same can be written as::

    print('I am' + term.bold('bold') + '!')

You may also use the *Terminal* instance as an argument for ``.format`` string
method, so that capabilities can be displayed in-line for more complex strings::

    print('{t.red_on_yellow}Candy corn{t.normal} for everyone!'.format(t=term))


Capabilities
------------

The basic capabilities supported by most terminals are:

``bold``
  Turn on 'extra bright' mode.
``reverse``
  Switch fore and background attributes.
``blink``
  Turn on blinking.
``normal``
  Reset attributes to default.

The less commonly supported capabilities:

``dim``
  Enable half-bright mode.
``underline``
  Enable underline mode.
``no_underline``
  Exit underline mode.
``italic``
  Enable italicized text.
``no_italic``
  Exit italics.
``shadow``
  Enable shadow text mode (rare).
``no_shadow``
  Exit shadow text mode.
``standout``
  Enable standout mode (often, an alias for ``reverse``.).
``no_standout``
  Exit standout mode.
``subscript``
  Enable subscript mode.
``no_subscript``
  Exit subscript mode.
``superscript``
  Enable superscript mode.
``no_superscript``
  Exit superscript mode.
``flash``
  Visual bell, flashes the screen.

Note that, while the inverse of *underline* is *no_underline*, the only way
to turn off *bold* or *reverse* is *normal*, which also cancels any custom
colors.

Many of these are aliases, their true capability names (such as 'smul' for
'begin underline mode') may still be used. Any capability in the `terminfo(5)`_
manual, under column **Cap-name**, may be used as an attribute to a *Terminal*
instance. If it is not a supported capability, or a non-tty is used as an
output stream, an empty string is returned.


Colors
------

Color terminals are capable of at least 8 basic colors.

* ``black``
* ``red``
* ``green``
* ``yellow``
* ``blue``
* ``magenta``
* ``cyan``
* ``white``

The same colors, prefixed with *bright_* (synonymous with *bold_*),
such as *bright_blue*, provides 16 colors in total.

The same colors, prefixed with *on_* sets the background color, some
terminals also provide an additional 8 high-intensity versions using
*on_bright*, some example compound formats::

    from blessings import Terminal

    term = Terminal()

    print(term.on_bright_blue('Blue skies!'))
    print(term.bright_red_on_bright_yellow('Pepperoni Pizza!'))

There is also a numerical interface to colors, which takes an integer from
0-15.::

    from blessings import Terminal

    term = Terminal()

    for n in range(16):
        print(term.color(n)('Color {}'.format(n)))

If the terminal defined by the **TERM** environment variable does not support
colors, these simply return empty strings, or the string passed as an argument
when used as a callable, without any video attributes. If the **TERM** defines
a terminal that does support colors, but actually does not, they are usually
harmless.

Colorless terminals, such as the amber or green monochrome *vt220*, do not
support colors but do support reverse video. For this reason, it may be
desirable in some applications, such as a selection bar, to simply select
a foreground color, followed by reverse video to achieve the desired
background color effect::

    from blessings import Terminal

    term = Terminal()

    print('some terminals {standout} more than others'.format(
        standout=term.green_reverse('standout')))

Which appears as *bright white on green* on color terminals, or *black text
on amber or green* on monochrome terminals.

You can check whether the terminal definition used supports colors, and how
many, using the ``number_of_colors`` property, which returns any of *0*,
*8* or *256* for terminal types such as *vt220*, *ansi*, and
*xterm-256color*, respectively.

**NOTE**: On most color terminals, unlink *black*, *bright_black* is not
invisible -- it is actually a very dark shade of gray!

Compound Formatting
-------------------

If you want to do lots of crazy formatting all at once, you can just mash it
all together::

    from blessings import Terminal

    term = Terminal()

    print(term.bold_underline_green_on_yellow('Woo'))

I'd be remiss if I didn't credit couleur_, where I probably got the idea for
all this mashing.  This compound notation comes in handy if you want to allow
users to customize formatting, just allow compound formatters, like *bold_green*,
as a command line argument or configuration item::

    #!/usr/bin/env python
    import argparse

    parser = argparse.ArgumentParser(
        description='displays argument as specified style')
    parser.add_argument('style', type=str, help='style formatter')
    parser.add_argument('text', type=str, nargs='+')

    from blessings import Terminal

    term = Terminal()
    args = parser.parse_args()

    style = getattr(term, args.style)

    print(style(' '.join(args.text)))

Saved as **tprint.py**, this could be called simply::

    $ ./tprint.py bright_blue_reverse Blue Skies


Moving The Cursor
-----------------

When you want to move the cursor, you have a few choices, the
``location(x=None, y=None)`` context manager, ``move(y, x)``, ``move_y(row)``,
and ``move_x(col)`` attributes.

**NOTE**: The ``location()`` method receives arguments in form of *(x, y)*,
whereas the ``move()`` argument receives arguments in form of *(y, x)*.  This
is a flaw in the original `erikrose/blessings`_ implementation, but remains
for compatibility.

Moving Temporarily
~~~~~~~~~~~~~~~~~~

A context manager, ``location()`` is provided to move the cursor to an
*(x, y)* screen position and restore the previous position upon exit::

    from blessings import Terminal

    term = Terminal()
    with term.location(0, term.height - 1):
        print('Here is the bottom.')
    print('This is back where I came from.')

Parameters to ``location()`` are **optional** *x* and/or *y*::

    with term.location(y=10):
        print('We changed just the row.')

When omitted, it saves the cursor position and restore it upon exit::

    with term.location():
        print(term.move(1, 1) + 'Hi')
        print(term.move(9, 9) + 'Mom')

**NOTE**: calls to ``location()`` may not be nested, as only one location
may be saved.


Moving Permanently
~~~~~~~~~~~~~~~~~~

If you just want to move and aren't worried about returning, do something like
this::

    from blessings import Terminal

    term = Terminal()
    print(term.move(10, 1) + 'Hi, mom!')

``move``
  Position the cursor, parameter in form of *(y, x)*
``move_x``
  Position the cursor at given horizontal column.
``move_y``
  Position the cursor at given vertical column.

One-Notch Movement
~~~~~~~~~~~~~~~~~~

Finally, there are some parameterless movement capabilities that move the
cursor one character in various directions:

* ``move_left``
* ``move_right``
* ``move_up``
* ``move_down``

**NOTE**: *move_down* is often valued as *\\n*, which additionally returns
the carriage to column 0, depending on your terminal emulator.


Height And Width
----------------

Use the *height* and *width* properties of the *Terminal* class instance::

    from blessings import Terminal

    term = Terminal()
    height, width = term.height, term.width
    with term.location(x=term.width / 3, y=term.height / 3):
        print('1/3 ways in!')

These are always current, so they may be used with a callback from SIGWINCH_ signals.::

    import signal
    from blessings import Terminal

    term = Terminal()

    def on_resize(sig, action):
        print('height={t.height}, width={t.width}'.format(t=term))

    signal.signal(signal.SIGWINCH, on_resize)

    term.inkey()


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


Full-Screen Mode
----------------

If you've ever noticed a program, such as an editor, restores the previous
screen (such as your shell prompt) after exiting, you're seeing the
*enter_fullscreen* and *exit_fullscreen* attributes in effect.

``enter_fullscreen``
    Switch to alternate screen, previous screen is stored by terminal driver.
``exit_fullscreen``
    Switch back to standard screen, restoring the same terminal state.

There's also a context manager you can use as a shortcut::

    from __future__ import division
    from blessings import Terminal

    term = Terminal()
    with term.fullscreen():
        print(term.move_y(term.height // 2) +
              term.center('press any key').rstrip())
        term.inkey()


Pipe Savvy
----------

If your program isn't attached to a terminal, such as piped to a program
like *less(1)* or redirected to a file, all the capability attributes on
*Terminal* will return empty strings. You'll get a nice-looking file without
any formatting codes gumming up the works.

If you want to override this, such as when piping output to ``less -r``, pass
argument ``force_styling=True`` to the *Terminal* constructor.

In any case, there is a *does_styling* attribute on *Terminal* that lets
you see whether the terminal attached to the output stream is capable of
formatting.  If it is *False*, you may refrain from drawing progress
bars and other frippery and just stick to content::

    from blessings import Terminal

    term = Terminal()
    if term.does_styling:
        with term.location(x=0, y=term.height - 1):
            print('Progress: [=======>   ]')
    print(term.bold('Important stuff'))


Sequence Awareness
------------------

Blessings may measure the printable width of strings containing sequences,
providing ``.center``, ``.ljust``, and ``.rjust`` methods, using the
terminal screen's width as the default *width* value::

    from blessings import Terminal

    term = Terminal()
    with term.location(y=term.height / 2):
        print (term.center(term.bold('X'))

Any string containing sequences may have its printable length measured using the
``.length`` method. Additionally, ``textwrap.wrap()`` is supplied on the Terminal
class as method ``.wrap`` method that is also sequence-aware, so now you may
word-wrap strings containing sequences.  The following example displays a poem
from Tao Te Ching, word-wrapped to 25 columns::

    from blessings import Terminal

    term = Terminal()

    poem = (term.bold_blue('Plan difficult tasks'),
            term.blue('through the simplest tasks'),
            term.bold_cyan('Achieve large tasks'),
            term.cyan('through the smallest tasks'))

    for line in poem:
        print('\n'.join(term.wrap(line, width=25, subsequent_indent=' ' * 4)))


Keyboard Input
--------------

The built-in python function ``raw_input`` function does not return a value until
the return key is pressed, and is not suitable for detecting each individual
keypress, much less arrow or function keys that emit multibyte sequences.

Special `termios(4)`_ routines are required to enter Non-canonical mode, known
in curses as `cbreak(3)`_.  When calling read on input stream, only bytes are
received, which must be decoded to unicode.

Blessings handles all of these special cases!!

cbreak
~~~~~~

The context manager ``cbreak`` can be used to enter *key-at-a-time* mode: Any
keypress by the user is immediately consumed by read calls::

    from blessings import Terminal
    import sys

    t = Terminal()

    with t.cbreak():
        # blocks until any key is pressed.
        sys.stdin.read(1)

raw
~~~

The context manager ``raw`` is the same as ``cbreak``, except interrupt (^C),
quit (^\\), suspend (^Z), and flow control (^S, ^Q) characters are not trapped,
but instead sent directly as their natural character. This is necessary if you
actually want to handle the receipt of Ctrl+C

inkey
~~~~~

The method ``inkey`` resolves many issues with terminal input by returning
a unicode-derived *Keypress* instance.  Although its return value may be
printed, joined with, or compared to other unicode strings, it also provides
the special attributes ``is_sequence`` (bool), ``code`` (int),
and ``name`` (str)::

    from blessings import Terminal

    t = Terminal()

    print("press 'q' to quit.")
    with t.cbreak():
        val = None
        while val not in (u'q', u'Q',):
            val = t.inkey(timeout=5)
            if not val:
               # timeout
               print("It sure is quiet in here ...")
            elif val.is_sequence:
               print("got sequence: {}.".format((str(val), val.name, val.code)))
            elif val:
               print("got {}.".format(val))
        print('bye!')

Its output might appear as::

    got sequence: ('\x1b[A', 'KEY_UP', 259).
    got sequence: ('\x1b[1;2A', 'KEY_SUP', 337).
    got sequence: ('\x1b[17~', 'KEY_F6', 270).
    got sequence: ('\x1b', 'KEY_ESCAPE', 361).
    got sequence: ('\n', 'KEY_ENTER', 343).
    got /.
    It sure is quiet in here ...
    got sequence: ('\x1bOP', 'KEY_F1', 265).
    It sure is quiet in here ...
    got q.
    bye!

A ``timeout`` value of *None* (default) will block forever. Any other value
specifies the length of time to poll for input, if no input is received after
such time has elapsed, an empty string is returned. A ``timeout`` value of *0*
is non-blocking.

keyboard codes
~~~~~~~~~~~~~~

The return value of the *Terminal* method ``inkey`` is an instance of the
class ``Keystroke``, and may be inspected for its property ``is_sequence``
(bool).  When *True*, the value is a **multibyte sequence**, representing
a special non-alphanumeric key of your keyboard.

The ``code`` property (int) may then be compared with attributes of
*Terminal*, which are duplicated from those seen in the manpage
`curs_getch(3)`_ or the curses_ module, with the following helpful
aliases:

* use ``KEY_DELETE`` for ``KEY_DC`` (chr(127)).
* use ``KEY_TAB`` for chr(9).
* use ``KEY_INSERT`` for ``KEY_IC``.
* use ``KEY_PGUP`` for ``KEY_PPAGE``.
* use ``KEY_PGDOWN`` for ``KEY_NPAGE``.
* use ``KEY_ESCAPE`` for ``KEY_EXIT``.
* use ``KEY_SUP`` for ``KEY_SR`` (shift + up).
* use ``KEY_SDOWN`` for ``KEY_SF`` (shift + down).
* use ``KEY_DOWN_LEFT`` for ``KEY_C1`` (keypad lower-left).
* use ``KEY_UP_RIGHT`` for ``KEY_A1`` (keypad upper-left).
* use ``KEY_DOWN_RIGHT`` for ``KEY_C3`` (keypad lower-left).
* use ``KEY_UP_RIGHT`` for ``KEY_A3`` (keypad lower-right).
* use ``KEY_CENTER`` for ``KEY_B2`` (keypad center).
* use ``KEY_BEGIN`` for ``KEY_BEG``.

The *name* property of the return value of ``inkey()`` will prefer
these aliases over the built-in curses_ names.

The following are **not** available in the curses_ module, but
provided for keypad support, especially where the ``keypad()``
context manager is used:

* ``KEY_KP_MULTIPLY``
* ``KEY_KP_ADD``
* ``KEY_KP_SEPARATOR``
* ``KEY_KP_SUBTRACT``
* ``KEY_KP_DECIMAL``
* ``KEY_KP_DIVIDE``
* ``KEY_KP_0`` through ``KEY_KP_9``

.. _`erikrose/blessings`: https://github.com/erikrose/blessings
.. _curses: https://docs.python.org/library/curses.html
.. _couleur: https://pypi.python.org/pypi/couleur
.. _wcwidth: https://pypi.python.org/pypi/wcwidth
.. _`cbreak(3)`: http://www.openbsd.org/cgi-bin/man.cgi?query=cbreak&apropos=0&sektion=3
.. _`curs_getch(3)`: http://www.openbsd.org/cgi-bin/man.cgi?query=curs_getch&apropos=0&sektion=3
.. _`termios(4)`: http://www.openbsd.org/cgi-bin/man.cgi?query=termios&apropos=0&sektion=4
.. _`terminfo(5)`: http://www.openbsd.org/cgi-bin/man.cgi?query=terminfo&apropos=0&sektion=5
.. _tparm: http://www.openbsd.org/cgi-bin/man.cgi?query=tparm&sektion=3
.. _SIGWINCH: https://en.wikipedia.org/wiki/SIGWINCH
.. _`API Documentation`: http://blessed.rtfd.org
.. _`PDCurses`: http://www.lfd.uci.edu/~gohlke/pythonlibs/#curses
.. _`ansi`: https://github.com/tehmaze/ansi
