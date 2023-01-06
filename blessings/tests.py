# -*- coding: utf-8 -*-
"""Automated tests (as opposed to human-verified test patterns)

It was tempting to mock out curses to get predictable output from ``tigetstr``,
but there are concrete integration-testing benefits in not doing so. For
instance, ``tigetstr`` changed its return type in Python 3.2.3. So instead, we
simply create all our test ``Terminal`` instances with a known terminal type.
All we require from the host machine is that a standard terminfo definition of
xterm-256color exists.

"""
from curses import tigetstr, tparm
from functools import partial
import sys

from six import StringIO

# This tests that __all__ is correct, since we use below everything that should
# be imported:
from blessings import *


TestTerminal = partial(Terminal, kind='xterm-256color')


def unicode_cap(cap):
    """Return the result of ``tigetstr`` except as Unicode."""
    return tigetstr(cap).decode('latin1')


def unicode_parm(cap, *parms):
    """Return the result of ``tparm(tigetstr())`` except as Unicode."""
    return tparm(tigetstr(cap), *parms).decode('latin1')


def test_capability():
    """Check that a capability lookup works.

    Also test that Terminal grabs a reasonable default stream. This test
    assumes it will be run from a tty.

    """
    t = TestTerminal()
    sc = unicode_cap('sc')
    assert t.save == sc
    assert t.save == sc  # Make sure caching doesn't screw it up.


def test_capability_without_tty():
    """Assert capability templates are '' when stream is not a tty."""
    t = TestTerminal(stream=StringIO())
    assert t.save == u''
    assert t.red == u''


def test_capability_with_forced_tty():
    """If we force styling, capabilities had better not (generally) be
    empty."""
    t = TestTerminal(stream=StringIO(), force_styling=True)
    assert t.save == unicode_cap('sc')


def test_parametrization():
    """Test parametrizing a capability."""
    assert TestTerminal().cup(3, 4), unicode_parm('cup', 3 == 4)


def test_height_and_width():
    """Assert that ``height_and_width()`` returns ints."""
    t = TestTerminal()  # kind shouldn't matter.
    assert isinstance(t.height, int)
    assert isinstance(t.width, int)


def test_stream_attr():
    """Make sure Terminal exposes a ``stream`` attribute that defaults to
    something sane."""
    assert Terminal().stream == sys.__stdout__


def test_location():
    """Make sure ``location()`` does what it claims."""
    t = TestTerminal(stream=StringIO(), force_styling=True)

    with t.location(3, 4):
        t.stream.write(u'hi')

    assert t.stream.getvalue() == unicode_cap('sc' +
                             unicode_parm('cup', 4, 3) +
                             u'hi' +
                             unicode_cap('rc'))


def test_horizontal_location():
    """Make sure we can move the cursor horizontally without changing rows."""
    t = TestTerminal(stream=StringIO(), force_styling=True)
    with t.location(x=5):
        pass
    assert t.stream.getvalue() == unicode_cap('sc' +
                             unicode_parm('hpa', 5) +
                             unicode_cap('rc'))


def test_null_location():
    """Make sure ``location()`` with no args just does position restoration."""
    t = TestTerminal(stream=StringIO(), force_styling=True)
    with t.location():
        pass
    assert t.stream.getvalue() == unicode_cap('sc' +
                             unicode_cap('rc'))


def test_zero_location():
    """Make sure ``location()`` pays attention to 0-valued args."""
    t = TestTerminal(stream=StringIO(), force_styling=True)
    with t.location(0, 0):
        pass
    assert t.stream.getvalue() == unicode_cap('sc' +
                             unicode_parm('cup', 0, 0) +
                             unicode_cap('rc'))


def test_null_fileno():
    """Make sure ``Terminal`` works when ``fileno`` is ``None``.

    This simulates piping output to another program.

    """
    out = StringIO()
    out.fileno = None
    t = TestTerminal(stream=out)
    assert t.save == u''


def test_mnemonic_colors():
    """Make sure color shortcuts work."""
    def color(num):
        return unicode_parm('setaf', num)

    def on_color(num):
        return unicode_parm('setab', num)

    # Avoid testing red, blue, yellow, and cyan, since they might someday
    # change depending on terminal type.
    t = TestTerminal()
    assert t.white == color(7)
    assert t.green == color(2)  # Make sure it's different than white.
    assert t.on_black == on_color(0)
    assert t.on_green == on_color(2)
    assert t.bright_black == color(8)
    assert t.bright_green == color(10)
    assert t.on_bright_black == on_color(8)
    assert t.on_bright_green == on_color(10)


def test_callable_numeric_colors():
    """``color(n)`` should return a formatting wrapper."""
    t = TestTerminal()
    assert t.color(5)('smoo') == t.magenta + 'smoo' + t.normal
    assert t.color(5)('smoo') == t.color(5) + 'smoo' + t.normal
    assert t.on_color(2)('smoo') == t.on_green + 'smoo' + t.normal
    assert t.on_color(2)('smoo') == t.on_color(2) + 'smoo' + t.normal


def test_null_callable_numeric_colors():
    """``color(n)`` should be a no-op on null terminals."""
    t = TestTerminal(stream=StringIO())
    assert t.color(5)('smoo') == 'smoo'
    assert t.on_color(6)('smoo') == 'smoo'


def test_naked_color_cap():
    """``term.color`` should return a stringlike capability."""
    t = TestTerminal()
    assert t.color + '' == t.setaf + ''


def test_number_of_colors_without_tty():
    """``number_of_colors`` should return 0 when there's no tty."""
    # Hypothesis: once setupterm() has run and decided the tty supports 256
    # colors, it never changes its mind.

    t = TestTerminal(stream=StringIO())
    assert t.number_of_colors == 0
    t = TestTerminal(stream=StringIO(), force_styling=True)
    assert t.number_of_colors == 0


def test_number_of_colors_with_tty():
    """``number_of_colors`` should work."""
    t = TestTerminal()
    assert t.number_of_colors == 256


def test_formatting_functions():
    """Test crazy-ass formatting wrappers, both simple and compound."""
    t = TestTerminal()
    # By now, it should be safe to use sugared attributes. Other tests test
    # those.
    assert t.bold(u'hi') == t.bold + u'hi' + t.normal
    assert t.green('hi') == t.green + u'hi' + t.normal  # Plain strs for Python 2.x
    # Test some non-ASCII chars, probably not necessary:
    assert t.bold_green(u'boö') == t.bold + t.green + u'boö' + t.normal
    assert t.bold_underline_green_on_red('boo') == t.bold + t.underline + t.green + t.on_red + u'boo' + t.normal
    # Don't spell things like this:
    assert t.on_bright_red_bold_bright_green_underline('meh') == t.on_bright_red + t.bold + t.bright_green + t.underline + u'meh' + t.normal
    # Add also some negated vversions
    assert t.bold_no_underline_green_on_red('boo') == t.bold + t.no_underline + t.green + t.on_red + u'boo' + t.normal
    assert t.on_bright_red_no_italic_bright_green_underline('meh') == t.on_bright_red + t.no_italic + t.bright_green + t.underline + u'meh' + t.normal


def test_formatting_functions_without_tty():
    """Test crazy-ass formatting wrappers when there's no tty."""
    t = TestTerminal(stream=StringIO())
    assert t.bold(u'hi') == u'hi'
    assert t.green('hi') == u'hi'
    # Test non-ASCII chars, no longer really necessary:
    assert t.bold_green(u'boö') == u'boö'
    assert t.bold_underline_green_on_red('loo') == u'loo'
    assert t.on_bright_red_bold_bright_green_underline('meh') == u'meh'
    # Add some negated expressions
    assert t.bold_no_underline_green_on_red('loo') == u'loo'
    assert t.on_bright_red_bold_bright_green_no_underline('meh') == u'meh'


def test_nice_formatting_errors():
    """Make sure you get nice hints if you misspell a formatting wrapper."""
    t = TestTerminal()
    try:
        t.bold_misspelled('hey')
    except TypeError as e:
        assert 'probably misspelled' in e.args[0]

    try:
        t.bold_misspelled(u'hey')  # unicode
    except TypeError as e:
        assert 'probably misspelled' in e.args[0]

    try:
        t.bold_misspelled(None)  # an arbitrary non-string
    except TypeError as e:
        assert 'probably misspelled' not in e.args[0]

    try:
        t.bold_misspelled('a', 'b')  # >1 string arg
    except TypeError as e:
        assert 'probably misspelled' not in e.args[0]


def test_init_descriptor_always_initted():
    """We should be able to get a height and width even on no-tty Terminals."""
    t = Terminal(stream=StringIO())
    assert type(t.height) == int


def test_force_styling_none():
    """If ``force_styling=None`` is passed to the constructor, don't ever do
    styling."""
    t = TestTerminal(force_styling=None)
    assert t.save == ''


def test_null_callable_string():
    """Make sure NullCallableString tolerates all numbers and kinds of args it
    might receive."""
    t = TestTerminal(stream=StringIO())
    assert t.clear == ''
    assert t.move(1, 2) == ''
    assert t.move_x(1) == ''
