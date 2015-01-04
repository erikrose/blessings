#!/usr/bin/env python
"""
This is an example application for the 'blessed' Terminal library for python.

This isn't a real progress bar, just a sample "animated prompt" of sorts
that demonstrates the separate move_x() and move_y() functions, made
mainly to test the `hpa' compatibility for 'screen' terminal type which
fails to provide one, but blessed recognizes that it actually does, and
provides a proxy.
"""
from __future__ import print_function
from blessed import Terminal
import sys


def main():
    term = Terminal()
    assert term.hpa(1) != u'', (
        'Terminal does not support hpa (Horizontal position absolute)')

    col, offset = 1, 1
    with term.cbreak():
        inp = None
        print("press 'X' to stop.")
        sys.stderr.write(term.move(term.height, 0) + u'[')
        sys.stderr.write(term.move_x(term.width) + u']' + term.move_x(1))
        while inp != 'X':
            if col >= (term.width - 2):
                offset = -1
            elif col <= 1:
                offset = 1
            sys.stderr.write(term.move_x(col) + u'.' if offset == -1 else '=')
            col += offset
            sys.stderr.write(term.move_x(col) + u'|\b')
            sys.stderr.flush()
            inp = term.inkey(0.04)
    print()

if __name__ == '__main__':
    main()
