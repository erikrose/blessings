"This primary module provides the Terminal class."
# standard modules
import collections
import contextlib
import warnings
import platform
import codecs
import curses
import locale
import struct
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
        """A dummy exception to take the place of Python 3's
        ``io.UnsupportedOperation`` in Python 2.5"""

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
    BufferedKeyboard,
    resolve_sequence,
)


class Terminal(object):
    """A wrapper for curses and related terminfo(5) terminal capabilities.

    Instance attributes:

      ``stream``
        The stream the terminal outputs to. It's convenient to pass the stream
        around with the terminal; it's almost always needed when the terminal
        is and saves sticking lots of extra args on client functions in
        practice.
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
        """Initialize the terminal.

        If ``stream`` is not a tty, I will default to returning an empty
        Unicode string for all capability values, so things like piping your
        output to a file won't strew escape sequences all over the place. The
        ``ls`` command sets a precedent for this: it defaults to columnar
        output when being sent to a tty and one-item-per-line when not.

        :arg kind: A terminal string as taken by ``setupterm()``. Defaults to
            the value of the ``TERM`` environment variable.
        :arg stream: A file-like object representing the terminal. Defaults to
            the original value of stdout, like ``curses.initscr()`` does.
        :arg force_styling: Whether to force the emission of capabilities, even
            if we don't seem to be in a terminal. This comes in handy if users
            are trying to pipe your output through something like ``less -r``,
            which supports terminal codes just fine but doesn't appear itself
            to be a terminal. Just expose a command-line option, and set
            ``force_styling`` based on it. Terminal initialization sequences
            will be sent to ``stream`` if it has a file descriptor and to
            ``sys.__stdout__`` otherwise. (``setupterm()`` demands to send them
            somewhere, and stdout is probably where the output is ultimately
            headed. If not, stderr is probably bound to the same terminal.)

            If you want to force styling to not happen, pass
            ``force_styling=None``.

        """
        global _CUR_TERM
        self.keyboard_fd = None

        # default stream is stdout, keyboard only valid as stdin when
        # output stream is stdout and output stream is a tty
        if stream is None or stream == sys.__stdout__:
            stream = sys.__stdout__
            self.keyboard_fd = sys.__stdin__.fileno()

        try:
            stream_fd = (stream.fileno() if hasattr(stream, 'fileno')
                         and callable(stream.fileno) else None)
        except IOUnsupportedOperation:
            stream_fd = None

        self._is_a_tty = stream_fd is not None and os.isatty(stream_fd)
        self._does_styling = ((self.is_a_tty or force_styling) and
                              force_styling is not None)

        # keyboard_fd only non-None if both stdin and stdout is a tty.
        self.keyboard_fd = (self.keyboard_fd
                            if self.keyboard_fd is not None and
                            self.is_a_tty and os.isatty(self.keyboard_fd)
                            else None)
        self._normal = None  # cache normal attr, preventing recursive lookups

        # The descriptor to direct terminal initialization sequences to.
        # sys.__stdout__ seems to always have a descriptor of 1, even if output
        # is redirected.
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
                    curses.setupterm(self._kind.encode('ascii'), self._init_descriptor)
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

        # build database of int code <=> KEY_NAME
        self._keycodes = get_keyboard_codes()

        # store attributes as: self.KEY_NAME = code
        for key_code, key_name in self._keycodes.items():
            setattr(self, key_name, key_code)

        # build database of sequence <=> KEY_NAME
        self._keymap = get_keyboard_sequences(self)

        if self.keyboard_fd is not None:
            locale.setlocale(locale.LC_ALL, '')
            self._encoding = locale.getpreferredencoding() or 'ascii'
            try:
                self._keyboard_decoder = codecs.getincrementaldecoder(
                    self._encoding)()
            except LookupError as err:
                warnings.warn('%s, fallback to ASCII for keyboard.' % (err,))
                self._encoding = 'ascii'
                self._keyboard_decoder = codecs.getincrementaldecoder(
                    self._encoding)()

        self.stream = stream

    def __getattr__(self, attr):
        """Return a terminal capability as Unicode string.

        For example, ``term.bold`` is a unicode string that may be prepended
        to text to set the video attribute for bold, which should also be
        terminated with the pairing ``term.normal``.

        This capability is also callable, so you can use ``term.bold("hi")``
        which results in the joining of (term.bold, "hi", term.normal).

        Compound formatters may also be used, for example:
        ``term.bold_blink_red_on_green("merry x-mas!")``.

        For a parametrized capability such as ``cup`` (cursor_address), pass
        the parameters as arguments ``some_term.cup(line, column)``. See
        manual page terminfo(5) for a complete list of capabilities.
        """
        if not self.does_styling:
            return NullCallableString()
        val = resolve_attribute(self, attr)
        # Cache capability codes.
        setattr(self, attr, val)
        return val

    @property
    def kind(self):
        """Name of this terminal type as string."""
        return self._kind

    @property
    def does_styling(self):
        """Whether this instance will emit terminal sequences (bool)."""
        return self._does_styling

    @property
    def is_a_tty(self):
        """Whether the ``stream`` associated with this instance is a terminal
        (bool)."""
        return self._is_a_tty

    @property
    def height(self):
        """T.height -> int

        The height of the terminal in characters.
        """
        return self._height_and_width().ws_row

    @property
    def width(self):
        """T.width -> int

        The width of the terminal in characters.
        """
        return self._height_and_width().ws_col

    @staticmethod
    def _winsize(fd):
        """T._winsize -> WINSZ(ws_row, ws_col, ws_xpixel, ws_ypixel)

        The tty connected by file desriptor fd is queried for its window size,
        and returned as a collections.namedtuple instance WINSZ.

        May raise exception IOError.
        """
        if HAS_TTY:
            data = fcntl.ioctl(fd, termios.TIOCGWINSZ, WINSZ._BUF)
            return WINSZ(*struct.unpack(WINSZ._FMT, data))
        return WINSZ(ws_row=24, ws_col=80, ws_xpixel=0, ws_ypixel=0)

    def _height_and_width(self):
        """Return a tuple of (terminal height, terminal width).
        """
        # TODO(jquast): hey kids, even if stdout is redirected to a file,
        # we can still query sys.__stdin__.fileno() for our terminal size.
        # -- of course, if both are redirected, we have no use for this fd.
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
                print 'Hello, world!'
                for x in xrange(10):
                    print 'I can do it %i times!' % x

        Specify ``x`` to move to a certain column, ``y`` to move to a certain
        row, both, or neither. If you specify neither, only the saving and
        restoration of cursor position will happen. This can be useful if you
        simply want to restore your place after doing some manual cursor
        movement.

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
        """Return a context manager that enters fullscreen mode while inside it
        and restores normal mode on leaving.

        Fullscreen mode is characterized by instructing the terminal emulator
        to store and save the current screen state (all screen output), switch
        to "alternate screen". Upon exiting, the previous screen state is
        returned.

        This call may not be tested; only one screen state may be saved at a
        time.
        """
        self.stream.write(self.enter_fullscreen)
        try:
            yield
        finally:
            self.stream.write(self.exit_fullscreen)

    @contextlib.contextmanager
    def hidden_cursor(self):
        """Return a context manager that hides the cursor upon entering,
        and makes it visible again upon exiting."""
        self.stream.write(self.hide_cursor)
        try:
            yield
        finally:
            self.stream.write(self.normal_cursor)

    @property
    def color(self):
        """Returns capability that sets the foreground color.

        The capability is unparameterized until called and passed a number
        (0-15), at which point it returns another string which represents a
        specific color change. This second string can further be called to
        color a piece of text and set everything back to normal afterward.

        :arg num: The number, 0-15, of the color

        """
        if not self.does_styling:
            return NullCallableString()
        return ParameterizingString(self._foreground_color,
                                    self.normal, 'color')

    @property
    def on_color(self):
        "Returns capability that sets the background color."
        if not self.does_styling:
            return NullCallableString()
        return ParameterizingString(self._background_color,
                                    self.normal, 'on_color')

    @property
    def normal(self):
        "Returns sequence that resets video attribute."
        if self._normal:
            return self._normal
        self._normal = resolve_capability(self, 'normal')
        return self._normal

    @property
    def number_of_colors(self):
        """Return the number of colors the terminal supports.

        Common values are 0, 8, 16, 88, and 256. Most commonly
        this may be used to test color capabilities at all::

            if term.number_of_colors:
                ..."""
        # trim value to 0, as tigetnum('colors') returns -1 if no support,
        # -2 if no such capability.
        return max(0, self.does_styling and curses.tigetnum('colors') or -1)

    @property
    def _foreground_color(self):
        return self.setaf or self.setf

    @property
    def _background_color(self):
        return self.setab or self.setb

    def ljust(self, text, width=None, fillchar=u' '):
        """T.ljust(text, [width], [fillchar]) -> unicode

        Return string ``text``, left-justified by printable length ``width``.
        Padding is done using the specified fill character (default is a
        space).  Default ``width`` is the attached terminal's width. ``text``
        may contain terminal sequences."""
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

    @contextlib.contextmanager
    def key_mode(self, raw=False):
        """Return a context manager that sets up the terminal to do
        key-at-a-time input.

        On entering the context manager, "cbreak" mode is activated, disabling
        line buffering of keyboard input and turning off automatic echoing of
        input. (You must explicitly print any input if you'd like it shown.)
        Also referred to as 'rare' mode, this is the opposite of 'cooked' mode,
        the default for most shells.

        Entering the context manager also yields a callable for retrieving a
        single keypress worth of input. See Recommend use::

            with term.key_mode() as key:
                a_key = key()

        If ``raw`` is True, enter "raw" mode instead of "cbreak" mode. Raw mode
        differs in that the interrupt, quit, suspend, and flow control
        characters are all passed through as their raw character values instead
        of generating a signal.

        More information can be found in the manual page for curses.h,
        http://www.openbsd.org/cgi-bin/man.cgi?query=cbreak

        The python manual for curses,
        http://docs.python.org/2/library/curses.html

        Note also that setcbreak sets VMIN = 1 and VTIME = 0,
        http://www.unixwiz.net/techtips/termios-vmin-vtime.html

        """
        if HAS_TTY and self.keyboard_fd is not None:
            # Save current terminal mode:
            save_mode = termios.tcgetattr(self.keyboard_fd)
            mode_setter = tty.setraw if raw else tty.setcbreak
            mode_setter(self.keyboard_fd, termios.TCSANOW)
            try:
                yield BufferedKeyboard(self._keymap,
                                       self._keycodes,
                                       self.KEY_ESCAPE,
                                       self.keyboard_fd,
                                       self._keyboard_decoder,
                                       HAS_TTY).key
            finally:
                # Restore prior mode:
                termios.tcsetattr(self.keyboard_fd,
                                  termios.TCSAFLUSH,
                                  save_mode)
        else:
            raise NoKeyboard

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


class NoKeyboard(Exception):
    """Exception raised when a Terminal that has no means of input connected is
    asked to perform input tasks."""


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
