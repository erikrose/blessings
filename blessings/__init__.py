from collections import defaultdict
import curses
from curses import tigetstr, setupterm, tparm
from fcntl import ioctl
from os import isatty, environ
import struct
import sys
from termios import TIOCGWINSZ


__all__ = ['Terminal']


class Terminal(object):
    """An abstraction around terminal capabilities

    Unlike curses, this doesn't require clearing the screen before doing
    anything, and it's friendlier to use. It keeps the endless calls to
    tigetstr() and tparm() out of your code, and it acts intelligently when
    somebody pipes your output to a non-terminal.

    Instance attributes:
      stream: The stream the terminal outputs to. It's convenient to pass
        the stream around with the terminal; it's almost always needed when the
        terminal is and saves sticking lots of extra args on client functions
        in practice.
      is_a_tty: Whether ``stream`` appears to be a terminal. You can examine
        this value to decide whether to draw progress bars or other frippery.

    """
    def __init__(self, kind=None, stream=None, force_styling=False):
        """Initialize the terminal.

        If ``stream`` is not a tty, I will default to returning '' for all
        capability values, so things like piping your output to a file won't
        strew escape sequences all over the place. The ``ls`` command sets a
        precedent for this: it defaults to columnar output when being sent to a
        tty and one-item-per-line when not.

        :arg kind: A terminal string as taken by setupterm(). Defaults to the
            value of the TERM environment variable.
        :arg stream: A file-like object representing the terminal. Defaults to
            the original value of stdout, like ``curses.initscr()``.
        :arg force_styling: Whether to force the emission of capabilities, even
            if we don't seem to be in a terminal. This comes in handy if users
            are trying to pipe your output through something like ``less -r``,
            which supports terminal codes just fine but doesn't appear itself
            to be a terminal. Just expose a command-line option, and set
            ``force_styling`` based on it. Terminal initialization sequences
            will be sent to ``stream`` if it has a file descriptor and to
            ``sys.__stdout__`` otherwise. (setupterm() demands to send them
            somewhere, and stdout is probably where the output is ultimately
            headed. If not, stderr is probably bound to the same terminal.)

        """
        if stream is None:
            stream = sys.__stdout__
        stream_descriptor = (stream.fileno() if hasattr(stream, 'fileno')
                                             and callable(stream.fileno)
                             else None)
        self.is_a_tty = stream_descriptor is not None and isatty(stream_descriptor)
        if self.is_a_tty or force_styling:
            # The desciptor to direct terminal initialization sequences to.
            # sys.__stdout__ seems to always have a descriptor of 1, even if
            # output is redirected.
            init_descriptor = (sys.__stdout__.fileno() if stream_descriptor is None
                               else stream_descriptor)

            # Make things like tigetstr() work. Explicit args make setupterm()
            # work even when -s is passed to nosetests. Lean toward sending
            # init sequences to the stream if it has a file descriptor, and
            # send them to stdout as a fallback, since they have to go
            # somewhere.
            setupterm(kind or environ.get('TERM', 'unknown'),
                      init_descriptor)

            # Cache capability codes, because IIRC tigetstr requires a
            # conversation with the terminal. [Now I can't find any evidence of
            # that.]
            self._codes = {}
        else:
            self._codes = NullDict(lambda: NullCallableString(''))

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
        position='cup',  # deprecated
        move='cup',
        move_x='hpa',
        move_y='vpa',

        # You can use these if you want, but the named equivalents
        # like "red" and "on_green" are probably easier.
        color='setaf',
        on_color='setab',
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

        For a parametrized capability like ``cup``, pass the parameter too:
        ``some_term.cup(line, column)``.

        ``man terminfo`` for a complete list of capabilities.

        """
        if attr not in self._codes:
            # Store sugary names under the sugary keys to save a hash lookup.
            # Fall back to '' for codes not supported by this terminal.
            self._codes[attr] = self._resolve_formatter(attr)
        return self._codes[attr]

    @property
    def height(self):
        return height_and_width()[0]

    @property
    def width(self):
        return height_and_width()[1]

    def location(self, x=None, y=None):
        """Return a context manager for temporarily moving the cursor

        Move the cursor to a certain position on entry, let you print stuff
        there, then return the cursor to its original position::

            term = Terminal()
            with term.location(2, 5):
                print 'Hello, world!'
                for x in xrange(10):
                    print 'I can do it %i times!' % x

        """
        return Location(self, x, y)

    def _resolve_formatter(self, attr):
        """Resolve a sugary or plain capability name, color, or compound formatting function name into a callable string."""
        if attr in COLORS:
            return self._resolve_color(attr)
        elif attr in COMPOUNDABLES:
            # Bold, underline, or something that takes no parameters
            return FormattingString(self._resolve_capability(attr), self)
        else:
            formatters = split_into_formatters(attr)
            if all(f in COMPOUNDABLES for f in formatters):
                # It's a compound formatter, like "bold_green_on_red". Future
                # optimization: combine all formatting into a single escape
                # sequence
                return FormattingString(''.join(self._resolve_formatter(s)
                                                for s in formatters),
                                        self)
            else:
                return ParametrizingString(self._resolve_capability(attr))

    def _resolve_capability(self, atom):
        """Return a terminal code for a capname or a sugary name, or ''."""
        return tigetstr(self._sugar.get(atom, atom)) or ''

    def _resolve_color(self, color):
        """Resolve a color like red or on_bright_green into a callable string."""
        # TODO: Does curses automatically exchange red and blue and cyan and
        # yellow when a terminal supports setf/setb rather than setaf/setab?
        # I'll be blasted if I can find any documentation. The following
        # assumes it does.
        color_cap = ((self.setab or self.setb) if 'on_' in color else
                     (self.setaf or self.setf))
        # curses constants go up to only 7, so pass in an offset to get at the
        # bright colors at 8-15:
        offset = 8 if 'bright_' in color else 0
        base_color = color.rsplit('_', 1)[-1]
        return FormattingString(
            color_cap(getattr(curses, 'COLOR_' + base_color.upper()) + offset),
            self)


COLORS = set(['black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white'])
COLORS.update(set([('on_' + c) for c in COLORS] +
                  [('bright_' + c) for c in COLORS] +
                  [('on_bright_' + c) for c in COLORS]))
del c
COMPOUNDABLES = (COLORS |
                 set(['bold', 'underline', 'reverse', 'blink', 'dim', 'italic',
                      'shadow', 'standout', 'subscript', 'superscript']))


class ParametrizingString(str):
    """A string which can be called to parametrize it as a terminal capability"""
    def __call__(self, *args):
        try:
            return tparm(self, *args)
        except curses.error:
            # Catch "must call (at least) setupterm() first" errors, as when
            # running simply `nosetests` (without progressive) on nose-
            # progressive. Perhaps the terminal has gone away between calling
            # tigetstr and calling tparm.
            return ''
        except TypeError:
            # If the first non-int (i.e. incorrect) arg was a string, suggest
            # something intelligent:
            if len(args) == 1 and isinstance(args[0], basestring):
                raise TypeError(
                    'A native or nonexistent capability template received '
                    '%r when it was expecting ints. You probably misspelled a '
                    'formatting call like bold_red_on_white(...).' % args)
            else:
                # Somebody passed a non-string; I don't feel confident
                # guessing what they were trying to do.
                raise


class FormattingString(str):
    """A string which can be called upon a piece of text to wrap it in formatting"""
    def __new__(cls, formatting, term):
        new = str.__new__(cls, formatting)
        new._term = term
        return new

    def __call__(self, text):
        """Return a new string that is ``text`` formatted with my contents.

        At the beginning of the string, I prepend the formatting that is my
        contents. At the end, I append the "normal" sequence to set everything
        back to defaults.

        This should work regardless of whether ``text`` is unicode.

        """
        return self + text + self._term.normal


class NullCallableString(str):
    """A callable string that returns '' when called with an int and the arg otherwise."""
    def __call__(self, arg):
        if isinstance(arg, int):
            return ''
        return arg


class NullDict(defaultdict):
    """A ``defaultdict`` that pretends to contain all keys"""
    def __contains__(self, key):
        return True


def height_and_width():
    """Return a tuple of (terminal height, terminal width)."""
    # tigetnum('lines') and tigetnum('cols') apparently don't update while
    # nose-progressive's progress bar is running.
    return struct.unpack('hhhh', ioctl(0, TIOCGWINSZ, '\000' * 8))[0:2]


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


class Location(object):
    """Context manager for temporarily moving the cursor

    On construction, specify ``x`` to move to a certain column, ``y`` to move
    to a certain row, or both.

    """
    def __init__(self, term, x=None, y=None):
        self.x, self.y = x, y
        self.term = term

    def __enter__(self):
        """Save position and move to the requested position."""
        self.term.stream.write(self.term.save)  # save position
        if self.x and self.y:
            self.term.stream.write(self.term.move(self.y, self.x))
        elif self.x:
            self.term.stream.write(self.term.move_x(self.x))
        elif self.y:
            self.term.stream.write(self.term.move_y(self.y))

    def __exit__(self, type, value, tb):
        self.term.stream.write(self.term.restore)  # restore position
