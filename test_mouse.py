#!/usr/bin/env python
import contextlib
import blessings
import sys
import re
"""Human tests; made interesting with various 'video games' """

def main():
    play_boxes()

MOUSE_REPORT = re.compile('\x1b\[(\d{2});(\d+);(\d+)M')
MOUSE_BUTTON_LEFT = 0
MOUSE_BUTTON_RIGHT = 1
MOUSE_BUTTON_MIDDLE = 2
MOUSE_BUTTON_RELEASED = 3

def play_boxes():
    """
    blessings.inkey does not handle mouse events, as it would require a
    more complex interface than Keystroke, and a terse understanding of
    all of the available mouse modes.

    This example parses mouse reporting events after enabling it with
    the mouse_tracking context manager. It reads button down events for
    the left mouse button, stores the (x, y), and when the button releases,
    draws a bounding box between the two points.
    """
    term = blessings.Terminal()
    def display_down(x, y):
        sys.stdout.write(term.move(term.height -2, 0))
        sys.stdout.write(term.clear_eol)
        sys.stdout.write('LEFT_DOWN %s,%s' % (x, y))
        sys.stdout.write(term.move(term.height -1, 0))
        sys.stdout.write(term.clear_eol)
        sys.stdout.flush()

    def display_release(x, y):
        sys.stdout.write(term.move(term.height -1, 0))
        sys.stdout.write(term.clear_eol)
        sys.stdout.write('LEFT_RELEASE %s,%s' % (x, y))
        sys.stdout.flush()

    def display_box(color, top, botom, left, right):
        sys.stdout.write(term.reverse)
        sys.stdout.write(color)
        for row in range(top, bottom):
            sys.stdout.write(term.move(row, left))
            sys.stdout.write('=' * (right - left))
        sys.stdout.write(term.normal)
        sys.stdout.flush()

    with contextlib.nested(term.cbreak(), term.mouse_tracking()):
        inp = None
        drawing = False
        start_col, start_row = -1, -1
        print term.clear + term.home + 'click and drag to draw a box'
        while True:
            inp = term.inkey(timeout=5.0)
            if inp is None:
                continue
            if inp in (u'q', 'Q'):
                break
            if inp == '\x1b':
                buf = [inp,]
                while inp != u'M':
                    inp = term.inkey(timeout=0.1)
                    if inp is not None:
                        buf.append(inp)
                action = MOUSE_REPORT.match(u''.join(buf))
                assert action is not None, 'Unexpected escape sequence'
                action, x, y = action.groups()
                action = int(action) - 32
                x, y = int(x), int(y)
                if action == MOUSE_BUTTON_LEFT:
                    drawing = True
                    start_col, start_row = x, y
                    display_down(x, y)
                elif action == MOUSE_BUTTON_RELEASED and drawing:
                    drawing = False
                    left, right = min(x, start_col), max(x, start_col)
                    top, bottom = min(y, start_row), max(y, start_row)
                    color = term.color((left + top) % 7)
                    if color == 1: color = 0
                    display_release(x, y)
                    display_box(color, top, bottom, left, right)
                sys.stdout.flush()
        print term.move(term.height - 1, 0)
if __name__ == '__main__':
    main()
