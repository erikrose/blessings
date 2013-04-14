#!/usr/bin/env python
import contextlib
import blessings
import string
import sys
import re
"""Human tests; made interesting with various 'video games' """

def main():
    play_boxes()

MOUSE_REPORT = re.compile('\x1b\[(\d+);(\d+);(\d+)M')
MOUSE_BUTTON_LEFT = 0
MOUSE_BUTTON_RIGHT = 1
MOUSE_BUTTON_MIDDLE = 2
MOUSE_BUTTON_RELEASED = 3
MOUSE_SCROLL_REVERSE = 64
MOUSE_SCROLL_FORWARD = 65

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

    def display_scroll(direction, x, y):
        """ Report scrolling at (x,y) position. """
        sys.stdout.write(term.move(term.height -3, 0))
        sys.stdout.write(term.clear_eol)
        sys.stdout.write('scroll %s; %s,%s' % (direction, x, y))
        sys.stdout.write(term.move(term.height -2, 0))
        sys.stdout.write(term.clear_eol)
        sys.stdout.write(term.move(term.height -1, 0))
        sys.stdout.write(term.clear_eol)
        sys.stdout.flush()


    def display_down(x, y):
        """ Report mouse button down (x,y) position. """
        sys.stdout.write(term.move(term.height -3, 0))
        sys.stdout.write(term.clear_eol)
        sys.stdout.write(term.move(term.height -2, 0))
        sys.stdout.write(term.clear_eol)
        sys.stdout.write('button1 down %s,%s' % (x, y))
        sys.stdout.write(term.move(term.height -1, 0))
        sys.stdout.write(term.clear_eol)
        sys.stdout.flush()

    def display_release(x, y):
        """ Report mouse button release (x,y) position. """
        sys.stdout.write(term.move(term.height -3, 0))
        sys.stdout.write(term.clear_eol)
        sys.stdout.write(term.move(term.height -1, 0))
        sys.stdout.write(term.clear_eol)
        sys.stdout.write('button1 release %s,%s' % (x, y))
        sys.stdout.flush()

    def display_box(top, botom, left, right):
        """ Display bounding box from top-left to bottom-right. """
        idx = top + bottom + left + right
        color_value = max(idx % 7, 1)
        width = max(1, (right - left))
        sys.stdout.write(term.reverse)
        sys.stdout.write(term.color(color_value))
        for row in range(top, bottom + 1):
            ucs = string.printable[idx % len(string.printable)]
            sys.stdout.write(term.move(row, left))
            sys.stdout.write(ucs * width)
        sys.stdout.write(term.normal)
        sys.stdout.flush()

    def get_remaining_inkey(buf):
        inp = None
        while inp != u'M':
            inp = term.inkey(timeout=0.1)
            if inp is not None:
                buf.append(inp)
        return ''.join(buf)

    with contextlib.nested(term.cbreak(), term.mouse_tracking()):
        inp = None
        drawing = False
        start_col, start_row = -1, -1
        print term.clear + term.home + 'click and drag to draw a box'
        while True:
            inp = term.inkey()
            if inp in (u'q', 'Q'):
                break
            if inp == '\x1b':
                buf = get_remaining_inkey([inp,])
                action = MOUSE_REPORT.match(buf)
                assert action is not None, (
                        'Unexpected escape sequence: %r' % (buf,))
                action, x, y = action.groups()
                # button is offset by 32, except wheel mice buttons 3 & 4,
                # which are offset by addtiona 64.
                action = int(action) - 32
                # Screen dimensions (1,1) starting.
                x = int(x) - 1
                y = int(y) - 1
                if action == MOUSE_BUTTON_LEFT:
                    drawing = True
                    start_col, start_row = x, y
                    display_down(x, y)
                elif action == MOUSE_BUTTON_RELEASED and drawing:
                    left, right = min(x, start_col), max(x, start_col)
                    top, bottom = min(y, start_row), max(y, start_row)
                    display_release(x, y)
                    display_box(top, bottom, left, right)
                    drawing = False
                elif action == MOUSE_SCROLL_FORWARD:
                    display_scroll('forward', x, y)
                elif action == MOUSE_SCROLL_REVERSE:
                    display_scroll('reverse', x, y)
                sys.stdout.flush()
        print term.move(term.height - 1, 0)
if __name__ == '__main__':
    main()
