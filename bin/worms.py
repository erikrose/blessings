#!/usr/bin/env python
from __future__ import division
from collections import namedtuple
from random import randrange
from functools import partial
from blessed import Terminal

term = Terminal()

# a worm is a list of (y, x) segments Locations
Location = namedtuple('Point', ('y', 'x',))

# a nibble is a (x,y) Location and value
Nibble = namedtuple('Nibble', ('location', 'value'))

# A direction is a bearing, fe.
# y=0, x=-1 = move right
# y=1, x=0 = move down
Direction = namedtuple('Direction', ('y', 'x',))

# these functions return a new Location instance, given
# the direction indicated by their name.
left_of = lambda s: Location(
    y=s.y, x=max(0, s.x - 1))

right_of = lambda s: Location(
    y=s.y, x=min(term.width - 1, s.x + 1))

below = lambda s: Location(
    y=min(term.height - 1, s.y + 1), x=s.x)

above = lambda s: Location(
    y=max(0, s.y - 1), x=s.x)

# returns a function providing the new location for the
# given `bearing' - a (y,x) difference of (src, dst).
move_given = lambda bearing: {
    (0, -1): left_of,
    (0, 1): right_of,
    (-1, 0): above,
    (1, 0): below}[(bearing.y, bearing.x)]

# return function that defines the new bearing for any matching
# keyboard code, otherwise the function for the current bearing.
next_bearing = lambda inp_code, bearing: {
    term.KEY_LEFT: left_of,
    term.KEY_RIGHT: right_of,
    term.KEY_DOWN: below,
    term.KEY_UP: above,
}.get(inp_code, move_given(bearing))


# return new bearing given the movement f(x).
change_bearing = lambda f_mov, segment: Direction(
    f_mov(segment).y - segment.y,
    f_mov(segment).x - segment.x)

echo = partial(print, end='', flush=True)

# generate a new 'nibble' (number for worm bite)
new_nibble = lambda t, v: Nibble(
    # create new random (x, y) location
    location=Location(x=randrange(1, t.width - 1),
                      y=randrange(1, t.height - 1)),
    # increase given value by 1
    value=v + 1)

# returns True if `loc' matches any (y, x) coordinates,
# within list `segments' -- such as a list composing a worm.
hit_any = lambda loc, segments: loc in segments

# returns True if segments are same position
hit = lambda src, dst: src.x == dst.x and src.y == dst.y

# returns a new Nibble if the current one is hit,
def next_nibble(term, nibble, head):
    return (new_nibble(term, nibble.value)
            if hit(head, nibble.location) else
            nibble)

# returns new worm_length if current nibble is hit,
def next_wormlength(nibble, head, worm_length):
    return (worm_length + nibble.value
            if hit(head, nibble.location) else
            worm_length)

def next_speed(nibble, head, speed, modifier):
    return (speed * modifier
            if hit(head, nibble.location) else
            speed)


#nibble = next_nibble(nibble, head, worm_length)
#worm_length = next_wormlength(nibble, head)


def main():
    worm = [Location(x=term.width // 2, y=term.height // 2)]
    worm_length = 2
    bearing = Direction(0, -1)
    nibble = Nibble(location=worm[0], value=0)
    color_nibble = term.bright_red
    color_worm = term.bright_yellow
    color_bg = term.on_blue
    echo(term.move(1, 1))
    echo(color_bg(term.clear))
    speed = 0.1
    modifier = 0.95

    with term.hidden_cursor(), term.cbreak():
        inp = None
        while inp not in (u'q', u'Q'):

            # delete the tail of the worm at worm_length
            if len(worm) > worm_length:
                echo(term.move(*worm.pop(0)))
                echo(color_bg(u' '))

            head = worm.pop()
            if hit_any(head, worm):
                break

            # check for nibble hit (new Nibble returned).
            n_nibble = next_nibble(term, nibble, head)

            # new worm_length & speed, if hit.
            worm_length = next_wormlength(nibble, head, worm_length)
            speed = next_speed(nibble, head, speed, modifier)

            # display next nibble, if hit
            if n_nibble != nibble:
                echo(term.move(*n_nibble.location))
                echo(color_nibble('{0}'.format(n_nibble.value)))

            # display new worm head each turn, regardless.
            echo(term.move(*head))
            echo(color_worm(u'\u2588'))

            # wait for keyboard input, which may indicate
            # a new direction (up/down/left/right)
            inp = term.inkey(speed)

            # discover new direction, given keyboard input and/or bearing
            direction = next_bearing(inp.code, bearing)

            # discover new bearing, given new direction compared to prev
            bearing = change_bearing(direction, head)

            # append the prior `head' onto the worm, then
            # a new `head' for the given direction.
            worm.extend([head, direction(head)])

            # re-assign new nibble,
            nibble = n_nibble

    score = (worm_length - 1) * 100
    echo(u''.join((term.move(term.height - 1, 1), term.normal)))
    echo(u''.join((u'\r\n', u'score: {}'.format(score), u'\r\n')))

if __name__ == '__main__':
    main()
