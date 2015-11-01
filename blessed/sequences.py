# encoding: utf-8
"""This module provides 'sequence awareness'."""
# std imports
import collections
import functools
import math
import re
import textwrap
import warnings

# local
from blessed._capabilities import (
    CAPABILITIES_CAUSE_MOVEMENT,
    CAPABILITIES_RAW_MIXIN,
    CAPABILITY_DATABASE,
)

# 3rd party
import wcwidth
import six

__all__ = ('Sequence', 'SequenceTextWrapper')

class Termcap():
    def __init__(self, name, pattern, attribute):
        """
        :param str name: name describing capability.
        :param str pattern: regular expression string.
        :param str attribute: :class:`~.Terminal` attribute used to build
            this terminal capability.
        """
        self.name = name
        self.pattern = pattern
        self.attribute = attribute
        self._re_compiled = None

    def __repr__(self):
        return '<Termcap {self.name}:{self.pattern!r}>'.format(self=self)

    @property
    def re_compiled(self):
        if self._re_compiled is None:
            self._re_compiled = re.compile(self.pattern)
        return self._re_compiled

    @property
    def named_pattern(self):
        return '(?P<{self.name}>{self.pattern})'.format(self=self)

    @property
    def will_move(self):
        """Whether capability causes cursor movement."""
        return self.name in CAPABILITIES_CAUSE_MOVEMENT

    def horizontal_distance(self, text):
        """
        Horizontal carriage adjusted by capability, may be negative!

        :rtype: int
        :param str text: for capabilities *parm_left_cursor*,
            *parm_right_cursor*, provide the matching sequence
            text, its interpreted distance is returned.

        :returns: 0 except for matching '
        """
        value = {
            'cursor_left': -1,
            'backspace': -1,
            'cursor_right': 1,
            'tab': 8,
            'ascii_tab': 8,
        }.get(self.name, None)
        if value is not None:
            return value

        unit = {
            'parm_left_cursor': -1,
            'parm_right_cursor': 1
        }.get(self.name, None)
        if unit is not None:
            value = int(self.re_compiled.match(text).group(1))
            return unit * value

        return 0

    @classmethod
    def build(cls, name, capability, attribute, nparams=0,
              numeric=99, match_grouped=False, match_any=False,
              match_optional=False):
        """
        :param str name: Variable name given for this pattern.
        :param str capability: A unicode string representing a terminal
            capability to build for. When ``nparams`` is non-zero, it
            must be a callable unicode string (such as the result from
            ``getattr(term, 'bold')``.
        :param attribute: The terminfo(5) capability name by which this
            pattern is known.
        :param int nparams: number of positional arguments for callable.
        :param bool match_grouped: If the numeric pattern should be
            grouped, ``(\d+)`` when ``True``, ``\d+`` default.
        :param bool match_any: When keyword argument ``nparams`` is given,
            *any* numeric found in output is suitable for building as
            pattern ``(\d+)``.  Otherwise, only the first matching value of
            range *(numeric - 1)* through *(numeric + 1)* will be replaced by
            pattern ``(\d+)`` in builder.
        :param bool match_optional: When ``True``, building of numeric patterns
            containing ``(\d+)`` will be built as optional, ``(\d+)?``.
        """
        _numeric_regex = r'\d+'
        if match_grouped:
            _numeric_regex = r'(\d+)'
        if match_optional:
            _numeric_regex = r'(\d+)?'
        numeric = 99 if numeric is None else numeric

        # basic capability attribute, not used as a callable
        if nparams == 0:
            return cls(name, re.escape(capability), attribute)

        # a callable capability accepting numeric argument
        _outp = re.escape(capability(*(numeric,) * nparams))
        if not match_any:
            for num in range(numeric - 1, numeric + 2):
                if str(num) in _outp:
                    pattern = _outp.replace(str(num), _numeric_regex)
                    return cls(name, pattern, attribute)

        if match_grouped:
            pattern = re.sub(r'(\d+)', _numeric_regex, _outp)
        else:
            pattern = re.sub(r'\d+', _numeric_regex, _outp)
        return cls(name, pattern, attribute)


class SequenceTextWrapper(textwrap.TextWrapper):
    """This docstring overridden."""

    def __init__(self, width, term, **kwargs):
        """
        Class initializer.

        This class supports the :meth:`~.Terminal.wrap` method.
        """
        self.term = term
        textwrap.TextWrapper.__init__(self, width, **kwargs)

    def _wrap_chunks(self, chunks):
        """
        Sequence-aware variant of :meth:`textwrap.TextWrapper._wrap_chunks`.

        This simply ensures that word boundaries are not broken mid-sequence,
        as standard python textwrap would incorrectly determine the length
        of a string containing sequences, and may also break consider sequences
        part of a "word" that may be broken by hyphen (``-``), where this
        implementation corrects both.
        """
        lines = []
        if self.width <= 0 or not isinstance(self.width, int):
            raise ValueError(
                "invalid width {0!r}({1!r}) (must be integer > 0)"
                .format(self.width, type(self.width)))

        term = self.term
        drop_whitespace = not hasattr(self, 'drop_whitespace'
                                      ) or self.drop_whitespace
        chunks.reverse()
        while chunks:
            cur_line = []
            cur_len = 0
            if lines:
                indent = self.subsequent_indent
            else:
                indent = self.initial_indent
            width = self.width - len(indent)
            if drop_whitespace and (
                    Sequence(chunks[-1], term).strip() == '' and lines):
                del chunks[-1]
            while chunks:
                chunk_len = Sequence(chunks[-1], term).length()
                if cur_len + chunk_len <= width:
                    cur_line.append(chunks.pop())
                    cur_len += chunk_len
                else:
                    break
            if chunks and Sequence(chunks[-1], term).length() > width:
                self._handle_long_word(chunks, cur_line, cur_len, width)
            if drop_whitespace and (
                    cur_line and Sequence(cur_line[-1], term).strip() == ''):
                del cur_line[-1]
            if cur_line:
                lines.append(indent + u''.join(cur_line))
        return lines

    def _handle_long_word(self, reversed_chunks, cur_line, cur_len, width):
        """Sequence-aware :meth:`textwrap.TextWrapper._handle_long_word`.

        This simply ensures that word boundaries are not broken mid-sequence,
        as standard python textwrap would incorrectly determine the length
        of a string containing sequences, and may also break consider sequences
        part of a "word" that may be broken by hyphen (``-``), where this
        implementation corrects both.
        """
        # Figure out when indent is larger than the specified width, and make
        # sure at least one character is stripped off on every pass
        if width < 1:
            space_left = 1
        else:
            space_left = width - cur_len

        # If we're allowed to break long words, then do so: put as much
        # of the next chunk onto the current line as will fit.

        if self.break_long_words:
            term = self.term
            chunk = reversed_chunks[-1]
            idx = nxt = 0
            for text, cap in iter_parse(term, chunk):
                nxt += len(text)
                if Sequence(chunk[:nxt], term).length() > space_left:
                    break
                idx = nxt
            cur_line.append(chunk[:idx])
            reversed_chunks[-1] = chunk[idx:]

        # Otherwise, we have to preserve the long word intact.  Only add
        # it to the current line if there's nothing already there --
        # that minimizes how much we violate the width constraint.
        elif not cur_line:
            cur_line.append(reversed_chunks.pop())

        # If we're not allowed to break long words, and there's already
        # text on the current line, do nothing.  Next time through the
        # main loop of _wrap_chunks(), we'll wind up here again, but
        # cur_len will be zero, so the next line will be entirely
        # devoted to the long word that we can't handle right now.


SequenceTextWrapper.__doc__ = textwrap.TextWrapper.__doc__

class Sequence(six.text_type):
    """
    A "sequence-aware" version of the base :class:`str` class.

    This unicode-derived class understands the effect of escape sequences
    of printable length, allowing a properly implemented :meth:`rjust`,
    :meth:`ljust`, :meth:`center`, and :meth:`length`.
    """

    def __new__(cls, sequence_text, term):
        """
        Class constructor.

        :param sequence_text: A string that may contain sequences.
        :param blessed.Terminal term: :class:`~.Terminal` instance.
        """
        new = six.text_type.__new__(cls, sequence_text)
        new._term = term
        return new

    def ljust(self, width, fillchar=u' '):
        """
        Return string containing sequences, left-adjusted.

        :param int width: Total width given to right-adjust ``text``.  If
            unspecified, the width of the attached terminal is used (default).
        :param str fillchar: String for padding right-of ``text``.
        :returns: String of ``text``, right-aligned by ``width``.
        :rtype: str
        """
        rightside = fillchar * int(
            (max(0.0, float(width - self.length()))) / float(len(fillchar)))
        return u''.join((self, rightside))

    def rjust(self, width, fillchar=u' '):
        """
        Return string containing sequences, right-adjusted.

        :param int width: Total width given to right-adjust ``text``.  If
            unspecified, the width of the attached terminal is used (default).
        :param str fillchar: String for padding left-of ``text``.
        :returns: String of ``text``, right-aligned by ``width``.
        :rtype: str
        """
        leftside = fillchar * int(
            (max(0.0, float(width - self.length()))) / float(len(fillchar)))
        return u''.join((leftside, self))

    def center(self, width, fillchar=u' '):
        """
        Return string containing sequences, centered.

        :param int width: Total width given to center ``text``.  If
            unspecified, the width of the attached terminal is used (default).
        :param str fillchar: String for padding left and right-of ``text``.
        :returns: String of ``text``, centered by ``width``.
        :rtype: str
        """
        split = max(0.0, float(width) - self.length()) / 2
        leftside = fillchar * int(
            (max(0.0, math.floor(split))) / float(len(fillchar)))
        rightside = fillchar * int(
            (max(0.0, math.ceil(split))) / float(len(fillchar)))
        return u''.join((leftside, self, rightside))

    def length(self):
        r"""
        Return the printable length of string containing sequences.

        Strings containing ``term.left`` or ``\b`` will cause "overstrike",
        but a length less than 0 is not ever returned. So ``_\b+`` is a
        length of 1 (displays as ``+``), but ``\b`` alone is simply a
        length of 0.

        Some characters may consume more than one cell, mainly those CJK
        Unified Ideographs (Chinese, Japanese, Korean) defined by Unicode
        as half or full-width characters.
        """
        # because control characters may return -1, "clip" their length to 0.
        clip = functools.partial(max, 0)
        return sum(clip(wcwidth.wcwidth(w_char))
                   for w_char in self.strip_seqs())

    # we require ur"" for the docstring, but it is not supported by pep257
    # tool: https://github.com/GreenSteam/pep257/issues/116
    length.__doc__ += (
        u"""For example:

            >>> from blessed import Terminal
            >>> from blessed.sequences import Sequence
            >>> term = Terminal()
            >>> Sequence(term.clear + term.red(u'コンニチハ'), term).length()
            10

        .. note:: Although accounted for, strings containing sequences such as
            ``term.clear`` will not give accurate returns, it is not
            considered lengthy (a length of 0).
        """)

    def strip(self, chars=None):
        """
        Return string of sequences, leading, and trailing whitespace removed.

        :param str chars: Remove characters in chars instead of whitespace.
        :rtype: str
        """
        return self.strip_seqs().strip(chars)

    def lstrip(self, chars=None):
        """
        Return string of all sequences and leading whitespace removed.

        :param str chars: Remove characters in chars instead of whitespace.
        :rtype: str
        """
        return self.strip_seqs().lstrip(chars)

    def rstrip(self, chars=None):
        """
        Return string of all sequences and trailing whitespace removed.

        :param str chars: Remove characters in chars instead of whitespace.
        :rtype: str
        """
        return self.strip_seqs().rstrip(chars)

    def strip_seqs(self):
        r"""
        Return string of all sequences removed.

            >>> from blessed import Terminal
            >>> from blessed.sequences import Sequence
            >>> term = Terminal()
            >>> Sequence(term.cuf(5) + term.red(u'test'), term).strip_seqs()
            u'     test'

        :rtype: str

        This method is used to determine the printable width of a string,
        and is the first pass of :meth:`length`.

        .. note:: Non-destructive sequences that adjust horizontal distance
            (such as ``\b`` or ``term.cuf(5)``) are replaced by destructive
            space or erasing.
        """
        gen = iter_parse(self._term, self.padd())
        return u''.join(text for text, cap in gen if not cap)

    def padd(self):
        """
        Return non-destructive horizontal movement as destructive spacing.

        :rtype: str
        """
        outp = ''
        for text, cap in iter_parse(self._term, self):
            if not cap:
                outp += text
                continue

            value = cap.horizontal_distance(text)
            if value > 0:
                outp += ' ' * value
            elif value < 0:
                outp = outp[:value]
            else:
                outp += text
        return outp

def iter_parse(term, ucs):
    for match in re.finditer(term._caps_compiled_any, ucs):
        name = match.lastgroup
        value = match.group(name)
        if name == 'MISMATCH':
            yield (value, None)
            continue
        yield value, term.caps[name]
