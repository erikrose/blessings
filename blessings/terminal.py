"""
This module contains :class:`Terminal`, the primary API interface of Blessings.
"""
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

try:
    import termios
    import fcntl
    import tty
except ImportError:
    tty_methods = ('setraw', 'cbreak', 'kbhit', 'height', 'width')
    msg_nosupport = (
        "One or more of the modules: 'termios', 'fcntl', and 'tty' "
        "are not found on your platform '{0}'. The following methods "
        "of Terminal are dummy/no-op unless a deriving class overrides "
        "them: {1}".format(sys.platform.lower(), ', '.join(tty_methods)))
    warnings.warn(msg_nosupport)
    HAS_TTY = False
else:
    HAS_TTY = True

try:
    from io import UnsupportedOperation as IOUnsupportedOperation
except ImportError:
    class IOUnsupportedOperation(Exception):
        """
        A dummy exception to take the place of Python 3's
        :class:`io.UnsupportedOperation` in Python 2.5
        """

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

    """
    Wrapper for curses and related terminfo(5) terminal capabilities.
    """

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
        """Initialize the Terminal.

        If ``stream`` is not a tty, I will default to returning an empty
        Unicode string for all capability values, so things like piping your
        output to a file won't strew escape sequences all over the place. The
        ``ls`` command sets a precedent for this: it defaults to columnar
        output when being sent to a tty and one-item-per-line when not.

        :param str kind: A terminal string as taken by
            :func:`curses.setupterm`.  Defaults to the value of the ``TERM``
            Environment variable.
        :param stream: A file-like object representing the Terminal. Defaults
            to the original value of ``sys.__stdout__``, like
            :func:`curses.initscr` does.
        :param bool force_styling: Whether to force the emission of
            capabilities, even if stdout does not seem to be connected to a
            terminal. This comes in handy if users are trying to pipe your
            output through something like ``less -r`` or build systems which
            support decoding of terminal sequences.

            If you want to force styling to not happen, pass
            ``force_styling=None``.
        """
        global _CUR_TERM
        self._keyboard_fd = None

        # Default stream is stdout, keyboard only valid as stdin when
        # output stream is stdout is a tty.
        if stream is None or stream == sys.__stdout__:
            stream = sys.__stdout__
            self._keyboard_fd = sys.__stdin__.fileno()

        try:
            stream_fd = (stream.fileno() if hasattr(stream, 'fileno')
                         and callable(stream.fileno) else None)
        except IOUnsupportedOperation:
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
        self._init_descriptor = (stream_fd is None and sys.__stdout__.fileno()
                                 or stream_fd)
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
        """Return a terminal capability as Unicode string.

        For example, ``term.bold`` is a unicode string that may be prepended
        to text to set the video attribute for bold, which should also be
        terminated with the pairing ``term.normal``.

        This capability returns a callable, so you can use ``term.bold("hi")``
        which results in the joining of ``(term.bold, "hi", term.normal)``.

        Compound formatters may also be used, for example:
        ``term.bold_blink_red_on_green("merry x-mas!")``.

        For a parametrized capability such as ``move`` (cup), pass the
        parameters as positional arguments ``term.move(line, column)``.  See
        manual page `terminfo(5)`_ for a complete list of capabilities and
        their arguments.

        .. _terminfo(5): http://www.openbsd.org/cgi-bin/man.cgi?query=terminfo&apropos=0&sektion=5
        """
        if not self.does_styling:
            return NullCallableString()
        val = resolve_attribute(self, attr)
        # Cache capability codes.
        setattr(self, attr, val)
        return val

    @property
    def kind(self):
        """Name of this terminal type.

        :rtype: str
        """
        return self._kind

    @property
    def does_styling(self):
        """Whether this instance will emit terminal sequences.

        :rtype: bool
        """
        return self._does_styling

    @property
    def is_a_tty(self):
        """Whether :attr:`~.stream` is a terminal.

        :rtype: bool
        """
        return self._is_a_tty

    @property
    def height(self):
        """The height of the terminal (by number of character cells).

        :rtype: int
        """
        return self._height_and_width().ws_row

    @property
    def width(self):
        """The width of the terminal (by number of character cells).

        :rtype: int
        """
        return self._height_and_width().ws_col

    @staticmethod
    def _winsize(fd):
        """Return named tuple describing size of the terminal by ``fd``.

        If the given platform does not have modules :mod:`termios`,
        :mod:`fcntl`, or :mod:`tty`, window size of 80 columns by 24
        rows is always returned.

        :param int fd: file descriptor queries for its window size.
        :raises IOError: the file descriptor ``fd`` is not a terminal.
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
            data = fcntl.ioctl(fd, termios.TIOCGWINSZ, WINSZ._BUF)
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
        for fd in (self._init_descriptor, sys.__stdout__):
            try:
                if fd is not None:
                    return self._winsize(fd)
            except IOError:
                pass

        return WINSZ(ws_row=int(os.getenv('LINES', '25')),
                     ws_col=int(os.getenv('COLUMNS', '80')),
                     ws_xpixel=None,
                     ws_ypixel=None)

    @contextlib.contextmanager
    def location(self, x=None, y=None):
        """Return a context manager for temporarily moving the cursor.

        Move the cursor to a certain position on entry, let you print stuff
        there, then return the cursor to its original position::

            term = Terminal()
            with term.location(2, 5):
                print('Hello, world!')
            print('previous location')

        Specify ``x`` to move to a certain column, ``y`` to move to a certain
        row, both, or neither. If you specify neither, only the saving and
        restoration of cursor position will happen. This can be useful if you
        simply want to restore your place after doing some manual cursor
        movement.

        :rtype: None
        """
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
        """Context manager that switches to alternate screen.

        "Fullscreen mode" is characterized by instructing the terminal to
        store and save the current output display before switching to an
        "alternate screen" (which often begins as an empty screen).  Upon
        exiting, the previous screen state is returned::

            with term.fullscreen(), term.hidden_cursor():
                main()

        There is only 1 primary and secondary screen: you should not use this
        context manager more than once within the same context.

        :rtype: None
        """
        self.stream.write(self.enter_fullscreen)
        try:
            yield
        finally:
            self.stream.write(self.exit_fullscreen)

    @contextlib.contextmanager
    def hidden_cursor(self):
        """Context manager that hides the cursor.

        Upon entering, ``hide_cursor`` is emitted to :attr:`stream`, and
        ``normal_cursor`` is emitted upon exit.

        You should not use this context manager more than once within the
        same context.

        :rtype: None
        """
        self.stream.write(self.hide_cursor)
        try:
            yield
        finally:
            self.stream.write(self.normal_cursor)

    @property
    def color(self):
        """Return capability that sets the foreground color.

        The capability is unparameterized until called and passed a number
        (0-15), at which point it returns another string which represents a
        specific color change. This second string can further be called to
        color a piece of text and set everything back to normal afterward.

        :arg int num: The foreground color index.  This should be within the
           bounds of :attr:`~.number_of_colors`.
        """
        if not self.does_styling:
            return NullCallableString()
        return ParameterizingString(self._foreground_color,
                                    self.normal, 'color')

    @property
    def on_color(self):
        """Return capability that sets the background color.

        :arg int num: The background color index.
        """
        if not self.does_styling:
            return NullCallableString()
        return ParameterizingString(self._background_color,
                                    self.normal, 'on_color')

    @property
    def normal(self):
        """Return sequence that resets all video attributes.

        :attr:`~.normal` is an alias for ``sgr0`` or ``exit_attribute_mode``:
        any attributes previously applied (such as foreground or
        background colors, reverse video, or bold) are unset.
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
        """The number of colors the terminal supports.

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
        """Convenience property used by :attr:`~.color`.

        Prefers returning sequence for capability ``setaf``, "Set foreground
        color to #1, using ANSI escape".  If the given terminal does not
        support such sequence, fallback to returning attribute ``setf``, "Set
        foreground color #1".
        """
        return self.setaf or self.setf

    @property
    def _background_color(self):
        """Convenience property used by :attr:`~.on_color`.

        Prefers returning sequence for capability ``setab``, "Set background
        color to #1, using ANSI escape".  If the given terminal does not
        support such sequence, fallback to returning attribute ``setb``, "Set
        background color #1".
        """
        return self.setab or self.setb

    def ljust(self, text, width=None, fillchar=u' '):
        """A sequence and window-size aware equivalent to :meth:`str.ljust`.

        String ``text`` is left-justified by ``width``, which defaults to the
        width of the terminal.  Return string ``text``, left-justified by
        printable length ``width``.  Padding is done using the specified
        ``fillchar`` (default is a space). ``text`` may contain terminal
        sequences::

            print(term.ljust(term.bold('page 1 of 9')))
        """
        if width is None:
            width = self.width
        return Sequence(text, self).ljust(width, fillchar)

    def rjust(self, text, width=None, fillchar=u' '):
        """T.rjust(text, [width], [fillchar]) -> unicode

        Return string ``text``, right-justified by printable length ``width``.
        Padding is done using the specified fill character (default is a
        space).  Default ``width`` is the attached terminal's width. ``text``
        may contain terminal sequences."""
        if width is None:
            width = self.width
        return Sequence(text, self).rjust(width, fillchar)

    def center(self, text, width=None, fillchar=u' '):
        """T.center(text, [width], [fillchar]) -> unicode

        Return string ``text``, centered by printable length ``width``.
        Padding is done using the specified fill character (default is a
        space).  Default ``width`` is the attached terminal's width. ``text``
        may contain terminal sequences."""
        if width is None:
            width = self.width
        return Sequence(text, self).center(width, fillchar)

    def length(self, text):
        """T.length(text) -> int

        Return the printable length of string ``text``, which may contain
        terminal sequences.  Strings containing sequences such as 'clear',
        which repositions the cursor, does not give accurate results, and
        their printable length is evaluated *0*..
        """
        return Sequence(text, self).length()

    def strip(self, text, chars=None):
        """T.strip(text) -> unicode

        Return string ``text`` with terminal sequences removed, and leading
        and trailing whitespace removed.
        """
        return Sequence(text, self).strip(chars)

    def rstrip(self, text, chars=None):
        """T.rstrip(text) -> unicode

        Return string ``text`` with terminal sequences and trailing whitespace
        removed.
        """
        return Sequence(text, self).rstrip(chars)

    def lstrip(self, text, chars=None):
        """T.lstrip(text) -> unicode

        Return string ``text`` with terminal sequences and leading whitespace
        removed.
        """
        return Sequence(text, self).lstrip(chars)

    def strip_seqs(self, text):
        """T.strip_seqs(text) -> unicode

        Return string ``text`` stripped only of its sequences.
        """
        return Sequence(text, self).strip_seqs()

    def wrap(self, text, width=None, **kwargs):
        """T.wrap(text, [width=None, **kwargs ..]) -> list[unicode]

        Wrap paragraphs containing escape sequences ``text`` to the full
        ``width`` of Terminal instance *T*, unless ``width`` is specified.
        Wrapped by the virtual printable length, irregardless of the video
        attribute sequences it may contain, allowing text containing colors,
        bold, underline, etc. to be wrapped.

        Returns a list of strings that may contain escape sequences. See
        ``textwrap.TextWrapper`` for all available additional kwargs to
        customize wrapping behavior such as ``subsequent_indent``.
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
        """T._next_char() -> unicode

        Read and decode next byte from keyboard stream.  May return u''
        if decoding is not yet complete, or completed unicode character.
        Should always return bytes when self._char_is_ready() returns True.

        Implementors of input streams other than os.read() on the stdin fd
        should derive and override this method.
        """
        assert self._keyboard_fd is not None
        byte = os.read(self._keyboard_fd, 1)
        return self._keyboard_decoder.decode(byte, final=False)

    def _char_is_ready(self, timeout=None, interruptable=True):
        """T._char_is_ready([timeout=None]) -> bool

        Returns True if a keypress has been detected on keyboard.

        When ``timeout`` is 0, this call is non-blocking, Otherwise blocking
        until keypress is detected (default).  When ``timeout`` is a positive
        number, returns after ``timeout`` seconds have elapsed.

        If input is not a terminal, False is always returned.
        """
        # Special care is taken to handle a custom SIGWINCH handler, which
        # causes select() to be interrupted with errno 4 (EAGAIN) --
        # it is ignored, and a new timeout value is derived from the previous,
        # unless timeout becomes negative, because signal handler has blocked
        # beyond timeout, then False is returned. Otherwise, when timeout is 0,
        # we continue to block indefinitely (default).
        stime = time.time()
        check_w, check_x, ready_r = [], [], [None, ]
        check_r = [self._keyboard_fd] if self._keyboard_fd is not None else []

        while HAS_TTY and True:
            try:
                ready_r, ready_w, ready_x = select.select(
                    check_r, check_w, check_x, timeout)
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
        """Return a context manager that sets up the terminal to do
        key-at-a-time input.

        On entering the context manager, "cbreak" mode is activated, disabling
        line buffering of keyboard input and turning off automatic echoing of
        input. (You must explicitly print any input if you'd like it shown.)
        Also referred to as 'rare' mode, this is the opposite of 'cooked' mode,
        the default for most shells.

        If ``raw`` is True, enter "raw" mode instead. Raw mode differs in that
        the interrupt, quit, suspend, and flow control characters are all
        passed through as their raw character values instead of generating a
        signal.

        More information can be found in the manual page for curses.h,
        http://www.openbsd.org/cgi-bin/man.cgi?query=cbreak

        The python manual for curses,
        http://docs.python.org/2/library/curses.html

        Note also that setcbreak sets VMIN = 1 and VTIME = 0,
        http://www.unixwiz.net/techtips/termios-vmin-vtime.html
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
        """
        Context manager that enables keypad input (*keyboard_transmit* mode).

        This enables the effect of calling the curses function keypad(3x):
        display terminfo(5) capability `keypad_xmit` (smkx) upon entering,
        and terminfo(5) capability `keypad_local` (rmkx) upon exiting.

        On an IBM-PC keypad of ttype *xterm*, with numlock off, the
        lower-left diagonal key transmits sequence ``\\x1b[F``, ``KEY_END``.

        However, upon entering keypad mode, ``\\x1b[OF`` is transmitted,
        translating to ``KEY_LL`` (lower-left key), allowing diagonal
        direction keys to be determined.
        """
        try:
            self.stream.write(self.smkx)
            yield
        finally:
            self.stream.write(self.rmkx)

    def keystroke(self, timeout=None, esc_delay=0.35, interruptable=True):
        """T.keystroke(timeout=None, [esc_delay, [interruptable]]) -> Keystroke

        Receive next keystroke from keyboard (stdin), blocking until a
        keypress is received or ``timeout`` elapsed, if specified.

        When used without the context manager ``cbreak``, stdin remains
        line-buffered, and this function will block until return is pressed,
        even though only one unicode character is returned at a time..

        The value returned is an instance of ``Keystroke``, with properties
        ``is_sequence``, and, when True, non-None values for attributes
        ``code`` and ``name``. The value of ``code`` may be compared against
        attributes of this terminal beginning with *KEY*, such as
        ``KEY_ESCAPE``.

        To distinguish between ``KEY_ESCAPE`` and sequences beginning with
        escape, the ``esc_delay`` specifies the amount of time after receiving
        the escape character (chr(27)) to seek for the completion
        of other application keys before returning ``KEY_ESCAPE``.

        Normally, when this function is interrupted by a signal, such as the
        installment of SIGWINCH, this function will ignore this interruption
        and continue to poll for input up to the ``timeout`` specified. If
        you'd rather this function return ``u''`` early, specify ``False`` for
        ``interruptable``.
        """
        # TODO(jquast): "meta sends escape", where alt+1 would send '\x1b1',
        #               what do we do with that? Surely, something useful.
        #               comparator to term.KEY_meta('x') ?
        # TODO(jquast): Ctrl characters, KEY_CTRL_[A-Z], and the rest;
        #               KEY_CTRL_\, KEY_CTRL_{, etc. are not legitimate
        #               attributes. comparator to term.KEY_ctrl('z') ?

        if timeout is None and self._keyboard_fd is None:
            raise NoKeyboard(
                'Waiting for a keystroke on a terminal with no keyboard '
                'attached and no timeout would take a long time. Add a '
                'timeout and revise your program logic.')

        def time_left(stime, timeout):
            """time_left(stime, timeout) -> float

            Returns time-relative time remaining before ``timeout``
            after time elapsed since ``stime``.
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
        ks = resolve(text=ucs)

        # so long as the most immediately received or buffered keystroke is
        # incomplete, (which may be a multibyte encoding), block until until
        # one is received.
        while not ks and self._char_is_ready(time_left(stime, timeout),
                                             interruptable):
            ucs += self._next_char()
            ks = resolve(text=ucs)

        # handle escape key (KEY_ESCAPE) vs. escape sequence (which begins
        # with KEY_ESCAPE, \x1b[, \x1bO, or \x1b?), up to esc_delay when
        # received. This is not optimal, but causes least delay when
        # (currently unhandled, and rare) "meta sends escape" is used,
        # or when an unsupported sequence is sent.
        if ks.code == self.KEY_ESCAPE:
            esctime = time.time()
            while (ks.code == self.KEY_ESCAPE and
                   self._char_is_ready(time_left(esctime, esc_delay))):
                ucs += self._next_char()
                ks = resolve(text=ucs)

        # buffer any remaining text received
        self._keyboard_buf.extendleft(ucs[len(ks):])
        return ks


class NoKeyboard(Exception):
    """Exception raised when a Terminal that has no means of input connected is
    asked to retrieve a keystroke without an infinite timeout."""


# From libcurses/doc/ncurses-intro.html (ESR, Thomas Dickey, et. al):
#
#   "After the call to setupterm(), the global variable cur_term is set to
#    point to the current structure of terminal capabilities. By calling
#    setupterm() for each terminal, and saving and restoring cur_term, it
#    is possible for a program to use two or more terminals at once."
#
# However, if you study Python's ./Modules/_cursesmodule.c, you'll find:
#
#   if (!initialised_setupterm && setupterm(termstr,fd,&err) == ERR) {
#
# Python - perhaps wrongly - will not allow for re-initialisation of new
# terminals through setupterm(), so the value of cur_term cannot be changed
# once set: subsequent calls to setupterm() have no effect.
#
# Therefore, the ``kind`` of each Terminal() is, in essence, a singleton.
# This global variable reflects that, and a warning is emitted if somebody
# expects otherwise.

_CUR_TERM = None

WINSZ = collections.namedtuple('WINSZ', (
    'ws_row',     # /* rows, in characters */
    'ws_col',     # /* columns, in characters */
    'ws_xpixel',  # /* horizontal size, pixels */
    'ws_ypixel',  # /* vertical size, pixels */
))
#: format of termios structure
WINSZ._FMT = 'hhhh'
#: buffer of termios structure appropriate for ioctl argument
WINSZ._BUF = '\x00' * struct.calcsize(WINSZ._FMT)
