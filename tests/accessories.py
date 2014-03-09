# -*- coding: utf-8 -*-
"""Accessories for automated tests."""
from __future__ import with_statement
import contextlib
import functools
import traceback
import termios
import codecs
import curses
import sys
import pty
import os

from blessed import Terminal

import pytest

TestTerminal = functools.partial(Terminal, kind='xterm-256color')
SEND_SEMAPHORE = SEMAPHORE = u'SEMAPHORE\n'.encode('ascii')
RECV_SEMAPHORE = u'%s\r\n' % (SEMAPHORE.rstrip(),)
all_xterms_params = ['xterm', 'xterm-256color']
all_terms_params = ['screen', 'vt220', 'rxvt', 'cons25', 'linux', 'ansi']
binpacked_terminal_params = ['avatar', 'kermit']
many_lines_params = [30, 100]
many_columns_params = [5, 30, 150, 500]
if os.environ.get('TRAVIS', None) is None:
    # TRAVIS-CI has a limited type of terminals, the others ...
    all_terms_params.extend(['avatar', 'kermit', 'dtterm', 'wyse520',
                             'minix', 'eterm', 'aixterm', 'putty'])
all_standard_terms_params = (set(all_terms_params) -
                             set(binpacked_terminal_params))


class as_subprocess(object):
    """This helper executes test cases in a child process,
       avoiding a python-internal bug of _curses: setupterm()
       may not be called more than once per process.
    """
    _CHILD_PID = 0
    encoding = 'utf8'

    def __init__(self, func):
        self.func = func

    def __call__(self, *args, **kwargs):
        pid, master_fd = pty.fork()
        if pid is self._CHILD_PID:
            # child process executes function, raises exception
            # if failed, causing a non-zero exit code, using the
            # protected _exit() function of ``os``; to prevent the
            # 'SystemExit' exception from being thrown.
            try:
                self.func(*args, **kwargs)
            except Exception:
                e_type, e_value, e_tb = sys.exc_info()
                o_err = list()
                for line in traceback.format_tb(e_tb):
                    o_err.append(line.rstrip().encode('utf-8'))
                o_err.append(('-=' * 20).encode('ascii'))
                o_err.extend([_exc.rstrip().encode('utf-8') for _exc in
                              traceback.format_exception_only(
                                  e_type, e_value)])
                os.write(sys.__stdout__.fileno(), '\n'.join(o_err))
                os.close(sys.__stdout__.fileno())
                os.close(sys.__stderr__.fileno())
                os.close(sys.__stdin__.fileno())
                os._exit(1)
            else:
                os._exit(0)

        exc_output = unicode()
        decoder = codecs.getincrementaldecoder(self.encoding)()
        while True:
            try:
                _exc = os.read(master_fd, 65534)
            except OSError:
                # linux EOF
                break
            if not _exc:
                # bsd EOF
                break
            exc_output += decoder.decode(_exc)

        # parent process asserts exit code is 0, causing test
        # to fail if child process raised an exception/assertion
        pid, status = os.waitpid(pid, 0)
        os.close(master_fd)

        # Display any output written by child process
        # (esp. any AssertionError exceptions written to stderr).
        exc_output_msg = 'Output in child process:\n%s\n%s\n%s' % (
            u'=' * 40, exc_output, u'=' * 40,)
        assert exc_output == '', exc_output_msg

        # Also test exit status is non-zero
        assert os.WEXITSTATUS(status) == 0


def read_until_semaphore(fd, semaphore=RECV_SEMAPHORE,
                         encoding='utf8', timeout=10):
    """Read file descriptor ``fd`` until ``semaphore`` is found."""
    # note that when a child process writes xyz\\n, the parent
    # process will ready xyz\\r\\n -- this is how pseudo terminals
    # behave; a virtual terminal requires both carriage return and
    # line feed, it is only for convenience that \\n does both.
    #
    # used to ensure the child process is awake and ready, for timing
    # tests; without a semaphore, the time to fork() would be (incorrectly)
    # included in the duration of the test, which can be very length on
    # continuous integration servers such as Travis.
    outp = unicode()
    decoder = codecs.getincrementaldecoder(encoding)()

    while not outp.startswith(semaphore):
        try:
            _exc = os.read(fd, 1)
        except OSError:  # linux EOF
            break
        if not _exc:  # bsd EOF
            break
        outp += decoder.decode(_exc, final=False)
    assert outp.startswith(semaphore), (
        'Semaphore not recv before EOF '
        '(expected %r, got %r)' % (semaphore, outp,))
    return outp[len(semaphore):]


def read_until_eof(fd, encoding='utf8'):
    """Read file descriptor ``fd`` until EOF. Return decoded string."""
    decoder = codecs.getincrementaldecoder(encoding)()
    outp = unicode()
    while True:
        try:
            _exc = os.read(fd, 100)
        except OSError:  # linux EOF
            break
        if not _exc:  # bsd EOF
            break
        outp += decoder.decode(_exc, final=False)
    return outp


@contextlib.contextmanager
def echo_off(fd):
    """Ensure any bytes written to pty fd are not duplicated as output."""
    try:
        attrs = termios.tcgetattr(fd)
        attrs[3] = attrs[3] & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        yield
    finally:
        attrs[3] = attrs[3] | termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, attrs)


def unicode_cap(cap):
    """Return the result of ``tigetstr`` except as Unicode."""
    return curses.tigetstr(cap).decode('latin1')


def unicode_parm(cap, *parms):
    """Return the result of ``tparm(tigetstr())`` except as Unicode."""
    return curses.tparm(curses.tigetstr(cap), *parms).decode('latin1')


@pytest.fixture(params=binpacked_terminal_params)
def unsupported_sequence_terminals(request):
    """Terminals that emit warnings for unsupported sequence-awareness."""
    return request.param


@pytest.fixture(params=all_xterms_params)
def xterms(request):
    """Common kind values for xterm terminals."""
    return request.param


@pytest.fixture(params=all_terms_params)
def all_terms(request):
    """Common kind values for all kinds of terminals."""
    return request.param


@pytest.fixture(params=all_standard_terms_params)
def all_standard_terms(request):
    """Common kind values for all kinds of terminals (except binary-packed)."""
    return request.param


@pytest.fixture(params=many_lines_params)
def many_lines(request):
    """Various number of lines for screen height."""
    return request.param


@pytest.fixture(params=many_columns_params)
def many_columns(request):
    """Various number of columns for screen width."""
    return request.param
