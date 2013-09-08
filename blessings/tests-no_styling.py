# -*- coding: utf-8 -*-
""" Automated tests for terminals without styling (force_styling=None).

Capabilities should return null strings (u'') for just about anything.
setupterm() should never be called, and curses C-land exported functions,
such as tigetstr() and tparm() should never be called, either.

"""
from __future__ import with_statement

from nose.tools import eq_
from nose import SkipTest

import os
import sys
import warnings
from platform import python_version_tuple
from blessings import Terminal
from StringIO import StringIO


# This tests that __all__ is correct, since we use below everything that should
# be imported:


term = Terminal(stream=StringIO(), kind='xterm-256color', force_styling=None)


def test_capability():
    """Check that a capability lookup is null when force_styling=None """
    sc, civis = u'', u''
    eq_(term.save, sc)
    eq_(term.save, sc)
    eq_(term.hide_cursor, civis)
    eq_(term.save, sc)


def test_parametrization():
    """Test parametrizing a capability."""
    eq_(term.cup(3, 4), u'')


def test_stream_attr():
    """Make sure Terminal exposes a ``stream`` attribute that defaults to something sane."""
    assert hasattr(term.stream, 'write')


def height_and_width():
    """Assert that ``height_and_width()`` returns ints."""
    assert isinstance(int, term.height)
    assert isinstance(int, term.width)


def test_location():
    """Make sure ``location()`` does what it claims."""

    with term.location(3, 4):
        term.stream.write(u'hi')

    eq_(term.stream.getvalue(), u'hi')
    term.stream.truncate(0)


def test_horizontal_location():
    """Make sure we can move the cursor horizontally without changing rows."""
    with term.location(x=5):
        pass
    eq_(term.stream.getvalue(), u'')
    term.stream.truncate(0)


def test_null_location():
    """Make sure ``location()`` with no args just does position restoration."""
    with term.location():
        pass
    eq_(term.stream.getvalue(), u'')
    term.stream.truncate(0)


def test_zero_location():
    """Make sure ``location()`` pays attention to 0-valued args."""
    with term.location(0, 0):
        pass
    eq_(term.stream.getvalue(), u'')
    term.stream.truncate(0)


def test_null_fileno():
    """Make sure ``Terminal`` works when ``fileno`` is ``None``.

    This simulates piping output to another program.

    """
    out = StringIO()
    out.fileno = None
    term = Terminal(stream=out, kind='xterm-256color', force_styling=None)
    eq_(term.save, u'')


def test_mnemonic_colors():
    """Make sure color shortcuts work."""
    # Avoid testing red, blue, yellow, and cyan, since they might someday
    # change depending on terminal type.
    eq_(term.white, u'')
    eq_(term.green, u'')
    eq_(term.on_black, u'')
    eq_(term.on_green, u'')
    eq_(term.bright_black, u'')
    eq_(term.bright_green, u'')
    eq_(term.on_bright_black, u'')
    eq_(term.on_bright_green, u'')


def test_callable_numeric_colors():
    """``color(n)`` should return a formatting wrapper."""
    eq_(term.color(5)('smoo'), 'smoo')
    eq_(term.color(5)('smoo'), 'smoo')
    eq_(term.on_color(2)('smoo'), 'smoo')
    eq_(term.on_color(2)('smoo'), 'smoo')


def test_null_callable_numeric_colors():
    """``color(n)`` should be a no-op on null terminals."""
    eq_(term.color(5)('smoo'), 'smoo')
    eq_(term.on_color(6)('smoo'), 'smoo')


def test_naked_color_cap():
    """``term.color`` should return a stringlike capability."""
    eq_(term.color + '', term.setaf + '')


def test_number_of_colors_with_tty():
    """``number_of_colors`` should work."""
    eq_(term.number_of_colors, 0)


def test_formatting_functions():
    """Test crazy-ass formatting wrappers, both simple and compound."""
    # By now, it should be safe to use sugared attributes. Other tests test
    # those.
    eq_(term.bold(u'hi'), u'hi')
    eq_(term.green('hi'), u'hi')  # Plain strs for Python 2.x
    # Test some non-ASCII chars, probably not necessary:
    eq_(term.bold_green(u'boö'), u'boö')
    eq_(term.bold_underline_green_on_red('boo'), u'boo')
    # Don't spell things like this:
    eq_(term.on_bright_red_bold_bright_green_underline('meh'), u'meh')


def test_nice_formatting_errors():
    """Make sure you get nice hints if you misspell a formatting wrapper."""
    try:
        term.bold_misspelled('hey')
    except TypeError, err:
        assert 'probably misspelled' in err.args[0]

    try:
        term.bold_misspelled(u'hey')  # unicode
    except TypeError, err:
        assert 'probably misspelled' in err.args[0]

    try:
        term.bold_misspelled(None)  # an arbitrary non-string
    except TypeError, err:
        assert 'probably misspelled' not in err.args[0]

    try:
        term.bold_misspelled('a', 'b')  # >1 string arg
    except TypeError, err:
        assert 'probably misspelled' not in err.args[0]


def test_init_descriptor_always_initted():
    """We should be able to get a height and width even on no-tty Terminals."""
    raise SkipTest
    # unfortunately, I cannot fake past the direct use of sys.__stdout__ that
    # occurs in the _height_and_width function to test the 80x24 fallback.

    with warnings.catch_warnings(record=True) as warned:
        class FakeStdout(StringIO):
            def fileno(self):
                return 9999
        fckdterm = Terminal(stream=StringIO(), kind='xterm-256color', force_styling=None)
        Terminal._init_descriptor = StringIO()
        sys.__stdout__ = FakeStdout()
        os.environ['COLUMNS']='x'
        os.environ['LINES']='x'
        eq_(type(term.height), int)
        eq_(term.height, 24)
        eq_(len(warned), 1)
        assert issubclass(warned[-1].category, RuntimeWarning)
        assert "due to an internal python curses bug" in warned[-1].message
        eq_(type(term.width), int)
        eq_(term.width, 80)
        eq_(len(warned), 2)
        assert issubclass(warned[-1].category, RuntimeWarning)
        print(warned[-1].message)


def test_null_callable_string():
    """Make sure NullCallableString tolerates all numbers and kinds of args it might receive."""
    eq_(term.clear, '')
    eq_(term.move(1, 2), '')
    eq_(term.move_x(1), '')
