from contextlib import contextmanager
import curses
import curses.has_key
import curses.ascii
from curses import tigetstr, tigetnum, setupterm, tparm
try:
    from io import UnsupportedOperation as IOUnsupportedOperation
except ImportError:
    class IOUnsupportedOperation(Exception):
        """A dummy exception to take the place of Python 3's ``io.UnsupportedOperation`` in Python 2"""
import os
from platform import python_version_tuple
import textwrap
import warnings
import codecs
import struct
import time
import math
import sys
import re

if sys.platform == 'win32':
    import msvcrt
else:
    import termios
    import select
    import fcntl
    import tty

__all__ = ['Terminal']


if ('3', '0', '0') <= python_version_tuple() < ('3', '2', '2+'):  # Good till 3.2.10
    # Python 3.x < 3.2.3 has a bug in which tparm() erroneously takes a string.
    raise ImportError('Blessings needs Python 3.2.3 or greater for Python 3 '
                      'support due to http://bugs.python.org/issue10570.')


class Terminal(object):
    """An abstraction around terminal capabilities

    Unlike curses, this doesn't require clearing the screen before doing
    anything, and it's friendlier to use. It keeps the endless calls to
    ``tigetstr()`` and ``tparm()`` out of your code, and it acts intelligently
    when somebody pipes your output to a non-terminal.

    Instance attributes:

      ``stream``
        The stream the terminal outputs to. It's convenient to pass the stream
        around with the terminal; it's almost always needed when the terminal
        is and saves sticking lots of extra args on client functions in
        practice.
      ``is_a_tty``
        Whether ``stream`` appears to be a terminal. You can examine this value
        to decide whether to draw progress bars or other frippery.

    """
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
        if stream is None:
            o_stream = sys.__stdout__
            i_stream = sys.__stdin__
        else:
            o_stream = stream
            i_stream = None
        try:
            o_fd = (o_stream.fileno() if hasattr(o_stream, 'fileno')
                             and callable(o_stream.fileno) else None)

        except IOUnsupportedOperation:
            o_fd = None

        # os.isatty returns True if output stream is an open file descriptor
        # connected to the slave end of a terminal.
        self.is_a_tty = (o_stream is not None and os.isatty(o_fd))
        self.do_styling = ((self.is_a_tty or force_styling) and
                              force_styling is not None)

        # The desciptor to direct terminal sequences to.
        self.o_fd = (sys.__stdout__.fileno() if o_stream is None else o_fd)
        if self.do_styling:
            # Make things like tigetstr() work. Explicit args make setupterm()
            # work even when -s is passed to nosetests. Lean toward sending
            # init sequences to the stream if it has a file descriptor, and
            # send them to stdout as a fallback, since they have to go
            # somewhere.
            setupterm(kind or os.environ.get('TERM', 'unknown'), self.o_fd)

        self.o_stream = o_stream
        self.i_stream = i_stream

        # a beginning state of echo ON and canonical mode is assumed.
        self._state_echo = True
        self._state_canonical = True

        # Inherit curses keycap capability names, such as KEY_DOWN, to be
        # used with Keystroke ``code`` property values for comparison to the
        # Terminal class instance it was received on.
        self._keycodes = [key for key in dir(curses) if key.startswith('KEY_')]
        for keycode in self._keycodes:
            # self.KEY_<keycode> = (int)
            setattr(self, keycode, getattr(curses, keycode))

        if self.i_stream is not None:
            # determine encoding of input stream. Only used for keyboard
            # input on posix systems. win32 systems use getwche which returns
            # unicode, and does not require decoding.
            import locale
            locale.setlocale(locale.LC_ALL, '')
            self.encoding = locale.getpreferredencoding()
            if sys.platform != 'win32':
                self.i_buf = unicode()
                self._idecoder = codecs.getincrementaldecoder(self.encoding)()
            else:
                self.i_buf = bytes()

        if self.is_a_tty and self.i_stream:
            # create lookup dictionary for multibyte keyboard input sequences
            self._init_keystrokes()
        # Friendly mnemonics for 'KEY_DELETE' and 'KEY_INSERT'.
        self.KEY_DELETE = self.KEY_DC
        self.KEY_INSERT = self.KEY_IC


    # Sugary names for commonly-used capabilities, intended to help avoid trips
    # to the terminfo man page and comments in your code:
    _sugar = dict(
        # Don't use "on" or "bright" as an underscore-separated chunk in any of
        # these (e.g. on_cology or rock_on) so we don't interfere with
        # __getattr__.
        save='sc',
        restore='rc',

        clear_eol='el',
        clear_bol='el1',
        clear_eos='ed',
        # 'clear' clears the whole screen.
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
        # 'bold' is just 'bold'. Similarly...
        # blink
        # dim
        # flash
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

    def _init_keystrokes(self):
        # dictionary of multibyte sequences to be paired with key codes
        self._keymap = dict()
        # list of key code names
        self._keycodes = list()

        # curses.has_key._capability_names is a dictionary keyed by termcap
        # capabilities, with integer values to be paired with KEY_ names;
        # using this dictionary, we query for the terminal sequence of the
        # terminal capability, and, if any result is found, store the sequence
        # in the _keymap lookup table with the integer valued to be paired by
        # key codes.
        for capability, i_val in curses.has_key._capability_names.iteritems():
            seq = curses.tigetstr(capability)
            if seq is not None:
                self._keymap[seq.decode('iso8859-1')] = i_val

        # include non-destructive space as KEY_RIGHT, in 'xterm-256color',
        # 'kcuf1' = '\x1bOC' and 'cuf1' = '\x1b[C'. []]
        ndsp = curses.tigetstr('cuf1')
        if ndsp is not None:
            self._keymap[ndsp.decode('iso8859-1')] = self.KEY_RIGHT

        # ... as well as a list of general NVT sequences you would
        # expect to receive from remote terminals, such as putty, rxvt,
        # SyncTerm, windows telnet, HyperTerminal, netrunner ...
        self._keymap.update([
            (unichr(10), self.KEY_ENTER), (unichr(13), self.KEY_ENTER),
            (unichr(8), self.KEY_BACKSPACE),
            (u"\x1bOA", self.KEY_UP),    (u"\x1bOB", self.KEY_DOWN),
            (u"\x1bOC", self.KEY_RIGHT), (u"\x1bOD", self.KEY_LEFT),
            (u"\x1bOH", self.KEY_LEFT),
            (u"\x1bOF", self.KEY_END),
            (u"\x1b[A", self.KEY_UP),    (u"\x1b[B", self.KEY_DOWN),
            (u"\x1b[C", self.KEY_RIGHT), (u"\x1b[D", self.KEY_LEFT),
            (u"\x1b[U", self.KEY_NPAGE), (u"\x1b[V", self.KEY_PPAGE),
            (u"\x1b[H", self.KEY_HOME),  (u"\x1b[F", self.KEY_END),
            (u"\x1b[K", self.KEY_END),
            (u"\x1bA", self.KEY_UP),     (u"\x1bB", self.KEY_DOWN),
            (u"\x1bC", self.KEY_RIGHT),  (u"\x1bD", self.KEY_LEFT),
            (u"\x1b?x", self.KEY_UP),    (u"\x1b?r", self.KEY_DOWN),
            (u"\x1b?v", self.KEY_RIGHT), (u"\x1b?t", self.KEY_LEFT),
            (u"\x1b[@", self.KEY_IC),  # insert
            (unichr(127), self.KEY_DC),  # delete
            ])

        # windows 'multibyte' translation, not tested.
        if sys.platform == 'win32':
            # http://msdn.microsoft.com/en-us/library/aa299374%28VS.60%29.aspx
            self._keymap.update([
                (u'\xe0\x48', self.KEY_UP),    (u'\xe0\x50', self.KEY_DOWN),
                (u'\xe0\x4D', self.KEY_RIGHT), (u'\xe0\x4B', self.KEY_LEFT),
                (u'\xe0\x51', self.KEY_NPAGE), (u'\xe0\x49', self.KEY_PPAGE),
                (u'\xe0\x47', self.KEY_HOME),  (u'\xe0\x4F', self.KEY_END),
                (u'\xe0\x3B', self.KEY_F1),    (u'\xe0\x3C', self.KEY_F2),
                (u'\xe0\x3D', self.KEY_F3),    (u'\xe0\x3E', self.KEY_F4),
                (u'\xe0\x3F', self.KEY_F5),    (u'\xe0\x40', self.KEY_F6),
                (u'\xe0\x41', self.KEY_F7),    (u'\xe0\x42', self.KEY_F8),
                (u'\xe0\x43', self.KEY_F9),    (u'\xe0\x44', self.KEY_F10),
                (u'\xe0\x85', self.KEY_F11),   (u'\xe0\x86', self.KEY_F12),
                (u'\xe0\x4C', self.KEY_B2),  # center
                (u'\xe0\x52', self.KEY_IC),  # insert
                (u'\xe0\x53', self.KEY_DC),  # delete
            ])
    def __getattr__(self, attr):
        """Return parametrized terminal capabilities, like bold.

        For example, you can say ``term.bold`` to get the string that turns on
        bold formatting and ``term.normal`` to get the string that turns it off
        again. Or you can take a shortcut: ``term.bold('hi')`` bolds its
        argument and sets everything to normal afterward. You can even combine
        things: ``term.bold_underline_red_on_bright_green('yowzers!')``.

        For a parametrized capability like ``cup``, pass the parameters too:
        ``some_term.cup(line, column)``.

        ``man terminfo`` for a complete list of capabilities.

        Return values are always Unicode.

        """
        resolution = (self._resolve_formatter(attr) if self.do_styling
                else NullCallableString())
        setattr(self, attr, resolution)  # Cache capability codes.
        return resolution

    @property
    def do_styling(self):
        """Wether the terminal will attempt to output sequences."""
        return self._do_styling

    @do_styling.setter
    def do_styling(self, value):
        self._do_styling = value

    @property
    def height(self):
        """The height of the terminal in characters

        If no stream or a stream not representing a terminal was passed in at
        construction, return the dimension of the controlling terminal so
        piping to things that eventually display on the terminal (like ``less
        -R``) work. If a stream representing a terminal was passed in, return
        the dimensions of that terminal. If there somehow is no controlling
        terminal, return ``None``. (Thus, you should check that ``is_a_tty`` is
        true before doing any math on the result.)

        """
        return self._height_and_width()[0]

    @property
    def width(self):
        """The width of the terminal in characters

        See ``height()`` for some corner cases.

        """
        return self._height_and_width()[1]

    def _height_and_width(self):
        """Return a tuple of (terminal height, terminal width).
           Returns (None, None) if terminal window size is indeterminate.
       """
        # tigetnum('lines') and tigetnum('cols') update only if we call
        # setupterm() again.
        if sys.platform == 'win32':
            # based on anatoly techtonik's work from pager.py, MIT/Pub Domain.
            # completely untested ... please report !!
            #WIN32_I_FD = -10
            WIN32_O_FD = -11
            from ctypes import windll, Structure, byref
            from ctypes.wintypes import SHORT, WORD, DWORD
            console_handle = windll.kernel32.GetStdHandle(WIN32_O_FD)
                # CONSOLE_SCREEN_BUFFER_INFO Structure
            class COORD(Structure):
                _fields_ = [("X", SHORT), ("Y", SHORT)]

            class SMALL_RECT(Structure):
                _fields_ = [("Left", SHORT), ("Top", SHORT),
                            ("Right", SHORT), ("Bottom", SHORT)]

            class CONSOLE_SCREEN_BUFFER_INFO(Structure):
                _fields_ = [("dwSize", COORD),
                            ("dwCursorPosition", COORD),
                            ("wAttributes", WORD),
                            ("srWindow", SMALL_RECT),
                            ("dwMaximumWindowSize", DWORD)]
            sbi = CONSOLE_SCREEN_BUFFER_INFO()
            ret = windll.kernel32.GetConsoleScreenBufferInfo(
                    console_handle, byref(sbi))
            if ret != 0:
                return (sbi.srWindow.Right - sbi.srWindow.Left + 1,
                        sbi.srWindow.Bottom - sbi.srWindow.Top + 1)
        else:
            buf = struct.pack('HHHH', 0, 0, 0, 0)
            for fd in self.o_fd, sys.__stdout__:
                try:
                    value = fcntl.ioctl(fd, termios.TIOCGWINSZ, buf)
                    return struct.unpack('hhhh', value)[0:2]
                except IOError:
                    pass
        return None, None

    def _kbhit_win32(self, timeout=0):
        hit = self._kbhit_win32()
        if timeout == 0 or hit:
            return hit
        # without polling for file descriptors on windows, there really isn't
        # a high-level select interface, as is evident in the documentation
        # for select. So, we have a small performance impact and precision
        # loss by sleeping for brief moments before polling again.
        stime = time.time()
        while not hit and timeout:
            time.sleep(0.05)
            hit = self._kbhit_win32()
            if time.time() - stime >= timeout:
                break
        return hit

    def _kbhit_posix(self, timeout=0):
        # there is no such 'kbhit' routine for posix ..
        r_fds, w_fds, x_fds = select.select([sys.i_stream], [], [], timeout)
        return sys.i_stream.fileno() in r_fds

    def kbhit(self, timeout=0):
        """ Returns True if a keypress has been detected on input.
        A subsequent call to getch() will not block on cbreak mode.
        A timeout of 0 returns immediately (default), A timeout of
        ``None`` blocks indefinitely. A timeout of non-zero blocks
        until timeout seconds elapsed. """
        if sys.platform == 'win32':
            return self._kbhit_win32(timeout)
        else:
            return self._kbhit_posix(timeout)

    def getch(self):
        """ Read a single byte from input stream. """
        if sys.platform == 'win32':
            return self._getch_win32()
        else:
            return self._getch_posix()

    def _getch_win32(self):
        """ Read 1 byte on win32 platform. Will block utill keypress
        unless kbhit() has first been called and returned True.
        No decoding of multibyte input is performed.  """
        if self._state_echo:
            return msvcrt.getwche()
        else:
            return msvcrt.getwch()

    def _getch_posix():
        """ Read 1 byte on posix systems. Will block until keypress
        unless kbhit() has first been called and returned True.
        No decoding of multibyte input is performed.  """
        return self.i_stream.read(1)


    def inkey(self, timeout=None, esc_delay=0.35):
        """ Read a single keystroke from input up to timeout in seconds,
        translating special application keys, such as KEY_LEFT.

        Ensure you use 'cbreak mode', by using the ``cbreak`` context
        manager, otherwise input is not received until return is pressed!

        When ``timeout`` is None (default), block until input is available.
        If ``timeout`` is 0, this function is non-blocking and None is
        returned if no input is available.  If ``timeout`` is non-zero,
        None is returned after ``timeout`` seconds have elapsed without input.

        This method differs from using kbhit in combination with getch in that
        Multibyte sequences are translated to key code values, and string
        sequence of length greater than 1 may be returned.

        The result is a unicode-typed instance of the Keystroke class, with
        additional properties ``is_sequence`` (bool), ``name`` (str),
        and ``value`` (int). esc_delay defines the time after which
        an escape key is pressed that the stream awaits a MBS.

        with term.cbreak():
            inp = None
            while inp not in (u'q', u'Q'):
                inp = term.inkey(3)
                if inp is None:
                    print 'timeout after 3 seconds'
                elif inp.value == term.KEY_UP:
                        print 'moving up!'
                else:
                    print 'pressed', 'sequence' if inp.is_sequence else 'ascii'
                    print 'key:', inp, inp.code
        """
        assert self.is_a_tty, u'stream is not a a tty.'
        assert self.i_stream is not None, 'no terminal on input.'
        esc = curses.ascii.ESC  # posix multibyte sequence (MBS) start mark
        wsb = ord('\xe0')       # win32 MBS start mark
        esc_active = False      # time of MBS start mark appearance
        esc_delay_next = 0.1    # when receiving MBS, wait no longer for
                                # subsequent bytes after byte #2 received.

        # returns time-relative remaining for user-specified timeout
        timeleft = lambda cmp_time: (
                float('inf') if timeout is None else
                timeout - (time.time() - cmp_time))

        # returns True if byte appears to mark the beginning of a MBS
        chk_start = lambda byte: (ord(byte) == esc or (
            sys.platform == 'win32' and ord(byte) == wsb))

        # returns True if MBS has been cancelled by timeout
        esc_cancel = lambda cmp_time: time.time() - cmp_time > esc_active


        stime = time.time()
        waitfor = timeleft(stime)
        buf = list()
        while waitfor > 0:
            if len(self.i_buf):
                # return keystroke buffered by previous call
                return self.i_buf.pop()
            if esc_active:
                # SB received, check for MBS; give up after esc_delay elapsed,
                # after bytes 2+ have been received attempt to match a MBS
                # pattern.
                ready = self.kbhit (esc_delay
                        if 1 == len(buf) else esc_delay_next)
                final = False
                if ready:
                    buf.append (self.getch())
                    detect = self.resolve_mbs(buf).next()
                    final = (detect.is_sequence
                            and detect.value != self.KEY_ESCAPE)
                if esc_cancel(esc_active):
                    final = True
                if final:
                    for keystroke in self.resolve_mbs(buf):
                        self.i_buf.append (keystroke)
                    esc_active = False
                    buf = list()
                continue
            # eagerly read all input until next MSB start byte
            # or no subsequent bytes are ready on input stream.
            ready = self.kbhit(waitfor)
            while ready and not esc_active:
                buf.append (self.getch())
                esc_active = time.time() if chk_start(buf[-1]) else False
                ready = self.kbhit()
            if len(buf) and not esc_active:
                # input received that does not begin with MSB sequence, still,
                # unix platforms benefit from utf-8 MSB decoding even though
                # no escape sequence was detected. For win32, this call is
                # mostly a pass-thru.
                for keystroke in self.resolve_mbs(buf):
                    self.i_buf.append (keystroke)

    @contextmanager
    def cbreak(self):
        """Return a context manager for entering 'cbreak' mode.

        This is anagolous to calling python's tty.setcbreak().

        In cbreak mode (sometimes called “rare” mode) normal tty line
        buffering is turned off and characters are available to be read one
        by one by ``getch()``. echo of input is also disabled, the application
        must explicitly copy-out any input received.

        It is assumed the terminal is in a 'cooked' or 'conanical' mode with
        line-at-a-time processing and echo on. The terminal is returned to
        this state upon exiting.

        More information can be found in the manual page for curses.h,
           http://www.openbsd.org/cgi-bin/man.cgi?query=cbreak
        Or the python manual for curses,
           http://docs.python.org/2/library/curses.html

        This is anagolous to the curses.wrapper() helper function, and the
        python standard module tty.setcbreak().
        """
        self._canonical(False)
        self._echo(False)
        yield
        self._canonical(True)
        self._echo(True)

    @contextmanager
    def echo_off(self):
        """Return a context manager suitable for echo of input."""
        self._echo(False)
        yield
        self._echo(True)

    def _canonical(self, state=True):
        """ Set terminal canonical mode on or off.
        In canonical mode (line-at-a-time processing):
            * Input is made available line by line. An input line is available
            when one of the line delimiters is typed (NL, EOL, EOL2; or EOF at
            the start of line). Except in the case of EOF, the line delimiter
            is included in the buffer returned by read(2).
       In noncanonical mode (character-at-a-time processing):
            * Input is available immediately (without the user having to type
            a line-delimiter character), and line editing is disabled. """
        self._state_canonical = state
        if sys.platform == 'win32':
            return
        else:
            # see python tty.setcbreak
            mode = self._get_term_attrs()
            mode[tty.LFLAG] = (
                    mode[tty.LFLAG] | termios.ICANON if state else
                    mode[tty.LFLAG] & ~termios.ICANON)
            self._set_term_mode_posix(mode)

    def _echo(self, state=True):
        """ Set terminal echo mode on or off. """
        self._state_echo = state
        if sys.platform == 'win32':
            return
        else:
            # see python tty.setcbreak
            mode = self._get_term_attrs()
            mode[tty.LFLAG] = (
                    mode[tty.LFLAG] | termios.ECHO if state else
                    mode[tty.LFLAG] & ~termios.ECHO)
            self._set_term_mode_posix(mode)

    @contextmanager
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
        self.o_stream.write(self.save)
        if x is not None and y is not None:
            self.o_stream.write(self.move(y, x))
        elif x is not None:
            self.o_stream.write(self.move_x(x))
        elif y is not None:
            self.o_stream.write(self.move_y(y))
        yield

        # Restore original cursor position:
        self.o_stream.write(self.restore)

    @contextmanager
    def fullscreen(self):
        """Return a context manager that enters fullscreen mode while inside it and restores normal mode on leaving."""
        self.o_stream.write(self.enter_fullscreen)
        yield
        self.o_stream.write(self.exit_fullscreen)

    @contextmanager
    def hidden_cursor(self):
        """Return a context manager that hides the cursor while inside it and makes it visible on leaving."""
        self.o_stream.write(self.hide_cursor)
        yield
        self.o_stream.write(self.normal_cursor)

    @property
    def color(self):
        """Return a capability that sets the foreground color.

        The capability is unparametrized until called and passed a number
        (0-15), at which point it returns another string which represents a
        specific color change. This second string can further be called to
        color a piece of text and set everything back to normal afterward.

        :arg num: The number, 0-15, of the color

        """
        return ParametrizingString(self._foreground_color, self.normal)

    def wrap(self, ucs, width=None, **kwargs):
        """
        A.wrap(S, [width=None, indent=u'']) -> unicode

        Like textwrap.wrap, but honor existing linebreaks and understand
        printable length of a unicode string that contains ANSI sequences,
        such as colors, bold, etc. if width is not specified, the terminal
        width is used.
        """
        if width is None:
            width = self.width
        lines = []
        for line in ucs.splitlines():
            if line.strip():
                for wrapped in ansiwrap(line, width, **kwargs):
                    lines.append(wrapped)
            else:
                lines.append(u'')
        return lines

    @property
    def on_color(self):
        """Return a capability that sets the background color.

        See ``color()``.

        """
        return ParametrizingString(self._background_color, self.normal)

    @property
    def number_of_colors(self):
        """Return the number of colors the terminal supports.

        Common values are 0, 8, 16, 88, and 256.

        Though the underlying capability returns -1 when there is no color
        support, we return 0. This lets you test more Pythonically::

            if term.number_of_colors:
                ...

        We also return 0 if the terminal won't tell us how many colors it
        supports, which I think is rare.

        """
        # This is actually the only remotely useful numeric capability. We
        # don't name it after the underlying capability, because we deviate
        # slightly from its behavior, and we might someday wish to give direct
        # access to it.
        colors = tigetnum('colors')  # Returns -1 if no color support, -2 if no such cap.
        #self.__dict__['colors'] = ret  # Cache it. It's not changing. (Doesn't work.)
        return colors if colors >= 0 else 0

    def _resolve_formatter(self, attr):
        """Resolve a sugary or plain capability name, color, or compound formatting function name into a callable capability."""
        if attr in COLORS:
            return self._resolve_color(attr)
        elif attr in COMPOUNDABLES:
            # Bold, underline, or something that takes no parameters
            return self._formatting_string(self._resolve_capability(attr))
        else:
            formatters = split_into_formatters(attr)
            if all(f in COMPOUNDABLES for f in formatters):
                # It's a compound formatter, like "bold_green_on_red". Future
                # optimization: combine all formatting into a single escape
                # sequence.
                return self._formatting_string(
                    u''.join(self._resolve_formatter(s) for s in formatters))
            else:
                return ParametrizingString(self._resolve_capability(attr))

    def _resolve_capability(self, atom):
        """Return a terminal code for a capname or a sugary name, or an empty Unicode.

        The return value is always Unicode, because otherwise it is clumsy
        (especially in Python 3) to concatenate with real (Unicode) strings.

        """
        code = tigetstr(self._sugar.get(atom, atom))
        if code:
            # We can encode escape sequences as UTF-8 because they never
            # contain chars > 127, and UTF-8 never changes anything within that
            # range..
            return code.decode('utf-8')
        return u''

    def resolve_mbs(self, buf):
        """ T._resolve_mbs(buf) -> Keystroke

        This generator yields unicode sequences with additional
        ``.is_sequence``, ``.name``, and ``.code`` properties that
        describle matching multibyte input sequences to keycode
        translations (if any) detected in input buffer, ``buf``.

        For win32 systems, the input buffer is a list of unicode values
        received by getwch. For Posix systems, the input buffer is a list
        of bytes recieved by sys.stdin.read(1), to be decoded to Unicode by
        the preferred locale.
        """
        if sys.platform == 'win32':
            return self._resolve_mbs_win32(buf)
        else:
            return self._resolve_mbs_posix(buf, self._idecoder)

    def _resolve_mbs_win32(self, buf):
        return self._resolve_mbs(self, u''.join(buf))

    def _resolve_mbs_posix(self, buf, decoder, end=True):
        decoded = list()
        for num, byte in enumerate(buf):
            is_final = end and num == (len(buf) - 1)
            ucs = decoder.decode(byte, final=is_final)
            if ucs is not None:
                decoded.append(ucs)
        return self._resolve_mbs(self, u''.join(decoded))

    def _resolve_mbs(self, ucs):
        CR_NVT = u'\r\x00' # NVT return (telnet, etc.)
        CR_LF = u'\r\n'    # carriage return + newline
        CR_CHAR = u'\n'    # returns only '\n' when return is detected.
        esc = curses.ascii.ESC
        decoder_errmsg = 'multibyte decoding failed in _resolve_multibyte: %r'

        def resolve_keycode(self, integer):
            """
            Returns printable string to represent matched multibyte sequence,
            such as 'KEY_LEFT'. For purposes of __repr__ or __str__ ?
            """
            assert type(integer) is int
            for keycode in self._keycodes:
                if getattr(self, keycode) == integer:
                    return keycode

        def scan_keymap(ucs):
            """
            Return sequence and keycode if ucs begins with any known sequence.
            """
            for (keyseq, keycode) in self._keymap.iteritems():
                if ucs.startswith(keyseq):
                    return (keyseq, resolve_keycode(keycode), keycode)
            return (None, None, None)  # no match

        # special care is taken to pass over the ineveitably troublesome
        # carriage return, which is a multibyte sequence issue of its own;
        # expect to receieve any of '\r\00', '\r\n', '\r', or '\n', but
        # yield only a single byte, u'\n'.
        while len(ucs):
            if ucs[:2] in (CR_NVT, CR_LF): # telnet return or dos CR+LF
                yield Keystroke(CR_CHAR, ('KEY_ENTER', self.KEY_ENTER))
                ucs = ucs[2:]
                continue
            elif ucs[:1] in (u'\r', u'\n'): # single-byte CR
                yield Keystroke(CR_CHAR, ('KEY_ENTER', self.KEY_ENTER))
                ucs = ucs[1:]
                continue
            elif 1 == len(ucs) and ucs == unichr(esc):
                yield Keystroke(ucs[0], ('KEY_ESCAPE', self.KEY_ESCAPE))
                break
            keyseq, keyname, keycode = scan_keymap(ucs)
            if (keyseq, keyname, keycode) == (None, None, None):
                if ucs.startswith(unichr(esc)):
                    # a multibyte sequence beginning with escape (27)
                    # was not decoded -- please report !
                    warnings.warn(decoder_errmsg % (ucs,))
                yield Keystroke(ucs[0], None)
                ucs = ucs[1:]
            else:
                yield Keystroke(keyseq, (keyname, keycode))
                ucs = ucs[len(keyseq):]

    def _resolve_color(self, color):
        """Resolve a color like red or on_bright_green into a callable capability."""
        # TODO: Does curses automatically exchange red and blue and cyan and
        # yellow when a terminal supports setf/setb rather than setaf/setab?
        # I'll be blasted if I can find any documentation. The following
        # assumes it does.
        color_cap = (self._background_color if 'on_' in color else
                     self._foreground_color)
        # curses constants go up to only 7, so add an offset to get at the
        # bright colors at 8-15:
        offset = 8 if 'bright_' in color else 0
        base_color = color.rsplit('_', 1)[-1]
        return self._formatting_string(
            color_cap(getattr(curses, 'COLOR_' + base_color.upper()) + offset))

    @property
    def _foreground_color(self):
        return self.setaf or self.setf

    @property
    def _background_color(self):
        return self.setab or self.setb

    def _formatting_string(self, formatting):
        """Return a new ``FormattingString`` which implicitly receives my notion of "normal"."""
        return FormattingString(formatting, self.normal)

    def _get_term_mode_posix(self):
        """ Get terminal attributes using termios.tcgetattr. """
        assert self.is_a_tty, 'stream is not a a tty.'
        assert self.i_stream is not None, 'no terminal on input.'
        assert sys.platform != 'win32', 'Windows is without termios'
        return termios.tcgetattr(self.i_fd)

    def _set_term_mode_posix(self, mode):
        """ Set terminal attributes using tcsetattr with flag TCSANOW.  """
        assert self.is_a_tty, 'stream is not a a tty.'
        assert self.i_stream is not None, 'no terminal on input.'
        assert sys.platform != 'win32', 'Windows is without termios'
        return termios.tcsetattr(self.i_fd, termios.TCSANOW, mode)

    def ljust(self, ucs, width=None):
        if width is None:
            width = self.width
        return AnsiString(ucs).ljust(width)
    ljust.__doc__ = unicode.ljust.__doc__

    def rjust(self, ucs, width=None):
        if width is None:
            width = self.width
        return AnsiString(ucs).rjust(width)
    rjust.__doc__ = unicode.rjust.__doc__

    def center(self, ucs, width=None):
        if width is None:
            width = self.width
        return AnsiString(ucs).center(width)
    center.__doc__ = unicode.center.__doc__


def derivative_colors(colors):
    """Return the names of valid color variants, given the base colors."""
    return set([('on_' + c) for c in colors] +
               [('bright_' + c) for c in colors] +
               [('on_bright_' + c) for c in colors])


COLORS = set(['black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white'])
COLORS.update(derivative_colors(COLORS))
COMPOUNDABLES = (COLORS |
                 set(['bold', 'underline', 'reverse', 'blink', 'dim', 'italic',
                      'shadow', 'standout', 'subscript', 'superscript']))


class ParametrizingString(unicode):
    """A Unicode string which can be called to parametrize it as a terminal capability"""
    def __new__(cls, formatting, normal=None):
        """Instantiate.

        :arg normal: If non-None, indicates that, once parametrized, this can
            be used as a ``FormattingString``. The value is used as the
            "normal" capability.

        """
        new = unicode.__new__(cls, formatting)
        new._normal = normal
        return new

    def __call__(self, *args):
        try:
            # Re-encode the cap, because tparm() takes a bytestring in Python
            # 3. However, appear to be a plain Unicode string otherwise so
            # concats work.
            parametrized = tparm(self.encode('utf-8'), *args).decode('utf-8')
            return (parametrized if self._normal is None else
                    FormattingString(parametrized, self._normal))
        except curses.error:
            # Catch "must call (at least) setupterm() first" errors, as when
            # running simply `nosetests` (without progressive) on nose-
            # progressive. Perhaps the terminal has gone away between calling
            # tigetstr and calling tparm.
            return u''
        except TypeError:
            # If the first non-int (i.e. incorrect) arg was a string, suggest
            # something intelligent:
            if len(args) == 1 and isinstance(args[0], basestring):
                raise TypeError(
                    'A native or nonexistent capability template received '
                    '%r when it was expecting ints. You probably misspelled a '
                    'formatting call like bright_red_on_white(...).' % args)
            else:
                # Somebody passed a non-string; I don't feel confident
                # guessing what they were trying to do.
                raise


class FormattingString(unicode):
    """A Unicode string which can be called upon a piece of text to wrap it in formatting"""
    def __new__(cls, formatting, normal):
        new = unicode.__new__(cls, formatting)
        new._normal = normal
        return new

    def __call__(self, text):
        """Return a new string that is ``text`` formatted with my contents.

        At the beginning of the string, I prepend the formatting that is my
        contents. At the end, I append the "normal" sequence to set everything
        back to defaults. The return value is always a Unicode.

        """
        return self + text + self._normal


class NullCallableString(unicode):
    """A dummy class to stand in for ``FormattingString`` and ``ParametrizingString``

    A callable bytestring that returns an empty Unicode when called with an int
    and the arg otherwise. We use this when there is no tty and so all
    capabilities are blank.

    """
    def __new__(cls):
        new = unicode.__new__(cls, u'')
        return new

    def __call__(self, arg):
        if isinstance(arg, int):
            return u''
        return arg  # TODO: Force even strs in Python 2.x to be unicodes? Nah. How would I know what encoding to use to convert it?


class Keystroke(unicode):
    """ A unicode-derived class for matched multibyte input sequences.  If the
    unicode string is a multibyte input sequence, then the ``is_sequence``
    property is True, and the ``name`` and ``value`` properties return a
    string and integer value.
    """
    def __new__(cls, ucs, keystroke=None):
        new = unicode.__new__(cls, ucs)
        new._keystroke = keystroke
        return new

    def __repr__(self):
        if self.is_sequence:
            return u'<%s>' % (self.name,)
        return unicode.__repr__(self)

    @property
    def is_sequence(self):
        """ Returns True if value represents a multibyte sequence. """
        return self._keystroke is not None

    @property
    def name(self):
        """ Returns string name of multibyte sequence, such as 'KEY_HOME'."""
        if self._keystroke is None:
            return str(None)
        return self._keystroke[0]

    @property
    def code(self):
        """ Returns curses integer value of multibyte sequence, such as 323."""
        if self._keystroke is not None:
            return self._keystroke[1]
        assert 1 == len(self), (
                'No integer value available for multibyte sequence')
        return ord(self)


def split_into_formatters(compound):
    """Split a possibly compound format string into segments.

    >>> split_into_formatters('bold_underline_bright_blue_on_red')
    ['bold', 'underline', 'bright_blue', 'on_red']

    """
    merged_segs = []
    # These occur only as prefixes, so they can always be merged:
    mergeable_prefixes = ['on', 'bright', 'on_bright']
    for s in compound.split('_'):
        if merged_segs and merged_segs[-1] in mergeable_prefixes:
            merged_segs[-1] += '_' + s
        else:
            merged_segs.append(s)
    return merged_segs


class AnsiWrapper(textwrap.TextWrapper):
    # pylint: disable=C0111
    #         Missing docstring
    def _wrap_chunks(self, chunks):
        """
        ANSI-safe varient of wrap_chunks, with exception of movement seqs!
        """
        lines = []
        if self.width <= 0:
            raise ValueError("invalid width %r (must be > 0)" % self.width)
        chunks.reverse()
        while chunks:
            cur_line = []
            cur_len = 0
            if lines:
                indent = self.subsequent_indent
            else:
                indent = self.initial_indent
            width = self.width - len(indent)
            if self.drop_whitespace and chunks[-1].strip() == '' and lines:
                del chunks[-1]
            while chunks:
                chunk_len = len(AnsiString(chunks[-1]))
                if cur_len + chunk_len <= width:
                    cur_line.append(chunks.pop())
                    cur_len += chunk_len
                else:
                    break
            if chunks and len(AnsiString(chunks[-1])) > width:
                self._handle_long_word(chunks, cur_line, cur_len, width)
            if (self.drop_whitespace
                    and cur_line
                    and cur_line[-1].strip() == ''):
                del cur_line[-1]
            if cur_line:
                lines.append(indent + u''.join(cur_line))
        return lines
AnsiWrapper.__doc__ = textwrap.TextWrapper.__doc__


def ansiwrap(ucs, width=70, **kwargs):
    """ Wrap a single paragraph of Unicode terminal sequences,
    returning a list of wrapped lines. ucs is ANSI-color safe.
    """
    assert ('break_long_words' not in kwargs
            or not kwargs['break_long_words']), (
                    'break_long_words is not sequence-safe')
    kwargs['break_long_words'] = False
    return AnsiWrapper(width=width, **kwargs).wrap(ucs)

_ANSI_COLOR = re.compile(r'\033\[(\d{2,3})m')
_ANSI_RIGHT = re.compile(r'\033\[(\d{1,4})C')
_ANSI_CODEPAGE = re.compile(r'\033[\(\)][AB012]')
_ANSI_WILLMOVE = re.compile(r'\033\[[HJuABCDEF]')
_ANSI_WONTMOVE = re.compile(r'\033\[[sm]')


class AnsiString(unicode):
    """
    This unicode variation understands the effect of ANSI sequences of
    printable length, allowing a properly implemented .rjust(), .ljust(),
    .center(), and .len() with bytes using terminal sequences

    Other ANSI helper functions also provided as methods.
    """
    # this is really bad; kludge dating as far back as 2002
    def __new__(cls, ucs):
        new = unicode.__new__(cls, ucs)
        return new

    def ljust(self, width):
        return self + u' ' * (max(0, width - self.__len__()))
    ljust.__doc__ = unicode.ljust.__doc__


    def rjust(self, width):
        return u' ' * (max(0, width - self.__len__())) + self
    rjust.__doc__ = unicode.rjust.__doc__


    def center(self, width):
        split = max(0.0, float(width) - self.__len__()) / 2
        return (u' ' * (max(0, int(math.floor(split)))) + self
                + u' ' * (max(0, int(math.ceil(split)))))
    center.__doc__ = unicode.center.__doc__


    def __len__(self):
        """
        Return the printed length of a string that contains (some types) of
        ANSI sequences. Although accounted for, strings containing sequences
        such as cls() will not give accurate returns (0). backspace, delete,
        and double-wide east-asian characters are accounted for.
        """
        # 'nxt' points to first *ch beyond current ansi sequence, if any.
        # 'width' is currently estimated display length.
        nxt, width = 0, 0
        def get_padding(ucs):
            """
             get_padding(S) -> integer

            Returns int('nn') in CSI sequence \\033[nnC for use with replacing
            ansi.right(nn) with printable characters. prevents bleeding when
            used with scrollable art. Otherwise 0 if not \033[nnC sequence.
            Needed to determine the 'width' of art that contains this padding.
            """
            right = _ANSI_RIGHT.match(ucs)
            if right is not None:
                return int(right.group(1))
            return 0
        for idx in range(0, unicode.__len__(self)):
            width += get_padding(self[idx:])
            if idx == nxt:
                nxt = idx + _seqlen(self[idx:])
            if nxt <= idx:
                # 'East Asian Fullwidth' and 'East Asian Wide' characters
                # can take 2 cells, see http://www.unicode.org/reports/tr11/
                # and http://www.gossamer-threads.com/lists/python/bugs/972834
                # TODO: could use wcswidth, but i've ommitted it -jq
                width += 1
                nxt = idx + _seqlen(self[idx:]) + 1
        return width

def _is_movement(ucs):
    """
    is_movement(S) -> bool

    Returns True if string S begins with a known terminal escape
    sequence that is "unhealthy for padding", that is, it has effects
    on the cursor position that are indeterminate.
    """
    # pylint: disable=R0911,R09120
    #        Too many return statements (20/6)
    #        Too many branches (23/12)
    # this isn't the best, perhaps for readability a giant REGEX can and
    # probably and already has been made.
    slen = unicode.__len__(ucs)
    if 0 == slen:
        return False
    elif ucs[0] != unichr(ESC):
        return False
    elif ucs[1] == u'c':
        # reset
        return True
    elif slen < 3:
        # unknown
        return False
    elif _ANSI_CODEPAGE.match(ucs):
        return False
    elif (ucs[0], ucs[1], ucs[2]) == (u'#', u'8'):
        # 'fill the screen'
        return True
    elif _ANSI_WILLMOVE.match(ucs):
        return True
    elif _ANSI_WONTMOVE.match(ucs):
        return False
    elif slen < 4:
        # unknown
        return False
    elif ucs[2] == '?':
        # CSI + '?25(h|l)' # show|hide
        ptr2 = 3
        while (ucs[ptr2].isdigit()):
            ptr2 += 1
        if not ucs[ptr2] in u'hl':
            # ? followed illegaly, UNKNOWN
            return False
        return False
    elif ucs[2] in ('(', ')'):
        # CSI + '\([AB012]' # set G0/G1
        assert ucs[3] in (u'A', 'B', '0', '1', '2',)
        return False
    elif not ucs[2].isdigit():
        # illegal nondigit in seq
        return False
    ptr2 = 2
    while (ucs[ptr2].isdigit()):
        ptr2 += 1
    # multi-attribute SGR '[01;02(..)'(m|H)
    n_tries = 0
    while ptr2 < slen and ucs[ptr2] == ';' and n_tries < 64:
        n_tries += 1
        ptr2 += 1
        try:
            while (ucs[ptr2].isdigit()):
                ptr2 += 1
            if ucs[ptr2] == 'H':
                # 'H' pos,
                return True
            elif ucs[ptr2] == 'm':
                # 'm' color;attr
                return False
            elif ucs[ptr2] == ';':
                # multi-attribute SGR
                continue
        except IndexError:
            # out-of-range in multi-attribute SGR
            return False
        # illegal multi-attribtue SGR
        return False
    if ptr2 >= slen:
        # unfinished sequence, hrm ..
        return False
    elif ucs[ptr2] in u'ABCDEFGJKSTH':
        # single attribute,
        # up, down, right, left, bnl, bpl,
        # pos, cls, cl, pgup, pgdown
        return True
    elif ucs[ptr2] == 'm':
        # normal
        return False
    # illegal single value, UNKNOWN
    return False


def _seqlen(ucs):
    """
    _seqlen(S) -> integer

    Returns non-zero for string S that begins with an ansi sequence, with
    value of bytes until sequence is complete. Use as a 'next' pointer to
    skip past sequences.
    """
    # pylint: disable=R0911,R0912
    #        Too many return statements (19/6)
    #        Too many branches (22/12)
    # it is regretable that this duplicates much of is_movement, but
    # they do serve different means .. again, more REGEX would help
    # readability.
    slen = unicode.__len__(ucs)
    esc = curses.ascii.ESC
    if 0 == slen:
        return 0  # empty string
    elif ucs[0] != unichr(esc):
        return 0  # not a sequence
    elif 1 == slen:
        return 0  # just esc,
    elif ucs[1] == u'c':
        return 2  # reset
    elif 2 == slen:
        return 0  # not a sequence
    elif (ucs[1], ucs[2]) == (u'#', u'8'):
        return 3  # fill screen (DEC)
    elif _ANSI_CODEPAGE.match(ucs) or _ANSI_WONTMOVE.match(ucs):
        return 3
    elif _ANSI_WILLMOVE.match(ucs):
        return 4
    elif ucs[1] == '[':
        # all sequences are at least 4 (\033,[,0,m)
        if slen < 4:
            # not a sequence !?
            return 0
        elif ucs[2] == '?':
            # CSI + '?25(h|l)' # show|hide
            ptr2 = 3
            while (ucs[ptr2].isdigit()):
                ptr2 += 1
            if not ucs[ptr2] in u'hl':
                # ? followed illegaly, UNKNOWN
                return 0
            return ptr2 + 1
        # SGR
        elif ucs[2].isdigit():
            ptr2 = 2
            while (ucs[ptr2].isdigit()):
                ptr2 += 1
                if ptr2 == unicode.__len__(ucs):
                    return 0

            # multi-attribute SGR '[01;02(..)'(m|H)
            while ucs[ptr2] == ';':
                ptr2 += 1
                if ptr2 == unicode.__len__(ucs):
                    return 0
                try:
                    while (ucs[ptr2].isdigit()):
                        ptr2 += 1
                except IndexError:
                    return 0
                if ucs[ptr2] in u'Hm':
                    return ptr2 + 1
                elif ucs[ptr2] == ';':
                    # multi-attribute SGR
                    continue
                # 'illegal multi-attribute sgr'
                return 0
            # single attribute SGT '[01(A|B|etc)'
            if ucs[ptr2] in u'ABCDEFGJKSTHm':
                # single attribute,
                # up/down/right/left/bnl/bpl,pos,cls,cl,
                # pgup,pgdown,color,attribute.
                return ptr2 + 1
            # illegal single value
            return 0
        # illegal nondigit
        return 0
    # unknown...
    return 0
