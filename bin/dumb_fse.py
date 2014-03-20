#!/usr/bin/env python
# Dumb full-screen editor. It doesn't save anything but to the screen.
#
# "Why wont python let me read memory
#  from screen like assembler? That's dumb." -hellbeard
from __future__ import division
import collections
import functools
from blessed import Terminal

echo_xy = lambda cursor, text: functools.partial(
    print, end='', flush=True)(cursor.term.move(cursor.y, cursor.x) + text)

Cursor = collections.namedtuple('Point', ('y', 'x', 'term'))

above = lambda b, n: Cursor(
    max(0, b.y - n), b.x, b.term)
below = lambda b, n: Cursor(
    min(b.term.height - 1, b.y + n), b.x, b.term)
right_of = lambda b, n: Cursor(
    b.y, min(b.term.width - 1, b.x + n), b.term)
left_of = lambda b, n: Cursor(
    b.y, max(0, b.x - n), b.term)
home = lambda b: Cursor(
    b.y, 1, b.term)

lookup_move = lambda inp_code, b: {
    # arrows
    b.term.KEY_LEFT: left_of(b, 1),
    b.term.KEY_RIGHT: right_of(b, 1),
    b.term.KEY_DOWN: below(b, 1),
    b.term.KEY_UP: above(b, 1),
    # shift + arrows
    b.term.KEY_SLEFT: left_of(b, 10),
    b.term.KEY_SRIGHT: right_of(b, 10),
    b.term.KEY_SDOWN: below(b, 10),
    b.term.KEY_SUP: above(b, 10),
    # carriage return
    b.term.KEY_ENTER: home(below(b, 1)),
    b.term.KEY_HOME: home(b),
}.get(inp_code, b)

term = Terminal()
csr = Cursor(1, 1, term)
with term.hidden_cursor(), term.raw(), term.location(), term.fullscreen():
    inp = None
    while True:
        echo_xy(csr, term.reverse(u' '))
        inp = term.inkey()
        if inp.code == term.KEY_ESCAPE or inp == chr(3):
            break
        echo_xy(csr, u' ')
        n_csr = lookup_move(inp.code, csr)
        if n_csr != csr:
            echo_xy(n_csr, u' ')
            csr = n_csr
        elif not inp.is_sequence:
            echo_xy(csr, inp)
            csr = right_of(csr, 1)
