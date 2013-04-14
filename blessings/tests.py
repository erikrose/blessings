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

from nose import SkipTest
from nose.tools import eq_, raises

# This tests that __all__ is correct, since we use below everything that should
# be imported:
from blessings import *


TestTerminal = partial(Terminal, kind='xterm-256color')


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
    t = TestTerminal()
    sc = unicode_cap('sc')
    eq_(t.save, sc)
    eq_(t.save, sc)  # Make sure caching doesn't screw it up.


def test_capability_without_tty():
    """Assert capability templates are '' when stream is not a tty."""
    t = TestTerminal(stream=StringIO())
    eq_(t.save, u'')
    eq_(t.red, u'')


def test_capability_with_forced_tty():
    """If we force styling, capabilities had better not (generally) be empty."""
    t = TestTerminal(stream=StringIO(), force_styling=True)
    eq_(t.save, unicode_cap('sc'))


def test_parametrization():
    """Test parametrizing a capability."""
    eq_(TestTerminal().cup(3, 4), unicode_parm('cup', 3, 4))


def height_and_width():
    """Assert that ``height_and_width()`` returns ints."""
    t = TestTerminal()  # kind shouldn't matter.
    assert isinstance(int, t.height)
    assert isinstance(int, t.width)


def test_stream_attr():
    """Make sure Terminal exposes a ``stream`` attribute that defaults to something sane."""
    eq_(Terminal().stream, sys.__stdout__)


def test_location():
    """Make sure ``location()`` does what it claims."""
    t = TestTerminal(stream=StringIO(), force_styling=True)

    with t.location(3, 4):
        t.stream.write(u'hi')

    eq_(t.stream.getvalue(), unicode_cap('sc') +
                             unicode_parm('cup', 4, 3) +
                             u'hi' +
                             unicode_cap('rc'))


def test_horizontal_location():
    """Make sure we can move the cursor horizontally without changing rows."""
    t = TestTerminal(stream=StringIO(), force_styling=True)
    with t.location(x=5):
        pass
    eq_(t.stream.getvalue(), unicode_cap('sc') +
                             unicode_parm('hpa', 5) +
                             unicode_cap('rc'))


def test_null_location():
    """Make sure ``location()`` with no args just does position restoration."""
    t = TestTerminal(stream=StringIO(), force_styling=True)
    with t.location():
        pass
    eq_(t.stream.getvalue(), unicode_cap('sc') +
                             unicode_cap('rc'))


def test_zero_location():
    """Make sure ``location()`` pays attention to 0-valued args."""
    t = TestTerminal(stream=StringIO(), force_styling=True)
    with t.location(0, 0):
        pass
    eq_(t.stream.getvalue(), unicode_cap('sc') +
                             unicode_parm('cup', 0, 0) +
                             unicode_cap('rc'))


def test_null_fileno():
    """Make sure ``Terminal`` works when ``fileno`` is ``None``.

    This simulates piping output to another program.

    """
    out = StringIO()
    out.fileno = None
    t = TestTerminal(stream=out)
    eq_(t.save, u'')


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


def test_callable_numeric_colors():
    """``color(n)`` should return a formatting wrapper."""
    t = TestTerminal()
    eq_(t.color(5)('smoo'), t.magenta + 'smoo' + t.normal)
    eq_(t.color(5)('smoo'), t.color(5) + 'smoo' + t.normal)
    eq_(t.on_color(2)('smoo'), t.on_green + 'smoo' + t.normal)
    eq_(t.on_color(2)('smoo'), t.on_color(2) + 'smoo' + t.normal)

# not sure about this, as python2.5 and 2.6 just
# raise a DepricationWarning, we could check and
# raise a TypeError ourselves for those platforms, or not.
#@raises(TypeError)
#def test_callable_float_typeError():
#    """ floats are illegal as formatting parameters """
#    t = TestTerminal()
#    t.move(1.0, 1.0)

@raises(TypeError)
def test_callable_str_typeError():
    """ strings are illegal as formatting parameters """
    t = TestTerminal()
    t.move('1', '1')

@raises(TypeError)
def test_callable_mixed_typeError():
    """ strings are illegal as formatting parameters """
    t = TestTerminal()
    t.move(1, '1')


def test_null_callable_numeric_colors():
    """``color(n)`` should be a no-op on null terminals."""
    t = TestTerminal(stream=StringIO())
    eq_(t.color(5)('smoo'), 'smoo')
    eq_(t.on_color(6)('smoo'), 'smoo')


def test_naked_color_cap():
    """``term.color`` should return a stringlike capability."""
    t = TestTerminal()
    eq_(t.color + '', t.setaf + '')


def test_number_of_colors_without_tty():
    """``number_of_colors`` should return 0 when there's no tty."""
    # Hypothesis: once setupterm() has run and decided the tty supports 256
    # colors, it never changes its mind.
    raise SkipTest

    t = TestTerminal(stream=StringIO())
    eq_(t.number_of_colors, 0)
    t = TestTerminal(stream=StringIO(), force_styling=True)
    eq_(t.number_of_colors, 0)


def test_number_of_colors_with_tty():
    """``number_of_colors`` should work."""
    t = TestTerminal()
    eq_(t.number_of_colors, 256)


def test_formatting_functions():
    """Test crazy-ass formatting wrappers, both simple and compound."""
    t = TestTerminal()
    # By now, it should be safe to use sugared attributes. Other tests test those.
    eq_(t.bold(u'hi'), t.bold + u'hi' + t.normal)
    eq_(t.green('hi'), t.green + u'hi' + t.normal)  # Plain strs for Python 2.x
    # Test some non-ASCII chars, probably not necessary:
    eq_(t.bold_green(u'boö'), t.bold + t.green + u'boö' + t.normal)
    eq_(t.bold_underline_green_on_red('boo'),
        t.bold + t.underline + t.green + t.on_red + u'boo' + t.normal)
    # Don't spell things like this:
    eq_(t.on_bright_red_bold_bright_green_underline('meh'),
        t.on_bright_red + t.bold + t.bright_green + t.underline + u'meh' + t.normal)


def test_formatting_functions_without_tty():
    """Test crazy-ass formatting wrappers when there's no tty."""
    t = TestTerminal(stream=StringIO())
    eq_(t.bold(u'hi'), u'hi')
    eq_(t.green('hi'), u'hi')
    # Test non-ASCII chars, no longer really necessary:
    eq_(t.bold_green(u'boö'), u'boö')
    eq_(t.bold_underline_green_on_red('loo'), u'loo')
    eq_(t.on_bright_red_bold_bright_green_underline('meh'), u'meh')


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


def test_init_descriptor_always_initted():
    """We should be able to get a height and width even on no-tty Terminals."""
    t = Terminal(stream=StringIO())
    eq_(type(t.height), int)


def test_force_styling_none():
    """If ``force_styling=None`` is passed to the constructor, don't ever do styling."""
    t = TestTerminal(force_styling=None)
    eq_(t.save, '')


def test_is_movement_true():
    """ Test parsers for correctness about sequences that result in cursor movement. """
    t = TestTerminal()
    from blessings import _seqlen, _is_movement
    # reset terminal causes term.clear to happen
    eq_(_is_movement(u'\x1bc'), True)
    eq_(len(u'\x1bc'), _seqlen(u'\x1bc'))
    # dec alignment tube test, could go either way
    eq_(_is_movement(u'\x1b#8'), True)
    eq_(len(u'\x1b#8'), _seqlen(u'\x1b#8'))
    # various movements
    eq_(_is_movement(t.move(98,76)), True)
    eq_(len(t.move(98,76)), _seqlen(t.move(98,76)))
    eq_(_is_movement(t.move(54)), True)
    eq_(len(t.move(54)), _seqlen(t.move(54)))
    eq_(_is_movement(t.cud1), True)
    # cud1 is actually '\n'; although movement,
    # is not a valid 'escape sequence'.
    eq_(0, _seqlen(t.cud1))
    eq_(_is_movement(t.cub1), True)
    # cub1 is actually '\b'; although movement,
    # is not a valid 'escape sequence'.
    eq_(0, _seqlen(t.cub1))
    eq_(_is_movement(t.cuf1), True)
    eq_(len(t.cuf1), _seqlen(t.cuf1))
    eq_(_is_movement(t.cuu1), True)
    eq_(len(t.cuu1), _seqlen(t.cuu1))
    eq_(_is_movement(t.cub(333)), True)
    eq_(len(t.cub(333)), _seqlen(t.cub(333)))
    eq_(_is_movement(t.home), True)
    eq_(len(t.home), _seqlen(t.home))
    # t.clear returns t.home + t.clear_eos
    eq_(_is_movement(t.clear), True)
    for subseq in t.clear.split('\x1b')[1:]:
        eq_(len('\x1b' + subseq), _seqlen('\x1b' + subseq))


def test_is_movement_false():
    """ Test parsers for correctness about sequences that do not move the cursor. """
    from blessings import _seqlen, _is_movement
    t = TestTerminal()
    eq_(_is_movement(u''), False)
    eq_(0, _seqlen(u''))
    # not even a mbs
    eq_(_is_movement(u'xyzzy'), False)
    eq_(0, _seqlen(u'xyzzy'))
    # a single escape is not movement
    eq_(_is_movement(u'\x1b'), False)
    eq_(0, _seqlen(u'\x1b'))
    # negative numbers, though printable as %d, do not result
    # in movement; just garbage. Also not a valid sequence.
    eq_(_is_movement(t.cuf(-333)), False)
    eq_(0, _seqlen(t.cuf(-333)))
    # sgr reset
    eq_(_is_movement(u'\x1b[m'), False)
    eq_(len(u'\x1b[m'), _seqlen(u'\x1b[m'))
    eq_(_is_movement(u'\x1b[s'), False)
    eq_(len(u'\x1b[s'), _seqlen(u'\x1b[s'))
    # fake sgr
    eq_(_is_movement(u'\x1b[01;02m'), False)
    eq_(len(u'\x1b[01;02m'), _seqlen(u'\x1b[01;02m'))
    # shift code page
    eq_(_is_movement(u'\x1b(0'), False)
    eq_(len(u'\x1b(0'), _seqlen(u'\x1b(0'))
    eq_(_is_movement(t.clear_eol), False)
    eq_(len(t.clear_eol), _seqlen(t.clear_eol))
    # various erases don't *move*
    eq_(_is_movement(t.clear_bol), False)
    eq_(len(t.clear_bol), _seqlen(t.clear_bol))
    eq_(_is_movement(t.clear_eos), False)
    eq_(len(t.clear_eos), _seqlen(t.clear_eos))
    eq_(_is_movement(t.bold), False)
    eq_(len(t.bold), _seqlen(t.bold))
    # various paints don't move
    eq_(_is_movement(t.red), False)
    eq_(len(t.red), _seqlen(t.red))
    eq_(_is_movement(t.civis), False)
    eq_(len(t.civis), _seqlen(t.civis))
    eq_(_is_movement(t.cnorm), False)
    # t.cnorm actually returns two sequences on xterm-256color
    for subseq in t.cnorm.split('\x1b')[1:]:
        eq_(len('\x1b' + subseq), _seqlen('\x1b' + subseq))
    eq_(_is_movement(t.cvvis), False)
    eq_(len(t.cvvis), _seqlen(t.cvvis))
    eq_(_is_movement(t.underline), False)
    eq_(len(t.underline), _seqlen(t.underline))
    eq_(_is_movement(t.reverse), False)
    eq_(len(t.reverse), _seqlen(t.reverse))
    # some raw code variations of multi-valued sequences, From
    # Thomas Dickey's vttest's color.c
    # vanilla
    eq_(len(u'\x1b[0m'), _seqlen(u'\x1b[0m'))
    eq_(_is_movement(u'\x1b[0m'), False)
    # bold
    eq_(len(u'\x1b[0;1m'), _seqlen(u'\x1b[0;1m'))
    eq_(_is_movement(u'\x1b[0;1m'), False)
    # bold
    eq_(len(u'\x1b[;1m'), _seqlen(u'\x1b[;1m'))
    eq_(_is_movement(u'\x1b[;1m'), False)
    # underline
    eq_(len(u'\x1b[;4m'), _seqlen(u'\x1b[;4m'))
    eq_(_is_movement(u'\x1b[;4m'), False)
    # blink
    eq_(len(u'\x1b[0;5m'), _seqlen(u'\x1b[0;5m'))
    eq_(_is_movement(u'\x1b[0;5m'), False)
    # bold blink
    eq_(len(u'\x1b[0;5;1m'), _seqlen(u'\x1b[0;5;1m'))
    eq_(_is_movement(u'\x1b[0;5;1m'), False)
    # underline blink
    eq_(len(u'\x1b[0;4;5m'), _seqlen(u'\x1b[0;4;5m'))
    eq_(_is_movement(u'\x1b[0;4;5m'), False)
    # bold underline blink
    eq_(len(u'\x1b[0;1;4;5m'), _seqlen(u'\x1b[0;1;4;5m'))
    eq_(_is_movement(u'\x1b[0;1;4;5m'), False)
    # negative
    eq_(len(u'\x1b[1;4;5;0;7m'), _seqlen(u'\x1b[1;4;5;0;7m'))
    eq_(_is_movement(u'\x1b[1;4;5;0;7m'), False)
    # bold negative
    eq_(len(u'\x1b[0;1;7m'), _seqlen(u'\x1b[0;1;7m'))
    eq_(_is_movement(u'\x1b[0;1;7m'), False)
    # underline negative
    eq_(len(u'\x1b[0;4;7m'), _seqlen(u'\x1b[0;4;7m'))
    eq_(_is_movement(u'\x1b[0;4;7m'), False)
    # bold underline negative
    eq_(len(u'\x1b[0;1;4;7m'), _seqlen(u'\x1b[0;1;4;7m'))
    eq_(_is_movement(u'\x1b[0;1;4;7m'), False)
    # blink negative
    eq_(len(u'\x1b[1;4;;5;7m'), _seqlen(u'\x1b[1;4;;5;7m'))
    eq_(_is_movement(u'\x1b[1;4;;5;7m'), False)
    # bold blink negative
    eq_(len(u'\x1b[0;1;5;7m'), _seqlen(u'\x1b[0;1;5;7m'))
    eq_(_is_movement(u'\x1b[0;1;5;7m'), False)
    # underline blink negative
    eq_(len(u'\x1b[0;4;5;7m'), _seqlen(u'\x1b[0;4;5;7m'))
    eq_(_is_movement(u'\x1b[0;4;5;7m'), False)
    # bold underline blink negative
    eq_(len(u'\x1b[0;1;4;5;7m'), _seqlen(u'\x1b[0;1;4;5;7m'))
    eq_(_is_movement(u'\x1b[0;1;4;5;7m'), False)

def test_ansiwrap():
    t = TestTerminal()
    pgraph = 'pony express, all aboard, choo, choo! ' * 100
    pgraph_colored = u''.join([t.color(n % 7) + t.bold + ch
        for n, ch in enumerate(pgraph)])
    import textwrap
    internal_wrapped = textwrap.wrap(pgraph, t.width, break_long_words=False)
    my_wrapped = t.wrap(pgraph)
    my_wrapped_colored = t.wrap(pgraph_colored)
    # ensure we textwrap ascii the same as python
    eq_(internal_wrapped, my_wrapped)
    # ensure our colored textwrap is the same line length
    eq_(len(internal_wrapped), len(t.wrap(pgraph_colored)))
    # ensure our last line ends at the same column
    from blessings import AnsiString
    eq_(len(internal_wrapped[-1]), AnsiString(my_wrapped_colored[-1]).__len__())

def test_ansistring():
    """Tests functions related to AnsiString class"""
    t = TestTerminal()
    from blessings import AnsiString
    pony_msg = 'pony express, all aboard, choo, choo!'
    pony_len = len(pony_msg)
    pony_colored = u''.join([t.color(n % 7) + ch for n, ch in enumerate(pony_msg)])
    ladjusted = AnsiString(t.ljust(pony_colored))
    radjusted = AnsiString(t.rjust(pony_colored))
    centered = AnsiString(t.center(pony_colored))
    eq_(AnsiString(pony_colored).__len__(), pony_len)
    eq_(AnsiString(centered.strip()).__len__(), pony_len)
    eq_(AnsiString(centered).__len__(), len(pony_msg.center(t.width)))
    eq_(AnsiString(ladjusted.rstrip()).__len__(), pony_len)
    eq_(AnsiString(ladjusted).__len__(), len(pony_msg.ljust(t.width)))
    eq_(AnsiString(radjusted.lstrip()).__len__(), pony_len)
    eq_(AnsiString(radjusted).__len__(), len(pony_msg.rjust(t.width)))

# TODO:
# test _resolve_msb directly
# test cbreak by using bitwise & for expected term settings
# test getch() blocks when kbhit() returns False
# assert do_styling with force_styling args
