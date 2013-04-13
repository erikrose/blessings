"""Automated tests (as opposed to human-verified test patterns) that use the
pexpect module; a pure-python implementation of expect.

This is used to test timed input functions, but can be used to test a wide variaty
of options not available without a pseudo-terminal and spawning a sub-process.
esp. regarding that only a single TERM can be tested per process, as subsequent
calls to setupterm() are non-op.
"""
from __future__ import with_statement  # Make 2.5-compatible
from nose import SkipTest
from nose.tools import eq_, assert_greater_equal, assert_less_equal
from functools import partial
import math
import time
import sys
import os

import pexpect

# TODO; there are helpers for nose.tools for 'n is near z' by so many decimal
# values. Not yet sure what kind of values to use, so just use floor()
# TODO:
# test utf-8 encoding of input (hamsterface)!


def client_inkey(timeout=None, **kwargs):
    """ This is the main entry point for client processes spawned by pexpect.
    this program is re-executed using the current python interpreter with a
    pseudo-terminal, running different variations of client_inkey by cmd line
    parameters.  """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__),os.path.pardir))
    from blessings import Terminal
    TestTerminal = partial(Terminal, kind='xterm-256color')
    t = TestTerminal()
    with t.cbreak():
        # to test 0-second timeout *with* input, we need time for our parent
        # process to make sure stdin has something buffed.
        if timeout <= 0:
            sys.stdout.write('pause')
            sys.stdout.flush()
            time.sleep(1)
        sys.stdout.write('> ')
        sys.stdout.flush ()
        stime = time.time()
        inp = t.inkey(timeout, **kwargs)
        if inp is None:
            sys.stdout.write ('timeout:%1.2f' % (time.time() - stime,))
        else:
            sys.stdout.write ('received:%s|%s|%s|%1.2f' % (
                inp, inp.code, inp.name, time.time() - stime))
        sys.stdout.flush ()
    return 0

def test_inkey_0s_noinput():
    """ Test 0-second inkey without input; None should be returned if no keypress
    is awaiting processing. """
    timeout_0s = pexpect.spawn(sys.executable, [__file__, '-c0'])
    msg, substr = timeout_0s.read().rstrip().split(':', 1)
    eq_(msg, 'pause> timeout')
    eq_(math.floor(float(substr)), 0.0)

def test_inkey_0s_input():
    """ Test 0-second inkey with input; keypress should be immediately returned."""
    timeout_0s = pexpect.spawn(sys.executable, [__file__, '-c0'])
    timeout_0s.send('x')
    timeout_0s.expect('pause')
    timeout_0s.expect('> ')
    msg, substr = timeout_0s.read().rstrip().split(':', 1)
    seq, code, name, elapsed = substr.split('|')
    eq_(msg, 'received')
    eq_(seq, 'x')
    eq_(code, '120')
    eq_(name, 'None')
    eq_(math.floor(float(elapsed)), 0.0)


def test_inkey_0s_input_mbs():
    """ Test 0-second inkey with multibyte input; should decode immediately."""
    SEQ_KEY_DOWN = '\x1b[B'
    # expect 0-second multibyte sequence input to be received in less than 1s,
    timeout_0s = pexpect.spawn(sys.executable, [__file__, '-c0'])
    timeout_0s.send(SEQ_KEY_DOWN)
    timeout_0s.expect('> ')
    msg, substr = timeout_0s.read().rstrip().split(':', 1)
    print msg, substr
    seq, code, name, elapsed = substr.split('|')
    eq_(msg, 'received')
    eq_(seq, SEQ_KEY_DOWN)
    eq_(code, '258')
    eq_(name, 'KEY_DOWN')
    eq_(math.floor(float(elapsed)), 0.0)

def test_inkey_1s_noinput():
    """ Test 1-second inkey without input; None should be returned after 1 second.
    """
    # test 1 second timeout
    timeout_1s = pexpect.spawn(sys.executable, [__file__, '-c1'])
    timeout_1s.expect('> ')
    msg, elapsed = timeout_1s.read().rstrip().split(':', 1)
    eq_(msg, 'timeout')
    eq_(math.floor(float(elapsed)), 1)

def test_inkey_1s_input():
    """ Test 1-second inkey with input; keystroke should be returned immediately.
    """
    # expect 1-second input to be received in less than 1s,
    SEQ_KEY_UP = '\x1b[A'
    timeout_1s = pexpect.spawn(sys.executable, [__file__, '-c1'])
    timeout_1s.expect('> ')
    timeout_1s.send(SEQ_KEY_UP)
    msg, substr = timeout_1s.read().rstrip().split(':', 1)
    seq, code, name, elapsed = substr.split('|')
    eq_(msg, 'received')
    eq_(seq, SEQ_KEY_UP)
    eq_(code, '259')
    eq_(name, 'KEY_UP')
    eq_(math.floor(float(elapsed)), 0.0)

def test_inkey_esc_delay035():
    """ Assert that a single curses.ascii.ESC byte takes at least 0.35 to reply,
    which is the default value for inkey esc_delay= parameter.
    """

    # 0.35 is just a magic number you'll find in many programs such as screen,
    # irssi, BitchX, etc.  There is even a mode "meta sends escape", so that
    # "alt+1" sends "\x1b1", this is used, for instance, by irssi to change
    # windows using the alt modifier.
    #
    # It is because of the escape delay that many implementors chose not to
    # incorperate the escape key at all in their interface. Those who failed to
    # implement the timing necessary for detecting a single escape keystroke
    # but still tried to read application key sequences suffered the poor
    # experience of "locking up the display" when a user pressed escape,
    # until he smashed extra keys.
    #
    # The many skeletons in the closets of unix terminal programming...
    #
    timeout_esc035 = pexpect.spawn(sys.executable, [__file__, '-ce035'])
    timeout_esc035.expect('> ')
    timeout_esc035.send('\x1b')
    msg, substr = timeout_esc035.read().rstrip().split(':', 1)
    seq, code, name, elapsed = substr.split('|')
    eq_(msg, 'received')
    eq_(seq, '\x1b')
    eq_(code, '361')
    eq_(name, 'KEY_ESCAPE')
    assert_greater_equal(float(elapsed), 0.35)
    assert_less_equal(float(elapsed), 0.50)

def test_inkey_esc_delay135():
    """ Assert that a single curses.ascii.ESC byte takes at least 1.35s to reply
    even on a 1-second timeout when esc_delay is set to 1.35.
    """
    # This is what both the user and the application programmer should expect
    # when trying to tailor to 3rd world dial-up. 0.35 is enough for 9600bps
    # terminals, so this compatibility is about extraordinary circumstances.
    timeout_esc035 = pexpect.spawn(sys.executable, [__file__, '-ce135'])
    timeout_esc035.expect('> ')
    timeout_esc035.send('\x1b')
    msg, substr = timeout_esc035.read().rstrip().split(':', 1)
    seq, code, name, elapsed = substr.split('|')
    eq_(msg, 'received')
    eq_(seq, '\x1b')
    eq_(code, '361')
    eq_(name, 'KEY_ESCAPE')
    assert_greater_equal(float(elapsed), 1.35)
    assert_less_equal(float(elapsed), 1.50)

if __name__ == '__main__':
    if len(sys.argv) == 1:
        sys.exit (1)
    if sys.argv[1] == '-cNone':
        sys.exit (client_inkey(timeout=None))
    elif sys.argv[1] == '-c0':
        sys.exit (client_inkey(timeout=0))
    elif sys.argv[1] == '-c-1':
        sys.exit (client_inkey(timeout=-1))
    elif sys.argv[1] == '-c1':
        sys.exit (client_inkey(timeout=1))
    elif sys.argv[1] == '-ce035':
        sys.exit (client_inkey(timeout=1, esc_delay=0.35))
    elif sys.argv[1] == '-ce135':
        sys.exit (client_inkey(timeout=1, esc_delay=1.35))
    else:
        sys.exit (1)
