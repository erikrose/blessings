# -*- coding: utf-8 -*-
"""Automated tests (as opposed to human-verified test patterns)

It was tempting to mock out curses to get predictable output from ``tigetstr``,
but there are concrete integration-testing benefits in not doing so. For
instance, ``tigetstr`` changed its return type in Python 3.2.3. So instead, we
simply create all our test ``Terminal`` instances with a known terminal type.
All we require from the host machine is that a standard terminfo definition of
xterm-256color, ansi, and vt220 exists.

"""
from __future__ import with_statement  # Make 2.5-compatible
from curses import tigetstr, tparm
from functools import partial
from StringIO import StringIO
import sys
import os
import pty
import traceback
import struct
import termios
from fcntl import ioctl

from nose.tools import eq_, raises

# This tests that __all__ is correct, since we use below everything that should
# be imported:
from blessings import *

TestTerminal = partial(Terminal, kind='xterm-256color')


class as_subprocess:
    """ This helper executes test cases in a child process,
        avoiding a Terminal illness: cannot call setupterm()
        more than once per process (issue #33).
    """
    def __init__(self, func):
        self.func = func

    def __call__(self, *args, **kwargs):
        pid, master_fd = pty.fork()
        if pid == 0:
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
                    o_err.append (line.rstrip().encode('utf-8'))
                o_err.append (('-=' * 20).encode('ascii'))
                o_err.extend ([_exc.rstrip().encode('utf-8')
                    for _exc in traceback.format_exception_only(e_type, e_value)])
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
    return tigetstr(cap).decode('utf-8')


def unicode_parm(cap, *parms):
    """Return the result of ``tparm(tigetstr())`` except as Unicode."""
    return tparm(tigetstr(cap), *parms).decode('utf-8')


def test_capability():
    """Check that a capability lookup works.

    Also test that Terminal grabs a reasonable default stream. This test
    assumes it will be run from a tty.

    """
    @as_subprocess
    def child():
        t = TestTerminal()
        sc = unicode_cap('sc')
        eq_(t.save, sc)
        eq_(t.save, sc)  # Make sure caching doesn't screw it up.
    child()


def test_capability_without_tty():
    """Assert capability templates are '' when stream is not a tty."""
    @as_subprocess
    def child():
        t = TestTerminal(stream=StringIO(), force_styling=None)
        eq_(t.save, u'')
        eq_(t.red, u'')
        eq_(t.stream.getvalue(), '')
    child()


def test_capability_with_forced_tty():
    """If we force styling, capabilities had better not be empty."""
    @as_subprocess
    def child():
        t = TestTerminal(stream=StringIO(), force_styling=True)
        eq_(t.save, unicode_cap('sc'))
        eq_(t.stream.getvalue(), '')
    child()


def test_parametrization():
    """Test parametrizing a capability."""
    @as_subprocess
    def child():
        eq_(TestTerminal().cup(3, 4), unicode_parm('cup', 3, 4))
    child()


def test_height_and_width_as_int():
    """Assert that ``height_and_width()`` returns ints."""
    @as_subprocess
    def child():
        t = TestTerminal()  # kind shouldn't matter.
        assert isinstance(t.height, int)
        assert isinstance(t.width, int)
    child()


def test_height_and_width_ioctl():
    """ Create a virtual pty, and set and test a window size of 3, 2. """
    @as_subprocess
    def child():
        lines, cols = 3, 2
        # set our window size, see noahspurrier/pexpect about
        # the various platforms that return the wrong value
        # of TIOCSWINSZ, aparently it is large enough to roll
        # over the signed bit on some platforms:
        TIOCSWINSZ = getattr(termios, 'TIOCSWINSZ', -2146929561)
        if TIOCSWINSZ == 2148037735:
            # Same bits, but with sign.
            TIOCSWINSZ = -2146929561

        # set the pty's virtual window size
        val = struct.pack('HHHH', lines, cols, 0, 0)
        ioctl(sys.__stdout__.fileno(), TIOCSWINSZ, val)

        # test new virtual window size
        eq_(Terminal()._height_and_width(), (lines, cols))
        eq_(Terminal().height, lines)
        eq_(Terminal().width, cols)
    child()


def test_stream_attr():
    """Make sure Terminal exposes a ``stream`` attribute that defaults to
    something sane."""
    @as_subprocess
    def child():
        eq_(Terminal().stream, sys.__stdout__)
    child()


def test_location():
    """Make sure ``location()`` does what it claims."""
    @as_subprocess
    def child_with_styling():
        """Check side effect of location as a context manager with styling."""
        t = TestTerminal(stream=StringIO(), force_styling=True)

        with t.location(3, 4):
            t.stream.write(u'hi')

        eq_(t.stream.getvalue(),
            unicode_cap('sc') + unicode_parm('cup', 4, 3)
            + u'hi' + unicode_cap('rc'))

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
        eq_(t.stream.getvalue(),
            unicode_cap('sc') + unicode_parm('hpa', 5)
            + unicode_cap('rc'))
    child()


def test_null_location():
    """Make sure ``location()`` with no args just does position restoration."""
    @as_subprocess
    def child_with_styling():
        t = TestTerminal(stream=StringIO(), force_styling=True)
        with t.location():
            pass
        eq_(t.stream.getvalue(),
            unicode_cap('sc') + unicode_cap('rc'))

    def child_without_styling():
        t = TestTerminal(stream=StringIO(), force_styling=None)
        with t.location():
            pass
        eq_(t.stream.getvalue(), u'')

    child_with_styling()
    child_without_styling()


def test_zero_location():
    """Make sure ``location()`` pays attention to 0-valued args."""
    @as_subprocess
    def child():
        t = TestTerminal(stream=StringIO(), force_styling=True)
        with t.location(0, 0):
            pass
        eq_(t.stream.getvalue(),
            unicode_cap('sc') + unicode_parm('cup', 0, 0) +
            unicode_cap('rc'))
    child()


def test_null_fileno():
    """Make sure ``Terminal`` works when ``fileno`` is ``None``.
    """
    # This simulates piping output to a programs such as tee(1) or less(1)
    @as_subprocess
    def child():
        out = StringIO()
        out.fileno = None
        t = TestTerminal(stream=out)
        eq_(t.save, u'')
    child()


def test_mnemonic_colors():
    """Make sure color shortcuts work."""
    @as_subprocess
    def child():
        def color(num):
            return unicode_parm('setaf', num)

        def on_color(num):
            return unicode_parm('setab', num)

        # Avoid testing red, blue, yellow, and cyan, since they might someday
        # change depending on terminal type.
        t = TestTerminal()
        eq_(t.white, color(7))
        eq_(t.green, color(2))  # Make sure it's different than white.
        eq_(t.on_black, on_color(0))
        eq_(t.on_green, on_color(2))
        eq_(t.bright_black, color(8))
        eq_(t.bright_green, color(10))
        eq_(t.on_bright_black, on_color(8))
        eq_(t.on_bright_green, on_color(10))
    child()


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
        t = TestTerminal(stream=StringIO(), force_styling=None)
        eq_(t.color(5)('smoo'), 'smoo')
        eq_(t.on_color(6)('smoo'), 'smoo')
        eq_(t.stream.getvalue(), '')
    child()


def test_callable_mixed_typeError():
    """ strings are illegal as formatting parameters """
    @as_subprocess
    @raises(TypeError)  # 'an integer is required'
    def child_move_mixed():
        t = TestTerminal()
        t.move(1, '1')

    @as_subprocess
    @raises(TypeError)  # 'an integer is required'
    def child_move_2strs():
        t = TestTerminal()
        t.move('1', '1')

    @as_subprocess
    @raises(TypeError)  # 'an integer is required'
    def child_color_2strs():
        t = TestTerminal()
        t.color('1', '1')

    @as_subprocess
    @raises(DeprecationWarning, TypeError)
    def child_move_float():
        import warnings
        warnings.filterwarnings("error", category=DeprecationWarning)
        term = TestTerminal(force_styling=True)
        term.move(1.0, 1.0)

    child_move_mixed()
    child_move_2strs()
    child_color_2strs()
    child_move_float()


def test_naked_color_cap():
    """``term.color`` should return a stringlike capability."""
    @as_subprocess
    def child():
        t = TestTerminal()
        eq_(t.color + '', t.setaf + '')
    child()


def test_num_colors_no_tty_or_styling():
    """``number_of_colors`` should return 0 when there's no tty."""
    @as_subprocess
    def child_256():
        t = TestTerminal(stream=StringIO())
        eq_(t.number_of_colors, 0)

    @as_subprocess
    def child_8():
        t = TestTerminal(kind='ansi', stream=StringIO())
        eq_(t.number_of_colors, 0)

    @as_subprocess
    def child_0():
        t = TestTerminal(kind='vt220', stream=StringIO())
        eq_(t.number_of_colors, 0)
    child_256()
    child_8()
    child_0()


def test_num_colors_no_tty_force_styling():
    """``number_of_colors`` may return 256 when force_styling is True."""
    @as_subprocess
    def child_256():
        t = TestTerminal(stream=StringIO(), force_styling=True)
        eq_(t.number_of_colors, 256)

    @as_subprocess
    def child_8():
        t = TestTerminal(kind='ansi', stream=StringIO(), force_styling=True)
        eq_(t.number_of_colors, 8)

    @as_subprocess
    def child_0():
        t = TestTerminal(kind='vt220', stream=StringIO(), force_styling=True)
        eq_(t.number_of_colors, 0)
    child_256()
    child_8()
    child_0()


def test_number_of_colors_with_tty():
    """``number_of_colors`` should work."""
    @as_subprocess
    def child_256():
        t = TestTerminal()
        eq_(t.number_of_colors, 256)

    @as_subprocess
    def child_8():
        t = TestTerminal(kind='ansi')
        eq_(t.number_of_colors, 8)

    @as_subprocess
    def child_0():
        t = TestTerminal(kind='vt220')
        eq_(t.number_of_colors, 0)
    child_256()
    child_8()
    child_0()


def test_formatting_functions():
    """Test crazy-ass formatting wrappers, both simple and compound."""
    @as_subprocess
    def child():
        t = TestTerminal()
        # By now, it should be safe to use sugared attributes. Other tests test
        # those.
        eq_(t.bold(u'hi'), t.bold + u'hi' + t.normal)
        # Plain strs for Python 2.x
        eq_(t.green('hi'), t.green + u'hi' + t.normal)
        # Test some non-ASCII chars, probably not necessary:
        eq_(t.bold_green(u'boö'), t.bold + t.green + u'boö' + t.normal)
        eq_(t.bold_underline_green_on_red('boo'),
            t.bold + t.underline + t.green + t.on_red + u'boo' + t.normal)
        # Don't spell things like this:
        eq_(t.on_bright_red_bold_bright_green_underline('meh'),
            t.on_bright_red + t.bold + t.bright_green + t.underline
            + u'meh' + t.normal)
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
        eq_(t.stream.getvalue(), '')
    child()


def test_nice_formatting_errors():
    """Make sure you get nice hints if you misspell a formatting wrapper."""
    @as_subprocess
    def child():
        t = TestTerminal()
        try:
            t.bold_misspelled('hey')
            assert not t.is_a_tty or False, 'Should have thrown exception'
            # (unless the test was run without a tty, in which, not throwing
            # an exception is acceptable (see next test case.)
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


def test_nice_formatting_errors_notty():
    """does_styling=False does not hint of formatting misspellings."""
    @as_subprocess
    def child():
        t = TestTerminal(stream=StringIO(), force_styling=None)
        t.bold_misspelled('hey')
        t.bold_misspelled(u'hey')  # unicode
        t.bold_misspelled(None)  # an arbitrary non-string
        t.bold_misspelled('a', 'b')  # >1 string arg
        eq_(t.stream.getvalue(), '')
    child()


def test_init_descriptor_always_initted():
    """We should be able to get a height and width even on no-tty Terminals."""
    @as_subprocess
    def child():
        t = TestTerminal(stream=StringIO())
        eq_(type(t.height), int)
        eq_(t.stream.getvalue(), '')
    child()


def test_force_styling_none():
    """If ``force_styling=None`` is used, don't perform capabilities."""
    @as_subprocess
    def child():
        t = TestTerminal(force_styling=None)
        eq_(t.save, '')
        eq_(t.color(9), '')
        eq_(t.bold('oi'), 'oi')
    child()


def test_null_callable_string():
    """Make sure NullCallableString tolerates all numbers and kinds of args it
    might receive."""
    @as_subprocess
    def child():
        t = TestTerminal(stream=StringIO(), force_styling=None)
        eq_(t.clear, '')
        eq_(t.bold(), '')
        eq_(t.bold('', 'x', 'huh?'), '')
        eq_(t.bold('', 9876), '')
        eq_(t.uhh(9876), '')
        eq_(t.clear('x'), 'x')
        eq_(t.move(1, 2), '')
        eq_(t.move(1, 2), '')
        eq_(t.move_x(1), '')
        eq_(t.stream.getvalue(), '')
    child()


def test_sequence_is_movement_true():
    """ Test parsers for sequences that result in cursor movement. """
    @as_subprocess
    def child(kind='xterm-256color'):
        t = TestTerminal(kind=kind)
        from blessings.sequences import (_unprintable_length,
                                         _sequence_is_movement)
        # reset terminal causes term.clear to happen
        eq_(_sequence_is_movement(u'\x1bc', t), True)
        eq_(len(u'\x1bc'), _unprintable_length(u'\x1bc', t))
        # dec alignment tube test, could go either way
        eq_(_sequence_is_movement(u'\x1b#8', t), True)
        eq_(len(u'\x1b#8'), _unprintable_length(u'\x1b#8', t))
        # various movements
        eq_(_sequence_is_movement(t.move(98, 76), t), True)
        eq_(len(t.move(98, 76)), _unprintable_length(t.move(98, 76), t))
        eq_(_sequence_is_movement(t.move(54), t), True)
        eq_(len(t.move(54)), _unprintable_length(t.move(54), t))
        eq_(_sequence_is_movement(t.cud1, t), True)
        eq_(len(t.cud1), _unprintable_length(t.cud1, t))
        eq_(_sequence_is_movement(t.cub1, t), True)
        eq_(len(t.cub1), _unprintable_length(t.cub1, t))
        eq_(_sequence_is_movement(t.cuf1, t), True)
        eq_(len(t.cuf1), _unprintable_length(t.cuf1, t))
        eq_(_sequence_is_movement(t.cuu1, t), True)
        eq_(len(t.cuu1), _unprintable_length(t.cuu1, t))
        eq_(_sequence_is_movement(t.cub(333), t), True)
        eq_(len(t.cub(333)), _unprintable_length(t.cub(333), t))
        eq_(_sequence_is_movement(t.home, t), True)
        eq_(len(t.home), _unprintable_length(t.home, t))
        eq_(_sequence_is_movement(t.restore, t), True)
        eq_(len(t.restore), _unprintable_length(t.restore, t))
        eq_(len(t.clear), sum([
            _unprintable_length('\x1b%s' % (seq,), t)
            for seq in t.clear.split('\x1b')]))
        eq_(any([
            _sequence_is_movement('\x1b%s' % (seq,), t)
            for seq in t.clear.split('\x1b')]), True)
    child()
    child('screen')
    child('vt220')
    child('rxvt')


def test_SequenceWrapper():
    """ Test that text wrapping accounts for sequences correctly. """
    @as_subprocess
    def child(kind='xterm-256color'):
        import textwrap
        # set the pty's virtual window size
        lines, cols = 5, 15
        TIOCSWINSZ = getattr(termios, 'TIOCSWINSZ', -2146929561)
        if TIOCSWINSZ == 2148037735:
            TIOCSWINSZ = -2146929561
        val = struct.pack('HHHH', lines, cols, 0, 0)
        ioctl(sys.__stdout__.fileno(), TIOCSWINSZ, val)

        # build a test paragraph, along with a very colorful version
        t = TestTerminal(kind=kind)
        pgraph = 'pony express, all aboard, choo, choo! ' + (
            ('whugga ' * 10) + ('choo, choo! ')) * 30
        pgraph_colored = u''.join([
            t.color(n % 7) + t.bold + ch
            for n, ch in enumerate(pgraph)])

        internal_wrapped = textwrap.wrap(pgraph, t.width,
                                         break_long_words=False)
        my_wrapped = t.wrap(pgraph)
        my_wrapped_colored = t.wrap(pgraph_colored)

        # ensure we textwrap ascii the same as python
        eq_(internal_wrapped, my_wrapped)

        # ensure our colored textwrap is the same line length
        eq_(len(internal_wrapped), len(t.wrap(pgraph_colored)))

        # ensure our last line ends at the same column
        eq_(len(internal_wrapped[-1]), t.length(my_wrapped_colored[-1]))

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
    child('screen')
    child('vt220')
    child('rxvt')


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
        eq_(t.length(centered.strip()), pony_len)
        eq_(t.length(centered), len(pony_msg.center(t.width)))
        eq_(t.length(ladjusted.rstrip()), pony_len)
        eq_(t.length(ladjusted), len(pony_msg.ljust(t.width)))
        eq_(t.length(radjusted.lstrip()), pony_len)
        eq_(t.length(radjusted), len(pony_msg.rjust(t.width)))
    child()
    child('screen')
    child('vt220')
    child('rxvt')


def test_setupterm_singleton_issue33():
    """A warning is emitted if a new terminal ``kind`` is used per process."""
    @as_subprocess
    def child():
        import warnings
        warnings.filterwarnings("error", category=RuntimeWarning)
        term = TestTerminal(force_styling=True)
        try:
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
    def child_mnemonics(kind='xterm-256color'):
        from blessings.sequences import (_unprintable_length,
                                         _sequence_is_movement)
        t = TestTerminal(kind=kind)
        eq_(_sequence_is_movement(u'', t), False)
        eq_(0, _unprintable_length(u'', t))
        # not even a mbs
        eq_(_sequence_is_movement(u'xyzzy', t), False)
        eq_(0, _unprintable_length(u'xyzzy', t))
        # a single escape is not movement
        eq_(_sequence_is_movement(u'\x1b', t), False)
        eq_(0, _unprintable_length(u'\x1b', t))
        # negative numbers, though printable as %d, do not result
        # in movement; just garbage. Also not a valid sequence.
        eq_(_sequence_is_movement(t.cuf(-333), t), False)
        eq_(0, _unprintable_length(t.cuf(-333), t))
        eq_(_sequence_is_movement(t.clear_eol, t), False)
        eq_(len(t.clear_eol), _unprintable_length(t.clear_eol, t))
        # various erases don't *move*
        eq_(_sequence_is_movement(t.clear_bol, t), False)
        eq_(len(t.clear_bol), _unprintable_length(t.clear_bol, t))
        eq_(_sequence_is_movement(t.clear_eos, t), False)
        eq_(len(t.clear_eos), _unprintable_length(t.clear_eos, t))
        eq_(_sequence_is_movement(t.bold, t), False)
        eq_(len(t.bold), _unprintable_length(t.bold, t))
        # various paints don't move
        eq_(_sequence_is_movement(t.red, t), False)
        eq_(len(t.red), _unprintable_length(t.red, t))
        eq_(_sequence_is_movement(t.civis, t), False)
        eq_(len(t.civis), _unprintable_length(t.civis, t))
        eq_(_sequence_is_movement(t.cnorm, t), False)
        eq_(_sequence_is_movement(t.cvvis, t), False)
        eq_(len(t.cvvis), _unprintable_length(t.cvvis, t))
        eq_(_sequence_is_movement(t.underline, t), False)
        eq_(len(t.underline), _unprintable_length(t.underline, t))
        eq_(_sequence_is_movement(t.reverse, t), False)
        eq_(len(t.reverse), _unprintable_length(t.reverse, t))
        for _num in range(t.number_of_colors):
            eq_(_sequence_is_movement(t.color(_num), t), False)
            eq_(len(t.color(_num)), _unprintable_length(t.color(_num), t))
        eq_(_sequence_is_movement(t.normal, t), False)
        eq_(len(t.normal), sum([
            _unprintable_length('\x1b%s' % (seq,), t)
            for seq in t.normal.split('\x1b')]))
        eq_(any([
            _sequence_is_movement('\x1b%s' % (seq,), t)
            for seq in t.normal_cursor.split('\x1b')]), False)
        eq_(len(t.normal_cursor), sum([
            _unprintable_length('\x1b%s' % (seq,), t)
            for seq in t.normal_cursor.split('\x1b')]))
        eq_(any([
            _sequence_is_movement('\x1b%s' % (seq,), t)
            for seq in t.normal_cursor.split('\x1b')]), False)
        eq_(_sequence_is_movement(t.hide_cursor, t), False)
        eq_(len(t.hide_cursor), _unprintable_length(t.hide_cursor, t))
        eq_(_sequence_is_movement(t.save, t), False)
        eq_(len(t.save), _unprintable_length(t.save, t))
        eq_(_sequence_is_movement(t.italic, t), False)
        eq_(len(t.italic), _unprintable_length(t.italic, t))
        eq_(_sequence_is_movement(t.standout, t), False)
        eq_(len(t.standout), _unprintable_length(t.standout, t))

    @as_subprocess
    def child_rawcodes():
        from blessings.sequences import (_unprintable_length,
                                         _sequence_is_movement)
        # some raw code variations of multi-valued sequences
        # vanilla
        t = TestTerminal()
        eq_(len(u'\x1b[0m'), _unprintable_length(u'\x1b[0m', t))
        eq_(_sequence_is_movement(u'\x1b[0m', t), False)
        # bold
        eq_(len(u'\x1b[0;1m'), _unprintable_length(u'\x1b[0;1m', t))
        eq_(_sequence_is_movement(u'\x1b[0;1m', t), False)
        # bold
        eq_(len(u'\x1b[;1m'), _unprintable_length(u'\x1b[;1m', t))
        eq_(_sequence_is_movement(u'\x1b[;1m', t), False)
        # underline
        eq_(len(u'\x1b[;4m'), _unprintable_length(u'\x1b[;4m', t))
        eq_(_sequence_is_movement(u'\x1b[;4m', t), False)
        # blink
        eq_(len(u'\x1b[0;5m'), _unprintable_length(u'\x1b[0;5m', t))
        eq_(_sequence_is_movement(u'\x1b[0;5m', t), False)
        # bold blink
        eq_(len(u'\x1b[0;5;1m'), _unprintable_length(u'\x1b[0;5;1m', t))
        eq_(_sequence_is_movement(u'\x1b[0;5;1m', t), False)
        # underline blink
        eq_(len(u'\x1b[0;4;5m'), _unprintable_length(u'\x1b[0;4;5m', t))
        eq_(_sequence_is_movement(u'\x1b[0;4;5m', t), False)
        # bold underline blink
        eq_(len(u'\x1b[0;1;4;5m'), _unprintable_length(u'\x1b[0;1;4;5m', t))
        eq_(_sequence_is_movement(u'\x1b[0;1;4;5m', t), False)
        # negative
        eq_(len(u'\x1b[1;4;5;0;7m'),
            _unprintable_length(u'\x1b[1;4;5;0;7m', t))
        eq_(_sequence_is_movement(u'\x1b[1;4;5;0;7m', t), False)
        # bold negative
        eq_(len(u'\x1b[0;1;7m'), _unprintable_length(u'\x1b[0;1;7m', t))
        eq_(_sequence_is_movement(u'\x1b[0;1;7m', t), False)
        # underline negative
        eq_(len(u'\x1b[0;4;7m'), _unprintable_length(u'\x1b[0;4;7m', t))
        eq_(_sequence_is_movement(u'\x1b[0;4;7m', t), False)
        # bold underline negative
        eq_(len(u'\x1b[0;1;4;7m'), _unprintable_length(u'\x1b[0;1;4;7m', t))
        eq_(_sequence_is_movement(u'\x1b[0;1;4;7m', t), False)
        # blink negative
        eq_(len(u'\x1b[1;4;;5;7m'), _unprintable_length(u'\x1b[1;4;;5;7m', t))
        eq_(_sequence_is_movement(u'\x1b[1;4;;5;7m', t), False)
        # bold blink negative
        eq_(len(u'\x1b[0;1;5;7m'), _unprintable_length(u'\x1b[0;1;5;7m', t))
        eq_(_sequence_is_movement(u'\x1b[0;1;5;7m', t), False)
        # underline blink negative
        eq_(len(u'\x1b[0;4;5;7m'), _unprintable_length(u'\x1b[0;4;5;7m', t))
        eq_(_sequence_is_movement(u'\x1b[0;4;5;7m', t), False)
        # bold underline blink negative
        eq_(len(u'\x1b[0;1;4;5;7m'),
            _unprintable_length(u'\x1b[0;1;4;5;7m', t))
        eq_(_sequence_is_movement(u'\x1b[0;1;4;5;7m', t), False)
        # sgr reset
        eq_(_sequence_is_movement(u'\x1b[m', t), False)
        eq_(len(u'\x1b[m'), _unprintable_length(u'\x1b[m', t))
        # save cursor (sc)
        eq_(_sequence_is_movement(u'\x1b[s', t), False)
        eq_(len(u'\x1b[s'), _unprintable_length(u'\x1b[s', t))
        # restore cursor (rc)
        eq_(_sequence_is_movement(u'\x1b[s', t), False)
        eq_(len(u'\x1b[s'), _unprintable_length(u'\x1b[s', t))
        # fake sgr
        eq_(_sequence_is_movement(u'\x1b[01;02m', t), False)
        eq_(len(u'\x1b[01;02m'), _unprintable_length(u'\x1b[01;02m', t))
        # shift code page
        eq_(_sequence_is_movement(u'\x1b(0'), False, t)
        eq_(len(u'\x1b(0'), _unprintable_length(u'\x1b(0'), t)
        # t.cnorm actually returns two sequences on xterm-256color
        for subseq in t.cnorm.split('\x1b')[1:]:
            eq_(len('\x1b' + subseq), _unprintable_length('\x1b' + subseq, t))

    child_mnemonics()
    child_mnemonics('screen')
    child_mnemonics('vt220')
    child_mnemonics('rxvt')
    child_rawcodes()


def test_string_containing_unprintable_length():
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
        seqs = (t.bold, t.underline, t.bold_underline, t.bold_red,
                t.reverse_red, t.blink_red, t.home, t.clear_eol,
                t.enter_fullscreen, t.exit_fullscreen,)
        text_wseqs = u''.join(chain(*zip(plain_text, cycle(seqs))))
        eq_(t.length(text_wseqs), len(plain_text))
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
        eq_(t.length(t.cub(10)), -10)
        eq_(t.length(t.move_right), 1)
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
