from StringIO import StringIO
from curses import tigetstr, tparm
import sys

from nose.tools import eq_

# This tests that __all__ is correct, since we use below everything that should
# be imported:
from blessings import *


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
    t = Terminal(stream=StringIO())
    eq_(t.save, '')


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
    # Let the Terminal grab the actual tty and call setupterm() so things work:
    t = Terminal()

    # Then rip it away, replacing it with something we can check later:
    output = t.stream = StringIO()

    with t.location(3, 4):
        output.write('hi')

    eq_(output.getvalue(), tigetstr('sc') +
                           tparm(tigetstr('cup'), 4, 3) +
                           'hi' +
                           tigetstr('rc'))


def test_null_fileno():
    """Make sure ``Terinal`` works when ``fileno`` is ``None``.

    This simulates piping output to another program.

    """
    out = stream=StringIO()
    out.fileno = None
    t = Terminal(stream=out)
    eq_(t.save, '')
