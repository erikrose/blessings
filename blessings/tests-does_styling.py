# -*- coding: utf-8 -*-
"""Automated tests for Terminals that perform Styling (force_styling=True). """

# It was tempting to mock out curses to get predictable output from ``tigetstr``,
# but there are concrete integration-testing benefits in not doing so. For
# instance, ``tigetstr`` changed its return type in Python 3.2.3. So instead, we
# simply create all our test ``Terminal`` instances with a known terminal type.
# All we require from the host machine is that a standard terminfo definition of
# xterm-256color exists.

from __future__ import with_statement  # Make 2.5-compatible
from curses import tigetstr, tparm
from StringIO import StringIO
import sys

from nose.tools import eq_

# This tests that __all__ is correct, since we use below everything
# that should be imported (which, is only 'Terminal', for now.)
from blessings import *

term = Terminal(kind='xterm-256color', force_styling=True)


def unicode_cap(cap):
    """Return the result of ``tigetstr`` as Unicode, not a bytestring."""
    return tigetstr(cap).decode('utf-8')


def unicode_parm(cap, *parms):
    """Return the result of ``tparm(tigetstr())`` except as Unicode."""
    return tparm(tigetstr(cap), *parms).decode('utf-8')


def test_capability():
    """Check that a capability lookup works.

    Also test that Terminal grabs a reasonable default stream. This test
    assumes it will be run from a tty.

    """
    sc = unicode_cap('sc')
    print(repr(term.save))
    print(repr(term.bold('hai')))
    eq_(term.save, sc)
    eq_(term.save, sc)  # Make sure caching doesn't screw it up.


def test_parametrization():
    """Test parametrizing a capability."""
    eq_(term.cup(3, 4), unicode_parm('cup', 3, 4))


def test_stream_attr():
    """Make sure Terminal exposes a ``stream`` attribute that defaults to something sane."""
    eq_(term.stream, sys.__stdout__)


def test_mnemonic_colors():
    """Make sure color shortcuts work."""
    def color(num):
        return unicode_parm('setaf', num)

    def on_color(num):
        return unicode_parm('setab', num)

    # Avoid testing red, blue, yellow, and cyan, since they might someday
    # change depending on terminal type.
    eq_(term.white, color(7))
    eq_(term.green, color(2))  # Make sure it's different than white.
    eq_(term.on_black, on_color(0))
    eq_(term.on_green, on_color(2))
    eq_(term.bright_black, color(8))
    eq_(term.bright_green, color(10))
    eq_(term.on_bright_black, on_color(8))
    eq_(term.on_bright_green, on_color(10))


def test_callable_numeric_colors():
    """``color(n)`` should return a formatting wrapper."""
    eq_(term.color(5)('smoo'), term.magenta + 'smoo' + term.normal)
    eq_(term.color(5)('smoo'), term.color(5) + 'smoo' + term.normal)
    eq_(term.on_color(2)('smoo'), term.on_green + 'smoo' + term.normal)
    eq_(term.on_color(2)('smoo'), term.on_color(2) + 'smoo' + term.normal)


def test_null_callable_numeric_colors():
    """``color(n)`` should work when force_styling is True."""
    eq_(term.color(5)('smoo'), '\x1b[35msmoo\x1b(B\x1b[m')
    eq_(term.on_color(6)('smoo'), '\x1b[46msmoo\x1b(B\x1b[m')


def test_naked_color_cap():
    """``term.color`` should return a stringlike capability."""
    eq_(term.color + '', term.setaf + '')


def test_number_of_colors_with_tty():
    """``number_of_colors`` should work."""
    eq_(term.number_of_colors, 256)


def test_formatting_functions():
    """Test crazy-ass formatting wrappers, both simple and compound."""
    # By now, it should be safe to use sugared attributes. Other tests test those.
    eq_(term.bold(u'hi'), term.bold + u'hi' + term.normal)
    eq_(term.green('hi'), term.green + u'hi' + term.normal)  # Plain strs for Python 2.x
    # Test some non-ASCII chars, probably not necessary:
    eq_(term.bold_green(u'boö'), term.bold + term.green + u'boö' + term.normal)
    eq_(term.bold_underline_green_on_red('boo'),
        term.bold + term.underline + term.green + term.on_red + u'boo' + term.normal)
    # Don't spell things like this:
    eq_(term.on_bright_red_bold_bright_green_underline('meh'),
        term.on_bright_red + term.bold + term.bright_green + term.underline + u'meh' + term.normal)


def test_nice_formatting_errors():
    """Make sure you get nice hints if you misspell a formatting wrapper."""
    try:
        term.bold_misspelled('hey')
    except TypeError as err:
        assert 'probably misspelled' in err.args[0]

    try:
        term.bold_misspelled(u'hey')  # unicode
    except TypeError as err:
        assert 'probably misspelled' in err.args[0]

    try:
        term.bold_misspelled(None)  # an arbitrary non-string
    except TypeError as err:
        assert 'probably misspelled' not in err.args[0]

    try:
        term.bold_misspelled('a', 'b')  # >1 string arg
    except TypeError as err:
        assert 'probably misspelled' not in err.args[0]

def height_and_width():
    """Assert that ``height_and_width()`` returns ints."""
    assert isinstance(int, term.height)
    assert isinstance(int, term.width)

def test_init_descriptor_always_initted():
    """We should be able to get a height and width even on no-tty Terminals."""
    eq_(type(term.height), int)
    eq_(type(term.width), int)


def test_null_callable_string():
    """Make sure NullCallableString tolerates all numbers and kinds of args it might receive."""
    eq_(term.clear, u'\x1b[H\x1b[2J')
    eq_(term.move(1, 2), u'\x1b[2;3H')
    eq_(term.move_x(1), u'\x1b[2G')
