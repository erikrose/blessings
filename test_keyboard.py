#!/usr/bin/env python
import contextlib
import blessings
import random
import sys
"""Human tests; made interesting with various 'video games' """

def main():
    play_whack_a_key()
    play_newtons_nightmare()

def play_newtons_nightmare():
    """
    Demonstration of animation and 'movement'.
    Go ahead, make yourself a rouge-like :-)
    """
    term = blessings.Terminal()
    n_balls = 6
    tail_length = 10

    def newball():
        ball = {
            'x': float(random.randint(1, term.width)),
            'y': float(random.randint(1, term.height)),
            'x_velocity': float(random.randint(1, 10)) * .1,
            'y_velocity': float(random.randint(1, 10)) * .1,
            'color': random.randint(1, 7),
            'tail': [],
            }
        ball['x_pos'] = ball['y_pos'] = -1
        return ball

    balls = list()
    for n in range(n_balls):
        balls.append (newball())
    gravity_x = term.width / 2
    gravity_y = term.height / 2
    gravity_xs = 0.0
    gravity_ys = 0.0

    def cycle(ball):
        if ball['x'] > gravity_x:
            ball['x_velocity'] -= 0.01
        else:
            ball['x_velocity'] += 0.01
        if ball['y'] > gravity_y:
            ball['y_velocity'] -= 0.01
        else:
            ball['y_velocity'] += 0.01
        ball['x_velocity'] = max(ball['x_velocity'], -1.0)
        ball['x_velocity'] = min(ball['x_velocity'], 1.0)
        ball['y_velocity'] = max(ball['y_velocity'], -1.0)
        ball['y_velocity'] = min(ball['y_velocity'], 1.0)
        return ball

    def chk_die(balls):
        for ball in balls:
            if (ball['x_pos'] == int(gravity_x)
                    and ball['y_pos'] == int(gravity_y)):
                return True

    def step(balls):
        for ball in balls:
            ball = cycle(ball)
            xv = ball['x_velocity']
            yv = ball['y_velocity']
            ball['x'] += xv
            ball['y'] += yv
        return balls

    def refresh(term, balls):
        # erase last gravity glpyh
        sys.stdout.write('\b ')
        def outofrange(ball):
            return (ball['y_pos'] < 0
                    or ball['y_pos'] > term.height
                    or ball['x_pos'] < 0
                    or ball['x_pos'] > term.width)
        def erase(ball):
            sys.stdout.write(term.move(ball['y_pos'], ball['x_pos']))
            sys.stdout.write(term.color(ball['color']))
            sys.stdout.write('.')
            sys.stdout.write(term.normal)
        def draw(ball):
            sys.stdout.write(term.bold)
            sys.stdout.write(term.color(ball['color']))
            sys.stdout.write(term.move(ball['y_pos'], ball['x_pos']) + u'*')
            sys.stdout.write(term.normal)
        for ball in balls:
            sx = int(ball['x'])
            sy = int(ball['y'])
            if ball['x_pos'] != sx or ball['y_pos'] != sy:
                # erase old ball
                if not outofrange(ball):
                    erase(ball)
                # update position and draw
                ball['x_pos'] = sx
                ball['y_pos'] = sy
                ball['tail'].insert(0, (sy, sx))
                # erase last tail-end
                if len(ball['tail']) > tail_length:
                    y, x = ball['tail'].pop()
                    if (x >= 0 and x <= term.width
                            and y >= 0 and y <= term.height):
                        sys.stdout.write(term.move(y, x))
                        sys.stdout.write(' ')
                if not outofrange(ball):
                    draw(ball)
        sys.stdout.write(term.move(int(gravity_y), int(gravity_x)))
        sys.stdout.write('+')
        sys.stdout.flush()

    delay = 0.05
    score = 0
    with contextlib.nested(term.hidden_cursor(), term.cbreak()):
        sys.stdout.write(term.clear + term.home)
        while True:
            score += 1
            if 0 == (score % 50):
                balls.append (newball())
            delay = max(delay - 0.00001, 0.01)
            balls = step(balls)
            gravity_x += gravity_xs
            gravity_y += gravity_ys
            if gravity_x >= (term.width - 1) or gravity_x <= 1:
                gravity_xs *= -1
            if gravity_y >= (term.height - 1) or gravity_y <= 1:
                gravity_ys *= -1
            refresh(term, balls)
            if chk_die(balls):
                sys.stdout.write(term.move(int(gravity_y), int(gravity_x)))
                for n in range(1, 20):
                    if 0 == (n % 2):
                        sys.stdout.write(term.white_on_red)
                    else:
                        sys.stdout.write(term.red_on_white)
                    sys.stdout.write('*\b')
                    term.inkey(0.1)
                    sys.stdout.flush()
                sys.stdout.write(term.normal)
                break
            inp = term.inkey(delay)
            if inp is None:
                continue
            if inp in (u'q', 'Q'):
                break
            if (inp.code == term.KEY_UP
                    and gravity_y > 1.0
                    and gravity_ys > -1.0):
                gravity_ys -= 0.2
            elif (inp.code == term.KEY_DOWN
                    and gravity_y < (term.height - 1)
                    and gravity_ys < 1.0):
                gravity_ys += 0.2
            elif (inp.code == term.KEY_LEFT
                    and gravity_x > 1.0
                    and gravity_xs > -1.0):
                gravity_xs -= 0.3
            elif (inp.code == term.KEY_RIGHT
                    and gravity_x < (term.width - 1)
                    and gravity_xs < 1.0):
                gravity_xs += 0.3
        print term.move(term.height, 0)
        print 'Your final score was', score
        print 'press any key'
        term.inkey()

def play_whack_a_key():
    """
    Displays all known key capabilities that may match the terminal.
    As each key is pressed on input, it is lit up and points are scored.
    """
    term = blessings.Terminal()
    score = 0
    level = 0
    hit_highbit = 0
    hit_unicode = 0
    dirty = True

    def refresh(term, board, level, score, inp):
        sys.stdout.write(term.home + term.clear)
        level_color = level % 7
        if level_color == 0:
            level_color = 4
        for keycode, attr in board.iteritems():
            sys.stdout.write(term.move(attr['row'], attr['column'])
                    + term.color(level_color)
                    + (term.reverse if attr['hit'] else term.bold)
                    + keycode + term.normal)
        sys.stdout.write(term.move(term.height, 0)
                + 'level: %s score: %s' % (level, score,))
        sys.stdout.write('      %r, %s, %s' % (inp,
            inp.code if inp is not None else None,
            inp.name if inp is not None else None, ))
        sys.stdout.flush()

        sys.stdout.flush()


    def build_gameboard(term):
        column, row = 0, 0
        board = dict()
        spacing = 2
        for keycode in term._keycodes:
            if keycode.startswith('KEY_F') and keycode[-1].isdigit():
                p = 0
                while not keycode[p].isdigit():
                    p += 1
                if int(keycode[p:]) > 24:
                    continue
            if column + len(keycode) + (spacing * 2) >= term.width:
                column = 0
                row += 1
            board[keycode] = { 'column': column,
                               'row': row,
                               'hit': 0,
                               }
            column += len(keycode) + (spacing * 2)
            if row >= term.height:
                sys.stderr.write('cheater!\n')
                break
        return board

    def add_score(score, pts, level):
        lvl_multiplier = 10
        score += pts
        if 0 == (score % (pts * lvl_multiplier)):
            level += 1
        return score, level

    gb = build_gameboard(term)

    with term.cbreak():
        inp = None
        while True:
            if dirty:
                refresh(term, gb, level, score, inp)
                dirty = False
            inp = term.inkey(timeout=5.0)
            dirty = True
            if inp is None:
                dirty = False
                continue
            if inp in (u'q', 'Q'):
                break
            if (inp.is_sequence and
                    inp.name in gb and
                    0 == gb[inp.name]['hit']):
                gb[inp.name]['hit'] = 1
                score, level = add_score (score, 100, level)
            elif inp.code > 128 and inp.code < 256:
                hit_highbit += 1
                if hit_highbit < 5:
                    score, level = add_score (score, 100, level)
            elif not inp.is_sequence and inp.code > 256:
                hit_unicode += 1
                if hit_unicode < 5:
                    score, level = add_score (score, 100, level)
        print term.move(term.height, 0)
        print 'Your final score was', score, 'at level', level
        if hit_highbit > 0:
            print 'You hit', hit_highbit, 'extended ascii characters'
        if hit_unicode > 0:
            print 'You hit', hit_unicode, 'unicode characters'
        print 'press any key'
        term.inkey()

if __name__ == '__main__':
    main()
