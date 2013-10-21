import textwrap
import math
import re


def _init_sequence_patterns(term):
    def bnc(cap, optional=False, base_num=99, nparams=1):
        """ Build re from capability having matching numeric parameter """
        _cap = getattr(term, cap)
        if _cap:
            cap_re = re.escape(_cap(*((base_num,) * nparams)))
            for num in range(base_num-1, base_num+2):
                if str(num) in cap_re:
                    cap_re = cap_re.replace(str(num),
                                            r'(\d+)%s' % ('?' if optional
                                                          else '',))
                    return cap_re
                elif base_num == 99 and re.escape(u'\x83') in cap_re:
                    # kermit, binary-packed
                    cap_re = cap_re.replace(re.escape(u'\x83'), u'.')
                    return cap_re
                #elif re.escape(u'\x08cc') in cap_re:
                #    # avatar, binary-packed
                #    cap_re = cap_re.replace(re.escape(u'\x08cc'), u'...')
                #    return cap_re
            assert False, ('Unknown parameter in %r, %r' % (cap, cap_re))

    def bna(cap, num=99, nparams=1):
        """ Build re from capability having *any* matching parameters """
        _cap = getattr(term, cap)
        if _cap:
            cap_re = re.escape(_cap(*((num,) * nparams)))
            cap_re = re.sub('(\d+)', r'(\d+)', cap_re)
            if r'(\d+)' in cap_re:
                return cap_re
            cap_rex01 = re.escape(_cap(*((1,) * nparams)))
            if num == 99 and re.escape(u'\x01') in cap_rex01:
                # kermit, binary packed
                cap_re = cap_re.replace(re.escape(u'\xff'), r'.')
                return cap_re
            ## avatar
            #if re.escape(u'\x01') in cap_re255:
            #    cap_re = cap_re.replace(re.escape(u'\xdf'), r'.')
            #    return cap_re
            assert r'(\d+)' in cap_re, (
                'Could not discover numeric capability '
                'in %r, %r' % (cap, cap_re,))

    # static pattern matching for _horiontal_distance
    #
    # parm_right_cursor: Move #1 characters to the right
    term._cuf = bnc('cuf', optional=True)
    term._re_cuf = re.compile(term._cuf) if term._cuf else None
    # cursor_right: Non-destructive space (move right one space)
    term._cuf1 = term.cuf1
    # parm_left_cursor: Move #1 characters to the left
    term._cub = bnc('cub', optional=True)
    term._re_cub = re.compile(term._cub) if term._cub else None
    # cursor_left: Move left one space
    term._cub1 = term.cub1

    # _will_move for _sequence_is_movement
    #
    will_move = set()
    # carriage_return
    will_move.add(re.escape(term.cr))
    # column_address: Horizontal position, absolute
    will_move.add(bnc('hpa'))
    # row_address: Vertical position #1 absolute
    will_move.add(bnc('vpa'))
    # cursor_address: Move to row #1 columns #2
    will_move.add(bnc('cup', nparams=2))
    # cursor_down: Down one line
    will_move.add(re.escape(term.cud1))
    # cursor_home: Home cursor (if no cup)
    will_move.add(re.escape(term.home))
    # cursor_left: Move left one space
    will_move.add(re.escape(term.cub1))
    # cursor_right: Non-destructive space (move right one space)
    will_move.add(re.escape(term.cuf1))
    # cursor_up: Up one line
    will_move.add(re.escape(term.cuu1))
    # param_down_cursor: Down #1 lines
    will_move.add(bnc('cud', optional=True))
    # restore_cursor: Restore cursor to position of last save_cursor
    will_move.add(re.escape(term.rc))
    # clear_screen: clear screen and home cursor
    will_move.add(re.escape(term.clear))
    # add cuf and cub stored seperately for horiz movement
    if term._cuf:
        will_move.add(term._cuf)
    if term._cub:
        will_move.add(term._cub)
    # cursor_up: Up one line
    will_move.add(re.escape(term.enter_fullscreen))
    will_move.add(re.escape(term.exit_fullscreen))

    # _wont_move for _unprintable_length
    #
    wont_move = set()
    # print_screen: Print contents of screen
    wont_move.add(re.escape(term.mc0))
    # prtr_off: Turn off printer
    wont_move.add(re.escape(term.mc4))
    # prtr_on: Turn on printer
    wont_move.add(re.escape(term.mc5))
    # reset_{1,2,3}string: Reset string
    wont_move.update(map(re.escape, (term.r1, term.r2, term.r3,)))
    # save_cursor: Save current cursor position (P)
    wont_move.add(re.escape(term.sc))
    # set_tab: Set a tab in every row, current columns
    wont_move.add(re.escape(term.hts))
    # enter_bold_mode: Turn on bold (extra bright) mode
    wont_move.add(re.escape(term.bold))
    # enter_underline_mode: Begin underline mode
    wont_move.add(re.escape(term.underline))
    # enter_blink_mode: Turn on blinking
    wont_move.add(re.escape(term.blink))
    # enter_dim_mode: Turn on half-bright mode
    wont_move.add(re.escape(term.dim))
    # cursor_invisible: Make cursor invisible
    wont_move.add(re.escape(term.civis))
    # cursor_visible: Make cursor very visible
    wont_move.add(re.escape(term.cvvis))
    # cursor_normal: Make cursor appear normal (undo civis/cvvis)
    wont_move.add(re.escape(term.cnorm))
    # clear_all_tabs: Clear all tab stops
    wont_move.add(re.escape(term.tbc))
    # change_scroll_region: Change region to line #1 to line #2
    wont_move.add(bnc('csr', nparams=2))
    # clr_bol: Clear to beginning of line
    wont_move.add(re.escape(term.el1))
    # clr_eol: Clear to end of line
    wont_move.add(re.escape(term.el))
    # clr_eos: Clear to end of screen
    wont_move.add(re.escape(term.clear_eos))
    # delete_character: Delete character
    wont_move.add(re.escape(term.dch1))
    # delete_line: Delete line (P*)
    wont_move.add(re.escape(term.dl1))
    # erase_chars: Erase #1 characters
    wont_move.add(bnc('ech'))
    # insert_line: Insert line (P*)
    wont_move.add(re.escape(term.il1))
    # parm_dch: Delete #1 characters
    wont_move.add(bnc('dch'))
    # parm_delete_line: Delete #1 lines
    wont_move.add(bnc('dl'))
    # exit_alt_charset_mode: End alternate character set (P)
    wont_move.add(re.escape(term.rmacs))
    # exit_am_mode: Turn off automatic margins
    wont_move.add(re.escape(term.rmam))
    # exit_attribute_mode: Turn off all attributes
    wont_move.add(re.escape(term.sgr0))
    # exit_ca_mode: Strings to end programs using cup
    wont_move.add(re.escape(term.rmcup))
    # exit_insert_mode: Exit insert mode
    wont_move.add(re.escape(term.rmir))
    # exit_standout_mode: Exit standout mode
    wont_move.add(re.escape(term.rmso))
    # exit_underline_mode: Exit underline mode
    wont_move.add(re.escape(term.rmul))
    # flash_hook: Flash switch hook
    wont_move.add(re.escape(term.hook))
    # flash_screen: Visible bell (may not move cursor)
    wont_move.add(re.escape(term.flash))
    # keypad_local: Leave 'keyboard_transmit' mode
    wont_move.add(re.escape(term.rmkx))
    # keypad_xmit: Enter 'keyboard_transmit' mode
    wont_move.add(re.escape(term.smkx))
    # meta_off: Turn off meta mode
    wont_move.add(re.escape(term.rmm))
    # meta_on: Turn on meta mode (8th-bit on)
    wont_move.add(re.escape(term.smm))
    # orig_pair: Set default pair to its original value
    wont_move.add(re.escape(term.op))
    # parm_ich: Insert #1 characters
    wont_move.add(bnc('ich'))
    # parm_index: Scroll forward #1
    wont_move.add(bnc('indn'))
    # parm_insert_line: Insert #1 lines
    wont_move.add(bnc('il'))
    # erase_chars: Erase #1 characters
    wont_move.add(bnc('ech'))
    # parm_rindex: Scroll back #1 lines
    wont_move.add(bnc('rin'))
    # parm_up_cursor: Up #1 lines
    wont_move.add(bnc('cuu'))
    # scroll_forward: Scroll text up (P)
    wont_move.add(re.escape(term.ind))
    # scroll_reverse: Scroll text down (P)
    wont_move.add(re.escape(term.rev))

    # the following are not *exactly* legal, being extra forgiving.
    #
    # set_attributes: Define video attributes #1-#9 (PG9)
    for _num in range(1,10):
        wont_move.add(bna('sgr', nparams=_num))
    # tab: Tab to next 8-space hardware tab stop
    wont_move.add(re.escape(term.ht))
    # set_a_background: Set background color to #1, using ANSI escape
    wont_move.add(bna('setab', num=1))
    wont_move.add(bna('setab', num=(term.number_of_colors - 1)))
    # set_a_foreground: Set foreground color to #1, using ANSI escape
    wont_move.add(bna('setaf', num=1))
    wont_move.add(bna('setaf', num=(term.number_of_colors - 1)))

    def merge_sequences(inp):
        """ Merge a list of input sequence patterns into a resulting
        regular expression.
        1. filtering out the empty capabilities into a single set,
        ordered by longest-first.
        2. Further splitting sequences containing 'sub-sequences'
        (by char \x1b) into their own independent sequence; resolving
        sequences such as t.normal_cursor, (u'\x1b[34h\x1b[?25h') into
        two independent sequences (u'\x1b[34h' and u'\x1b[?25h').
        """
        inp = list(filter(None, inp))
        #out = set()
        #for seq in inp:
        #    #if re.escape('\x1b') in seq[1:]:
        #    #    out.update([re.escape('\x1b') + '%s' % (sub_seq)
        #    #                for sub_seq in seq.split(re.escape('\x1b'))
        #    #                if sub_seq])
        #    #else:
        #    #    assert seq != re.escape('\x1b'), seq
        #        out.add(seq)
        return sorted(inp, key=len, reverse=True)

    # store pre-compiled list as '_will_move' and '_wont_move', for debugging
    term._will_move = merge_sequences(will_move)
    term._re_will_move = re.compile('(%s)' % ('|'.join(term._will_move)))

    term._wont_move = merge_sequences(wont_move)
    term._re_wont_move = re.compile('(%s)' % ('|'.join(term._wont_move)))


class _SequenceTextWrapper(textwrap.TextWrapper):
    def __init__(self, width, term, **kwargs):
        self.term = term
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
            raise ValueError("invalid width %r(%s) (must be integer > 0)" % (
                self.width, type(self.width)))
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
                chunk_len = len(_Sequence(chunks[-1], self.term))
                if cur_len + chunk_len <= width:
                    cur_line.append(chunks.pop())
                    cur_len += chunk_len
                else:
                    break
            if chunks and len(_Sequence(chunks[-1], self.term)) > width:
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

    def __new__(cls, sequence_text, term):
        new = unicode.__new__(cls, sequence_text)
        new._term = term
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
            width += _horizontal_distance(self[idx:], self._term)
            if idx == nxt:
                # point beyond this sequence
                nxt = idx + _unprintable_length(self[idx:], self._term)
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
                nxt = idx + _unprintable_length(self[idx:], self._term) + 1
        return width

def _unprintable_length(ucs, term):
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
    # x0e,x0f = shift out, shift in
    ctrl_seqs = u'\a\b\r\n\x0e\x0f'
    if any([ucs.startswith(_ch) for _ch in ctrl_seqs]):
        return 1
    # known multibyte sequences,
    matching_seq = term and (
        term._re_will_move.match(ucs) or     # terminal-specific auto-generated
        term._re_wont_move.match(ucs))
    if matching_seq:
        start, end = matching_seq.span()
        return end
    # none found, must be printable!
    return 0


def _horizontal_distance(ucs, term):
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
        assert cap in ('cuf', 'cub')
        # match cub1(left), cuf1(right)
        one = getattr(term, '_%s1' % (cap,))
        if one and ucs.startswith(one):
            return unit

        # match cub(n), cuf(n) using regular expressions
        re_pattern = getattr(term, '_re_%s' % (cap,))
        _dist = re_pattern and re_pattern.match(ucs)
        if _dist:
            return unit * int(_dist.group(1))

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

    return term_distance('cub', -1) or term_distance('cuf', 1) or 0


def _sequence_is_movement(ucs, term):
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
    return bool(term._re_will_move.match(ucs))
