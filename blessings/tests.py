# -*- coding: utf-8 -*-
"""Automated tests (as opposed to human-verified test patterns)

It was tempting to mock out curses to get predictable output from ``tigetstr``,
but there are concrete integration-testing benefits in not doing so. For
instance, ``tigetstr`` changed its return type in Python 3.2.3. So instead, we
simply create all our test ``Terminal`` instances with a known terminal type.
All we require from the host machine is that a standard terminfo definition of
xterm-256color exists.

"""
from __future__ import with_statement  # Make 2.5-compatible
from curses import tigetstr, tparm
from functools import partial
from StringIO import StringIO
import os
import sys
import pty
import traceback
import time
import math
import termios
import codecs

from nose.tools import eq_

# This tests that __all__ is correct, since we use below everything that should
# be imported:
from blessings import *


TestTerminal = partial(Terminal, kind='xterm-256color')


class as_subprocess:
    """ This helper executes test cases in a child process,
        avoiding a python-internal bug of _curses: setupterm()
        may not be called more than once per process.
    """
    _CHILD_PID = 0

    def __init__(self, func):
        self.func = func

    def __call__(self, *args, **kwargs):
        pid, master_fd = pty.fork()
        if pid is self._CHILD_PID:
            # child process executes function, raises exception
            # if failed, causing a non-zero exit code, using the
            # protected _exit() function of ``os``; to prevent the
            # 'SystemExit' exception from being thrown.
            try:
                self.func(*args, **kwargs)
            except Exception:
                e_type, e_value, e_tb = sys.exc_info()
                o_err = list()
                for line in traceback.format_tb(e_tb):
                    o_err.append(line.rstrip().encode('utf-8'))
                o_err.append(('-=' * 20).encode('ascii'))
                o_err.extend([_exc.rstrip().encode('utf-8') for _exc in
                              traceback.format_exception_only(
                                  e_type, e_value)])
                os.write(sys.__stdout__.fileno(), '\n'.join(o_err))
                os._exit(1)
            else:
                os._exit(0)

        exc_output = unicode()
        while True:
            try:
                _exc = os.read(master_fd, 65534)
            except OSError:
                # linux EOF
                break
            if not _exc:
                # bsd EOF
                break
            exc_output += _exc.decode('utf-8')

        # parent process asserts exit code is 0, causing test
        # to fail if child process raised an exception/assertion
        pid, status = os.waitpid(pid, 0)

        # Display any output written by child process (esp. those
        # AssertionError exceptions written to stderr).
        exc_output_msg = 'Output in child process:\n%s\n%s\n%s' % (
            u'=' * 40, exc_output, u'=' * 40,)
        eq_('', exc_output, exc_output_msg)

        # Also test exit status is non-zero
        eq_(os.WEXITSTATUS(status), 0)


def unicode_cap(cap):
    """Return the result of ``tigetstr`` except as Unicode."""
    return tigetstr(cap).decode('latin1')


def unicode_parm(cap, *parms):
    """Return the result of ``tparm(tigetstr())`` except as Unicode."""
    return tparm(tigetstr(cap), *parms).decode('latin1')


def test_capability():
    """Check that capability lookup works."""
    @as_subprocess
    def child():
        # Also test that Terminal grabs a reasonable default stream. This test
        # assumes it will be run from a tty.
        t = TestTerminal()
        sc = unicode_cap('sc')
        eq_(t.save, sc)
        eq_(t.save, sc)  # Make sure caching doesn't screw it up.
    child()


def test_capability_without_tty():
    """Assert capability templates are '' when stream is not a tty."""
    @as_subprocess
    def child():
        t = TestTerminal(stream=StringIO())
        eq_(t.save, u'')
        eq_(t.red, u'')
    child()


def test_capability_with_forced_tty():
    """force styling should return sequences even for non-ttys."""
    @as_subprocess
    def child():
        t = TestTerminal(stream=StringIO(), force_styling=True)
        eq_(t.save, unicode_cap('sc'))
    child()


def test_parametrization():
    """Test parametrizing a capability."""
    @as_subprocess
    def child():
        eq_(TestTerminal().cup(3, 4), unicode_parm('cup', 3, 4))
    child()


def test_height_and_width():
    """Assert that ``height_and_width()`` returns full integers."""
    @as_subprocess
    def child():
        t = TestTerminal()  # kind shouldn't matter.
        assert isinstance(t.height, int)
        assert isinstance(t.width, int)
    child()


def test_stream_attr():
    """Make sure Terminal exposes a ``stream`` attribute to stdout."""
    @as_subprocess
    def child():
        eq_(Terminal().stream, sys.__stdout__)
    child()


def test_location():
    """Make sure ``location()`` does what it claims."""
    @as_subprocess
    def child_with_styling():
        t = TestTerminal(stream=StringIO(), force_styling=True)
        with t.location(3, 4):
            t.stream.write(u'hi')
        eq_(t.stream.getvalue(), unicode_cap('sc') +
                                 unicode_parm('cup', 4, 3) +
                                 u'hi' +
                                 unicode_cap('rc'))
    child_with_styling()

    @as_subprocess
    def child_without_styling():
        """No side effect for location as a context manager without styling."""
        t = TestTerminal(stream=StringIO(), force_styling=None)

        with t.location(3, 4):
            t.stream.write(u'hi')

        eq_(t.stream.getvalue(), u'hi')

    child_with_styling()
    child_without_styling()


def test_horizontal_location():
    """Make sure we can move the cursor horizontally without changing rows."""
    @as_subprocess
    def child():
        t = TestTerminal(stream=StringIO(), force_styling=True)
        with t.location(x=5):
            pass
        eq_(t.stream.getvalue(), unicode_cap('sc') +
                                 unicode_parm('hpa', 5) +
                                 unicode_cap('rc'))
    child()


def test_null_location():
    """Make sure ``location()`` with no args just does position restoration."""
    @as_subprocess
    def child():
        t = TestTerminal(stream=StringIO(), force_styling=True)
        with t.location():
            pass
        eq_(t.stream.getvalue(), unicode_cap('sc') +
                                 unicode_cap('rc'))
    child()


def test_zero_location():
    """Make sure ``location()`` pays attention to 0-valued args."""
    @as_subprocess
    def child():
        t = TestTerminal(stream=StringIO(), force_styling=True)
        with t.location(0, 0):
            pass
        eq_(t.stream.getvalue(), unicode_cap('sc') +
                                 unicode_parm('cup', 0, 0) +
                                 unicode_cap('rc'))
    child()


def test_null_fileno():
    """Make sure ``Terminal`` works when ``fileno`` is ``None``."""
    @as_subprocess
    def child():
        # This simulates piping output to another program.
        out = StringIO()
        out.fileno = None
        t = TestTerminal(stream=out)
        eq_(t.save, u'')
    child()


def test_mnemonic_colors():
    """Make sure color shortcuts work."""
    @as_subprocess
    def child(kind='xterm-256color'):
        def color(t, num):
            return t.number_of_colors and unicode_parm('setaf', num) or ''

        def on_color(t, num):
            return t.number_of_colors and unicode_parm('setab', num) or ''

        # Avoid testing red, blue, yellow, and cyan, since they might someday
        # change depending on terminal type.
        t = TestTerminal(kind=kind)
        eq_(t.white, color(t, 7))
        eq_(t.green, color(t, 2))  # Make sure it's different than white.
        eq_(t.on_black, on_color(t, 0))
        eq_(t.on_green, on_color(t, 2))
        eq_(t.bright_black, color(t, 8))
        eq_(t.bright_green, color(t, 10))
        eq_(t.on_bright_black, on_color(t, 8))
        eq_(t.on_bright_green, on_color(t, 10))
    child()
    child('screen')
    child('vt220')
    child('rxvt')
    child('cons25')
    child('linux')
    child('ansi')


def test_callable_numeric_colors():
    """``color(n)`` should return a formatting wrapper."""
    @as_subprocess
    def child():
        t = TestTerminal()
        eq_(t.color(5)('smoo'), t.magenta + 'smoo' + t.normal)
        eq_(t.color(5)('smoo'), t.color(5) + 'smoo' + t.normal)
        eq_(t.on_color(2)('smoo'), t.on_green + 'smoo' + t.normal)
        eq_(t.on_color(2)('smoo'), t.on_color(2) + 'smoo' + t.normal)
    child()


def test_null_callable_numeric_colors():
    """``color(n)`` should be a no-op on null terminals."""
    @as_subprocess
    def child():
        t = TestTerminal(stream=StringIO())
        eq_(t.color(5)('smoo'), 'smoo')
        eq_(t.on_color(6)('smoo'), 'smoo')
    child()


def test_naked_color_cap():
    """``term.color`` should return a stringlike capability."""
    @as_subprocess
    def child():
        t = TestTerminal()
        eq_(t.color + '', t.setaf + '')
    child()


def test_number_of_colors_without_tty():
    """``number_of_colors`` should return 0 when there's no tty."""
    @as_subprocess
    def child_256_nostyle():
        t = TestTerminal(stream=StringIO())
        eq_(t.number_of_colors, 0)
    child_256_nostyle()

    @as_subprocess
    def child_256_forcestyle():
        t = TestTerminal(stream=StringIO(), force_styling=True)
        eq_(t.number_of_colors, 256)
    child_256_forcestyle()

    @as_subprocess
    def child_8_forcestyle():
        t = TestTerminal(kind='ansi', stream=StringIO(), force_styling=True)
        eq_(t.number_of_colors, 8)
    child_8_forcestyle()

    @as_subprocess
    def child_0_forcestyle():
        t = TestTerminal(kind='vt220', stream=StringIO(), force_styling=True)
        eq_(t.number_of_colors, 0)
    child_0_forcestyle()


def test_number_of_colors_with_tty():
    """``number_of_colors`` should work."""
    @as_subprocess
    def child_256():
        t = TestTerminal()
        eq_(t.number_of_colors, 256)
    child_256()

    @as_subprocess
    def child_8():
        t = TestTerminal(kind='ansi')
        eq_(t.number_of_colors, 8)
    child_8()

    @as_subprocess
    def child_0():
        t = TestTerminal(kind='vt220')
        eq_(t.number_of_colors, 0)
    child_0()


def test_formatting_functions():
    """Test crazy-ass formatting wrappers, both simple and compound."""
    @as_subprocess
    def child():
        t = TestTerminal()
        # By now, it should be safe to use sugared attributes. Other tests test
        # those.
        eq_(t.bold(u'hi'), t.bold + u'hi' + t.normal)
        eq_(t.green('hi'), t.green + u'hi' + t.normal)  # Plain strs for Python 2.x
        # Test some non-ASCII chars, probably not necessary:
        eq_(t.bold_green(u'boö'), t.bold + t.green + u'boö' + t.normal)
        eq_(t.bold_underline_green_on_red('boo'),
            t.bold + t.underline + t.green + t.on_red + u'boo' + t.normal)
        # Don't spell things like this:
        eq_(t.on_bright_red_bold_bright_green_underline('meh'),
            t.on_bright_red + t.bold + t.bright_green + t.underline + u'meh' +
                              t.normal)
    child()


def test_formatting_functions_without_tty():
    """Test crazy-ass formatting wrappers when there's no tty."""
    @as_subprocess
    def child():
        t = TestTerminal(stream=StringIO())
        eq_(t.bold(u'hi'), u'hi')
        eq_(t.green('hi'), u'hi')
        # Test non-ASCII chars, no longer really necessary:
        eq_(t.bold_green(u'boö'), u'boö')
        eq_(t.bold_underline_green_on_red('loo'), u'loo')
        eq_(t.on_bright_red_bold_bright_green_underline('meh'), u'meh')
    child()


def test_nice_formatting_errors():
    """Make sure you get nice hints if you misspell a formatting wrapper."""
    @as_subprocess
    def child():
        t = TestTerminal()
        try:
            t.bold_misspelled('hey')
            assert not t.is_a_tty or False, 'Should have thrown exception'
        except TypeError, e:
            assert 'probably misspelled' in e.args[0]
        try:
            t.bold_misspelled(u'hey')  # unicode
            assert not t.is_a_tty or False, 'Should have thrown exception'
        except TypeError, e:
            assert 'probably misspelled' in e.args[0]

        try:
            t.bold_misspelled(None)  # an arbitrary non-string
            assert not t.is_a_tty or False, 'Should have thrown exception'
        except TypeError, e:
            assert 'probably misspelled' not in e.args[0]

        try:
            t.bold_misspelled('a', 'b')  # >1 string arg
            assert not t.is_a_tty or False, 'Should have thrown exception'
        except TypeError, e:
            assert 'probably misspelled' not in e.args[0]
    child()


def test_init_descriptor_always_initted():
    """We should be able to get a height and width on no-tty Terminals."""
    @as_subprocess
    def child(kind='xterm-256color'):
        t = Terminal(kind=kind, stream=StringIO())
        eq_(type(t.height), int)
    child()
    child('screen')
    child('vt220')
    child('rxvt')
    child('cons25')
    child('linux')
    child('ansi')


def test_force_styling_none():
    """If ``force_styling=None`` is used, don't ever do styling."""
    @as_subprocess
    def child(kind='xterm-256color'):
        t = TestTerminal(kind=kind, force_styling=None)
        eq_(t.save, '')
        eq_(t.color(9), '')
        eq_(t.bold('oi'), 'oi')
    child()
    child('screen')
    child('vt220')
    child('rxvt')
    child('cons25')
    child('linux')
    child('ansi')


def test_SequenceWrapper():
    """ Test that text wrapping accounts for sequences correctly. """
    @as_subprocess
    def child(kind='xterm-256color', lines=25, cols=80):
        import textwrap
        import termios
        import struct
        import fcntl
        # set the pty's virtual window size
        TIOCSWINSZ = getattr(termios, 'TIOCSWINSZ', -2146929561)
        if TIOCSWINSZ == 2148037735:
            TIOCSWINSZ = -2146929561
        val = struct.pack('HHHH', lines, cols, 0, 0)
        fcntl.ioctl(sys.__stdout__.fileno(), TIOCSWINSZ, val)

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
        eq_(internal_wrapped, my_wrapped)

        # ensure our first and last line wraps at its ends
        first_l = internal_wrapped[0]
        last_l = internal_wrapped[-1]
        my_first_l = my_wrapped_colored[0]
        my_last_l = my_wrapped_colored[-1]
        eq_(len(first_l), t.length(my_first_l))
        eq_(len(last_l), t.length(my_last_l))
        eq_(len(internal_wrapped[-1]), t.length(my_wrapped_colored[-1]))

        # ensure our colored textwrap is the same line length
        eq_(len(internal_wrapped), len(my_wrapped_colored))
        # test subsequent_indent=
        internal_wrapped = textwrap.wrap(pgraph, t.width,
                                         break_long_words=False,
                                         subsequent_indent=' '*4)
        my_wrapped = t.wrap(pgraph, subsequent_indent=' '*4)
        my_wrapped_colored = t.wrap(pgraph_colored, subsequent_indent=' '*4)

        eq_(internal_wrapped, my_wrapped)
        eq_(len(internal_wrapped), len(my_wrapped_colored))
        eq_(len(internal_wrapped[-1]), t.length(my_wrapped_colored[-1]))
    child()
    child('screen', 5, 10)
    child('vt220', 20, 30)
    child('rxvt', 60, 90)
    child('cons25', 100, 120)
    child('linux', 15, 15)
    child('ansi', 20, 40)


def test_Sequence():
    """Tests methods related to Sequence class, namely ljust, rjust, center"""
    @as_subprocess
    def child(kind='xterm-256color'):
        t = TestTerminal(kind=kind)
        pony_msg = 'pony express, all aboard, choo, choo! '
        pony_len = len(pony_msg)
        pony_colored = u''.join(
            [t.color(n % 7) + ch for n, ch in enumerate(pony_msg)]
            ) + t.normal
        ladjusted = t.ljust(pony_colored)
        radjusted = t.rjust(pony_colored)
        centered = t.center(pony_colored)
        eq_(t.length(pony_colored), pony_len)
        eq_(t.length(centered), pony_len)
        eq_(t.length(centered), len(pony_msg.center(t.width)))
        eq_(t.length(ladjusted), pony_len)
        eq_(t.length(ladjusted), len(pony_msg.ljust(t.width)))
        eq_(t.length(radjusted), pony_len)
        eq_(t.length(radjusted), len(pony_msg.rjust(t.width)))


def test_null_callable_string():
    """Make sure NullCallableString tolerates all kinds of args."""
    @as_subprocess
    def child(kind='xterm-256color'):
        t = TestTerminal(stream=StringIO())
        eq_(t.clear, '')
        eq_(t.move(1, 2), '')
        eq_(t.move_x(1), '')
        eq_(t.bold(), '')
        eq_(t.bold('', 'x', 'huh?'), '')
        eq_(t.bold('', 9876), '')
        eq_(t.uhh(9876), '')
        eq_(t.clear('x'), 'x')
    child()
    child('screen')
    child('vt220')
    child('rxvt')
    child('cons25')
    child('linux')
    child('ansi')


def test_setupterm_singleton_issue33():
    """A warning is emitted if a new terminal ``kind`` is used per process."""
    @as_subprocess
    def child():
        import warnings
        warnings.filterwarnings("error", category=RuntimeWarning)

        # instantiate first terminal, of type xterm-256color
        term = TestTerminal(force_styling=True)

        try:
            # a second instantiation raises RuntimeWarning
            term = TestTerminal(kind="vt220", force_styling=True)
            assert not term.is_a_tty or False, 'Should have thrown exception'

        except RuntimeWarning, err:
            assert (err.args[0].startswith(
                    'A terminal of kind "vt220" has been requested')
                    ), err.args[0]
            assert ('a terminal of kind "xterm-256color" will '
                    'continue to be returned' in err.args[0]), err.args[0]
        finally:
            del warnings
    child()


def test_sequence_is_movement_false():
    """ Test parsers for about sequences that do not move the cursor. """
    @as_subprocess
    def child_mnemonics_wontmove(kind='xterm-256color'):
        from blessings.sequences import measure_length
        t = TestTerminal(kind=kind)
        eq_(0, measure_length(u'', t))
        # not even a mbs
        eq_(0, measure_length(u'xyzzy', t))
        # negative numbers, though printable as %d, do not result
        # in movement; just garbage. Also not a valid sequence.
        eq_(0, measure_length(t.cuf(-333), t))
        eq_(len(t.clear_eol), measure_length(t.clear_eol, t))
        # various erases don't *move*
        eq_(len(t.clear_bol), measure_length(t.clear_bol, t))
        eq_(len(t.clear_eos), measure_length(t.clear_eos, t))
        eq_(len(t.bold), measure_length(t.bold, t))
        # various paints don't move
        eq_(len(t.red), measure_length(t.red, t))
        eq_(len(t.civis), measure_length(t.civis, t))
        if t.cvvis:
            eq_(len(t.cvvis), measure_length(t.cvvis, t))
        eq_(len(t.underline), measure_length(t.underline, t))
        eq_(len(t.reverse), measure_length(t.reverse, t))
        for _num in range(t.number_of_colors):
            eq_(len(t.color(_num)), measure_length(t.color(_num), t))
        eq_(len(t.normal), measure_length(t.normal, t))
        eq_(len(t.normal_cursor), measure_length(t.normal_cursor, t))
        eq_(len(t.hide_cursor), measure_length(t.hide_cursor, t))
        eq_(len(t.save), measure_length(t.save, t))
        eq_(len(t.italic), measure_length(t.italic, t))
        eq_(len(t.standout), measure_length(t.standout, t))

    @as_subprocess
    def child_mnemonics_willmove(kind='xterm-256color'):
        from blessings.sequences import measure_length
        t = TestTerminal(kind=kind)
        # movements
        eq_(len(t.move(98, 76)), measure_length(t.move(98, 76), t))
        eq_(len(t.move(54)), measure_length(t.move(54), t))
        if t.cud1:
            eq_(len(t.cud1), measure_length(t.cud1, t))
        if t.cub1:
            eq_(len(t.cub1), measure_length(t.cub1, t))
        if t.cuf1:
            eq_(len(t.cuf1), measure_length(t.cuf1, t))
        if t.cuu1:
            eq_(len(t.cuu1), measure_length(t.cuu1, t))
        if t.cub:
            eq_(len(t.cub(333)), measure_length(t.cub(333), t))
        if t.cuf:
            eq_(len(t.cuf(333)), measure_length(t.cuf(333), t))
        if t.home:
            eq_(len(t.home), measure_length(t.home, t))
        if t.restore:
            eq_(len(t.restore), measure_length(t.restore, t))
        if t.clear:
            # clear moves, why? it contains HOME sequence!
            eq_(len(t.clear), measure_length(t.clear, t))

    child_mnemonics_wontmove()
    child_mnemonics_wontmove('screen')
    child_mnemonics_wontmove('vt220')
    child_mnemonics_wontmove('rxvt')
    child_mnemonics_wontmove('cons25')
    child_mnemonics_wontmove('linux')
    child_mnemonics_wontmove('ansi')
    child_mnemonics_willmove()
    child_mnemonics_willmove('screen')
    child_mnemonics_willmove('vt220')
    child_mnemonics_willmove('rxvt')
    child_mnemonics_willmove('cons25')
    child_mnemonics_willmove('linux')
    child_mnemonics_willmove('ansi')


def test_sequence_length():
    """ Ensure T.length(string containing sequence) is correct. """
    @as_subprocess
    def child(kind='xterm-256color'):
        from itertools import chain, cycle
        t = TestTerminal(kind=kind)
        # Create a list of ascii characters, to be seperated
        # by word, to be zipped up with a cycling list of
        # terminal sequences. Then, compare the length of
        # each, the basic plain_text.__len__ vs. the Terminal
        # method length. They should be equal.
        plain_text = ('The softest things of the world '
                      'Override the hardest things of the world '
                      'That which has no substance '
                      'Enters into that which has no openings')
        if t.bold:
            eq_(t.length(t.bold), 0)
            eq_(t.length(t.bold('x')), 1)
            eq_(t.length(t.bold_red), 0)
            eq_(t.length(t.bold_red('x')), 1)
        if t.underline:
            eq_(t.length(t.underline), 0)
            eq_(t.length(t.underline('x')), 1)
            eq_(t.length(t.underline_red), 0)
            eq_(t.length(t.underline_red('x')), 1)
        if t.reverse:
            eq_(t.length(t.reverse), 0)
            eq_(t.length(t.reverse('x')), 1)
            eq_(t.length(t.reverse_red), 0)
            eq_(t.length(t.reverse_red('x')), 1)
        if t.blink:
            eq_(t.length(t.blink), 0)
            eq_(t.length(t.blink('x')), 1)
            eq_(t.length(t.blink_red), 0)
            eq_(t.length(t.blink_red('x')), 1)
        if t.home:
            eq_(t.length(t.home), 0)
        if t.clear_eol:
            eq_(t.length(t.clear_eol), 0)
        if t.enter_fullscreen:
            eq_(t.length(t.enter_fullscreen), 0)
        if t.exit_fullscreen:
            eq_(t.length(t.exit_fullscreen), 0)

        # horizontally, we decide move_down and move_up are 0,
        eq_(t.length(t.move_down), 0)
        eq_(t.length(t.move_down(2)), 0)
        eq_(t.length(t.move_up), 0)
        eq_(t.length(t.move_up(2)), 0)
        # other things aren't so simple, somewhat edge cases,
        # moving backwards and forwards horizontally must be
        # accounted for as a "length", as <x><move right 10><y>
        # will result in a printed column length of 12 (even
        # though columns 2-11 are non-destructive space
        eq_(t.length('\b'), -1)
        eq_(t.length(t.move_left), -1)
        if t.cub:
            eq_(t.length(t.cub(10)), -10)
        eq_(t.length(t.move_right), 1)
        if t.cuf:
            eq_(t.length(t.cuf(10)), 10)

        # vertical spacing is unaccounted as a 'length'
        eq_(t.length(t.move_up), 0)
        eq_(t.length(t.cuu(10)), 0)
        eq_(t.length(t.move_down), 0)
        eq_(t.length(t.cud(10)), 0)
        # this is how manpages perform underlining, this is done
        # with the 'overstrike' capability of teletypes, and aparently
        # less(1), '123' -> '1\b_2\b_3\b_'
        text_wseqs = u''.join(chain(*zip(plain_text, cycle(['\b_']))))
        eq_(t.length(text_wseqs), len(plain_text))
    child()
    child('screen')
    child('vt220')
    child('rxvt')
    child('cons25')
    child('linux')
    child('ansi')


def test_inkey_0s_noinput():
    """ 0-second inkey without input; '' should be returned """
    @as_subprocess
    def child():
        term = TestTerminal()
        with term.key_at_a_time():
            stime = time.time()
            inp = term.keypress(timeout=0)
            eq_(inp, u'')
            eq_(math.floor(time.time() - stime), 0.0)
    child()


def test_inkey_1s_noinput():
    """ 1-second inkey without input; '' should be returned after ~1 second.
    """
    @as_subprocess
    def child():
        term = TestTerminal()
        with term.key_at_a_time():
            stime = time.time()
            inp = term.keypress(timeout=1)
            eq_(inp, u'')
            eq_(math.floor(time.time() - stime), 1.0)
    child()


def test_inkey_0s_input():
    """ 0-second inkey with input; keypress should be immediately returned."""
    pid, master_fd = pty.fork()
    if pid is 0:  # child
        term = TestTerminal()
        with term.key_at_a_time():
            inp = term.keypress(timeout=0)
            sys.stdout.write(inp)
        os._exit(0)
    exc_output = unicode()
    stime = time.time()
    os.write(master_fd, b'x')
    while True:
        try:
            _exc = os.read(master_fd, 65534)
        except OSError:  # linux EOF
            break
        if not _exc:  # bsd EOF
            break
        exc_output += _exc.decode('utf-8')
    pid, status = os.waitpid(pid, 0)
    eq_(os.WEXITSTATUS(status), 0)
    eq_(exc_output, u'x')
    eq_(math.floor(time.time() - stime), 0.0)


def test_inkey_0s_multibyte_utf8():
    """ 0-second inkey with multibte utf-8 input; should decode immediately."""
    pid, master_fd = pty.fork()
    if pid is 0:  # child
        term = TestTerminal()
        with term.key_at_a_time():
            inp = term.keypress(timeout=0)
            os.write(sys.__stdout__.fileno(), inp.encode('utf-8'))
            sys.stdout.flush()
        os._exit(0)

    attrs = termios.tcgetattr(master_fd)
    attrs[3] = attrs[3] & ~termios.ECHO
    termios.tcsetattr(master_fd, termios.TCSANOW, attrs)
    # LATIN CAPITAL LETTER UPSILON
    os.write(master_fd, u'\u01b1'.encode('utf-8'))
    attrs[3] = attrs[3] | termios.ECHO
    termios.tcsetattr(master_fd, termios.TCSANOW, attrs)

    stime = time.time()
    exc_output = unicode()
    decoder = codecs.getincrementaldecoder('utf8')()
    while True:
        try:
            _exc = os.read(master_fd, 65534)
        except OSError:  # linux EOF
            break
        if not _exc:  # bsd EOF
            break
        exc_output += decoder.decode(_exc, final=False)
    pid, status = os.waitpid(pid, 0)
    eq_(exc_output, u'Ʊ')
    eq_(os.WEXITSTATUS(status), 0)
    eq_(math.floor(time.time() - stime), 0.0)


def test_inkey_0s_sequence():
    """ 0-second inkey with multibte sequence; should decode immediately."""
    pid, master_fd = pty.fork()
    if pid is 0:  # child
        term = TestTerminal()
        with term.key_at_a_time():
            inp = term.keypress(timeout=0)
            os.write(sys.__stdout__.fileno(), ('%s' % (inp.name,)))
            sys.stdout.flush()
        os._exit(0)

    attrs = termios.tcgetattr(master_fd)
    attrs[3] = attrs[3] & ~termios.ECHO
    termios.tcsetattr(master_fd, termios.TCSANOW, attrs)
    os.write(master_fd, b'\x1b[D')
    attrs[3] = attrs[3] | termios.ECHO
    termios.tcsetattr(master_fd, termios.TCSANOW, attrs)

    stime = time.time()
    exc_output = unicode()
    while True:
        try:
            _exc = os.read(master_fd, 65534)
        except OSError:  # linux EOF
            break
        if not _exc:  # bsd EOF
            break
        exc_output += _exc.decode('utf-8')
    pid, status = os.waitpid(pid, 0)
    eq_(exc_output, u'KEY_LEFT')
    eq_(os.WEXITSTATUS(status), 0)
    eq_(math.floor(time.time() - stime), 0.0)


def test_inkey_1s_input():
    """ 1-second inkey with multibte sequence; should return after ~1 second."""
    pid, master_fd = pty.fork()
    if pid is 0:  # child
        term = TestTerminal()
        with term.key_at_a_time():
            inp = term.keypress(timeout=5)
            os.write(sys.__stdout__.fileno(), ('%s' % (inp.name,)))
            sys.stdout.flush()
        os._exit(0)

    stime = time.time()
    time.sleep(1)
    attrs = termios.tcgetattr(master_fd)
    attrs[3] = attrs[3] & ~termios.ECHO
    termios.tcsetattr(master_fd, termios.TCSANOW, attrs)
    os.write(master_fd, b'\x1b[C')
    attrs[3] = attrs[3] | termios.ECHO
    termios.tcsetattr(master_fd, termios.TCSANOW, attrs)

    exc_output = unicode()
    while True:
        try:
            _exc = os.read(master_fd, 65534)
        except OSError:  # linux EOF
            break
        if not _exc:  # bsd EOF
            break
        exc_output += _exc.decode('utf-8')
    pid, status = os.waitpid(pid, 0)
    eq_(exc_output, u'KEY_RIGHT')
    eq_(os.WEXITSTATUS(status), 0)
    eq_(math.floor(time.time() - stime), 1.0)


def test_esc_delay_035():
    """ esc_delay will cause a single ESC (\\x1b) to delay for 0.35. """
    pid, master_fd = pty.fork()
    if pid is 0:  # child
        term = TestTerminal()
        with term.key_at_a_time():
            stime = time.time()
            inp = term.keypress(timeout=5)
            os.write(sys.__stdout__.fileno(), ('%s,%i' % (
                inp.name, (time.time() - stime) * 100,)))
            sys.stdout.flush()
        os._exit(0)

    attrs = termios.tcgetattr(master_fd)
    attrs[3] = attrs[3] & ~termios.ECHO
    termios.tcsetattr(master_fd, termios.TCSANOW, attrs)
    os.write(master_fd, b'\x1b')
    attrs[3] = attrs[3] | termios.ECHO
    termios.tcsetattr(master_fd, termios.TCSANOW, attrs)

    exc_output = unicode()
    while True:
        try:
            _exc = os.read(master_fd, 65534)
        except OSError:  # linux EOF
            break
        if not _exc:  # bsd EOF
            break
        exc_output += _exc.decode('utf-8')
    pid, status = os.waitpid(pid, 0)
    key_name, duration = exc_output.split(',')
    eq_(key_name, u'KEY_EXIT')
    eq_(os.WEXITSTATUS(status), 0)
    assert 35 <= int(duration) <= 45


def test_esc_delay_135():
    """ esc_delay=1.35 will cause a single ESC (\\x1b) to delay for 1.35. """
    pid, master_fd = pty.fork()
    if pid is 0:  # child
        term = TestTerminal()
        with term.key_at_a_time():
            stime = time.time()
            inp = term.keypress(timeout=5, esc_delay=1.35)
            os.write(sys.__stdout__.fileno(), ('%s,%i' % (
                inp.name, (time.time() - stime) * 100,)))
            sys.stdout.flush()
        os._exit(0)

    attrs = termios.tcgetattr(master_fd)
    attrs[3] = attrs[3] & ~termios.ECHO
    termios.tcsetattr(master_fd, termios.TCSANOW, attrs)
    os.write(master_fd, b'\x1b')
    attrs[3] = attrs[3] | termios.ECHO
    termios.tcsetattr(master_fd, termios.TCSANOW, attrs)

    exc_output = unicode()
    while True:
        try:
            _exc = os.read(master_fd, 65534)
        except OSError:  # linux EOF
            break
        if not _exc:  # bsd EOF
            break
        exc_output += _exc.decode('utf-8')
    pid, status = os.waitpid(pid, 0)
    key_name, duration = exc_output.split(',')
    eq_(key_name, u'KEY_EXIT')
    eq_(os.WEXITSTATUS(status), 0)
    assert 135 <= int(duration) <= 145, int(duration)
