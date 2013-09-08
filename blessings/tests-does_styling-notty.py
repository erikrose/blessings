# -*- coding: utf-8 -*-
"""Automated tests for Terminals that perform styling without a tty (force_styling=True).

Because setupterm() cannot be called with more than one ``kind`` of
terminal type (as often defined in a regular environment by the TERM
environment value, or the ``-tn`` parameter of xterm/urxvt) we create
individual test files for each terminal kind; hopefully this will ensure
that each file is executed in a seperate process, so that the terminal
behaviors may be predicted for unique kinds.
"""
from __future__ import with_statement

from curses import tigetstr, tparm

from nose.tools import eq_

from blessings import Terminal
from StringIO import StringIO


term = Terminal(stream=StringIO(), kind='xterm-256color', force_styling=True)


def unicode_cap(cap):
    """Return the result of ``tigetstr`` as Unicode, not bytestring."""
    return tigetstr(cap).decode('utf-8')


def unicode_parm(cap, *parms):
    """Return the result of ``tparm(tigetstr())`` except as Unicode."""
    return tparm(tigetstr(cap), *parms).decode('utf-8')


def test_location():
    """Make sure ``location()`` does what it claims."""

    with term.location(3, 4):
        term.stream.write(u'hi')

    eq_(term.stream.getvalue(),
        unicode_cap('sc') + unicode_parm('cup', 4, 3)
        + u'hi' + unicode_cap('rc'))
    term.stream.truncate(0)


def test_horizontal_location():
    """Make sure we can move the cursor horizontally without changing rows."""
    with term.location(x=5):
        pass
    eq_(term.stream.getvalue(), unicode_cap('sc') +
        unicode_parm('hpa', 5) +
        unicode_cap('rc'))
    term.stream.truncate(0)


def test_null_location():
    """Make sure ``location()`` with no args just does position restoration."""
    with term.location():
        pass
    eq_(term.stream.getvalue(), unicode_cap('sc') + unicode_cap('rc'))
    term.stream.truncate(0)


def test_zero_location():
    """Make sure ``location()`` pays attention to 0-valued args."""
    with term.location(0, 0):
        pass
    eq_(term.stream.getvalue(), unicode_cap('sc') +
        unicode_parm('cup', 0, 0) +
        unicode_cap('rc'))
    term.stream.truncate(0)


def test_null_fileno():
    """Make sure ``Terminal`` works when ``fileno`` is ``None``.

    This simulates piping output to another program.

    """
    out = StringIO()
    out.fileno = None
    t = Terminal(stream=out, kind='xterm-256color', force_styling=True)
    eq_(t.save, unicode_cap('sc'))


def test_capability_without_tty():
    """Assert capability templates are '' when stream is not a tty."""
    eq_(term.save, unicode_cap('sc'))
    eq_(term.red, unicode_parm('setaf', 1))


def test_number_of_colors_without_tty():
    """``number_of_colors`` should return 0 when there's no tty,
        unless force_styling is set True. """
    eq_(term.number_of_colors, 256)


def test_capability_with_forced_tty():
    """If we force styling, capabilities had better not (generally) be empty."""
    eq_(term.save, unicode_cap('sc'))


def test_formatting_functions_without_tty():
    """Test crazy-ass formatting wrappers when there's no tty."""
    assert term.bold(u'hi').startswith('\033')
    eq_(term.bold(u'hi'), term.bold + u'hi' + term.normal)
    eq_(term.green(u'hi'), term.green + u'hi' + term.normal)
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
