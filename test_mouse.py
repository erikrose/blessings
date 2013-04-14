#!/usr/bin/env python
import contextlib
import blessings
import string
import random
import time
import sys
import re
"""Human tests; made interesting with various 'video games' """

def main():
    play_boxes()
    play_pong()

MOUSE_REPORT = re.compile('\x1b\[(\d+);(\d+);(\d+)M')
MOUSE_BUTTON_LEFT = 0
MOUSE_BUTTON_RIGHT = 1
MOUSE_BUTTON_MIDDLE = 2
MOUSE_BUTTON_RELEASED = 3
MOUSE_SCROLL_REVERSE = 64
MOUSE_SCROLL_FORWARD = 65

def get_remaining_inkey(term, buf):
    inp = None
    while inp != u'M':
        inp = term.inkey(timeout=0.1)
        if inp is not None:
            buf.append(inp)
    return ''.join(buf)


def play_pong():
    """
    This example plays a game of pong with the mouse scroll wheel.
    """
    term = blessings.Terminal()
    paddles = {}
    def newball():
        return {
                'x': term.width / 2,
                'y': term.height / 2,
                'xv': random.choice([-1, 1]),
                'yv': 1 - random.randint(1, 20) * .1
                }
    ball = newball()
    paddle_height = max(4, term.height / 7)
    paddle_width = max(2, term.width / 30)
    paddle_ymax = (term.height - paddle_height - 1)
    paddles['left'] = {
            'x': 1,
            'y': float(ball['y']),
            }
    paddles['right'] = {
            'x': term.width - paddle_width,
            'y': ball['y'],
            }
    delay = 0.03
    score_player, score_computer = 0, 0
    difficulty = 0.1


    def draw_score():
        sys.stdout.write(term.move(term.height, paddle_width + 2))
        sys.stdout.write(term.green('score'))
        sys.stdout.write(term.bold_green(': '))
        sys.stdout.write(term.bold_white(str(score_computer)))

        sys.stdout.write(term.move(term.height, term.width - 10))
        sys.stdout.write(term.green('score'))
        sys.stdout.write(term.bold_green(': '))
        sys.stdout.write(term.bold_white(str(score_player)))

    def refresh():
        sys.stdout.write(term.home + term.clear)
        draw_paddle(paddles['left'])
        draw_paddle(paddles['right'])
        draw_score()
        draw_ball(ball)
        sys.stdout.flush()

    def draw_paddle(paddle, erase=False):
        """ Display bounding box from top-left to bottom-right. """
        if not erase:
            sys.stdout.write(term.reverse)
            sys.stdout.write(term.green)
        for row in range(int(paddle['y']),
                int(paddle['y']) + paddle_height + 1):
            sys.stdout.write(term.move(row, paddle['x']))
            sys.stdout.write(' ' * paddle_width)
        sys.stdout.write(term.normal)

    def move_paddle(paddle, y):
#        print y
        dirty = int(paddle['y']) != int(y)
        if dirty:
            draw_paddle(paddle, erase=True)
        paddle['y'] = y
        if dirty:
            draw_paddle(paddle)

    def erase_ball(ball):
        sys.stdout.write(term.move(
            int(ball['y']), int(ball['x'])))
        sys.stdout.write('.')

    def draw_ball(ball):
        y, x = int(ball['y']), int(ball['x'])
        if (y >= 0 and y < term.height and
                x >= 0 and x < term.width):
            sys.stdout.write(term.move(y, x))
            sys.stdout.write(term.bold_white_on_green)
            sys.stdout.write('*')
            sys.stdout.write(term.normal)

    def move_ball(ball):
        x, y = int(ball['x']), int(ball['y'])
        ball['x'] += ball['xv']
        ball['y'] += ball['yv']
        if int(x) != int(ball['x']) or int(y) != int(ball['y']):
            erase_ball({'x': x, 'y': y})
            draw_ball(ball)

    def move_paddle_ai(paddle, ball):
        y, x = ball['y'], ball['x']
        if y > paddle['y'] + paddle_height / 2:
            move_paddle(paddle, paddle['y'] + (min(difficulty, 1)))
        elif y < paddle['y'] + paddle_height / 2:
            move_paddle(paddle, paddle['y'] - (min(difficulty, 1)))

    def bounce_ball(ball):
        if ball['y'] <= 1 and ball['yv'] < 0:
            ball['yv'] *= -1
        elif ball['y'] >= (term.height - 2) and ball['yv'] > 0:
            ball['yv'] *= -1

    def hit_detect(ball, paddles):
        if (ball['y'] >= paddles['right']['y'] and
                ball['y'] <= paddles['right']['y'] + (paddle_height + 1) and
                ball['x'] >= (paddles['right']['x'] - 1) and
                ball['xv'] > 0):
            # bounce off player's paddle
            ball['xv'] *= -1
            diff = ball['y'] - (paddles['right']['y'] + (paddle_height / 2))
            ball['yv'] += diff / paddle_height
        elif (ball['y'] >= paddles['left']['y'] and
                ball['y'] <= paddles['left']['y'] + (paddle_height + 1) and
                ball['x'] <= paddles['left']['x'] + paddle_width and
                ball['xv'] < 0):
            # bounce off computer's paddle
            ball['xv'] *= -1
            diff = ball['y'] - (paddles['left']['y'] + (paddle_height / 2))
            ball['yv'] += diff / paddle_height

    def die_detect(ball):
        # returns 1: die on left, 2: die on right, 0: no death
        if ball['x'] <= 0:
            return 1
        elif ball['x'] >= term.width:
            return 2
        return 0

    with contextlib.nested(
            term.cbreak(),
            term.mouse_tracking(),
            term.hidden_cursor()):
        inp = None
        refresh()
        dirty = time.time()
        term.inkey() # wait for player start
        while score_player < 20 and score_computer < 20:
            if dirty == True:
                refresh()
                dirty = time.time()
            if time.time() - dirty >= delay:
                move_ball(ball)
                bounce_ball(ball)
                hit_detect(ball, paddles)
                move_paddle_ai(paddles['left'], ball)
                dirty = time.time()
            if die_detect(ball) == 1:
                score_player += 1
                ball = newball()
                difficulty += .001
                dirty = True
            elif die_detect(ball) == 2:
                score_computer += 1
                ball = newball()
                dirty = True
            sys.stdout.flush()
            inp = term.inkey(delay)
            if inp in (u'q', 'Q'):
                break
            if inp == '\x1b':
                buf = get_remaining_inkey(term, [inp,])
                action = MOUSE_REPORT.match(buf)
                assert action is not None, (
                        'Unexpected escape sequence: %r' % (buf,))
                action, x, y = action.groups()
                action = int(action) - 32
                x, y = int(x) - 1, int(y) - 1
                if (action == MOUSE_SCROLL_FORWARD
                        and paddles['right']['y'] < paddle_ymax):
                    move_paddle(paddles['right'], paddles['right']['y'] + 1)
                elif (action == MOUSE_SCROLL_REVERSE
                        and paddles['right']['y'] > 0):
                    move_paddle(paddles['right'], paddles['right']['y'] - 1)
                sys.stdout.flush()
        sys.stdout.write(term.move(term.height -1, 0))
        sys.stdout.write(term.clear_eol)
        if score_computer > score_player:
            print 'You lost!'
        else:
            print 'You won!'

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
                buf = get_remaining_inkey(term, [inp,])
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
