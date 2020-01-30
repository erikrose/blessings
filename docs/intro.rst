| |docs| |travis| |codecov|
| |pypi| |downloads| |gitter|
| |linux| |windows| |mac| |bsd|

.. |docs| image:: https://img.shields.io/readthedocs/blessed.svg?logo=read-the-docs
    :target: https://blessed.readthedocs.org
    :alt: Documentation Status

.. |travis| image:: https://img.shields.io/travis/jquast/blessed/master.svg?logo=travis
    :alt: Travis Continuous Integration
    :target: https://travis-ci.org/jquast/blessed/

.. |codecov| image:: https://codecov.io/gh/jquast/blessed/branch/master/graph/badge.svg
    :alt: codecov.io Code Coverage
    :target: https://codecov.io/gh/jquast/blessed

.. |pypi| image:: https://img.shields.io/pypi/v/blessed.svg?logo=pypi
    :alt: Latest Version
    :target: https://pypi.python.org/pypi/blessed

.. |downloads| image:: https://img.shields.io/pypi/dm/blessed.svg?logo=pypi
    :alt: Downloads
    :target: https://pypi.python.org/pypi/blessed

.. |linux| image:: https://img.shields.io/badge/Linux-yes-success?logo=linux
    :alt: Linux supported
    :target: https://pypi.python.org/pypi/blessed

.. |windows| image:: https://img.shields.io/badge/Windows-NEW-success?logo=windows
    :alt: Windows supported
    :target: https://pypi.python.org/pypi/blessed

.. |mac| image:: https://img.shields.io/badge/MacOS-yes-success?logo=apple
    :alt: MacOS supported
    :target: https://pypi.python.org/pypi/blessed

.. |bsd| image:: https://img.shields.io/badge/BSD-yes-success?logo=freebsd
    :alt: BSD supported
    :target: https://pypi.python.org/pypi/blessed

Introduction
============

Blessed is an easy, practical library for making terminal apps, by providing Colors_, Styles_,
interactive Keyboard_ input, and screen Positioning_ capabilities.

It's meant to be *fun* and *easy*, to do basic terminal graphics and styling with Python!

Programming with *Blessed* looks like this ...

.. code-block:: python

    from blessed import Terminal

    t = Terminal()

    print(t.home + t.clear + t.move_y(t.height // 2))
    print(t.black_on_darkkhaki(t.center('press any key to continue.')))

    with t.cbreak(), t.hidden_cursor():
        inp = t.inkey()

    print(t.move_down(2) + 'You pressed ' + t.bold(repr(inp)))


Requirements
------------

*Blessed* works with Windows, Mac, Linux, and BSD's, on Python 2.7, 3.4, 3.5, 3.6, 3.7, and 3.8.

Brief Overview
--------------

*Blessed* is more than just a Python wrapper around curses_:

* Windows support, new since Dec. 2019!
* 24-bit color support, using `Terminal.color_rgb()`_ and `Terminal.on_color_rgb()`_ and all X11
  Colors_ by name, and not by number.
* Styles, color, and maybe a little positioning without necessarily clearing the whole screen first.
* Works great with standard Python string formatting.
* Provides up-to-the-moment terminal height and width, so you can respond to terminal size changes.
* Avoids making a mess if the output gets piped to a non-terminal: outputs to any file-like object
  such as *StringIO*, files, or pipes.
* Uses the `terminfo(5)`_ database so it works with any terminal type and supports any terminal
  capability: No more C-like calls to tigetstr_ and tparm_.
* Keeps a minimum of internal state, so you can feel free to mix and match with calls to curses or
  whatever other terminal libraries you like.
* Provides plenty of context managers to safely express terminal modes, such as
  `Terminal.fullscreen()`, `Terminal.hidden_cursor()` and `Terminal.location()` for output modes and
  `Terminal.cbreak()`_, `Terminal.raw()`_, or `Terminal.keypad()`_ context managers for keyboard
  input modes.
* Act intelligently when somebody redirects your output to a file, omitting all of the terminal
  sequences such as styling, colors, or positioning.
* Dead-simple keyboard handling: safely decoding unicode input in your system's preferred locale and
  supports application/arrow keys.
* Allows sequences to be removed from strings that contain them, using `Terminal.strip_seqs()`_ or
  sequences and whitespace using `Terminal.strip()`_.
* Allows the printable length of strings containing sequences to be determined, using
  `Terminal.length()`_, supporting terminal methods for alignment of text containing sequences
  `Terminal.rstrip()`_, `Terminal.lstrip()`_, `Terminal.wrap()`_, `Terminal.center()`_,

* `Terminal.inkey()`_ for keyboard event detection

Further Documentation
---------------------

More documentation can be found at http://blessed.readthedocs.org/en/latest/

.. _curses: https://docs.python.org/3/library/curses.html
.. _tigetstr: http://www.openbsd.org/cgi-bin/man.cgi/OpenBSD-current/man3/tigetstr.3
.. _tparm: http://www.openbsd.org/cgi-bin/man.cgi/OpenBSD-current/man3/tparm.3
.. _`terminfo(5)`: http://invisible-island.net/ncurses/man/terminfo.5.html
.. _`Terminal.color_rgb()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.color_rgb
.. _`Terminal.on_color_rgb()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.on_color_rgb
.. _`Terminal.length()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.length
.. _`Terminal.strip()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.strip
.. _`Terminal.rstrip()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.rstrip
.. _`Terminal.lstrip()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.lstrip
.. _`Terminal.strip_seqs()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.strip_seqs
.. _`Terminal.wrap()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.wrap
.. _`Terminal.center()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.center
.. _`Terminal.rjust()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.rjust
.. _`Terminal.ljust()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.ljust
.. _`Terminal.cbreak()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.cbreak
.. _`Terminal.raw()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.raw
.. _`Terminal.inkey()`: https://blessed.readthedocs.io/en/stable/api.html#blessed.terminal.Terminal.inkey
