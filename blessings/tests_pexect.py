"""Automated tests (as opposed to human-verified test patterns) that use the
pexpect module; a pure-python implementation of expect.

This is used to test timed input functions, but can be used to test a wide variaty
of options not available without a pseudo-terminal and spawning a sub-process.
esp. regarding that only a single TERM can be tested per process, as subsequent
calls to setupterm() are non-op.
"""
from __future__ import with_statement  # Make 2.5-compatible
from nose import SkipTest
from nose.tools import eq_, assert_greater_equal
from functools import partial
import math
import time
import sys

from blessings import Terminal
import pexpect
TestTerminal = partial(Terminal, kind='xterm-256color')

def client_inkey(timeout=None, **kwargs):
    t = TestTerminal()
    with t.cbreak():
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

def test_inkey():
    SEQ_KEY_UP = '\x1b[A'
    SEQ_KEY_DOWN = '\x1b[B'

    # test 0 second timeout
    timeout_0s = pexpect.spawn(sys.executable, [__file__, '-c0'])
    msg, substr = timeout_0s.read().rstrip().split(':', 1)
    eq_(msg, '> timeout')
    eq_(int(float(substr)), 0)

    # test 1 second timeout
    timeout_1s = pexpect.spawn(sys.executable, [__file__, '-c1'])
    msg, substr = timeout_1s.read().rstrip().split(':', 1)
    eq_(msg, '> timeout')
    eq_(int(float(substr)), 1)

    # expect 0-second input to be received in less than 1s,
    timeout_0s = pexpect.spawn(sys.executable, [__file__, '-c1'])
    timeout_0s.expect('> ')
    timeout_0s.send(SEQ_KEY_DOWN)
    msg, substr = timeout_0s.read().rstrip().split(':', 1)
    seq, code, name, elapsed = substr.split('|')
    eq_(msg, 'received')
    eq_(seq, SEQ_KEY_DOWN)
    eq_(code, '258')
    eq_(name, 'KEY_DOWN')
    eq_(math.floor(float(elapsed)), 0.0)

    # expect 1-second input to be received in less than 1s,
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

    # assert a single 'esc' takes at least 0.35 to reply,
    # which is the default value of inkey's kwargument esc_delay=
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

    # assert esc_delay set to 1.35, like africa dialup might need
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

    # TODO:
    # test utf-8 encoding of input (hamsterface)!

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
