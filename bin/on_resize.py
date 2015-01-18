#!/usr/bin/env python
"""
This is an example application for the 'blessed' Terminal library for python.

Window size changes are caught by the 'on_resize' function using a traditional
signal handler.  Meanwhile, blocking keyboard input is displayed to stdout.
If a resize event is discovered, an empty string is returned by ``inkey()``
when _intr_continue is False, as it is here.
"""
import signal
from blessed import Terminal

term = Terminal()


def on_resize(sig, action):
    # Its generally not a good idea to put blocking functions (such as print)
    # within a signal handler -- if another SIGWINCH is recieved while this
    # function blocks, an error will occur. In most programs, you'll want to
    # set some kind of 'dirty' flag, perhaps by a Semaphore or global variable.
    print('height={t.height}, width={t.width}\r'.format(t=term))

signal.signal(signal.SIGWINCH, on_resize)

# note that, a terminal driver actually writes '\r\n' when '\n' is found, but
# in raw mode, we are allowed to write directly to the terminal without the
# interference of such driver -- so we must write \r\n ourselves; as python
# will append '\n' to our print statements, we simply end our statements with
# \r.
with term.key_mode(raw=True) as inkey:
    print("press 'X' to stop.\r")
    inp = None
    while inp != 'X':
        inp = inkey(_intr_continue=False)
        print(repr(inp) + u'\r')
