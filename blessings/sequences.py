import textwrap
import math
import re


def _init_sequence_patterns(term):
    def build_numeric_capability(cap):
        cap = getattr(term, cap)
        if cap:
            cap_re = re.escape(cap(99)).replace('99', r'(\d+)?')
#            assert False, repr(cap_re)
            return re.compile(cap_re)
        return None
    term._re_cuf = build_numeric_capability('cuf')
    term._re_cub = build_numeric_capability('cub')
    term._re_willmove = re.compile('xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')


class _SequenceTextWrapper(textwrap.TextWrapper):
    def __init__(self, width, **kwargs):
        self.term = kwargs.pop('term')
        textwrap.TextWrapper.__init__(self, width, **kwargs)

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
            if (not hasattr(self, 'drop_whitespace')
                or self.drop_whitespace) and (
                    chunks[-1].strip() == '' and lines):
                del chunks[-1]
            while chunks:
                chunk_len = len(_Sequence(chunks[-1]))
                if cur_len + chunk_len <= width:
                    cur_line.append(chunks.pop())
                    cur_len += chunk_len
                else:
                    break
            if chunks and len(_Sequence(chunks[-1])) > width:
                self._handle_long_word(chunks, cur_line, cur_len, width)
            if (not hasattr(self, 'drop_whitespace')
                or self.drop_whitespace) and (
                    cur_line and cur_line[-1].strip() == ''):
                del cur_line[-1]
            if cur_line:
                lines.append(indent + u''.join(cur_line))
        return lines


class _Sequence(unicode):
    """
    This unicode-derived class understands the effect of escape sequences
    of printable length, allowing a properly implemented .rjust(), .ljust(),
    .center(), and .len()
    """

    def __new__(cls, term, sequence_text):
        new = unicode.__new__(cls, sequence_text)
        self.term = term
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
        sequences such as 'clear' will not give accurate returns
        (length of 0).
        """
        # TODO: also \a, and other such characters are accounted for in the
        #       same way that python does, they are considered 'lengthy'
        # ``nxt``: points to first character beyond current escape sequence.
        # ``width``: currently estimated display length.
        nxt, width = 0, 0
        for idx in range(0, unicode.__len__(self)):
            # account for width of sequences that contain padding (a sort of
            # SGR-equivalent cheat for the python equivalent of ' '*N, for
            # very large values of N that may xmit fewer bytes than many raw
            # spaces. It should be noted, however, that this is a
            # non-destructive space.
            width += _horizontal_distance(self[idx:], term)
            if idx == nxt:
                # point beyond this sequence
                nxt = idx + _unprintable_length(self[idx:], term)
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
                nxt = idx + _unprintable_length(self[idx:], term) + 1
        return width

# We provide a database of "typical" sequences. mrxvt_seq.txt by Gautam Iyer
# <gi1242@users.sourceforge.net> was invaluable in the authoring of these
# regular expressions. The current author of xterm (Thomas Dickey) also
# provides many invaluable resources.

_SEQ_WONTMOVE = re.compile(
    r'\x1b('  # curses.ascii.ESC
        r'([\(\)\*\+\$]'  # Designate G0-G3,Kangi Character Set
            r'[0AB<5CK])'  # 0=DEC,A=UK,B=USASCII,<=Multinational
                           # 5/C=Finnish,K=German
        r'|7'  # save_cursor
        r'|\[('  # \x1b[: Begin Control Sequence Initiator(CSI) ...
            r'[0-2]?[JK]'  # J:erase in display (0=below,1=above,2=All)
                           # K:erase in line (0=right,1=left,2=All)
            r'|\d+;\d+;\d+;\d+;\dT'
                           # Initiate hilite mouse tracking, params are
                           # func;startx;starty;firstrow;lastrow
            r'|[025]W'  # tabular funcs: 0=set,2=clear Current,5=clear All
            r'|[03]g'  # tab clear: 0=current,3=all
            r'|4[hl]'  # hl: insert, replace mode.
            r'|(\d{0,3}(;\d{0,3}){1,5}|\d{1,3}|)m'
                        # SGR (attributes), extraordinarily forgiving!
            r'|0?c'  # send device attributes (terminal replies!)
            r'|[5-8]n'  # device status report, 5: answers OK, 6: cursor pos,
                       # 7: display name, 8: version number (terminal replies!)
            r'|[zs]'  # save_cursor
        r'|(\?'  # DEC Private Modes -- extraordinarily forgiving!
            r'[0-9]{0,4}(;\d{1,4}){0,4}[hlrst]'
                # hlrst:set, reset, restore, save, toggle:
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
        r')'  # end DEC Private Modes
      r')'  # end CSI
    r')')  # end \x1b

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
        r'|\][0-9]{1,2};[\s\w]+('  # Set XTerm params, ESC ] Ps;Pt ST
            + '\x9c'  # 8-bit terminator
            + '|\a'   # old terminator (BEL)
            + r'|\x1b\\)'  # 7-bit terminator
    r')'  # end CSI
r')')  # end x1b


def _unprintable_length(ucs, term=None):
    """
    _unprintable_length(S) -> integer

    Returns non-zero for string ``S`` that begins with a terminal sequence,
    with value of the number of characters until sequence is complete.  For
    use as a 'next' pointer to skip past sequences.  If string ``S`` is not
    a sequence, 0 is returned. A sequence may be a typical terminal sequence
    beginning with <esc>, especially a Control Sequence Initiator(CSI, \033[),
    or those of '\a', '\b', '\r', '\n',
    """
    # simple terminal control characters,
    if any([ucs.startswith(_ch) for _ch in u'\a\b\r\n\x0e\x0f']):
        # x0e,x0f = shift out, shift in
        return 1
    # known multibyte sequences,
    matching_seq = _SEQ_WILLMOVE.match(ucs) or _SEQ_WONTMOVE.match(ucs)
    if matching_seq is not None:
        start, end = matching_seq.span()
        return end
    # none found, must be printable!
    return 0


_SEQ_SGR_RIGHT = re.compile(r'\033\[(\d+)?C')
_SEQ_SGR_LEFT = re.compile(r'\033\[(\d+)?D')


def _horizontal_distance(ucs, term=None):
    """ _horizontal_distance(S) -> integer

    Returns Integer n in SGR sequence of form <ESC>[<n>C (T.move_right(nn)).
    Returns Integer -(n) in SGR sequence of form <ESC>[<n>D (T.move_left(nn)).
    Returns -1 for backspace (0x08), Otherwise 0.
    Tabstop (\t) cannot be correctly calculated, as the relative column
    position cannot be determined: 8 is always (and incorrectly) returned.
    """
    def term_distance(cap, unit):
        """ Match by simple cub1/cuf1 string matching (distance of 1)
            Or, by regular expression (using dynamic regular expressions
            built using cub(n) and cuf(n). Failing that, the standard
            SGR sequences (\033[C, \033[D, \033[nC, \033[nD
        """
        # match cub1(left), cuf1(right)
        one = getattr(term, '{}1'.format(cap))
        if one and ucs.startswith(one):
            return unit

        # match cub(n), cuf(n) using regular expressions
        re_pattern = getattr(term, '_re_{}'.format(cap))
        _dist = re_pattern.match(ucs)
        if _dist:
            return unit * int(_dist.group(1))

        # match SGR left,right

    if ucs.startswith('\b'):
        return -1

    elif ucs.startswith('\t'):
        # as best as I can prove it, a tabstop is always 8 by default.
        # Within the context provided by blessings, which is 1. unaware
        # of the output device's current cursor position, and 2. unaware
        # of when or where a user may chose to output any given string,
        # it is impossible to determine how many cells any particular
        # \t would consume on the output device.
        return 8

    _td = term and (term_distance('cub', -1) or term_distance('cuf', 1))
    if _td:
        return _td
    left = _SEQ_SGR_LEFT.match(ucs)
    if left:
        return -1 * int(left.group(1))
    right = _SEQ_SGR_RIGHT.match(ucs)
    if right:
        return 1 * int(right.group(1))

    return 0


def _sequence_is_movement(ucs, term=None):
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
    return bool(_SEQ_WILLMOVE.match(ucs) or
                term and term._re_willmove.match(ucs) or
                _horizontal_distance(ucs, term))
