Version History
===============
1.14
  * bugfix: :meth:`~.Terminal.wrap` misbehaved for text containing newlines,
    :ghissue:`74`.

1.13
  * enhancement: :meth:`~.Terminal.split_seqs` introduced, and 4x cost
    reduction in related sequence-aware functions, :ghissue:`29`.
  * deprecated: ``blessed.sequences.measure_length`` function superseded by
    :func:`~.iter_parse` if necessary.
  * deprecated: warnings about "binary-packed capabilities" are no longer
    emitted on strange terminal types, making best effort.

1.12
  * enhancement: :meth:`~.Terminal.get_location` returns the ``(row, col)``
    position of the cursor at the time of call for attached terminal.
  * enhancement: a keyboard now detected as *stdin* when
    :paramref:`~.Terminal.__init__.stream` is :obj:`sys.stderr`.

1.11
  * enhancement: :meth:`~.Terminal.inkey` can return more quickly for
    combinations such as ``Alt + Z`` when ``MetaSendsEscape`` is enabled,
    :ghissue:`30`.
  * enhancement: :class:`~.FormattingString` may now be nested, such as
    ``t.red('red', t.underline('rum'))``, :ghissue:`61`

1.10
  * workaround: provide ``sc`` and ``rc`` for Terminals of ``kind='ansi'``,
    repairing :meth:`~.Terminal.location` :ghissue:`44`.
  * bugfix: length of simple SGR reset sequence ``\x1b[m`` was not correctly
    determined on all terminal types, :ghissue:`45`.
  * deprecated: ``_intr_continue`` arguments introduced in 1.8 are now marked
    deprecated in 1.10: beginning with python 3.5, the default behavior is as
    though this argument is always True, `PEP-475
    <https://www.python.org/dev/peps/pep-0475/>`_, blessed does the same.

1.9
  * enhancement: :paramref:`~.Terminal.wrap.break_long_words` now supported by
    :meth:`Terminal.wrap`
  * Ignore :class:`curses.error` message ``'tparm() returned NULL'``:
    this occurs on win32 or other platforms using a limited curses
    implementation, such as PDCurses_, where :func:`curses.tparm` is
    not implemented, or no terminal capability database is available.
  * Context manager :meth:`~.keypad` emits sequences that enable
    "application keys" such as the diagonal keys on the numpad.
    This is equivalent to :meth:`curses.window.keypad`.
  * bugfix: translate keypad application keys correctly.
  * enhancement: no longer depend on the '2to3' tool for python 3 support.
  * enhancement: allow ``civis`` and ``cnorm`` (*hide_cursor*, *normal_hide*)
    to work with terminal-type *ansi* by emulating support by proxy.
  * enhancement: new public attribute: :attr:`~.kind`: the very same as given
    :paramref:`Terminal.__init__.kind` keyword argument.  Or, when not given,
    determined by and equivalent to the ``TERM`` Environment variable.

1.8
  * enhancement: export keyboard-read function as public method ``getch()``,
    so that it may be overridden by custom terminal implementers.
  * enhancement: allow :meth:`~.inkey` and :meth:`~.kbhit` to return early
    when interrupted by signal by passing argument ``_intr_continue=False``.
  * enhancement: allow ``hpa`` and ``vpa`` (*move_x*, *move_y*) to work on
    tmux(1) or screen(1) by emulating support by proxy.
  * enhancement: add :meth:`~.Terminal.rstrip` and :meth:`~.Terminal.lstrip`,
    strips both sequences and trailing or leading whitespace, respectively.
  * enhancement: include wcwidth_ library support for
    :meth:`~.Terminal.length`: the printable width of many kinds of CJK
    (Chinese, Japanese, Korean) ideographs and various combining characters
    may now be determined.
  * enhancement: better support for detecting the length or sequences of
    externally-generated *ecma-48* codes when using ``xterm`` or ``aixterm``.
  * bugfix: when :func:`locale.getpreferredencoding` returns empty string or
    an encoding that is not valid for ``codecs.getincrementaldecoder``,
    fallback to ASCII and emit a warning.
  * bugfix: ensure :class:`~.FormattingString` and
    :class:`~.ParameterizingString` may be pickled.
  * bugfix: allow `~.inkey` and related to be called without a keyboard.
  * **change**: ``term.keyboard_fd`` is set ``None`` if ``stream`` or
    ``sys.stdout`` is not a tty, making ``term.inkey()``, ``term.cbreak()``,
    ``term.raw()``, no-op.
  * bugfix: ``\x1bOH`` (KEY_HOME) was incorrectly mapped as KEY_LEFT.

1.7
  * Forked github project `erikrose/blessings`_ to `jquast/blessed`_, this
    project was previously known as **blessings** version 1.6 and prior.
  * introduced: context manager :meth:`~.cbreak`, which is equivalent to
    entering terminal state by :func:`tty.setcbreak` and returning
    on exit, as well as the lesser recommended :meth:`~.raw`,
    pairing from :func:`tty.setraw`.
  * introduced: :meth:`~.inkey`, which will return one or more characters
    received by the keyboard as a unicode sequence, with additional attributes
    :attr:`~.Keystroke.code` and :attr:`~.Keystroke.name`.  This allows
    application keys (such as the up arrow, or home key) to be detected.
    Optional value :paramref:`~.inkey.timeout` allows for timed poll.
  * introduced: :meth:`~.Terminal.center`, :meth:`~.Terminal.rjust`,
    :meth:`~.Terminal.ljust`, allowing text containing sequences to be aligned
    to detected horizontal screen width, or by
    :paramref:`~.Terminal.center.width` specified.
  * introduced: :meth:`~.wrap` method.  Allows text containing sequences to be
    word-wrapped without breaking mid-sequence, honoring their printable width.
  * introduced: :meth:`~.Terminal.strip`, strips all sequences *and*
    whitespace.
  * introduced: :meth:`~.Terminal.strip_seqs` strip only sequences.
  * introduced: :meth:`~.Terminal.rstrip` and :meth:`~.Terminal.lstrip` strips
    both sequences and trailing or leading whitespace, respectively.
  * bugfix: cannot call :func:`curses.setupterm` more than once per process
    (from :meth:`Terminal.__init__`):  Previously, blessed pretended
    to support several instances of different Terminal :attr:`~.kind`, but was
    actually using the :attr:`~.kind` specified by the first instantiation of
    :class:`~.Terminal`.  A warning is now issued.  Although this is
    misbehavior is still allowed, a :class:`warnings.WarningMessage` is now
    emitted to notify about subsequent terminal misbehavior.
  * bugfix: resolved issue where :attr:`~.number_of_colors` fails when
    :attr:`~.does_styling` is ``False``.  Resolves issue where piping tests
    output would fail.
  * bugfix: warn and set :attr:`~.does_styling` to ``False`` when the given
    :attr:`~.kind` is not found in the terminal capability database.
  * bugfix: allow unsupported terminal capabilities to be callable just as
    supported capabilities, so that the return value of
    :attr:`~.color`\(n) may be called on terminals without color
    capabilities.
  * bugfix: for terminals without underline, such as vt220,
    ``term.underline('text')`` would emit ``'text' + term.normal``.
    Now it emits only ``'text'``.
  * enhancement: some attributes are now properties, raise exceptions when
    assigned.
  * enhancement: pypy is now a supported python platform implementation.
  * enhancement: removed pokemon ``curses.error`` exceptions.
  * enhancement: do not ignore :class:`curses.error` exceptions, unhandled
    curses errors are legitimate errors and should be reported as a bug.
  * enhancement: converted nose tests to pytest, merged travis and tox.
  * enhancement: pytest fixtures, paired with a new ``@as_subprocess``
    decorator
    are used to test a multitude of terminal types.
  * enhancement: test accessories ``@as_subprocess`` resolves various issues
    with different terminal types that previously went untested.
  * deprecation: python2.5 is no longer supported (as tox does not supported).

1.6
  * Add :attr:`~.does_styling`. This takes :attr:`~.force_styling`
    into account and should replace most uses of :attr:`~.is_a_tty`.
  * Make :attr:`~.is_a_tty` a read-only property like :attr:`~.does_styling`.
    Writing to it never would have done anything constructive.
  * Add :meth:`~.fullscreen`` and :meth:`hidden_cursor` to the
    auto-generated docs.

1.5.1
  * Clean up fabfile, removing the redundant ``test`` command.
  * Add Travis support.
  * Make ``python setup.py test`` work without spurious errors on 2.6.
  * Work around a tox parsing bug in its config file.
  * Make context managers clean up after themselves even if there's an
    exception (Vitja Makarov :ghpull:`29`).
  * Parameterizing a capability no longer crashes when there is no tty
    (Vitja Makarov :ghpull:`31`)

1.5
  * Add syntactic sugar and documentation for ``enter_fullscreen``
    and ``exit_fullscreen``.
  * Add context managers :meth:`~.fullscreen` and :meth:`~.hidden_cursor`.
  * Now you can force a :class:`~.Terminal` to never to emit styles by
    passing keyword argument ``force_styling=None``.

1.4
  * Add syntactic sugar for cursor visibility control and single-space-movement
    capabilities.
  * Endorse the :meth:`~.location` context manager for restoring cursor
    position after a series of manual movements.
  * Fix a bug in which :meth:`~.location` that wouldn't do anything when
    passed zeros.
  * Allow tests to be run with ``python setup.py test``.

1.3
  * Added :attr:`~.number_of_colors`, which tells you how many colors the
    terminal supports.
  * Made :attr:`~.color`\(n) and :attr:`~.on_color`\(n) callable to wrap a
    string, like the named colors can. Also, make them both fall back to the
    ``setf`` and ``setb`` capabilities (like the named colors do) if the
    termcap entries for ``setaf`` and ``setab`` are not available.
  * Allowed :attr:`~.color` to act as an unparametrized string, not just a
    callable.
  * Made :attr:`~.height` and :attr:`~.width` examine any passed-in stream
    before falling back to stdout (This rarely if ever affects actual behavior;
    it's mostly philosophical).
  * Made caching simpler and slightly more efficient.
  * Got rid of a reference cycle between :class:`~.Terminal` and
    :class:`~.FormattingString`.
  * Updated docs to reflect that terminal addressing (as in :meth:`~location`)
    is 0-based.

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
  * Added :attr:`~.is_a_tty` to determine whether the output stream is a
    terminal.
  * Sugared the remaining interesting string capabilities.
  * Allow :meth:`~.location` to operate on just an x *or* y coordinate.

1.0
  * Extracted Blessed from `nose-progressive`_.


.. _`nose-progressive`: http://pypi.python.org/pypi/nose-progressive/
.. _`erikrose/blessings`: https://github.com/erikrose/blessings
.. _`jquast/blessed`: https://github.com/jquast/blessed
.. _`issue tracker`: https://github.com/jquast/blessed/issues/
.. _curses: https://docs.python.org/library/curses.html
.. _couleur: https://pypi.python.org/pypi/couleur
.. _colorama: https://pypi.python.org/pypi/colorama
.. _wcwidth: https://pypi.python.org/pypi/wcwidth
.. _`cbreak(3)`: http://www.openbsd.org/cgi-bin/man.cgi?query=cbreak&apropos=0&sektion=3
.. _`curs_getch(3)`: http://www.openbsd.org/cgi-bin/man.cgi?query=curs_getch&apropos=0&sektion=3
.. _`termios(4)`: http://www.openbsd.org/cgi-bin/man.cgi?query=termios&apropos=0&sektion=4
.. _`terminfo(5)`: http://www.openbsd.org/cgi-bin/man.cgi?query=terminfo&apropos=0&sektion=5
.. _tigetstr: http://www.openbsd.org/cgi-bin/man.cgi?query=tigetstr&sektion=3
.. _tparm: http://www.openbsd.org/cgi-bin/man.cgi?query=tparm&sektion=3
.. _SIGWINCH: https://en.wikipedia.org/wiki/SIGWINCH
.. _`API Documentation`: http://blessed.rtfd.org
.. _`PDCurses`: http://www.lfd.uci.edu/~gohlke/pythonlibs/#curses
.. _`ansi`: https://github.com/tehmaze/ansi
