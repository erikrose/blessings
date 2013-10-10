"""A thin, practical wrapper around terminal coloring, styling, and
positioning"""

from contextlib import contextmanager
import curses
from curses import setupterm, tigetnum, tigetstr, tparm
from fcntl import ioctl

try:
    from io import UnsupportedOperation as IOUnsupportedOperation
except ImportError:
    class IOUnsupportedOperation(Exception):
        """A dummy exception to take the place of Python 3's
        ``io.UnsupportedOperation`` in Python 2"""

from os import isatty, environ
from platform import python_version_tuple
import struct
import sys
from termios import TIOCGWINSZ
import warnings
import textwrap
import math
import re

# provide TIOCGWINSZ for platforms that are missing it,
# according to noahspurrier/pexpect, they exist!
import termios
TIOCGWINSZ = getattr(termios, 'TIOCGWINSZ', 1074295912)

__all__ = ['Terminal', 'Sequence']


if ('3', '0', '0') <= python_version_tuple() < ('3', '2', '2+'):  # Good till
                                                                  # 3.2.10
    # Python 3.x < 3.2.3 has a bug in which tparm() erroneously takes a string.
    raise ImportError('Blessings needs Python 3.2.3 or greater for Python 3 '
                      'support due to http://bugs.python.org/issue10570.')

_SEQ_WONTMOVE = re.compile(
        r'\x1b('  # curses.ascii.ESC
        r'([\(\)\*\+\$]'  # Designate G0-G3,Kangi Character Set
            r'[0AB<5CK])'  # 0=DEC,A=UK,B=USASCII,<=Multinational
                           # 5/C=Finnish,K=German
        r'|7'  # save_cursor
        r'|\[('  # \x1b[: Begin Control Sequence Initiator(CSI) ...
            r'[0-2]?[JK]'  # J:erase in display (0=below,1=above,2=All)
                           # K:erase in line (0=right,1=left,2=All)
            r'|\d{1,4};\d{1,4};\d{1,4};\d{1,4};\d{1,4}T'
                            # Initiate hilite mouse tracking, params are
                            # func;startx;starty;firstrow;lastrow
            r'|[025]W'  # tabular funcs: 0=set,2=clear Current,5=clear All
            r'|[03]g'  # tab clear: 0=current,3=all
            r'|4[hl]'  # hl: insert, replace mode.
            r'|(\d{0,3}(;\d{0,3}){1,5}|\d{1,3}|)m' # |(\d{1;3})
                         # SGR (attributes), extraordinarily forgiving!
            r'|0?c'  # send device attributes (terminal replies!)
            r'|[5-8]n'  # device status report, 5: answers OK, 6: cursor pos,
                       # 7: display name, 8: version number (terminal replies!)
            r'|[zs]'  # save_cursor
        r'|(\?'  # DEC Private Modes -- extraordinarily forgiving!
            r'[0-9]{0,4}(;\d{1,4}){0,4}[hlrst]' # hlrst:set, reset, restore, save, toggle:
                # 1: application keys, 2: ansi/vt52 mode, 3: 132/80 columns,
                # 4: smooth/jump scroll, 5: normal/reverse video,
                # 6: origin/cursor mode 7: wrap/no wrap at margin,
                # 8: auto-repeat keys?, 9: X10 XTerm Mouse reporting,
                # 10: menubar visible/invis (rxvt), 25: cursor visable/invis
                # 30: scrollbar visible/invis, 35: xterm shift+key sequences,
                # 38: Tektronix mode, 40: allow 80/132, 44: margin bell,
                # 45: reverse wraparound mode on/off, 46: unknown
                # 47: use alt/normal screen buffer, 66: app/normal keypad,
                # 67: backspace sends BS/DEL, 1000: X11 Xterm Mouse reporting
                # 1001: X11 Xterm Mouse Tracking
                # 1010: donot/do scroll-to-bottom on output, 1011: "" on input
                # 1047: use alt/normal screen buffer, clear if returning
                # 1048: save/restore cursor position
                # 1049: is 1047+1048 combined.
                # !! Most of these do not cause cursor movement. Instead of
                #    tracking each individual mode, we bucket them all as
                #    "healthy for padding" (not movement).
        r')' # end DEC Private Modes
      r')'  # end CSI
    r')')  # end \x1b


# mrxvt_seq.txt by Gautam Iyer <gi1242@users.sourceforge.net> was invaluable
# in the authoring of these regular expressions. The current author of xterm
# (Thomas Dickey) also provides many invaluable resources.
_SEQ_WILLMOVE = re.compile(
        r'\x1b('  # curses.ascii.ESC
        r'[cZ]'  # rs1: reset string (cursor position undefined)
        r'|8'  # restore_cursor
        r'|#8'  # DEC Alignment Screen Test (cursor position undefined)
        r'|(\[('  # \x1b[: Begin Control Sequence Initiator(CSI) ...
            r'(\d{1,4})?[AeBCaDEFG\'IZdLMPX]'
                # [Ae]B[Ca]D: up/down/forward/backword N-times
                # EF: down/up N times, goto 1st column,
                # [G']IZ: to column N, forward N tabstops, backward N tabstops
                # d: to line N, # LMP:insert/delete N lines, Delete N chars
                                 # X: del N chars
            r'|(\d{1,4})?(;\d{1,4})?[Hf]'
                # H: home, opt. (row, col)
                # f: horiz/vert pos
            r'|u'  # restore_cursor
            r'|[0-9]x'  # DEC request terminal parameters (terminal replies!)
        r')'  # end CSI
        r'|\][0-9]{1,2};[\s\w]+(' # Set XTerm params, ESC ] Ps;Pt ST
            + '\x9c'  # 8-bit terminator
            + '|\a'   # old terminator (BEL)
            + r'|\x1b\\)'  # 7-bit terminator
    r')'  # end CSI
r')')  # end x1b

_SEQ_SGR_RIGHT = re.compile(r'\033\[(\d{1,4})C')

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
# Python - perhaps wrongly - will not allow a re-initialisation of *new*
# terminals through setupterm(), so the value of cur_term cannot be changed,
# and subsequent calls to setupterm() silently have *no effect* !
#
# Therefore, the ``kind`` of each Terminal() is, in essence, a singleton.
# This global variable reflects that, and a warning is emitted if somebody
# expects otherwise.
_CUR_TERM = None

_SEQ_WONTMOVE = re.compile(
        r'\x1b('  # curses.ascii.ESC
        r'([\(\)\*\+\$]'  # Designate G0-G3,Kangi Character Set
            r'[0AB<5CK])'  # 0=DEC,A=UK,B=USASCII,<=Multinational
                           # 5/C=Finnish,K=German
        r'|7'  # save_cursor
        r'|\[('  # \x1b[: Begin Control Sequence Initiator(CSI) ...
            r'[0-2]?[JK]'  # J:erase in display (0=below,1=above,2=All)
                           # K:erase in line (0=right,1=left,2=All)
            r'|\d{1,4};\d{1,4};\d{1,4};\d{1,4};\d{1,4}T'
                            # Initiate hilite mouse tracking, params are
                            # func;startx;starty;firstrow;lastrow
            r'|[025]W'  # tabular funcs: 0=set,2=clear Current,5=clear All
            r'|[03]g'  # tab clear: 0=current,3=all
            r'|4[hl]'  # hl: insert, replace mode.
            r'|(\d{0,3}(;\d{0,3}){1,5}|\d{1,3}|)m' # |(\d{1;3})
                         # SGR (attributes), extraordinarily forgiving!
            r'|0?c'  # send device attributes (terminal replies!)
            r'|[5-8]n'  # device status report, 5: answers OK, 6: cursor pos,
                       # 7: display name, 8: version number (terminal replies!)
            r'|[zs]'  # save_cursor
        r'|(\?'  # DEC Private Modes -- extraordinarily forgiving!
            r'[0-9]{0,4}(;\d{1,4}){0,4}[hlrst]' # hlrst:set, reset, restore, save, toggle:
                # 1: application keys, 2: ansi/vt52 mode, 3: 132/80 columns,
                # 4: smooth/jump scroll, 5: normal/reverse video,
                # 6: origin/cursor mode 7: wrap/no wrap at margin,
                # 8: auto-repeat keys?, 9: X10 XTerm Mouse reporting,
                # 10: menubar visible/invis (rxvt), 25: cursor visable/invis
                # 30: scrollbar visible/invis, 35: xterm shift+key sequences,
                # 38: Tektronix mode, 40: allow 80/132, 44: margin bell,
                # 45: reverse wraparound mode on/off, 46: unknown
                # 47: use alt/normal screen buffer, 66: app/normal keypad,
                # 67: backspace sends BS/DEL, 1000: X11 Xterm Mouse reporting
                # 1001: X11 Xterm Mouse Tracking
                # 1010: donot/do scroll-to-bottom on output, 1011: "" on input
                # 1047: use alt/normal screen buffer, clear if returning
                # 1048: save/restore cursor position
                # 1049: is 1047+1048 combined.
                # !! Most of these do not cause cursor movement. Instead of
                #    tracking each individual mode, we bucket them all as
                #    "healthy for padding" (not movement).
        r')' # end DEC Private Modes
      r')'  # end CSI
    r')')  # end \x1b


# mrxvt_seq.txt by Gautam Iyer <gi1242@users.sourceforge.net> was invaluable
# in the authoring of these regular expressions. The current author of xterm
# (Thomas Dickey) also provides many invaluable resources.
_SEQ_WILLMOVE = re.compile(
        r'\x1b('  # curses.ascii.ESC
        r'[cZ]'  # rs1: reset string (cursor position undefined)
        r'|8'  # restore_cursor
        r'|#8'  # DEC Alignment Screen Test (cursor position undefined)
        r'|(\[('  # \x1b[: Begin Control Sequence Initiator(CSI) ...
            r'(\d{1,4})?[AeBCaDEFG\'IZdLMPX]'
                # [Ae]B[Ca]D: up/down/forward/backword N-times
                # EF: down/up N times, goto 1st column,
                # [G']IZ: to column N, forward N tabstops, backward N tabstops
                # d: to line N, # LMP:insert/delete N lines, Delete N chars
                                 # X: del N chars
            r'|(\d{1,4})?(;\d{1,4})?[Hf]'
                # H: home, opt. (row, col)
                # f: horiz/vert pos
            r'|u'  # restore_cursor
            r'|[0-9]x'  # DEC request terminal parameters (terminal replies!)
        r')'  # end CSI
        r'|\][0-9]{1,2};[\s\w]+(' # Set XTerm params, ESC ] Ps;Pt ST
            + '\x9c'  # 8-bit terminator
            + '|\a'   # old terminator (BEL)
            + r'|\x1b\\)'  # 7-bit terminator
    r')'  # end CSI
r')')  # end x1b


_SEQ_SGR_RIGHT = re.compile(r'\033\[(\d{1,4})C')

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

    """
    def __init__(self, kind=None, stream=None, force_styling=False):
        """Initialize the terminal.

        If ``stream`` is not a tty, I will default to returning an empty
        Unicode string for all capability values, so things like piping your
        output to a file won't strew escape sequences all over the place. The
        ``ls`` command sets a precedent for this: it defaults to columnar
        output when being sent to a tty and one-item-per-line when not.

        :arg kind: A terminal string as taken by ``setupterm()``. Defaults to
            the value of the ``TERM`` environment variable. As setupterm() may
            only be called once per-process, this value is essentially a
            singleton (All Terminal() instances must have the same ``kind``).
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
        if stream is None:
            stream = sys.__stdout__
        try:
            stream_descriptor = (stream.fileno() if hasattr(stream, 'fileno')
                                 and callable(stream.fileno)
                                 else None)
        except IOUnsupportedOperation:
            stream_descriptor = None

        self._is_a_tty = (stream_descriptor is not None and
                         isatty(stream_descriptor))
        self._does_styling = ((self.is_a_tty or force_styling) and
                              force_styling is not None)

        # The desciptor to direct terminal initialization sequences to.
        # sys.__stdout__ seems to always have a descriptor of 1, even if output
        # is redirected.
        self._init_descriptor = (sys.__stdout__.fileno()
                                 if stream_descriptor is None
                                 else stream_descriptor)
        if self.does_styling:
            # Make things like tigetstr() work. Explicit args make setupterm()
            # work even when -s is passed to nosetests. Lean toward sending
            # init sequences to the stream if it has a file descriptor, and
            # send them to stdout as a fallback, since they have to go
            # somewhere.
            cur_term = kind or environ.get('TERM', 'unknown')
            if _CUR_TERM is None or cur_term == _CUR_TERM:
                _CUR_TERM = cur_term
            else:
                warnings.warn('A terminal of kind "%s" has been requested; '
                              'due to an internal python curses bug, terminal '
                              'capabilities for a terminal of kind "%s" will '
                              'continue to be returned for the remainder of '
                              'this process. see: '
                              'https://github.com/erikrose/blessings/issues/33'
                              % (cur_term, _CUR_TERM,), RuntimeWarning)

            setupterm(cur_term, self._init_descriptor)

        self.stream = stream

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

    def __getattr__(self, attr):
        """Return a terminal capability, like bold.

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
        resolution = (self._resolve_formatter(attr) if self.does_styling
                      else NullCallableString())
        setattr(self, attr, resolution)  # Cache capability codes.
        return resolution

    @property
    def does_styling(self):
        """Whether attempt to emit capabilities

        This is influenced by the ``is_a_tty`` property and by the
        ``force_styling`` argument to the constructor. You can examine
        this value to decide whether to draw progress bars or other frippery.

        """
        return self._does_styling

    @property
    def is_a_tty(self):
        """Whether my ``stream`` appears to be associated with a terminal"""
        return self._is_a_tty

    @property
    def height(self):
        """The height of the terminal in characters

        If no stream or a stream not representing a terminal was passed in at
        construction, return the dimension of the controlling terminal so
        piping to things that eventually display on the terminal (like ``less
        -R``) work. If a stream representing a terminal was passed in, return
        the dimensions of that terminal. If there somehow is no controlling
        terminal, return ``None``. (Thus, you should check that the property
        ``is_a_tty`` is true before doing any math on the result.)

        """
        return self._height_and_width()[0]

    @property
    def width(self):
        """The width of the terminal in characters

        See ``height()`` for some corner cases.

        """
        return self._height_and_width()[1]

    def _height_and_width(self):
        """Return a tuple of the current terminal dimensions, (height, width),
           except for instances not attached to a tty -- where the environment
           values LINES and COLUMNS are returned. failing that, 24 and 80.
        """
        def get_winsize(tty_fd):
            """Returns the value of the ``winsize`` struct for the terminal
               specified by argument ``tty_fd`` as four integers:
                 (lines, cols, y_height, x_height).
               The first pair are character cells, the latter pixel size.
            """
            val = ioctl(tty_fd, TIOCGWINSZ, '\x00' * 8)
            return struct.unpack('hhhh', val)

        for descriptor in self._init_descriptor, sys.__stdout__:
            try:
                lines, cols, _yp, _xp = get_winsize(descriptor)
                return lines, cols
            except IOError:
                # when output is a non-tty, and init_descriptor stdout, is piped
                # to another program, such as tee(1), this ioctl will raise
                # an IOError.
                pass
        lines = int(environ.get('LINES', '24'))
        cols = int(environ.get('COLUMNS', '80'))
        return lines, cols

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

    @contextmanager
    def fullscreen(self):
        """Return a context manager that enters fullscreen mode while inside it
        and restores normal mode on leaving."""
        self.stream.write(self.enter_fullscreen)
        try:
            yield
        finally:
            self.stream.write(self.exit_fullscreen)

    @contextmanager
    def hidden_cursor(self):
        """Return a context manager that hides the cursor while inside it and
        makes it visible on leaving."""
        self.stream.write(self.hide_cursor)
        try:
            yield
        finally:
            self.stream.write(self.normal_cursor)

    @property
    def color(self):
        """Return a capability that sets the foreground color.

        The capability is unparametrized until called and passed a number
        (0-15), at which point it returns another string which represents a
        specific color change. This second string can further be called to
        color a piece of text and set everything back to normal afterward.

        :arg num: The number, 0-15, of the color

        """
        return (ParametrizingString(self._foreground_color, self.normal)
                if self.does_styling else NullCallableString())

    @property
    def on_color(self):
        """Return a capability that sets the background color.

        See ``color()``.

        """
        return (ParametrizingString(self._background_color, self.normal)
                if self.does_styling else NullCallableString())

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
        #
        # tigetnum('colors') returns -1 if no color support, -2 if no such
        # capability. This higher-level capability provided by blessings
        # returns only non-negative values. For values (0, -1, -2), the value
        # 0 is always returned.
        colors = tigetnum('colors') if self.does_styling else -1
        #  self.__dict__['colors'] = ret  # Cache it. It's not changing.
                                          # (Doesn't work.)
        return max(0, colors)

    def _resolve_formatter(self, attr):
        """Resolve a sugary or plain capability name, color, or compound
        formatting function name into a callable capability.

        Return a ``ParametrizingString`` or a ``FormattingString``.

        """
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
        """Return a terminal code for a capname or a sugary name, or an empty
        Unicode.

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

    def _resolve_color(self, color):
        """Resolve a color like red or on_bright_green into a callable
        capability."""
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
        """Return a new ``FormattingString`` which implicitly receives my
        notion of "normal"."""
        return FormattingString(formatting, self.normal)

    def ljust(self, text, width=None, fillchar=u' '):
        """T.ljust(text, [width], [fillchar]) -> string

        Return string ``text``, left-justified by printable length ``width``.
        Padding is done using the specified fill character (default is a space).
        Default width is the attached terminal's width. ``text`` is
        escape-sequence safe."""
        if width is None:
            width = self.width
        return Sequence(text).ljust(width, fillchar)

    def rjust(self, text, width=None, fillchar=u' '):
        """T.rjust(text, [width], [fillchar]) -> string

        Return string ``text``, right-justified by printable length ``width``.
        Padding is done using the specified fill character (default is a space)
        Default width is the attached terminal's width. ``text`` is
        escape-sequence safe."""
        if width is None:
            width = self.width
        return Sequence(text).rjust(width, fillchar)

    def center(self, text, width=None, fillchar=u' '):
        """T.center(text, [width], [fillchar]) -> string

        Return string ``text``, centered by printable length ``width``.
        Padding is done using the specified fill character (default is a space).
        Default width is the attached terminal's width. ``text`` is
        escape-sequence safe."""
        if width is None:
            width = self.width
        return Sequence(text).center(width, fillchar)

    def wrap(self, text, width=None, **kwargs):
        """
        T.wrap(S, [width=None, indent=u'']) -> unicode

        Wrap paragraphs containing escape sequences, ``S``, to the width of
        terminal instance ``T``, wrapped by the virtual printable length,
        irregardless of the escape sequences it may contain. Returns a list
        of strings that may contain escape sequences. See textwrap.TextWrapper
        class for available keyword args to customize wrapping behaviour. Note
        that the keyword argument ``break_long_words`` may not be set True, as
        it is not sequence-safe.
        """
        _blw = 'break_long_words'
        assert (_blw not in kwargs or not kwargs[_blw]), (
                "keyword argument `{}' is not sequence-safe".format(_blw))
        width = self.width if width is None else width
        lines = []
        for line in text.splitlines():
            if not line.strip():
                lines.append(u'')
                continue
            for wrapped in _SequenceTextWrapper(width, **kwargs).wrap(text):
                lines.append(wrapped)
        return lines


def derivative_colors(colors):
    """Return the names of valid color variants, given the base colors."""
    return set([('on_' + c) for c in colors] +
               [('bright_' + c) for c in colors] +
               [('on_bright_' + c) for c in colors])


COLORS = set(['black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan',
              'white'])
COLORS.update(derivative_colors(COLORS))
COMPOUNDABLES = (COLORS |
                 set(['bold', 'underline', 'reverse', 'blink', 'dim', 'italic',
                      'shadow', 'standout', 'subscript', 'superscript']))


class ParametrizingString(unicode):
    """A Unicode string which can be called to parametrize it as a terminal
    capability"""

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
    """A Unicode string which can be called upon a piece of text to wrap it in
    formatting"""

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
    """A dummy callable Unicode to stand in for ``FormattingString`` and
    ``ParametrizingString``

    We use this when there is no tty and thus all capabilities should be blank.

    """
    def __new__(cls):
        new = unicode.__new__(cls, u'')
        return new

    def __call__(self, *args):
        """Return a Unicode or whatever you passed in as the first arg
        (hopefully a string of some kind).

        When called with an int as the first arg, return an empty Unicode. An
        int is a good hint that I am a ``ParametrizingString``, as there are
        only about half a dozen string-returning capabilities on OS X's
        terminfo man page which take any param that's not an int, and those are
        seldom if ever used on modern terminal emulators. (Most have to do with
        programming function keys. Blessings' story for supporting
        non-string-returning caps is undeveloped.) And any parametrized
        capability in a situation where all capabilities themselves are taken
        to be blank are, of course, themselves blank.

        When called with a non-int as the first arg (no no args at all), return
        the first arg. I am acting as a ``FormattingString``.

        """
        if len(args) != 1 or isinstance(args[0], int):
            # I am acting as a ParametrizingString.

            # tparm can take not only ints but also (at least) strings as its
            # second...nth args. But we don't support callably parametrizing
            # caps that take non-ints yet, so we can cheap out here. TODO: Go
            # through enough of the motions in the capability resolvers to
            # determine which of 2 special-purpose classes,
            # NullParametrizableString or NullFormattingString, to return, and
            # retire this one.
            #
            # As a NullCallableString, even when provided with a parameter,
            # such as t.color(5), we must also still be callable:
            #   t.color(5)('shmoo')
            # is actually a NullCallable()().
            # so turtles all the way down: we return another instance.
            return NullCallableString()
        return args[0]  # Should we force even strs in Python 2.x to be
                        # unicodes? No. How would I know what encoding to use
                        # to convert it?

class _SequenceTextWrapper(textwrap.TextWrapper):

    def _wrap_chunks(self, chunks):
        """
        escape-sequence aware varient of _wrap_chunks. Though
        movement sequences, such as term.left() are certainly not
        honored, sequences such as term.bold() are, and are not
        broken mid-sequence.
        """
        lines = []
        if self.width <= 0 or not isinstance(self.width, int):
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
            if (not hasattr(self, 'drop_whitespace') or self.drop_whitespace
                    ) and (chunks[-1].strip() == '' and lines):
                del chunks[-1]
            while chunks:
                chunk_len = len(Sequence(chunks[-1]))
                if cur_len + chunk_len <= width:
                    cur_line.append(chunks.pop())
                    cur_len += chunk_len
                else:
                    break
            if chunks and len(Sequence(chunks[-1])) > width:
                self._handle_long_word(chunks, cur_line, cur_len, width)
            if (not hasattr(self, 'drop_whitespace') or self.drop_whitespace
                    ) and (cur_line and cur_line[-1].strip() == ''):
                del cur_line[-1]
            if cur_line:
                lines.append(indent + u''.join(cur_line))
        return lines


class Sequence(unicode):
    """
    This unicode-derived class understands the effect of escape sequences
    of printable length, allowing a properly implemented .rjust(), .ljust(),
    .center(), and .len()
    """

    def __new__(cls, sequence_text):
        new = unicode.__new__(cls, sequence_text)
        return new

    def ljust(self, width, fillchar=u' '):
        return self + fillchar * (max(0, width - self.__len__()))

    def rjust(self, width, fillchar=u' '):
        return fillchar * (max(0, width - self.__len__())) + self

    def center(self, width, fillchar=u' '):
        split = max(0.0, float(width) - self.__len__()) / 2
        return (fillchar * (max(0, int(math.floor(split)))) + self
                + fillchar * (max(0, int(math.ceil(split)))))
    @property
    def will_move(self):
        return _sequence_is_movement(self)

    def __len__(self):
        """  S.__len__() -> integer

        Return the printable length of a string that contains (some types) of
        (escape) sequences. Although accounted for, strings containing
        sequences such as cls() will not give accurate returns (length of 0).
        backspace (\b) delete (chr(127)), are accounted for, however.
        """
        # TODO: also \a, and other such characters are accounted for in the
        #       same way that python does, they are considered 'lengthy'
        # ``nxt``: points to first character beyond current escape sequence.
        # ``width``: currently estimated display length.
        nxt, width = 0, 0

        def get_padding(text):
            """ get_padding(S) -> integer

            Returns int('nn') in SGR sequence '\\033[nnC' for use with replacing
            Terminal().right(nn) with printable characters, Otherwise 0 if
            ``S`` is not an escape sequence, or an SGR sequence of form '\\033[nnC'.
            """
            # Use case: displaying ansi art, which presumes \r\n remains
            # that line as empty; however, if this ansi art is placed in a
            # pager window, and scrolling upward is performed, or re-displayed
            # over existing text, then an undesirable "ghosting" effect occurs,
            # where previously displayed artwork is not overwritten.
            right = _SEQ_SGR_RIGHT.match(text)
            return (0 if right is None
                    else int(right.group(1)))
            # XXX test get_padding(1), make global method and test directly

        for idx in range(0, unicode.__len__(self)):
            # account for width of sequences that contain padding (a sort of
            # SGR-equivalent cheat for the python equivalent of ' '*N, for
            # very large values of N that may xmit fewer bytes than many raw
            # spaces. It should be noted, however, that this is a
            # non-destructive space.
            width += _sequence_padding(self[idx:])
            if idx == nxt:
                # point beyond this sequence
                nxt = idx + _sequence_length(self[idx:])
            if nxt <= idx:
                # TODO:
                # 'East Asian Fullwidth' and 'East Asian Wide' characters
                # can take 2 cells, see http://www.unicode.org/reports/tr11/
                # and http://www.gossamer-threads.com/lists/python/bugs/972834
                # ( or even emoticons, such as hamsterface (chr(128057)) --
                # though.. it should, it doesn't on iTerm, this is bleeding
                # edge stuffs!! watchout! besides 'narrow' build still default
                # in many OS's, shame...); wcswidth.py accounts at least for
                # those east asian fullwidth characters.
                width += 1
                # point beyond next sequence, if any, otherwise next character
                nxt = idx + _sequence_length(self[idx:]) + 1
        return width



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


def _sequence_length(ucs):
    """
    _sequence_length(S) -> integer

    Returns non-zero for string ``S`` that begins with an escape sequence,
    with value of the number of characters until sequence is complete.  For
    use as a 'next' pointer to skip past sequences.  If string ``S`` is not
    a sequence, 0 is returned.
    """
    _esc = '\x1b'
    ulen = unicode.__len__(ucs)
    if ulen in (0, 1) or not ucs.startswith(_esc):
        # '' or '\x1b', or any other value not beginning with '\x1b' returns 0.
        # A single string of value '\x1b' is not a *sequence* ..
        # It is simply a single escape character. Though unprintable, it
        # doesn\'t merit anything on its own.
        return 0
    matching_seq = _SEQ_WILLMOVE.match(ucs) or _SEQ_WONTMOVE.match(ucs)
    if matching_seq is not None:
        start, end = matching_seq.span()
        return end
    # no matching sequence found
    return 0

    """
    _sequence_is_movement(S) -> bool

    Returns True for string ``S`` that begins with an escape sequence that
    may cause the cursor position to move.

    Most printable characters simply forward the "carriage" a single unit
    (with the exception of a few "double-wide", usually east-asian but also
    emoticon, characters).

    Most escape sequences typically change or set Terminal attributes, and
    are hidden from printable display. Other sequences, however, such as
    "move to column N", or "restore alternate screen", have an effect of
    moving the cursor to an indeterminable location, at least in the sense of
    "what is the printable width of this string". Additionaly, the CR, LF
    and BS are also considered "movement".

    Such sequences return ``True``, if found at the beginning of ``S``.
    """
    if len(ucs) and ucs[0] in u'\r\n\b':
        return True
    return False if _SEQ_WILLMOVE.match(ucs) is None else True
