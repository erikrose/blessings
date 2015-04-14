# encoding: utf-8
"""This module contains :class:`Terminal`, the primary API interface."""
# std imports
import collections
import contextlib
import functools
import warnings
import platform
import codecs
import curses
import locale
import select
import struct
import time
import sys
import os
import io

try:
    import termios
    import fcntl
    import tty
except ImportError:
    _TTY_METHODS = ('setraw', 'cbreak', 'kbhit', 'height', 'width')
    _MSG_NOSUPPORT = (
        "One or more of the modules: 'termios', 'fcntl', and 'tty' "
        "are not found on your platform '{0}'. The following methods "
        "of Terminal are dummy/no-op unless a deriving class overrides "
        "them: {1}".format(sys.platform.lower(), ', '.join(_TTY_METHODS)))
    warnings.warn(_MSG_NOSUPPORT)
    HAS_TTY = False
else:
    HAS_TTY = True

try:
    _ = InterruptedError
    del _
except NameError:
    # alias py2 exception to py3
    InterruptedError = select.error

# local imports
from .formatters import (
    ParameterizingString,
    NullCallableString,
    resolve_capability,
    resolve_attribute,
)

from .sequences import (
    init_sequence_patterns,
    SequenceTextWrapper,
    Sequence,
)

from .keyboard import (
    get_keyboard_sequences,
    get_keyboard_codes,
    resolve_sequence,
)


class Terminal(object):

    """Wrapper for curses and related terminfo(5) terminal capabilities."""

    #: Sugary names for commonly-used capabilities
    _sugar = dict(
        save='sc',
        restore='rc',
        # 'clear' clears the whole screen.
        clear_eol='el',
        clear_bol='el1',
        clear_eos='ed',
        position='cup',  # deprecated
        enter_fullscreen='smcup',
        exit_fullscreen='rmcup',
        move='cup',
        move_x='hpa',
        move_y='vpa',
        move_left='cub1',
        move_right='cuf1',
        move_up='cuu1',
        move_down='cud1',
        hide_cursor='civis',
        normal_cursor='cnorm',
        reset_colors='op',  # oc doesn't work on my OS X terminal.
        normal='sgr0',
        reverse='rev',
        italic='sitm',
        no_italic='ritm',
        shadow='sshm',
        no_shadow='rshm',
        standout='smso',
        no_standout='rmso',
        subscript='ssubm',
        no_subscript='rsubm',
        superscript='ssupm',
        no_superscript='rsupm',
        underline='smul',
        no_underline='rmul')

    def __init__(self, kind=None, stream=None, force_styling=False):
        """
        Class initializer.

        :param str kind: A terminal string as taken by
            :func:`curses.setupterm`.  Defaults to the value of the ``TERM``
            Environment variable.
        :param stream: A file-like object representing the Terminal. Defaults
            to the original value of :obj:`sys.__stdout__`, like
            :func:`curses.initscr` does.  If ``stream`` is not a tty, empty
            Unicode strings are returned for all capability values, so things
            like piping your program output to a pipe or file does not emit
            terminal sequences.
        :param bool force_styling: Whether to force the emission of
            capabilities even if :obj:`sys.__stdout__` does not seem to be
            connected to a terminal.  This comes in handy if users are trying
            to pipe your output through something like ``less -r`` or build
            systems which support decoding of terminal sequences.

            If you want to force styling to not happen, pass
            ``force_styling=None``.
        """
        # pylint: disable=global-statement
        #         Using the global statement (col 8)

        global _CUR_TERM
        self._keyboard_fd = None

        # Default stream is stdout, keyboard only valid as stdin when
        # output stream is stdout is a tty.
        if stream is None or stream == sys.__stdout__:
            stream = sys.__stdout__
            self._keyboard_fd = sys.__stdin__.fileno()

        try:
            stream_fd = (stream.fileno() if hasattr(stream, 'fileno') and
                         callable(stream.fileno) else None)
        except io.UnsupportedOperation:
            stream_fd = None

        self._is_a_tty = stream_fd is not None and os.isatty(stream_fd)
        self._does_styling = ((self.is_a_tty or force_styling) and
                              force_styling is not None)

        # _keyboard_fd only non-None if both stdin and stdout is a tty.
        self._keyboard_fd = (self._keyboard_fd
                             if self._keyboard_fd is not None and
                             self.is_a_tty and os.isatty(self._keyboard_fd)
                             else None)
        self._normal = None  # cache normal attr, preventing recursive lookups

        # The descriptor to direct terminal initialization sequences to.
        self._init_descriptor = (stream_fd is None and
                                 sys.__stdout__.fileno() or
                                 stream_fd)
        self._kind = kind or os.environ.get('TERM', 'unknown')

        if self.does_styling:
            # Make things like tigetstr() work. Explicit args make setupterm()
            # work even when -s is passed to nosetests. Lean toward sending
            # init sequences to the stream if it has a file descriptor, and
            # send them to stdout as a fallback, since they have to go
            # somewhere.
            try:
                if (platform.python_implementation() == 'PyPy' and
                        isinstance(self._kind, unicode)):
                    # pypy/2.4.0_2/libexec/lib_pypy/_curses.py, line 1131
                    # TypeError: initializer for ctype 'char *' must be a str
                    curses.setupterm(self._kind.encode('ascii'),
                                     self._init_descriptor)
                else:
                    curses.setupterm(self._kind, self._init_descriptor)
            except curses.error as err:
                warnings.warn('Failed to setupterm(kind={0!r}): {1}'
                              .format(self._kind, err))
                self._kind = None
                self._does_styling = False
            else:
                if _CUR_TERM is None or self._kind == _CUR_TERM:
                    _CUR_TERM = self._kind
                else:
                    warnings.warn(
                        'A terminal of kind "%s" has been requested; due to an'
                        ' internal python curses bug, terminal capabilities'
                        ' for a terminal of kind "%s" will continue to be'
                        ' returned for the remainder of this process.' % (
                            self._kind, _CUR_TERM,))

        for re_name, re_val in init_sequence_patterns(self).items():
            setattr(self, re_name, re_val)

        # Build database of int code <=> KEY_NAME.
        self._keycodes = get_keyboard_codes()

        # Store attributes as: self.KEY_NAME = code.
        for key_code, key_name in self._keycodes.items():
            setattr(self, key_name, key_code)

        # Build database of sequence <=> KEY_NAME.
        self._keymap = get_keyboard_sequences(self)

        self._keyboard_buf = collections.deque()
        if self._keyboard_fd is not None:
            locale.setlocale(locale.LC_ALL, '')
            self._encoding = locale.getpreferredencoding() or 'ascii'
            try:
                self._keyboard_decoder = codecs.getincrementaldecoder(
                    self._encoding)()
            except LookupError as err:
                warnings.warn('LookupError: %s, fallback to ASCII for '
                              'keyboard.' % (err,))
                self._encoding = 'ascii'
                self._keyboard_decoder = codecs.getincrementaldecoder(
                    self._encoding)()

        self._stream = stream

    def __getattr__(self, attr):
        r"""
        Return a terminal capability as Unicode string.

        For example, ``term.bold`` is a unicode string that may be prepended
        to text to set the video attribute for bold, which should also be
        terminated with the pairing ``term.normal``.  This capability
        returns a callable, so you can use ``term.bold("hi")`` which
        results in the joining of ``(term.bold, "hi", term.normal)``.

        Compound formatters may also be used, for example:

        >>> term.bold_blink_red_on_green("merry x-mas!").
        u'\x1b[1m\x1b[5m\x1b[31m\x1b[42mmerry x-mas!\x1b[m'

        For a parametrized capability such as ``move`` (cup), pass the
        parameters as positional arguments ``term.move(line, column)``.  See
        manual page of terminfo(5) for a complete list of capabilities and
        their arguments.
        """
        if not self.does_styling:
            return NullCallableString()
        val = resolve_attribute(self, attr)
        # Cache capability codes.
        setattr(self, attr, val)
        return val

    @property
    def kind(self):
        """
        Name of this terminal type.

        :rtype: str
        """
        return self._kind

    @property
    def does_styling(self):
        """
        Whether this instance will emit terminal sequences.

        :rtype: bool
        """
        return self._does_styling

    @property
    def is_a_tty(self):
        """
        Whether :attr:`~.stream` is a terminal.

        :rtype: bool
        """
        return self._is_a_tty

    @property
    def height(self):
        """
        The height of the terminal (by number of character cells).

        :rtype: int
        """
        return self._height_and_width().ws_row

    @property
    def width(self):
        """
        The width of the terminal (by number of character cells).

        :rtype: int
        """
        return self._height_and_width().ws_col

    @staticmethod
    def _winsize(fdesc):
        """
        Return named tuple describing size of the terminal by ``fdesc``.

        If the given platform does not have modules :mod:`termios`,
        :mod:`fcntl`, or :mod:`tty`, window size of 80 columns by 24
        rows is always returned.

        :param int fdesc: file descriptor queries for its window size.
        :raises IOError: the file descriptor ``fdesc`` is not a terminal.
        :rtype: WINSZ

        WINSZ is a :class:`collections.namedtuple` instance, whose structure
        directly maps to the return value of the :const:`termios.TIOCGWINSZ`
        ioctl return value.  The return parameters are:

            - ``ws_row``: width of terminal by its number of character cells.
            - ``ws_col``: height of terminal by its number of character cells.
            - ``ws_xpixel``: width of terminal by pixels (not accurate).
            - ``ws_ypixel``: height of terminal by pixels (not accurate).
        """
        if HAS_TTY:
            data = fcntl.ioctl(fdesc, termios.TIOCGWINSZ, WINSZ._BUF)
            return WINSZ(*struct.unpack(WINSZ._FMT, data))
        return WINSZ(ws_row=24, ws_col=80, ws_xpixel=0, ws_ypixel=0)

    def _height_and_width(self):
        """
        Return a tuple of (terminal height, terminal width).

        If :attr:`stream` or :obj:`sys.__stdout__` is not a tty or does not
        support :func:`fcntl.ioctl` of :const:`termios.TIOCGWINSZ`, a window
        size of 80 columns by 24 rows is returned.

        :rtype: WINSZ

        WINSZ is a :class:`collections.namedtuple` instance, whose structure
        directly maps to the return value of the :const:`termios.TIOCGWINSZ`
        ioctl return value.  The return parameters are:

            - ``ws_row``: width of terminal by its number of character cells.
            - ``ws_col``: height of terminal by its number of character cells.
            - ``ws_xpixel``: width of terminal by pixels (not accurate).
            - ``ws_ypixel``: height of terminal by pixels (not accurate).

        """
        for fdesc in (self._init_descriptor, sys.__stdout__):
            # pylint: disable=pointless-except
            #         Except doesn't do anything
            try:
                if fdesc is not None:
                    return self._winsize(fdesc)
            except IOError:
                pass

        return WINSZ(ws_row=int(os.getenv('LINES', '25')),
                     ws_col=int(os.getenv('COLUMNS', '80')),
                     ws_xpixel=None,
                     ws_ypixel=None)

    @contextlib.contextmanager
    def location(self, x=None, y=None):
        """
        Return a context manager for temporarily moving the cursor.

        :param int x: Move to a specific column (optional).
        :param int y: Move to a specific row (optional).
        :rtype: None

        Move the cursor to a certain position on entry, let you print stuff
        there, then return the cursor to its original position:

        >>> term = Terminal()
        >>> with term.location(2, 5):
        ...     print('Hello, world!')
        >>> print('previous location')

        This context manager yields no value, its side-effect is to write
        the "save cursor position (sc)" sequence upon entering to
        :attr:`stream` and "restore cursor position (rc)" upon entering.

        .. note:: Store and restore cursor provides no stack: This means that
            :meth:`location` calls cannot be chained: only one should be
            entered at a time.
        """
        # pylint: disable=invalid-name
        #         Invalid argument name "x"

        # Save position and move to the requested column, row, or both:
        self.stream.write(self.save)
        if x is not None and y is not None:
            self.stream.write(self.move(y, x))
        elif x is not None:
            self.stream.write(self.move_x(x))
        elif y is not None:
            self.stream.write(self.move_y(y))
        try:
            yield
        finally:
            # Restore original cursor position:
            self.stream.write(self.restore)

    @contextlib.contextmanager
    def fullscreen(self):
        """
        Context manager that switches to alternate screen.

        :rtype: None

        This context manager yields no value, its side-effect is to save
        the primary screen buffer on entering, and to restore it again
        upon exit.  The secondary screen buffer entered while using the
        context manager also remains, and is faithfully restored again
        on the next entrance:

            with term.fullscreen(), term.hidden_cursor():
                main()

        .. note:: There is only one primary and secondary screen: This means
            that :meth:`fullscreen` calls cannot be chained: only one should
            be entered at a time.
        """
        self.stream.write(self.enter_fullscreen)
        try:
            yield
        finally:
            self.stream.write(self.exit_fullscreen)

    @contextlib.contextmanager
    def hidden_cursor(self):
        """
        Context manager that hides the cursor.

        :rtype: None

        This context manager yields no value, its side-effect is to emit
        the ``hide_cursor`` sequence to :attr:`stream` on entering, and
        to emit ``normal_cursor`` sequence upon exit:

            with term.fullscreen(), term.hidden_cursor():
                main()

        .. note:: :meth:`hidden_cursor` calls cannot be chained: only one
            should be entered at a time.
        """
        self.stream.write(self.hide_cursor)
        try:
            yield
        finally:
            self.stream.write(self.normal_cursor)

    @property
    def color(self):
        """
        Callable string that sets the foreground color.

        :arg int num: The foreground color index.  This should be within the
           bounds of :attr:`~.number_of_colors`.

        The capability is unparameterized until called and passed a number
        (0-15), at which point it returns another string which represents a
        specific color change. This second string can further be called to
        color a piece of text and set everything back to normal afterward.
        """
        if not self.does_styling:
            return NullCallableString()
        return ParameterizingString(self._foreground_color,
                                    self.normal, 'color')

    @property
    def on_color(self):
        """
        Capability that sets the background color.

        :arg int num: The background color index.
        :rtype: ParameterizingString
        """
        if not self.does_styling:
            return NullCallableString()
        return ParameterizingString(self._background_color,
                                    self.normal, 'on_color')

    @property
    def normal(self):
        """
        Capability that resets all video attributes.

        :rtype: str

        :attr:`~.normal` is an alias for ``sgr0`` or ``exit_attribute_mode``:
        **any** styling attributes previously applied, such as foreground or
        background colors, reverse video, or bold are set to default.
        """
        if self._normal:
            return self._normal
        self._normal = resolve_capability(self, 'normal')
        return self._normal

    @property
    def stream(self):
        """
        The output stream connected to the terminal.

        This is a convenience attribute.  It is used for implied writes
        performed by context managers :meth:`~.hidden_cursor`,
        :meth:`~.fullscreen`, :meth:`~.location` and :meth:`~.keypad`.
        """
        return self._stream

    @property
    def number_of_colors(self):
        """
        The number of colors the terminal supports.

        Common values are 0, 8, 16, 88, and 256. Most commonly
        this may be used to test whether the terminal supports colors::

            if term.number_of_colors:
                ...
        """
        # trim value to 0, as tigetnum('colors') returns -1 if no support,
        # and -2 if no such capability.
        return max(0, self.does_styling and curses.tigetnum('colors') or -1)

    @property
    def _foreground_color(self):
        """
        Convenience capability to support :attr:`~.on_color`.

        Prefers returning sequence for capability ``setaf``, "Set foreground
        color to #1, using ANSI escape".  If the given terminal does not
        support such sequence, fallback to returning attribute ``setf``,
        "Set foreground color #1".
        """
        return self.setaf or self.setf

    @property
    def _background_color(self):
        """
        Convenience capability to support :attr:`~.on_color`.

        Prefers returning sequence for capability ``setab``, "Set background
        color to #1, using ANSI escape".  If the given terminal does not
        support such sequence, fallback to returning attribute ``setb``,
        "Set background color #1".
        """
        return self.setab or self.setb

    def ljust(self, text, width=None, fillchar=u' '):
        """
        Return string ``text`` containing sequences, left-adjusted.

        :param str text: String of text to be right-adjusted, may contain
            terminal sequences.
        :param int width: Total width given to right-adjust ``text``.  If
            unspecified, the width of the attached terminal is used (default).
        :param str fillchar: String for padding right-of ``text``.
        :returns: String of ``text``, right-aligned by ``width``.
        :rtype: str
        """
        if width is None:
            width = self.width
        return Sequence(text, self).ljust(width, fillchar)

    def rjust(self, text, width=None, fillchar=u' '):
        """
        Return string ``text`` containing sequences, right-adjusted.

        :param str text: String of text to be right-adjusted, may contain
            terminal sequences.
        :param int width: Total width given to right-adjust ``text``.  If
            unspecified, the width of the attached terminal is used (default).
        :param str fillchar: String for padding left-of ``text``.
        :returns: String of ``text``, right-aligned by ``width``.
        :rtype: str
        """
        if width is None:
            width = self.width
        return Sequence(text, self).rjust(width, fillchar)

    def center(self, text, width=None, fillchar=u' '):
        """
        Return string ``text`` containing sequences, centered.

        :param str text: String of text to be centered, may contain terminal
            sequences.
        :param int width: Total width given to center ``text``.  If
            unspecified, the width of the attached terminal is used (default).
        :param str fillchar: String for padding left and right-of ``text``.
        :returns: String of ``text``, centered by ``width``.
        :rtype: str
        """
        if width is None:
            width = self.width
        return Sequence(text, self).center(width, fillchar)

    def length(self, text):
        u"""
        Return printable length of string ``text`` containing sequences.

        :param str text: String of text to determine printable length, may
            contain terminal sequences.
        :rtype: int
        :returns: printable length of string as terminal character cells.

        Strings containing text that consumes 2 character cells are supported.

        >>> term = Terminal()
        >>> term.length(term.clear + term.red(u'コンニチハ'))
        10

        .. note:: Sequences such as 'clear', which is considered as a
            "movement sequence" because it would move the cursor to
            (y, x)(0, 0), are evaluated as a printable length of
            *0*.
        """
        return Sequence(text, self).length()

    def strip(self, text, chars=None):
        r"""
        Return ``text`` without sequences and leading or trailing whitespace.

        :param str text: String of text that may contain terminal
            sequences.
        :returns: Text stripped of sequences and leading or trailing
            whitespace.
        :rtype: str

        >>> term = blessings.Terminal()
        >>> term.strip(u' \x1b[0;3m XXX ')
        u'XXX'
        """
        return Sequence(text, self).strip(chars)

    def rstrip(self, text, chars=None):
        r"""
        Return ``text`` stripped of terminal sequences and trailing whitespace.

        :param str text: String of text that may contain terminal sequences.
        :returns: Text stripped of sequences and trailing whitespace.
        :rtype: str

        >>> term = blessings.Terminal()
        >>> term.rstrip(u' \x1b[0;3m XXX ')
        u'  XXX'
        """
        return Sequence(text, self).rstrip(chars)

    def lstrip(self, text, chars=None):
        r"""
        Return ``text`` stripped of terminal sequences and leading whitespace.

        :param str text: String of text that may contain terminal sequences.
        :returns: Text stripped of sequences and leading whitespace.
        :rtype: str

        >>> term = blessings.Terminal()
        >>> term.lstrip(u' \x1b[0;3m XXX ')
        u'XXX '
        """
        return Sequence(text, self).lstrip(chars)

    def strip_seqs(self, text):
        r"""
        Return ``text`` stripped only of its terminal sequences.

        :param str text: String of text that may contain terminal sequences.
        :returns: Text stripped of sequences.
        :rtype: str

        >>> term = blessings.Terminal()
        >>> term.strip_seqs(u'\x1b[0;3mXXX')
        u'XXX'
        """
        return Sequence(text, self).strip_seqs()

    def wrap(self, text, width=None, **kwargs):
        """
        Wrap a string of ``text``, returning an array of wrapped lines.

        :param str text: Unlike :func:`textwrap.wrap`, ``text`` may contain
            terminal sequences, such as colors, bold, or underline.  By
            default, tabs in ``text`` are expanded by
            :func:`string.expandtabs`.
        :param int width: Unlike :func:`textwrap.wrap`, ``width`` will
            default to the width of the attached terminal.
        :rtype: list
        :returns: list of strings that may contain escape sequences.

        See :class:`textwrap.TextWrapper` class for available keyword arguments
        to customize wrapping behaviour.
        """
        width = self.width if width is None else width
        lines = []
        for line in text.splitlines():
            lines.extend(
                (_linewrap for _linewrap in SequenceTextWrapper(
                    width=width, term=self, **kwargs).wrap(text))
                if line.strip() else (u'',))

        return lines

    def _next_char(self):
        """
        Read and decode next byte from keyboard stream.

        :rtype: unicode
        :returns: a single unicode character, or ``u''`` if a multi-byte
            sequence has not yet been fully received.

        This method supports :meth:`keystroke`, reading only one byte from
        the keyboard string at a time. This method should always return
        without blocking if called when :meth:`_char_is_ready` returns
        True.

        Implementors of alternate input stream methods should override
        this method.
        """
        assert self._keyboard_fd is not None
        byte = os.read(self._keyboard_fd, 1)
        return self._keyboard_decoder.decode(byte, final=False)

    def _char_is_ready(self, timeout=None, interruptable=True):
        """
        Whether a keypress has been detected on the keyboard.

        This method is used by method :meth:`keystroke` to determine if
        a byte may be read using method :meth:`_next_char` without blocking.

        :param float timeout: When ``timeout`` is 0, this call is
            non-blocking, otherwise blocking indefinitely until keypress
            is detected when None (default).  When ``timeout`` is a
            positive number, returns after ``timeout`` seconds have
            elapsed (float).
        :param bool interruptable: Normally, when this function is interrupted
           by a signal, such as the installment of SIGWINCH, this function will
           ignore this interruption and continue to poll for input up to the
           ``timeout`` specified. If you'd rather this function return ``u''``
           early, specify False for ``interruptable``.

           This is an open issue for review to **remove** this parameter,
           https://github.com/erikrose/blessings/issues/96
        :rtype: bool
        :returns: True if a keypress is awaiting to be read on the keyboard
            attached to this terminal.  If input is not a terminal, False is
            always returned.
        """
        # Special care is taken to handle a custom SIGWINCH handler, which
        # causes select() to be interrupted with errno 4 (EAGAIN) --
        # it is ignored, and a new timeout value is derived from the previous,
        # unless timeout becomes negative, because signal handler has blocked
        # beyond timeout, then False is returned. Otherwise, when timeout is 0,
        # we continue to block indefinitely (default).
        stime = time.time()
        ready_r = [None, ]
        check_r = [self._keyboard_fd] if self._keyboard_fd is not None else []

        while HAS_TTY and True:
            try:
                ready_r, _, _ = select.select(check_r, [], [], timeout)
            except InterruptedError:
                if not interruptable:
                    return u''
                if timeout is not None:
                    # subtract time already elapsed,
                    timeout -= time.time() - stime
                    if timeout > 0:
                        continue
                    # no time remains after handling exception (rare)
                    ready_r = []
                    break
            else:
                break

        return False if self._keyboard_fd is None else check_r == ready_r

    @contextlib.contextmanager
    def keystroke_input(self, raw=False):
        """
        Context manager that enables key-at-a-time input.

        Normally, characters received from the keyboard cannot be read by
        python until the return key is pressed: this is referred to as
        "cooked" or "canonical input" mode, allowing the tty driver to perform
        line editing before being read by your program and is usually the
        default mode set by your unix shell before executing any programs.

        Also referred to as 'rare' mode, entering this context is the opposite
        of 'cooked' mode: On entering, :func:`tty.setcbreak` mode is activated,
        disabling line buffering of keyboard input and turning off automatic
        echoing of input.  This allows each keystroke to be received immediately
        after it is pressed.

        :param bool raw: When True, enter :func:`tty.setraw` mode instead.
           Raw mode differs in that the interrupt, quit, suspend, and flow
           control characters are all passed through as their raw character
           values instead of generating a signal.

        This context manager yields no value, its side-effect is to
        set the :mod:`termios` attributes of the terminal attached to
        :obj:`sys.__stdin__`.

        .. note:: you must explicitly print any input received you'd like it
            shown on output.  And, if providing any kind of editing, you must
            also explicitly handle backspacing and other line editing
            control characters.

        .. note:: :func:`tty.setcbreak` sets ``VMIN = 1`` and ``VTIME = 0``,
            see http://www.unixwiz.net/techtips/termios-vmin-vtime.html
        """
        if HAS_TTY and self._keyboard_fd is not None:
            # Save current terminal mode:
            save_mode = termios.tcgetattr(self._keyboard_fd)
            mode_setter = tty.setraw if raw else tty.setcbreak
            mode_setter(self._keyboard_fd, termios.TCSANOW)
            try:
                yield
            finally:
                # Restore prior mode:
                termios.tcsetattr(self._keyboard_fd,
                                  termios.TCSAFLUSH,
                                  save_mode)
        else:
            yield

    @contextlib.contextmanager
    def keypad(self):
        r"""
        Context manager that enables keypad input ("keyboard_transmit" mode).

        This context manager yields no value, its side-effect is to emit
        capability keypad_xmit (smkx) upon entering, and keypad_local
        (rmkx) upon exiting.

        On an IBM-PC keyboard with numeric keypad of terminal-type *xterm*,
        with numlock off, the lower-left diagonal key transmits sequence
        ``\\x1b[F``, translated to :class:`~.Terminal` attribute
        ``KEY_END``.

        However, upon entering :meth:`keypad`, ``\\x1b[OF`` is transmitted,
        translating to ``KEY_LL`` (lower-left key), allowing diagonal
        direction keys to be determined.
        """
        try:
            self.stream.write(self.smkx)
            yield
        finally:
            self.stream.write(self.rmkx)

    def keystroke(self, timeout=None, esc_delay=0.35, interruptable=True):
        """
        Receive and return next keystroke from keyboard within given timeout.

        :param float timeout: Number of seconds to allow to elapse without
           keystroke before returning.  When None (default), this
           method blocks indefinitely.
        :param float esc_delay: To distinguish between ``KEY_ESCAPE`` and
           sequences beginning with escape, the parameter ``esc_delay``
           specifies the amount of time after receiving the escape character
           (``chr(27)``) to seek for the completion of an application key
           before returning a :class:`~.Keystroke` for ``KEY_ESCAPE``.
        :param bool interruptable: Normally, when this function is interrupted
           by a signal, such as the installment of SIGWINCH, this function will
           ignore this interruption and continue to poll for input up to the
           ``timeout`` specified. If you'd rather this function return ``u''``
           early, specify False for ``interruptable``.

           This is an open issue for review to **remove** this parameter,
           https://github.com/erikrose/blessings/issues/96
        :rtype: :class:`~.Keystroke`.
        :raises NoKeyboard: The :attr:`stream` is not a terminal with
            timeout parameter as the default value of None, which would
            cause the program to hang indefinitely.
        :returns: :class:`~.Keystroke`, which may be empty (``u''``) if
           ``timeout`` is specified and keystroke is not received.

        .. note:: When used without the context manager
            :meth:`keystroke_input`, :obj:`sys.__stdin__` remains line-buffered,
            and this function will block until the return key is pressed.
        """
        if timeout is None and self._keyboard_fd is None:
            raise NoKeyboard(
                'Waiting for a keystroke on a terminal with no keyboard '
                'attached and no timeout would take a long time. Add a '
                'timeout and revise your program logic.')

        def time_left(stime, timeout):
            """
            Return time remaining since ``stime`` before given ``timeout``.

            This function assists determining the value of ``timeout`` for
            class method :meth:`_char_is_ready`.

            :param float stime: starting time for measurement
            :param float timeout: timeout period, may be set to None to
               indicate no timeout (where 0 is always returned).
            :rtype: float or int
            :returns: time remaining as float.  If no time is remaining,
               then the integer ``0`` is returned.
            """
            if timeout is not None:
                if timeout == 0:
                    return 0
                return max(0, timeout - (time.time() - stime))

        resolve = functools.partial(resolve_sequence,
                                    mapper=self._keymap,
                                    codes=self._keycodes)

        stime = time.time()

        # re-buffer previously received keystrokes,
        ucs = u''
        while self._keyboard_buf:
            ucs += self._keyboard_buf.pop()

        # receive all immediately available bytes
        while self._char_is_ready(0):
            ucs += self._next_char()

        # decode keystroke, if any
        keystroke = resolve(text=ucs)

        # so long as the most immediately received or buffered keystroke is
        # incomplete, (which may be a multibyte encoding), block until until
        # one is received.
        while (not keystroke and
               self._char_is_ready(time_left(stime, timeout), interruptable)):
            ucs += self._next_char()
            keystroke = resolve(text=ucs)

        # handle escape key (KEY_ESCAPE) vs. escape sequence (which begins
        # with KEY_ESCAPE, \x1b[, \x1bO, or \x1b?), up to esc_delay when
        # received. This is not optimal, but causes least delay when
        # (currently unhandled, and rare) "meta sends escape" is used,
        # or when an unsupported sequence is sent.
        if keystroke.code == self.KEY_ESCAPE:
            esctime = time.time()
            while (keystroke.code == self.KEY_ESCAPE and
                   self._char_is_ready(time_left(esctime, esc_delay))):
                ucs += self._next_char()
                keystroke = resolve(text=ucs)

        # buffer any remaining text received
        self._keyboard_buf.extendleft(ucs[len(keystroke):])
        return keystroke


class NoKeyboard(Exception):

    """Illegal operation requiring a keyboard without one attached."""


class WINSZ(collections.namedtuple('WINSZ', (
        'ws_row', 'ws_col', 'ws_xpixel', 'ws_ypixel'))):

    """
    Structure represents return value of :const:`termios.TIOCGWINSZ`.

    .. py:attribute:: ws_row

        rows, in characters

    .. py:attribute:: ws_col

        columns, in characters

    .. py:attribute:: ws_xpixel

        horizontal size, pixels

    .. py:attribute:: ws_ypixel

        vertical size, pixels
    """

    #: format of termios structure
    _FMT = 'hhhh'
    #: buffer of termios structure appropriate for ioctl argument
    _BUF = '\x00' * struct.calcsize(_FMT)

#: From libcurses/doc/ncurses-intro.html (ESR, Thomas Dickey, et. al)::
#:
#:   "After the call to setupterm(), the global variable cur_term is set to
#:    point to the current structure of terminal capabilities. By calling
#:    setupterm() for each terminal, and saving and restoring cur_term, it
#:    is possible for a program to use two or more terminals at once."
#:
#: However, if you study Python's ./Modules/_cursesmodule.c, you'll find::
#:
#:   if (!initialised_setupterm && setupterm(termstr,fd,&err) == ERR) {
#:
#: Python - perhaps wrongly - will not allow for re-initialisation of new
#: terminals through setupterm(), so the value of cur_term cannot be changed
#: once set: subsequent calls to setupterm() have no effect.
#:
#: Therefore, the ``kind`` of each Terminal() is, in essence, a singleton.
#: This global variable reflects that, and a warning is emitted if somebody
#: expects otherwise.
_CUR_TERM = None
