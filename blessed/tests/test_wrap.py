import platform
import textwrap
import termios
import struct
import fcntl
import sys

from .accessories import (
    as_subprocess,
    TestTerminal,
    many_columns,
    all_terms,
)

import pytest


def test_SequenceWrapper_invalid_width():
    """Test exception thrown from invalid width"""
    WIDTH = -3

    @as_subprocess
    def child():
        t = TestTerminal()
        try:
            my_wrapped = t.wrap(u'------- -------------', WIDTH)
        except ValueError as err:
            assert err.args[0] == (
                "invalid width %r(%s) (must be integer > 0)" % (
                    WIDTH, type(WIDTH)))
        else:
            assert False, 'Previous stmt should have raised exception.'
            del my_wrapped  # assigned but never used

    child()


@pytest.mark.parametrize("kwargs", [
    dict(break_long_words=False,
         drop_whitespace=False,
         subsequent_indent=''),
    dict(break_long_words=False,
         drop_whitespace=True,
         subsequent_indent=''),
    dict(break_long_words=False,
         drop_whitespace=False,
         subsequent_indent=' '),
    dict(break_long_words=False,
         drop_whitespace=True,
         subsequent_indent=' '),
    dict(break_long_words=True,
         drop_whitespace=False,
         subsequent_indent=''),
    dict(break_long_words=True,
         drop_whitespace=True,
         subsequent_indent=''),
    dict(break_long_words=True,
         drop_whitespace=False,
         subsequent_indent=' '),
    dict(break_long_words=True,
         drop_whitespace=True,
         subsequent_indent=' '),
])
def test_SequenceWrapper(all_terms, many_columns, kwargs):
    """Test that text wrapping matches internal extra options."""
    @as_subprocess
    def child(term, width, kwargs):
        # build a test paragraph, along with a very colorful version
        t = TestTerminal()
        pgraph = u' '.join((
            'a', 'bc', 'def', 'ghij', 'klmno', 'pqrstu', 'vwxyz012',
            '34567890A', 'BCDEFGHIJK', 'LMNOPQRSTUV', 'WXYZabcdefgh',
            'ijklmnopqrstu', 'vwxyz123456789', '0ABCDEFGHIJKLMN  '))

        pgraph_colored = u''.join([
            t.color(idx % 7)(char) if char != ' ' else ' '
            for idx, char in enumerate(pgraph)])

        internal_wrapped = textwrap.wrap(pgraph, width=width, **kwargs)
        my_wrapped = t.wrap(pgraph, width=width, **kwargs)
        my_wrapped_colored = t.wrap(pgraph_colored, width=width, **kwargs)

        # ensure we textwrap ascii the same as python
        assert (internal_wrapped == my_wrapped)

        # ensure our first and last line wraps at its ends
        first_l = internal_wrapped[0]
        last_l = internal_wrapped[-1]
        my_first_l = my_wrapped_colored[0]
        my_last_l = my_wrapped_colored[-1]
        assert (len(first_l) == t.length(my_first_l))
        assert (len(last_l) == t.length(my_last_l))
        assert (len(internal_wrapped[-1]) == t.length(my_wrapped_colored[-1]))

        # ensure our colored textwrap is the same line length
        assert (len(internal_wrapped) == len(my_wrapped_colored))

    child(all_terms, many_columns, kwargs)
