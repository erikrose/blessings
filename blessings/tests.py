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
import codecs

from nose.tools import eq_

# This tests that __all__ is correct, since we use below everything that should
# be imported:
from blessings import *


TestTerminal = partial(Terminal, kind='xterm-256color')


class as_subprocess(object):
    """ This helper executes test cases in a child process,
        avoiding a python-internal bug of _curses: setupterm()
        may not be called more than once per process.
    """
    _CHILD_PID = 0
    encoding = 'utf8'

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
                    o_err.append(line.rstrip().encode(self.encoding))
                o_err.append(('-=' * 20).encode(self.encoding))
                o_err.extend([_exc.rstrip().encode(self.encoding) for _exc in
                              traceback.format_exception_only(
                                  e_type, e_value)])
                os.write(sys.__stdout__.fileno(), '\n'.join(o_err))
                os._exit(1)
            else:
                os._exit(0)

        exc_output = unicode()
        decoder = codecs.getincrementaldecoder(self.encoding)()
        while True:
            try:
                _exc = os.read(master_fd, 65534)
            except OSError:
                # linux EOF
                break
            if not _exc:
                # bsd EOF
                break
            exc_output += decoder.decode(_exc)

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
            assert not t.is_a_tty, 'Should have thrown exception'
        except TypeError, e:
            assert 'probably misspelled' in e.args[0]
        try:
            t.bold_misspelled(u'hey')  # unicode
            assert not t.is_a_tty, 'Should have thrown exception'
        except TypeError, e:
            assert 'probably misspelled' in e.args[0]

        try:
            t.bold_misspelled(None)  # an arbitrary non-string
            assert not t.is_a_tty, 'Should have thrown exception'
        except TypeError, e:
            assert 'probably misspelled' not in e.args[0]

        try:
            t.bold_misspelled('a', 'b')  # >1 string arg
            assert not t.is_a_tty, 'Should have thrown exception'
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

