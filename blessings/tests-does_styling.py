# -*- coding: utf-8 -*-
"""Automated tests for Terminals that perform Styling (force_styling=True).

   This terminal is sys.stdout (the default), which may or may not be a tty,
   depending on wether the test cases are piped to another program, such as tee(1)
   or cat(1), which is often the case for automated test suites or build logs.
   Regardless, the tests should pass either way, as force_styling is True.
"""

# It was tempting to mock out curses to get predictable output from ``tigetstr``,
# but there are concrete integration-testing benefits in not doing so. For
# instance, ``tigetstr`` changed its return type in Python 3.2.3. So instead, we
# simply create all our test ``Terminal`` instances with a known terminal type.
# All we require from the host machine is that a standard terminfo definition of
# xterm-256color exists.

from __future__ import with_statement

import sys
import warnings
from curses import tigetstr, tparm
from platform import python_version_tuple
from nose import SkipTest
from nose.tools import eq_

from blessings import *


# This tests that __all__ is correct, since we use below everything
# that should be imported (which, is only 'Terminal', for now.)

term = Terminal(kind='xterm-256color', force_styling=True)


def unicode_cap(cap):
    """Return the result of ``tigetstr`` as Unicode, not a bytestring."""
    return tigetstr(cap).decode('utf-8')


def unicode_parm(cap, *parms):
    """Return the result of ``tparm(tigetstr())`` except as Unicode."""
    return tparm(tigetstr(cap), *parms).decode('utf-8')


def test_sugared_capability():
    """Check that a "sugared" capability lookup works; friendly mnumonics for
    difficult to remember names, such as 'save' for 'sc'. """
    sc, civis = unicode_cap('sc'), unicode_cap('civis')
    eq_(term.save, sc)
    eq_(term.hide_cursor, civis)
    eq_(term.save, sc)
    assert sc.startswith('\033') and civis.startswith('\033')


def test_parametrization():
    """Test parametrizing a capability."""
    eq_(term.cup(3, 4), unicode_parm('cup', 3, 4))


def test_stream_attr():
    """Make sure Terminal exposes a ``stream`` attribute."""
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
    assert term.color(5).startswith('\033')
    eq_(term.color(5)('smoo'), term.magenta + 'smoo' + term.normal)
    eq_(term.color(5)('smoo'), term.color(5) + 'smoo' + term.normal)
    eq_(term.on_color(2)('smoo'), term.on_green + 'smoo' + term.normal)
    eq_(term.on_color(2)('smoo'), term.on_color(2) + 'smoo' + term.normal)


def test_null_callable_numeric_colors():
    """``color(n)`` should work when force_styling is True."""
    eq_(term.color(5)('smoo'), term.color(5) + 'smoo' + term.normal)
    eq_(term.on_color(6)('smoo'), term.on_color(6) + 'smoo' + term.normal)


def test_naked_color_cap():
    """``term.color`` should return a stringlike capability."""
    eq_(term.color + '', term.setaf + '')


def test_xterm256_number_of_colors():
    """``number_of_colors`` should always work when force_styling=True."""
    eq_(term.number_of_colors, 256)


def test_xterm256_formatting_functions():
    """Test crazy-ass formatting wrappers, both simple and compound."""
    # By now, it should be safe to use sugared attributes. Other tests test
    # those.
    assert term.bold('hi').startswith('\033')
    eq_(term.bold(u'hi'), term.bold + u'hi' + term.normal)
    # Plain strs for Python 2.x become unicode
    eq_(term.green('hi'), term.green + u'hi' + term.normal)
    # Test some non-ASCII chars, probably not necessary:
    eq_(term.bold_green(u'boö'),
        term.bold + term.green + u'boö' + term.normal)
    eq_(term.bold_underline_green_on_red('boo'),
        term.bold + term.underline + term.green
        + term.on_red + u'boo' + term.normal)
    # Don't spell things like this:
    eq_(term.on_bright_red_bold_bright_green_underline('meh'),
        term.on_bright_red + term.bold + term.bright_green
        + term.underline + u'meh' + term.normal)


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
    """We should always receive height and width as an integer."""
    eq_(type(term.height), int)
    eq_(type(term.width), int)


def test_null_callable_string():
    """Make sure NullCallableString tolerates integers and strings."""
    # valid uses,
    eq_(term.clear, u'\x1b[H\x1b[2J')
    eq_(term.move(1, 2), u'\x1b[2;3H')
    eq_(term.move_x(1), u'\x1b[2G')
    # invalid uses, not all uses raise TypeError ( should they? )
    eq_(term.clear(1), u'\x1b[H\x1b[2J')
    eq_(term.clear(1, 2, 3), u'\x1b[H\x1b[2J')
    eq_(term.move(1, 2, 3, 4, 5, 6, 7, 8, 9), u'\x1b[2;3H')
    try:
        eq_(term.move(1, 2, 3, 4, 5, 6, 7, 8, 10, 11), 'should-toss-exception')
    except TypeError, err:
        eq_('%s' % (err,), 'tparm() takes at most 10 arguments (11 given)')
    if python_version_tuple() < ('2', '6'):
        warnings.filterwarnings(action='error', category=DeprecationWarning)
    try:
        eq_(term.move_x(1.5), 'should-toss-exception')
    except (TypeError, DeprecationWarning), err:
        eq_('%s' % (err,), 'integer argument expected, got float')


def test_setupterm_kind_singleton_warning():
    """ Ensure a warning is emitted for issue #33. """
    if python_version_tuple() < ('2', '6'):
        warnings.filterwarnings(action='error', category=RuntimeWarning)
        try:
            term = Terminal(kind='vt220', force_styling=True)
            term.do_nothing()
            assert False, "Should have raised RuntimeWarning exception"
        except RuntimeWarning, err:
            assert "due to an internal python curses bug" in "%s" % (err,)
        # and, if we were to initialize an xterm-256color terminal, there is no
        # need to emit a warning -- we receive the behavior exactly as wanted,
        term = Terminal(kind='xterm-256color', force_styling=True)
        term.do_nothing()
        # a tip for you youngsters: dtterm is a perfectly good suitable
        # replacement for xterm-256color on sun solaris, where it is missing,
        # and the 'xterm' definition is so classical, it excludes color!
        try:
            term = Terminal(kind='dtterm', force_styling=True)
            term.do_nothing()
            assert False, "Should have raised RuntimeWarning exception"
        except RuntimeWarning, err:
            assert "due to an internal python curses bug" in "%s" % (err,)
        return

    with warnings.catch_warnings(record=True) as warned:
        eq_(len(warned), 0)
        # we've already initialized an xterm-256color terminal, so a vt220
        # terminal should emite a warning,
        term = Terminal(kind='vt220', force_styling=True)
        term.do_nothing()
        eq_(len(warned), 1)
        assert issubclass(warned[-1].category, RuntimeWarning)
        print(repr(warned[-1].message))
        assert "due to an internal python curses bug" in '%s' % (warned[-1].message,)
        # but if we initialize the same terminal type again, the same warning
        # would be emitted, so it is supressed -- which is what makes warnings
        # so much more useful than direct stderr writes or logger warnings.
        term = Terminal(kind='vt220', force_styling=True)
        term.do_nothing()
        eq_(len(warned), 1)
        # and, if we were to initialize an xterm-256color terminal, there is no
        # need to emit a warning -- we receive the behavior exactly as wanted,
        term = Terminal(kind='xterm-256color', force_styling=True)
        term.do_nothing()
        eq_(len(warned), 1)
        # a tip for you youngsters: dtterm is a perfectly good suitable
        # replacement for xterm-256color on sun solaris, where it is missing,
        # and the 'xterm' definition is so classical, it excludes color!
        term = Terminal(kind='dtterm', force_styling=True)
        eq_(len(warned), 2)
        assert "due to an internal python curses bug" in '%s' % (warned[-1].message,)
