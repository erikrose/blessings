""" This sub-module provides 'keyboard awareness' for blessings.
"""

__author__ = 'Jeff Quast <contact@jeffquast.com>'
__license__ = 'MIT'

__all__ = ['init_keyboard_consts', 'init_keyboard_sequences', 'Keystroke']

import curses
import curses.has_key


class Keystroke(unicode):
    """
    unicode-derived class for describing keyboard input returned by
    term.inkey() that may, at times, be a sequence, providing properties
    ``is_sequence`` which returns True when the string is a known keyboard
    input sequence, and ``code``, which returns an integer value that may be
    compared against the terminal class attributes such as *KEY_LEFT*.
    """
    def __new__(cls, ucs='', code=None, name=None):
        new = unicode.__new__(cls, ucs)
        new._name = name
        new._code = code
        return new

    @property
    def is_sequence(self):
        """ Returns True if value represents a multibyte sequence. """
        return self._code is not None

    def __repr__(self):
        if self._name is None:
            return unicode.__repr__(self)
        return self._name
    __repr__.__doc__ = unicode.__doc__

    @property
    def name(self):
        """ Returns sring name of key sequence, such as 'KEY_LEFT'
        """
        return self._name

    @property
    def code(self):
        """ Returns integer keycode value of multibyte sequence.
        """
        return self._code


def init_keyboard_consts(term):
    """
    Initialize and attach to a blessings Terminal, ``term``, keycode attribute
    names, (such as ``KEY_LEFT``), and a mapping table, ``_keyboard_seqnames``
    that maps a given a keycode integer (such as the value of
    ``term.KEY_LEFT``) to the string name 'KEY_LEFT'. This is used by the
    ``__repr()__`` method and ``name`` property of the ``Keystroke`` class.
    """
    term._keyboard_seqnames = dict()
    for key_name, key_code in ((kc, getattr(curses, kc))
                               for kc in dir(curses)
                               if kc.startswith('KEY_')):
        setattr(term, key_name, key_code)
        term._keyboard_seqnames[key_code] = key_name

    # Inject KEY_TAB
    if not hasattr(curses, 'KEY_TAB'):
        setattr(term, 'KEY_TAB', max(term._keyboard_seqnames)+1)
        term._keyboard_seqnames[term.KEY_TAB] = 'KEY_TAB'

    # Friendly names for commonly used keyboard constants
    term.KEY_DELETE = term.KEY_DC
    term.KEY_INSERT = term.KEY_IC
    term.KEY_PGUP = term.KEY_PPAGE
    term.KEY_PGDOWN = term.KEY_NPAGE
    term.KEY_ESCAPE = term.KEY_EXIT


def init_keyboard_sequences(term):
    """
    Initialize and attach attribute ``_keyboard_mapper`` to blessings Terminal
    instance ``term``, a programatically generated mapping of
    keyboard-generated sequences, such as '\x1b[D', to their const definition,
    such as KEY_LEFT.  Additionally, pre-cache a sorted list of sequences,
    ``_keyboard_sequences`` sorted by longest-first, for pattern matching.
    """
    term._keyboard_mapper = dict()
    # A small gem from curses.has_key that makes this all possible,
    # *_capability_names*: a lookup table of terminal capability names for
    # keyboard sequences (fe. kcub1, key_left), keyed by the values of
    # constants found beginning with KEY_ in the main curses module
    # (such as KEY_LEFT).
    term._keyboard_mapper.update([
        (seq.decode('latin1'), val)
        for (seq, val) in [(curses.tigetstr(cap), val) for (val, cap) in
                           curses.has_key._capability_names.iteritems()
                           ] if seq
    ])

    # some terminals report a different value for kcuf1 than cuf1,
    # but actually send the value of cuf1 for right arrow key
    # (which is non-destructive space).
    if term._cuf1:
        term._keyboard_mapper[term._cuf1] = term.KEY_RIGHT
    if term._cub1:
        term._keyboard_mapper[term._cub1] = term.KEY_LEFT

    # In a perfect world, terminal emulators would always send exactly what the
    # terminfo db would expect from them, by the TERM name they declare.
    #
    # But this isn't a perfect world. Many vt220-derived terminals, such as
    # those declaring 'xterm', will continue to send vt220 codes instead of
    # their native-declared codes. This goes for many: rxvt, putty, iTerm.
    term._keyboard_mapper.update(dict([
        # these common control characters (and 127, ctrl+'?') mapped to
        # an application key definition.
        (unichr(10), term.KEY_ENTER),
        (unichr(13), term.KEY_ENTER),
        (unichr(8), term.KEY_BACKSPACE),
        (unichr(9), term.KEY_TAB),
        (unichr(27), term.KEY_EXIT),
        (unichr(127), term.KEY_DC),
        # vt100 application keys are still sent by xterm & friends, even if
        # their db reports otherwise; for compatibility reasons, likely.
        (u"\x1bOA", term.KEY_UP),
        (u"\x1bOB", term.KEY_DOWN),
        (u"\x1bOC", term.KEY_RIGHT),
        (u"\x1bOD", term.KEY_LEFT),
        (u"\x1bOH", term.KEY_LEFT),
        (u"\x1bOF", term.KEY_END),
        (u"\x1bOP", term.KEY_F1),
        (u"\x1bOQ", term.KEY_F2),
        (u"\x1bOR", term.KEY_F3),
        (u"\x1bOS", term.KEY_F4),
        # typical for vt220-derived
        (u"\x1b[A", term.KEY_UP),
        (u"\x1b[B", term.KEY_DOWN),
        (u"\x1b[C", term.KEY_RIGHT),
        (u"\x1b[D", term.KEY_LEFT),
        (u"\x1b[U", term.KEY_NPAGE),
        (u"\x1b[V", term.KEY_PPAGE),
        (u"\x1b[H", term.KEY_HOME),
        (u"\x1b[F", term.KEY_END),
        (u"\x1b[K", term.KEY_END),
        # atypical,
        (u"\x1bA", term.KEY_UP),
        (u"\x1bB", term.KEY_DOWN),
        (u"\x1bC", term.KEY_RIGHT),
        (u"\x1bD", term.KEY_LEFT),
        # rxvt,
        (u"\x1b?r", term.KEY_DOWN),
        (u"\x1b?x", term.KEY_UP),
        (u"\x1b?v", term.KEY_RIGHT),
        (u"\x1b?t", term.KEY_LEFT),
        (u"\x1b[@", term.KEY_IC),
    ]))

    # pre-cached sorted list, greatest length first, of keyboard sequence
    # keys. This is for fast lookup matching of sequences, prefering
    # full sequence (such as '\x1b[D', KEY_LEFT) over simple sequences
    # ('\x1b', KEY_EXIT).
    term._keyboard_sequences = list(sorted(term._keyboard_mapper,
                                           key=len,
                                           reverse=True))
