#!/usr/bin/env python
import signal
from blessed import Terminal

term = Terminal()


def on_resize(sig, action):
    print('height={t.height}, width={t.width}'.format(t=term))

signal.signal(signal.SIGWINCH, on_resize)

with term.cbreak():
    while True:
        print(repr(term.inkey(_intr_continue=False)))
