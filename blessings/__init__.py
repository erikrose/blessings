from collections import defaultdict
from contextlib import contextmanager
import curses
from curses import tigetstr, tigetnum, setupterm, tparm
import curses.has_key
from fcntl import ioctl
try:
    from io import UnsupportedOperation as IOUnsupportedOperation
except ImportError:
    class IOUnsupportedOperation(Exception):
        """A dummy exception to take the place of Python 3's ``io.UnsupportedOperation`` in Python 2"""
import os
from os import isatty, environ
from platform import python_version_tuple
import codecs
import struct
import sys
from termios import TIOCGWINSZ


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
            stream = sys.__stdout__
        try:
            stream_descriptor = (stream.fileno() if hasattr(stream, 'fileno')
                                                 and callable(stream.fileno)
                                 else None)
        except IOUnsupportedOperation:
            stream_descriptor = None

        self.is_a_tty = stream_descriptor is not None and isatty(stream_descriptor)
        self._does_styling = ((self.is_a_tty or force_styling) and
                              force_styling is not None)

        # The desciptor to direct terminal initialization sequences to.
        # sys.__stdout__ seems to always have a descriptor of 1, even if output
        # is redirected.
        self._init_descriptor = (sys.__stdout__.fileno()
                                 if stream_descriptor is None
                                 else stream_descriptor)
        if self._does_styling:
            # Make things like tigetstr() work. Explicit args make setupterm()
            # work even when -s is passed to nosetests. Lean toward sending
            # init sequences to the stream if it has a file descriptor, and
            # send them to stdout as a fallback, since they have to go
            # somewhere.
            setupterm(kind or environ.get('TERM', 'unknown'),
                      self._init_descriptor)

        self.stream = stream

        # as we receive input as a bytestring, and incrementally decode it
        # using the input decoding.
        import locale
        locale.setlocale(locale.LC_ALL, '')
        self.encoding = locale.getpreferredencoding()
        self.inpdecoder = codecs.getincrementaldecoder(self.encoding)()

        # Inherit curses keycap capability names, such as KEY_DOWN, to be
        # used with Keystroke code values for comparison to the terminal
        # instance.  The values are integer enumerations outside of 8-bit
        # or iso8859-1 range, so that they can be mixed by value, and not
        # confused with the value of control characters, alphanumerics,
        # and high-bits such as <alt>+a (integer 225).
        self._keycodes = [key for key in dir(curses) if key.startswith('KEY_')]
        for keycode in self._keycodes:
            # self.KEY_<keycode> = (int)
            setattr(self, keycode, getattr(curses, keycode))

        # This strange gem in standard python distrubtion appears to exist
        # even in the win32 distribution; a mapping of terminal capabilities
        # to the KEY_ attributes we've just previously copied. We construct a
        # dictionary of multibyte characters to expect, with an Integer value
        # suitable for pairing with KEY_ attribute values.
        self._keymap = dict()
        for keycode, cap in curses.has_key._capability_names.iteritems():
            value = curses.tigetstr(cap)
            if value is not None:
                self._keymap[value.decode('iso8859-1')] = keycode

        # Because our matching is paired by multibyte unicode strings, there
        # is not harm in going the extra mile to ensure our key mapping is
        # as closely paired as possible by including our own hand-paired
        # mapping, what doesn't match doesn't really hurt.
        self._keymap.update([(_seq.decode('iso8859-1'), _keyname)
            for (_seq, _keyname) in (
                (curses.tigetstr('khome'), self.KEY_HOME),
                (curses.tigetstr('kend'), self.KEY_END),
                (curses.tigetstr('kcuu1'), self.KEY_UP),
                (curses.tigetstr('kcud1'), self.KEY_DOWN),
                (curses.tigetstr('cuf1'), self.KEY_RIGHT),
                (curses.tigetstr('kcub1'), self.KEY_LEFT),
                (curses.tigetstr('knp'), self.KEY_NPAGE),
                (curses.tigetstr('kind'), self.KEY_NPAGE),
                (curses.tigetstr('kpp'), self.KEY_PPAGE),
                (curses.tigetstr('kri'), self.KEY_PPAGE),
                (curses.tigetstr('kent'), self.KEY_ENTER),
                (curses.tigetstr('kbs'), self.KEY_BACKSPACE),
                (curses.tigetstr('kdch1'), self.KEY_BACKSPACE),
                (curses.tigetstr('kich1'), self.KEY_INSERT),
                ) if _seq is not None and 0 != len(_seq)])

        # ... as well as a list of general NVT sequences you would
        # expect to receive from remote terminals, such as putty, rxvt,
        # SyncTerm, windows telnet, HyperTerminal, netrunner ..
        self._keymap.update([
            (unichr(10), self.KEY_ENTER),
            (unichr(13), self.KEY_ENTER),
            (unichr(8), self.KEY_BACKSPACE),
            (unichr(127), self.KEY_BACKSPACE),
            (unichr(27) + u"OA", self.KEY_UP),
            (unichr(27) + u"OB", self.KEY_DOWN),
            (unichr(27) + u"OC", self.KEY_RIGHT),
            (unichr(27) + u"OD", self.KEY_LEFT),
            (unichr(27) + u"OH", self.KEY_LEFT),
            (unichr(27) + u"OF", self.KEY_END),
            (unichr(27) + u"[A", self.KEY_UP),
            (unichr(27) + u"[B", self.KEY_DOWN),
            (unichr(27) + u"[C", self.KEY_RIGHT),
            (unichr(27) + u"[D", self.KEY_LEFT),
            (unichr(27) + u"[H", self.KEY_HOME),
            (unichr(27) + u"[F", self.KEY_END),
            (unichr(27) + u"[K", self.KEY_END),
            (unichr(27) + u"[U", self.KEY_NPAGE),
            (unichr(27) + u"[V", self.KEY_PPAGE),
            (unichr(27) + u"[@", self.KEY_INSERT),
            (unichr(27) + u"A", self.KEY_UP),
            (unichr(27) + u"B", self.KEY_DOWN),
            (unichr(27) + u"C", self.KEY_RIGHT),
            (unichr(27) + u"D", self.KEY_LEFT),
            (unichr(27) + u"?x", self.KEY_UP),
            (unichr(27) + u"?r", self.KEY_DOWN),
            (unichr(27) + u"?v", self.KEY_RIGHT),
            (unichr(27) + u"?t", self.KEY_LEFT), ])

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
        resolution = self._resolve_formatter(attr) if self._does_styling else NullCallableString()
        setattr(self, attr, resolution)  # Cache capability codes.
        return resolution

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
        """Return a tuple of (terminal height, terminal width)."""
        # tigetnum('lines') and tigetnum('cols') update only if we call
        # setupterm() again.
        for descriptor in self._init_descriptor, sys.__stdout__:
            try:
                return struct.unpack('hhhh', ioctl(descriptor, TIOCGWINSZ, '\000' * 8))[0:2]
            except IOError:
                pass
        return None, None  # Should never get here

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
        yield

        # Restore original cursor position:
        self.stream.write(self.restore)

    @contextmanager
    def fullscreen(self):
        """Return a context manager that enters fullscreen mode while inside it and restores normal mode on leaving."""
        self.stream.write(self.enter_fullscreen)
        yield
        self.stream.write(self.exit_fullscreen)

    @contextmanager
    def hidden_cursor(self):
        """Return a context manager that hides the cursor while inside it and makes it visible on leaving."""
        self.stream.write(self.hide_cursor)
        yield
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
        return ParametrizingString(self._foreground_color, self.normal)

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

    def _resolve_keycode(self, integer):
        """
        Returns printable string to represent matched multibyte sequence,
        such as 'KEY_LEFT'. For purposes of __repr__ or __str__ ?
        """
        assert type(integer) is int
        for keycode in self._keycodes:
            if getattr(self, keycode) == integer:
                return keycode

    def _resolve_multibyte(self, text, end=False):
        """
        Yield a unicode with additional ``.is_sequence``, ``.name``,
        and ``.code`` properties that describle matching multibyte input
        sequences to keycode (if any). Set end=True if the last byte is
        known to be the final byte in the sequence. Throws UnicodeDecodeError.
        """
        CR_NVT = u'\r\x00' # NVT return (telnet, etc.)
        CR_DOS = u'\r\n'   # carriage return + newline
        decoded = list()
        for num, byte in enumerate(text):
            ucs = self.inpdecoder.decode(byte,
                    final=(end or num == (len(text)- 1)))
            if ucs is not None:
                decoded.append(ucs)
        data = u''.join(decoded)

        def scan_keymap(text):
            """
            Return sequence and keycode if text begins with any known sequence.
            """
            for (keyseq, keycode) in self._keymap.iteritems():
                if text.startswith(keyseq):
                    return (keyseq, self._resolve_keycode(keycode), keycode)
            return (None, None, None)  # no match

        # special care is taken to pass over the ineveitably troublesome
        # carriage return, which is a multibyte sequence issue of its own;
        # expect to receieve '\r\00', '\r\n', '\r', or '\n'.
        while len(data):
            if data[:2] in (CR_NVT, CR_DOS):
                yield Keystroke(data[2:], ('KEY_ENTER', self.KEY_ENTER))
                data = data[2:]
                continue
            elif data[:1] in (u'\r', u'\n'):
                yield Keystroke(data[1:], ('KEY_ENTER', self.KEY_ENTER))
                data = data[1:]
                continue
            keyseq, keyname, keycode = scan_keymap(data)
            if (keyseq, keyname, keycode) == (None, None, None):
                yield Keystroke(data[0], None)
                data = data[1:]
            else:
                yield Keystroke(keyseq, (keyname, keycode))
                data = data[len(keyseq):]


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
