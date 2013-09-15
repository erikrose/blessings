# -*- coding: utf-8 -*-
"""Automated tests (as opposed to human-verified test patterns)

It was tempting to mock out curses to get predictable output from ``tigetstr``,
but there are concrete integration-testing benefits in not doing so. For
instance, ``tigetstr`` changed its return type in Python 3.2.3. So instead, we
simply create all our test ``Terminal`` instances with a known terminal type.
All we require from the host machine is that a standard terminfo definition of
xterm-256color, dtterm, and vt220 exists, for testing 256, 8, and 0-color
terminals, respectively.

"""
from __future__ import with_statement  # Make 2.5-compatible
from curses import tigetstr, tparm
from functools import partial
from StringIO import StringIO
import os
import sys
import warnings

from nose import SkipTest
from nose.tools import eq_

# This tests that __all__ is correct, since we use below everything that should
# be imported:
from blessings import *

TestTerminal = partial(Terminal, kind='xterm-256color')

warnings.filterwarnings("error", category=RuntimeWarning)

class forkit:
    """ This helper executes test cases in a child process,
        avoiding a Terminal illness: cannot call setupterm()
        more than once per process (issue #33).
    """
    def __init__(self, func):
        self.func = func

    def __call__(self):
        pid = os.fork()
        if pid == 0:
            # child process executes function, raises exception
            # if failed, causing a non-zero exit code
            self.func()
            os._exit(0)

        # parent process asserts exit code is 0, causing test
        # to fail if child process raised an exception/assertion
        pid, status = os.waitpid(pid, 0)
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
    @forkit
    def doit():
        t = TestTerminal(force_styling=True)
        sc = unicode_cap('sc')
        eq_(t.save, sc)
        eq_(t.save, sc)  # Make sure caching doesn't screw it up.
    doit()


def test_capability_without_tty():
    """Assert capability templates are '' when stream is not a tty."""
    @forkit
    def doit():
        t = TestTerminal(stream=StringIO())
        eq_(t.save, u'')
        eq_(t.red, u'')
    doit()


def test_capability_with_forced_tty():
    """If we force styling, capabilities had better not (generally) be
    empty."""
    @forkit
    def doit():
        t = TestTerminal(stream=StringIO(), force_styling=True)
        eq_(t.save, unicode_cap('sc'))
    doit()


def test_parametrization():
    """Test parametrizing a capability."""
    @forkit
    def doit():
        t = TestTerminal(force_styling=True)
        cup34 = unicode_parm('cup', 3, 4)
        eq_(t.cup(3, 4), cup34)
    doit()


def test_height_and_width():
    """Assert that ``height_and_width()`` returns ints."""
    @forkit
    def doit():
        t = TestTerminal()  # kind shouldn't matter.
        eq_(int, type(t.height))
        eq_(int, type(t.width))
    doit()


def test_stream_attr():
    """Make sure Terminal exposes a ``stream`` attribute."""
    @forkit
    def doit():
        eq_(TestTerminal().stream, sys.__stdout__)
    doit()


def test_location():
    """Make sure ``location()`` does what it claims."""
    @forkit
    def doit():
        t = TestTerminal(stream=StringIO(), force_styling=True)

        with t.location(3, 4):
            t.stream.write(u'hi')

        eq_(t.stream.getvalue(), unicode_cap('sc') +
                                 unicode_parm('cup', 4, 3) +
                                 u'hi' +
                                 unicode_cap('rc'))
    doit()


def test_horizontal_location():
    """Make sure we can move the cursor horizontally without changing rows."""
    @forkit
    def doit():
        t = TestTerminal(stream=StringIO(), force_styling=True)
        with t.location(x=5):
            pass
        eq_(t.stream.getvalue(), unicode_cap('sc') +
                                 unicode_parm('hpa', 5) +
                                 unicode_cap('rc'))
    doit()


def test_null_location():
    """Make sure ``location()`` with no args just does position restoration."""
    @forkit
    def doit():
        t = TestTerminal(stream=StringIO(), force_styling=True)
        with t.location():
            pass
        eq_(t.stream.getvalue(), unicode_cap('sc') +
                                 unicode_cap('rc'))
    doit()


def test_zero_location():
    """Make sure ``location()`` pays attention to 0-valued args."""
    @forkit
    def doit():
        t = TestTerminal(stream=StringIO(), force_styling=True)
        with t.location(0, 0):
            pass
        eq_(t.stream.getvalue(), unicode_cap('sc') +
                                 unicode_parm('cup', 0, 0) +
                                 unicode_cap('rc'))
    doit()


def test_null_fileno():
    """Make sure ``Terminal`` works when ``fileno`` is ``None``."""
    @forkit
    def doit():
        # This simulates piping output to another program.
        out = StringIO()
        out.fileno = None
        t = TestTerminal(stream=out)
        eq_(t.save, u'')
    doit()


def test_mnemonic_colors():
    """Make sure color shortcuts work."""
    @forkit
    def doit():
        def color(num):
            return unicode_parm('setaf', num)

        def on_color(num):
            return unicode_parm('setab', num)

        # Avoid testing red, blue, yellow, and cyan, since they might someday
        # change depending on terminal type.
        t = TestTerminal(force_styling=True)
        eq_(t.white, color(7))
        eq_(t.green, color(2))  # Make sure it's different than white.
        eq_(t.on_black, on_color(0))
        eq_(t.on_green, on_color(2))
        eq_(t.bright_black, color(8))
        eq_(t.bright_green, color(10))
        eq_(t.on_bright_black, on_color(8))
        eq_(t.on_bright_green, on_color(10))
    doit()


def test_callable_numeric_colors():
    """``color(n)`` should return a formatting wrapper."""
    @forkit
    def doit():
        t = TestTerminal(force_styling=True)
        from blessings import FormattingString
        eq_(type(t.color(5)), FormattingString)
        eq_(t.color(5)('smoo'), t.magenta + 'smoo' + t.normal)
        eq_(t.color(5)('smoo'), t.color(5) + 'smoo' + t.normal)
        eq_(t.on_color(2)('smoo'), t.on_green + 'smoo' + t.normal)
        eq_(t.on_color(2)('smoo'), t.on_color(2) + 'smoo' + t.normal)
    doit()


def test_null_callable_numeric_colors():
    """``color(n)`` should be a no-op on null terminals."""
    @forkit
    def doit():
        # NullCallableString should not be used by mere mortals
        assert 'NullCallableString' not in globals()
        t = TestTerminal(stream=StringIO())
        from blessings import NullCallableString
        # ensure bare unicode is not returned,
        eq_(type(t.color(3)), NullCallableString)
        eq_(type(t.bold), NullCallableString)
        eq_(type(t.green_on_black), NullCallableString)
        eq_(type(t.bright_blue), NullCallableString)
        # an empty unicode should be returned for most capabilities
        eq_(t.color(4), u'')
        eq_(t.color(5)('smoo'), 'smoo')
        eq_(t.bold('smoo'), 'smoo')
        eq_(t.green_on_black('smoo'), 'smoo')
        eq_(t.bright_yellow('smoo'), 'smoo')
        # even non-existant ones work
        eq_(t.bright_bullshit('smoo'), 'smoo')
        eq_(t.on_color(6)('smoo'), 'smoo')
    doit()


def test_naked_color_cap():
    """``term.color`` should return a stringlike capability."""
    @forkit
    def doit():
        t = TestTerminal()
        eq_(t.color + '', t.setaf + '')
    doit()


def test_number_of_colors_xterm_notty_forced_style():
    """``number_of_colors`` should return 256 for xterm-256color when force_styling is True. """
    @forkit
    def doit():
        term = TestTerminal(stream=StringIO(), kind='xterm-256color', force_styling=True)
        eq_(term.number_of_colors, 256)
    doit()


def test_number_of_colors_xterm_notty():
    """``number_of_colors`` should return 0 for xterm-256color when there's no tty. """
    @forkit
    def doit():
        term = TestTerminal(stream=StringIO(), kind='xterm-256color', force_styling=None)
        eq_(term.number_of_colors, 0)
    doit()


def test_number_of_colors_vt220_notty_forced_style():
    """``number_of_colors`` should return 0 for vt220 -- amber or green-on-black, only. """
    @forkit
    def doit():
        term = TestTerminal(stream=StringIO(), kind='vt220', force_styling=True)
        eq_(term.number_of_colors, 0)
    doit()


def test_number_of_colors_dtterm_notty_forced_style():
    """``number_of_colors`` should return 8 for dtterm -- an early sun xterm variant. """
    @forkit
    def doit():
        term = TestTerminal(stream=StringIO(), kind='dtterm', force_styling=True)
        eq_(term.number_of_colors, 8)
    doit()


def test_formatting_functions():
    """Test crazy-ass formatting wrappers, both simple and compound."""
    @forkit
    def doit():
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
    doit()


def test_formatting_functions_without_tty():
    """Test crazy-ass formatting wrappers when there's no tty."""
    @forkit
    def doit():
        t = TestTerminal(stream=StringIO())
        eq_(t.bold(u'hi'), u'hi')
        eq_(t.green('hi'), u'hi')
        # Test non-ASCII chars, no longer really necessary:
        eq_(t.bold_green(u'boö'), u'boö')
        eq_(t.bold_underline_green_on_red('loo'), u'loo')
        eq_(t.on_bright_red_bold_bright_green_underline('meh'), u'meh')
    doit()


def test_missing_formatting_errors():
    """Unfortunately, missing ttys do not (yet?) throw formatting errors."""
    @forkit
    def doit():
        t = TestTerminal(stream=StringIO())
        t.bold_misspelled('hey')
        t.bold_misspelled(u'hey')  # unicode
        t.bold_misspelled(None)  # an arbitrary non-string
        t.bold_misspelled('a', 'b')  # >1 string arg
    doit()


def test_nice_formatting_errors():
    """Make sure you get nice hints if you misspell a formatting wrapper."""
    @forkit
    def doit():
        t = TestTerminal()
        try:
            t.bold_misspelled('hey')
            assert False, 'Should have thrown exception'
        except TypeError, e:
            assert 'probably misspelled' in e.args[0]

        try:
            t.bold_misspelled(u'hey')  # unicode
            assert False, 'Should have thrown exception'
        except TypeError, e:
            assert 'probably misspelled' in e.args[0]

        try:
            t.bold_misspelled(None)  # an arbitrary non-string
            assert False, 'Should have thrown exception'
        except TypeError, e:
            assert 'probably misspelled' not in e.args[0]

        try:
            t.bold_misspelled('a', 'b')  # >1 string arg
            assert False, 'Should have thrown exception'
        except TypeError, e:
            assert 'probably misspelled' not in e.args[0]
    doit()


def test_init_descriptor_always_initted():
    """We should be able to get a height and width even on no-tty Terminals."""
    @forkit
    def doit():
        t = TestTerminal(stream=StringIO())
        eq_(type(t.height), int)
    doit()


def test_force_styling_none():
    """If ``force_styling=None`` is passed to constructor, don't style."""
    @forkit
    def doit():
        t = TestTerminal(force_styling=None)
        eq_(t.save, '')
    doit()


def test_null_callable_string():
    """Make sure NullCallableString tolerates all numbers and kinds of args."""
    @forkit
    def doit():
        t = TestTerminal(stream=StringIO())
        eq_(t.clear, '')
        eq_(t.move(1, 2), '')
        eq_(t.move_x(1), '')
    doit()
