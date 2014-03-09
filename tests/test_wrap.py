import textwrap
import termios
import struct
import fcntl
import sys

from accessories import (
    as_subprocess,
    TestTerminal,
    many_columns,
    many_lines,
    all_terms,
)


def test_SequenceWrapper(all_terms, many_lines, many_columns):
    """Test that text wrapping accounts for sequences correctly."""
    @as_subprocess
    def child(kind, lines=25, cols=80):
        # set the pty's virtual window size
        val = struct.pack('HHHH', lines, cols, 0, 0)
        fcntl.ioctl(sys.__stdout__.fileno(), termios.TIOCSWINSZ, val)

        # build a test paragraph, along with a very colorful version
        t = TestTerminal(kind=kind)
        pgraph = 'pony express, all aboard, choo, choo! ' + (
            ('whugga ' * 10) + ('choo, choooOOOOOOOooooOOooOooOoo! ')) * 10
        pgraph_colored = u''.join([
            t.color(n % 7) + t.bold + ch
            for n, ch in enumerate(pgraph)])

        internal_wrapped = textwrap.wrap(pgraph, t.width,
                                         break_long_words=False)
        my_wrapped = t.wrap(pgraph)
        my_wrapped_colored = t.wrap(pgraph_colored)

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
        # test subsequent_indent=
        internal_wrapped = textwrap.wrap(pgraph, t.width,
                                         break_long_words=False,
                                         subsequent_indent=' '*4)
        my_wrapped = t.wrap(pgraph, subsequent_indent=' '*4)
        my_wrapped_colored = t.wrap(pgraph_colored, subsequent_indent=' '*4)

        assert (internal_wrapped == my_wrapped)
        assert (len(internal_wrapped) == len(my_wrapped_colored))
        assert (len(internal_wrapped[-1]) == t.length(my_wrapped_colored[-1]))

    child(all_terms, many_lines, many_columns)
