=======
Blessed
=======

Coding with Blessed looks like this... ::

    from blessed import Terminal

    t = Terminal()

    print(t.bold('Hi there!'))
    print(t.bold_red_on_bright_green('It hurts my eyes!'))

    with t.location(0, t.height - 1):
        print(t.center(t.blink('press any key to continue.')))

    with t.cbreak():
        t.inkey()

Or, for byte-level control, you can drop down and play with raw terminal
capabilities::

    print('{t.bold}All your {t.red}bold and red base{t.normal}'.format(t=t))

The Pitch
=========

Blessed lifts several of curses_' limiting assumptions, and it makes your
code pretty, too:

* Use styles, color, and maybe a little positioning without necessarily
  clearing the whole screen first.
* Leave more than one screenful of scrollback in the buffer after your program
  exits, like a well-behaved command-line application should.
* Get rid of all those noisy, C-like calls to ``tigetstr`` and ``tparm``, so
  your code doesn't get crowded out by terminal bookkeeping.
* Act intelligently when somebody redirects your output to a file, omitting the
  terminal control codes the user doesn't want to see (optional).

.. _curses: http://docs.python.org/library/curses.html

Before And After
----------------

Without Blessed, this is how you'd print some underlined text at the bottom
of the screen::

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
with Blessed::

    from blessed import Terminal

    term = Terminal()
    with term.location(0, term.height - 1):
        print('This is', term.underline('pretty!'))

Much better.

What It Provides
================

Blessed provides just one top-level object: ``Terminal``. Instantiating a
``Terminal`` figures out whether you're on a terminal at all and, if so, does
any necessary terminal setup. After that, you can proceed to ask it all sorts
of things about the terminal. Terminal terminal terminal.

Simple Formatting
-----------------

Lots of handy formatting codes (capabilities, `terminfo(5)`_) are available
as attributes on a ``Terminal``. For example::

    from blessed import Terminal

    term = Terminal()
    print('I am ' + term.bold + 'bold' + term.normal + '!')

Though they are strings at heart, you can also use them as callable wrappers,
which automatically ends each string with ``normal`` attributes::

    print('I am', term.bold('bold') + '!')

You may also use Python's string ``.format`` method::

    print('All your {t.red}base {t.underline}are belong to us{t.normal}'
          .format(t=term))

Simple capabilities of interest include...

* ``bold``
* ``reverse``
* ``blink``
* ``normal`` (which turns off everything, even colors)

Here are a few more which are less likely to work on all terminals:

* ``dim``
* ``underline``
* ``no_underline`` (which turns off underlining)
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
string-returning capability listed on the `terminfo(5)`_ manual page, by the name
under the **Cap-name** column: for example, ``term.rum`` (End reverse character).

.. _`terminfo(5)`: http://www.openbsd.org/cgi-bin/man.cgi?query=terminfo&apropos=0&sektion=5

Color
-----

16 colors, both foreground and background, are available as easy-to-remember
attributes::

    from blessed import Terminal

    term = Terminal()
    print(term.red + term.on_green + 'Red on green? Ick!' + term.normal)
    print(term.bright_red + term.on_bright_blue + 'This is even worse!' + term.normal)

You can also call them as wrappers, which sets everything back to normal at the
end::

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
0-15::

    term.color(5) + 'Hello' + term.normal
    term.on_color(3) + 'Hello' + term.normal

    term.color(5)('Hello')
    term.on_color(3)('Hello')

If some color is unsupported (for instance, if only the normal colors are
available, not the bright ones), trying to use it will, on most terminals, have
no effect: the foreground and background colors will stay as they were. You can
get fancy and do different things depending on the supported colors by checking
`number_of_colors`_.

.. _`number_of_colors`: http://packages.python.org/blessed/#blessed.Terminal.number_of_colors

Compound Formatting
-------------------

If you want to do lots of crazy formatting all at once, you can just mash it
all together::

    from blessed import Terminal

    term = Terminal()
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

Most often, moving to a screen position is only temporary. A contest manager,
``location`` is provided to move to a screen position and restore the previous
position upon exit::

    from blessed import Terminal

    term = Terminal()
    with term.location(0, term.height - 1):
        print('Here is the bottom.')
    print('This is back where I came from.')

Parameters to ``location()`` are ``x`` and then ``y``, but you can also pass
just one of them, leaving the other alone. For example... ::

    with term.location(y=10):
        print('We changed just the row.')

If you're doing a series of ``move`` calls (see below) and want to return the
cursor to its original position afterward, call ``location()`` with no
arguments, and it will do only the position restoring::

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
this::

    from blessed import Terminal

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


.. _`terminfo(5)`: http://www.openbsd.org/cgi-bin/man.cgi?query=terminfo&apropos=0&sektion=5

One-Notch Movement
~~~~~~~~~~~~~~~~~~

Finally, there are some parameterless movement capabilities that move the
cursor one character in various directions:

* ``move_left``
* ``move_right``
* ``move_up``
* ``move_down``

For example... ::

    print(term.move_up + 'Howdy!')

Height And Width
----------------

It's simple to get the height and width of the terminal, in characters::

    from blessed import Terminal

    term = Terminal()
    height = term.height
    width = term.width

These are newly updated each time you ask for them, so they're safe to use from
SIGWINCH handlers.

Clearing The Screen
-------------------

Blessed provides syntactic sugar over some screen-clearing capabilities:

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
screen state (Your shell prompt) after exiting, you're seeing the
``enter_fullscreen`` and ``exit_fullscreen`` attributes in effect.

``enter_fullscreen``
    Switch to alternate screen, previous screen is stored by terminal driver.
``exit_fullscreen``
    Switch back to standard screen, restoring the same termnal state.

There's also a context manager you can use as a shortcut::

    from blessed import Terminal

    term = Terminal()
    with term.fullscreen():
        print(term.move_y(term.height/2) +
              term.center('press any key'))
        term.inkey()

Pipe Savvy
----------

If your program isn't attached to a terminal, such as piped to a program
like ``less(1)`` or redirected to a file, all the capability attributes on
``Terminal`` will return empty strings. You'll get a nice-looking file without
any formatting codes gumming up the works.

If you want to override this, such as using ``less -r``, pass argument
``force_styling=True`` to the ``Terminal`` constructor.

In any case, there is a ``does_styling`` attribute on ``Terminal`` that lets
you see whether the terminal attached to the output stream is capable of
formatting.  If it is ``False``, you may refrain from drawing progress
bars and other frippery and just stick to content::

    from blessed import Terminal

    term = Terminal()
    if term.does_styling:
        with term.location(0, term.height - 1):
            print('Progress: [=======>   ]')
    print(term.bold('Important stuff'))

Sequence Awareness
------------------

Blessed may measure the printable width of strings containing sequences,
providing ``.center``, ``.ljust``, and ``.rjust`` methods, using the
terminal screen's width as the default ``width`` value::

    from blessed import Terminal

    term = Terminal()
    with term.location(y=term.height / 2):
        print (term.center(term.bold('X'))

Any string containing sequences may have its printable length measured using the
``.length`` method. Additionally, ``textwrap.wrap()`` is supplied on the Terminal
class as method ``.wrap`` method that is also sequence-aware, so now you may
word-wrap strings containing sequences.  The following example displays a poem
from Tao Te Ching, word-wrapped to 25 columns::

    from blessed import Terminal

    t = Terminal()

    poem = u''.join((term.bold_blue('Plan difficult tasks '),
                     term.bold_black('through the simplest tasks'),
                     term.bold_cyan('Achieve large tasks '),
                     term.cyan('through the smallest tasks'))
    for line in poem:
        print('\n'.join(term.wrap(line, width=25,
                                  subsequent_indent=' ' * 4)))

Keyboard Input
--------------

You may have noticed that the built-in python ``raw_input`` doesn't return
until the return key is pressed (line buffering). Special `termios(4)`_ routines
are required to enter Non-canonical, known in curses as `cbreak(3)_`.

You may also have noticed that special keys, such as arrow keys, actually
input several byte characters, and different terminals send different strings.

Finally, you may have noticed characters such as ä from ``raw_input`` are also
several byte characters in a sequence ('\xc3\xa4') that must be decoded.

Handling all of these possibilities can be quite difficult, but Blessed has
you covered!

cbreak
~~~~~~

The context manager ``cbreak`` can be used to enter key-at-a-time mode.
Any keypress by the user is immediately value::

    from blessed import Terminal
    import sys

    t = Terminal()

    with t.cbreak():
        # blocks until any key is pressed.
        sys.stdin.read(1)

raw
~~~

The context manager ``raw`` is the same as ``cbreak``, except interrupt (^C),
quit (^\), suspend (^Z), and flow control (^S, ^Q) characters are not trapped
by signal handlers, but instead sent directly. This is necessary if you
actually want to handle the receipt of Ctrl+C

inkey
~~~~~

The method ``inkey`` resolves many issues with terminal input by returning
a unicode-derived ``Keypress`` instance. Although its return value may be
printed, joined with, or compared to other unicode strings, it also provides
the special attributes ``is_sequence`` (bool), ``code`` (int),
and ``name`` (str)::

    from blessed import Terminal

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

.. _`cbreak(3)`: www.openbsd.org/cgi-bin/man.cgi?query=cbreak&apropos=0&sektion=3
.. _`termios(4)`: www.openbsd.org/cgi-bin/man.cgi?query=termios&apropos=0&sektion=4


codes
~~~~~

The return value of ``inkey`` can be inspected for property ``is_sequence``.
When ``True``, the ``code`` property (int) may be compared with any of the
following attributes available on the associated Terminal, which are equivalent
to the same available in curs_getch(3X), with the following exceptions
 * use ``KEY_DELETE`` instead of ``KEY_DC`` (chr(127))
 * use ``KEY_INSERT`` instead of ``KEY_IC``
 * use ``KEY_PGUP`` instead of ``KEY_PPAGE``
 * use ``KEY_PGDOWN`` instead of ``KEY_NPAGE``
 * use ``KEY_ESCAPE`` instead of ``KEY_EXIT``
 * use ``KEY_SUP`` instead of ``KEY_SR`` (shift + up)
 * use ``KEY_SDOWN`` instead of ``KEY_SF`` (shift + down)

Additionally, use any of the following common attributes:

 * ``KEY_BACKSPACE`` (chr(8)).
 * ``KEY_TAB`` (chr(9)).
 * ``KEY_DOWN``, ``KEY_UP``, ``KEY_LEFT``, ``KEY_RIGHT``.
 * ``KEY_SLEFT`` (shift + left).
 * ``KEY_SRIGHT``  (shift + right).
 * ``KEY_HOME``, ``KEY_END``.
 * ``KEY_F1`` through ``KEY_F22``.

And much more. All attributes begin with prefix ``KEY_``.

Shopping List
=============

There are decades of legacy tied up in terminal interaction, so attention to
detail and behavior in edge cases make a difference. Here are some ways
Blessed has your back:

* Uses the `terminfo(5)`_ database so it works with any terminal type
* Provides up-to-the-moment terminal height and width, so you can respond to
  terminal size changes (SIGWINCH signals). (Most other libraries query the
  ``COLUMNS`` and ``LINES`` environment variables or the ``cols`` or ``lines``
  terminal capabilities, which don't update promptly, if at all.)
* Avoids making a mess if the output gets piped to a non-terminal.
* Works great with standard Python string formatting.
* Provides convenient access to **all** terminal capabilities.
* Outputs to any file-like object (StringIO, file), not just stdout.
* Keeps a minimum of internal state, so you can feel free to mix and match with
  calls to curses or whatever other terminal libraries you like

Blessed does not provide...

* Native color support on the Windows command prompt. However, it should work
  when used in concert with colorama_.

.. _colorama: http://pypi.python.org/pypi/colorama/0.2.4

Bugs
====

Bugs or suggestions? Visit the `issue tracker`_.

.. _`issue tracker`: https://github.com/jquast/blessed/issues/

.. image:: https://secure.travis-ci.org/jquast/blessed.png


License
=======

Blessed is derived from Blessings, which is under the MIT License, and
shares the same. See the LICENSE file.

Version History
===============

1.7
  * Forked github project `erikrose/blessings`_ to `jquast/blessed`_, this
    project was previously known as **blessings** version 1.6 and prior.
  * introduced context manager ``cbreak`` and ``raw``, which is equivalent
    to ``tty.setcbreak`` and ``tty.setraw``, allowing input from stdin to be
    read as each key is pressed.
  * introduced ``inkey()``, which will return 1 or more characters as
    a unicode sequence, with attributes ``.code`` and ``.name`` non-None when
    a multibyte sequence is received, allowing arrow keys and such to be
    detected. Optional value ``timeout`` allows timed polling or blocking.
  * introduced ``center()``, ``rjust()``, and ``ljust()`` methods, allows text
    containing sequences to be aligned to screen, or ``width`` specified.
  * introduced ``wrap()``, allows text containing sequences to be
    word-wrapped without breaking mid-sequence and honoring their printable
    width.
  * bugfix: cannot call ``setupterm()`` more than once per process -- issue a
    warning about what terminal kind subsequent calls will use.
  * bugfix: resolved issue where ``number_of_colors`` fails when ``does_styling``
    is ``False``. resolves issue where piping tests output to stdout would fail.
  * bugfix: warn and set ``does_styling`` to ``False`` when TERM is unknown.
  * bugfix: allow unsupported terminal capabilities to be callable just as
    supported capabilities, so that the return value of ``term.color(n)`` may
    be called on terminals without color capabilities.
  * bugfix: for terminals without underline, such as vt220, ``term.underline('x')``
    would be ``u'x' + term.normal``, now it is only ``u'x'``.
  * attributes that should be read-only have now raise exception when
    re-assigned (properties).
  * enhancement: pypy is not a supported platform implementation.
  * enhancement: removed pokemon ``curses.error`` exceptions.
  * enhancement: converted nosetests to pytest, install and use ``tox`` for testing.
  * enhancement: pytext fixtures, paired with a new ``@as_subprocess`` decorator
    are used to test a multitude of terminal types.
  * introduced ``@as_subprocess`` to discover and resolve various issues.
  * deprecation: python2.5 is no longer supported (as tox does not supported).

1.6
  * Add ``does_styling`` property. This takes ``force_styling`` into account
    and should replace most uses of ``is_a_tty``.
  * Make ``is_a_tty`` a read-only property, like ``does_styling``. Writing to
    it never would have done anything constructive.
  * Add ``fullscreen()`` and ``hidden_cursor()`` to the auto-generated docs.

1.5.1
  * Clean up fabfile, removing the redundant ``test`` command.
  * Add Travis support.
  * Make ``python setup.py test`` work without spurious errors on 2.6.
  * Work around a tox parsing bug in its config file.
  * Make context managers clean up after themselves even if there's an
    exception. (Vitja Makarov)
  * Parameterizing a capability no longer crashes when there is no tty. (Vitja
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
.. _`erikrose/blessings`: https://github.com/erikrose/blessings
.. _`jquast/blessed`: https://github.com/jquast/blessed
