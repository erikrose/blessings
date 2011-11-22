# -*- coding: utf-8 -*-

from __future__ import with_statement  # Make 2.5-compatible
try:
    from io import BytesIO
except ImportError:
    from StringIO import StringIO as BytesIO
from curses import tigetstr, tparm
import sys

from nose.tools import eq_

# This tests that __all__ is correct, since we use below everything that should
# be imported:
from blessings import *
from blessings import Capability


def bytes_eq(bytes1, bytes2):
    """Make sure ``bytes1`` equals ``bytes2``, the latter of which gets cast to something bytes-like, depending on Python version."""
    eq_(bytes1, Capability(bytes2))


def test_capability():
    """Check that a capability lookup works.

    Also test that Terminal grabs a reasonable default stream. This test
    assumes it will be run from a tty.

    """
    t = Terminal()
    sc = tigetstr('sc')
    eq_(t.save, sc)
    eq_(t.save, sc)  # Make sure caching doesn't screw it up.


def test_capability_without_tty():
    """Assert capability templates are '' when stream is not a tty."""
    t = Terminal(stream=BytesIO())
    eq_(t.save, Capability(''.encode('utf-8')))
    eq_(t.red, Capability(''.encode('utf-8')))


def test_capability_with_forced_tty():
    """If we force styling, capabilities had better not (generally) be empty."""
    t = Terminal(stream=BytesIO(), force_styling=True)
    assert len(t.save) > 0


def test_parametrization():
    """Test parametrizing a capability."""
    eq_(Terminal().cup(3, 4), tparm(tigetstr('cup'), 3, 4))


def height_and_width():
    """Assert that ``height_and_width()`` returns ints."""
    t = Terminal()
    assert isinstance(int, t.height)
    assert isinstance(int, t.width)


def test_stream_attr():
    """Make sure Terminal exposes a ``stream`` attribute that defaults to something sane."""
    eq_(Terminal().stream, sys.__stdout__)


def test_location():
    """Make sure ``location()`` does what it claims."""
    t = Terminal(stream=BytesIO(), force_styling=True)

    with t.location(3, 4):
        t.stream.write('hi'.encode(t.encoding))

    eq_(t.stream.getvalue(), tigetstr('sc') +
                             tparm(tigetstr('cup'), 4, 3) +
                             'hi'.encode(t.encoding) +
                             tigetstr('rc'))

def test_horizontal_location():
    """Make sure we can move the cursor horizontally without changing rows."""
    t = Terminal(stream=BytesIO(), force_styling=True)
    with t.location(x=5):
        pass
    eq_(t.stream.getvalue(), t.save + tparm(tigetstr('hpa'), 5) + t.restore)


def test_null_fileno():
    """Make sure ``Terminal`` works when ``fileno`` is ``None``.

    This simulates piping output to another program.

    """
    out = stream=BytesIO()
    out.fileno = None
    t = Terminal(stream=out)
    eq_(t.save, ''.encode('utf-8'))


def test_mnemonic_colors():
    """Make sure color shortcuts work."""
    def color(num):
        return tparm(tigetstr('setaf'), num)

    def on_color(num):
        return tparm(tigetstr('setab'), num)

    # Avoid testing red, blue, yellow, and cyan, since they might someday
    # chance depending on terminal type.
    t = Terminal()
    eq_(t.white, color(7))
    bytes_eq(t.green, color(2))  # Make sure it's different than white.
    bytes_eq(t.on_black, on_color(0))
    bytes_eq(t.on_green, on_color(2))
    bytes_eq(t.bright_black, color(8))
    bytes_eq(t.bright_green, color(10))
    bytes_eq(t.on_bright_black, on_color(8))
    bytes_eq(t.on_bright_green, on_color(10))


def test_formatting_functions():
    """Test crazy-ass formatting wrappers, both simple and compound."""
    t = Terminal(encoding='utf-8')
    eq_(t.bold('hi'), t.bold + 'hi'.encode('utf-8') + t.normal)
    eq_(t.green('hi'), t.green + 'hi'.encode('utf-8') + t.normal)
    # Test encoding of unicodes:
    eq_(t.bold_green(u'boö'), t.bold + t.green + u'boö'.encode('utf-8') + t.normal)
    eq_(t.bold_underline_green_on_red('boo'),
        t.bold + t.underline + t.green + t.on_red + 'boo'.encode('utf-8') + t.normal)
    # Don't spell things like this:
    eq_(t.on_bright_red_bold_bright_green_underline('meh'),
        t.on_bright_red + t.bold + t.bright_green + t.underline + 'meh'.encode('utf-8') + t.normal)


def test_formatting_functions_without_tty():
    """Test crazy-ass formatting wrappers when there's no tty."""
    t = Terminal(stream=BytesIO())
    eq_(t.bold('hi'), 'hi'.encode('utf-8'))
    eq_(t.green('hi'), 'hi'.encode('utf-8'))
    # Test encoding of unicodes:
    eq_(t.bold_green(u'boö'), u'boö'.encode('utf-8'))  # unicode
    eq_(t.bold_underline_green_on_red('boo'), 'boo'.encode('utf-8'))
    eq_(t.on_bright_red_bold_bright_green_underline('meh'), 'meh'.encode('utf-8'))


def test_nice_formatting_errors():
    """Make sure you get nice hints if you misspell a formatting wrapper."""
    t = Terminal()
    try:
        t.bold_misspelled('hey')
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
