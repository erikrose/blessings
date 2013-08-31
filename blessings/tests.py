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
import sys
import os

from nose import SkipTest
from nose.tools import eq_

# This tests that __all__ is correct, since we use below everything that should
# be imported:
from blessings import *


TestTerminal = partial(Terminal, kind='xterm-256color')


class forkit:
    """ This helper executes test cases in a child process,
        avoiding a Terminal illness: cannot call setupterm()
        more than once per process (issue #33).
    """
    def __init__(self, func):
        pid = os.fork()
        if pid == 0:
            # only the child process runs function,
            func()
            os._exit(0)
        else:
            # parent process waits for child to complete
            os.waitpid(pid, 0)


def unicode_cap(cap):
    """Return the result of ``tigetstr`` except as Unicode."""
    return tigetstr(cap).decode('utf-8')


def unicode_parm(cap, *parms):
    """Return the result of ``tparm(tigetstr())`` except as Unicode."""
    return tparm(tigetstr(cap), *parms).decode('utf-8')


@forkit
def test_capability():
    """Check that a capability lookup works.

    Also test that Terminal grabs a reasonable default stream. This test
    assumes it will be run from a tty.

    """
    t = TestTerminal()
    sc = unicode_cap('sc')
    eq_(t.save, sc)
    eq_(t.save, sc)  # Make sure caching doesn't screw it up.


@forkit
def test_capability_without_tty():
    """Assert capability templates are '' when stream is not a tty."""
    t = TestTerminal(stream=StringIO())
    eq_(t.save, u'')
    eq_(t.red, u'')


@forkit
def test_capability_with_forced_tty():
    """If we force styling, capabilities had better not (generally) be
    empty."""
    t = TestTerminal(stream=StringIO(), force_styling=True)
    eq_(t.save, unicode_cap('sc'))


@forkit
def test_parametrization():
    """Test parametrizing a capability."""
    eq_(TestTerminal().cup(3, 4), unicode_parm('cup', 3, 4))


@forkit
def height_and_width():
    """Assert that ``height_and_width()`` returns ints."""
    t = TestTerminal()  # kind shouldn't matter.
    eq_(int, type(t.height))
    eq_(int, type(t.width))


@forkit
def test_stream_attr():
    """Make sure Terminal exposes a ``stream`` attribute that defaults to
    something sane."""
    eq_(Terminal().stream, sys.__stdout__)


@forkit
def test_location():
    """Make sure ``location()`` does what it claims."""
    t = TestTerminal(stream=StringIO(), force_styling=True)

    with t.location(3, 4):
        t.stream.write(u'hi')

    eq_(t.stream.getvalue(), unicode_cap('sc') +
                             unicode_parm('cup', 4, 3) +
                             u'hi' +
                             unicode_cap('rc'))


@forkit
def test_horizontal_location():
    """Make sure we can move the cursor horizontally without changing rows."""
    t = TestTerminal(stream=StringIO(), force_styling=True)
    with t.location(x=5):
        pass
    eq_(t.stream.getvalue(), unicode_cap('sc') +
                             unicode_parm('hpa', 5) +
                             unicode_cap('rc'))


@forkit
def test_null_location():
    """Make sure ``location()`` with no args just does position restoration."""
    t = TestTerminal(stream=StringIO(), force_styling=True)
    with t.location():
        pass
    eq_(t.stream.getvalue(), unicode_cap('sc') +
                             unicode_cap('rc'))


@forkit
def test_zero_location():
    """Make sure ``location()`` pays attention to 0-valued args."""
    t = TestTerminal(stream=StringIO(), force_styling=True)
    with t.location(0, 0):
        pass
    eq_(t.stream.getvalue(), unicode_cap('sc') +
                             unicode_parm('cup', 0, 0) +
                             unicode_cap('rc'))


@forkit
def test_null_fileno():
    """Make sure ``Terminal`` works when ``fileno`` is ``None``.

    This simulates piping output to another program.

    """
    out = StringIO()
    out.fileno = None
    t = TestTerminal(stream=out)
    eq_(t.save, u'')


@forkit
def test_mnemonic_colors():
    """Make sure color shortcuts work."""
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


@forkit
def test_callable_numeric_colors():
    """``color(n)`` should return a formatting wrapper."""
    t = TestTerminal()
    eq_(t.color(5)('smoo'), t.magenta + 'smoo' + t.normal)
    eq_(t.color(5)('smoo'), t.color(5) + 'smoo' + t.normal)
    eq_(t.on_color(2)('smoo'), t.on_green + 'smoo' + t.normal)
    eq_(t.on_color(2)('smoo'), t.on_color(2) + 'smoo' + t.normal)


@forkit
def test_null_callable_numeric_colors():
    """``color(n)`` should be a no-op on null terminals."""
    t = TestTerminal(kind='vt220', force_styling=True)
    eq_(t.color(5)('smoo'), 'smoo')
    eq_(t.on_color(6)('smoo'), 'smoo')


@forkit
def test_naked_color_cap():
    """``term.color`` should return a stringlike capability."""
    t = TestTerminal()
    eq_(t.color + '', t.setaf + '')


@forkit
def test_number_of_colors_xterm_notty_forced_style():
    """``number_of_colors`` should return 256 for xterm-256color when force_styling is True. """
    term = Terminal(stream=StringIO(), kind='xterm-256color', force_styling=True)
    eq_(term.number_of_colors, 256)


@forkit
def test_number_of_colors_xterm_notty():
    """``number_of_colors`` should return 0 for xterm-256color when there's no tty. """
    term = Terminal(stream=StringIO(), kind='xterm-256color')
    eq_(term.number_of_colors, 0)


@forkit
def test_number_of_colors_vt220_notty_forced_style():
    """``number_of_colors`` should return 0 for vt220 -- amber or green-on-black, only. """
    term = Terminal(stream=StringIO(), kind='vt220', force_styling=True)
    eq_(term.number_of_colors, 0)


@forkit
def test_number_of_colors_dtterm_notty_forced_style():
    """``number_of_colors`` should return 8 for dtterm -- an early sun xterm variant. """
    term = Terminal(stream=StringIO(), kind='dtterm', force_styling=True)
    eq_(term.number_of_colors, 8)


@forkit
def test_formatting_functions():
    """Test crazy-ass formatting wrappers, both simple and compound."""
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


@forkit
def test_formatting_functions_without_tty():
    """Test crazy-ass formatting wrappers when there's no tty."""
    t = TestTerminal(stream=StringIO())
    eq_(t.bold(u'hi'), u'hi')
    eq_(t.green('hi'), u'hi')
    # Test non-ASCII chars, no longer really necessary:
    eq_(t.bold_green(u'boö'), u'boö')
    eq_(t.bold_underline_green_on_red('loo'), u'loo')
    eq_(t.on_bright_red_bold_bright_green_underline('meh'), u'meh')


@forkit
def test_nice_formatting_errors():
    """Make sure you get nice hints if you misspell a formatting wrapper."""
    t = TestTerminal()
    try:
        t.bold_misspelled('hey')
    except TypeError, e:
        assert 'probably misspelled' in e.args[0]

    try:
        t.bold_misspelled(u'hey')  # unicode
    except TypeError, e:
        assert 'probably misspelled' in e.args[0]

    try:
        t.bold_misspelled(None)  # an arbitrary non-string
    except TypeError, e:
        assert 'probably misspelled' not in e.args[0]

    try:
        t.bold_misspelled('a', 'b')  # >1 string arg
    except TypeError, e:
        assert 'probably misspelled' not in e.args[0]


@forkit
def test_init_descriptor_always_initted():
    """We should be able to get a height and width even on no-tty Terminals."""
    t = Terminal(stream=StringIO())
    eq_(type(t.height), int)


@forkit
def test_force_styling_none():
    """If ``force_styling=None`` is passed to the constructor, don't ever do
    styling."""
    t = TestTerminal(force_styling=None)
    eq_(t.save, '')


@forkit
def test_null_callable_string():
    """Make sure NullCallableString tolerates all numbers and kinds of args it
    might receive."""
    t = TestTerminal(stream=StringIO())
    eq_(t.clear, '')
    eq_(t.move(1, 2), '')
    eq_(t.move_x(1), '')
