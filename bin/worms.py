#!/usr/bin/env python
from __future__ import division
from collections import namedtuple
from random import randrange
from functools import partial
from blessed import Terminal

term = Terminal()

# a worm is made of segments, of (y, x) Locations
Location = namedtuple('Point', ('y', 'x',))

# a nibble is a location and a value
Nibble = namedtuple('Nibble', ('location', 'value'))

# A direction is a bearing,
# y=0, x=-1 = move right
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

# returns one of the functions that returns
# a new segment in the direction indicated
# by bearing `d'.
moved = lambda d: (left_of if d.x < 0 else
                   right_of if d.x else
                   above if d.y < 0 else
                   below if d.y else None)

# returns True if segment is found in worm.
hit_any = lambda segment, worm: segment in worm

# returns True if segments are same position
hit = lambda src, dst: src.x == dst.x and src.y == dst.y

# return function that defines the new bearing for any matching
# keyboard code, otherwise the function for the current bearing.
next_bearing = lambda inp_code, bearing: (
    left_of if inp_code == term.KEY_LEFT else
    right_of if inp_code == term.KEY_RIGHT else
    below if inp_code == term.KEY_DOWN else
    above if inp_code == term.KEY_UP else
    moved(bearing)
)

# return new bearing given the movement f(x).
change_bearing = lambda f_mov, segment: Direction(
    f_mov(segment).y - segment.y,
    f_mov(segment).x - segment.x)

echo = partial(print, end='', flush=True)

make_nibble = lambda value: Nibble(
    location=Location(x=randrange(1, term.width - 1),
                      y=randrange(1, term.height - 1)),
    value=value + 1)


def main():
    worm = [Location(x=term.width // 2, y=term.height // 2)]
    worm_length = 2
    bearing = Direction(0, -1)
    nibble = make_nibble(-1)
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

            elif nibble.value is 0 or hit(head, nibble.location):
                # eat,
                value = nibble.value
                worm_length += value
                # create new digit,
                nibble = make_nibble(value)
                # unless it is within our worm ..
                while hit_any(nibble.location, worm):
                    nibble = make_nibble(value)
                # display it
                echo(term.move(*nibble.location))
                echo(color_nibble('{0}'.format(nibble.value)))
                # speed up,
                speed = speed * modifier

            # display new worm head
            echo(term.move(*head))
            echo(color_worm(u'\u2588'))

            # wait for keyboard input, which may indicate
            # a new direction (up/down/left/right)
            inp = term.inkey(speed)
            direction = next_bearing(inp.code, bearing)
            bearing = change_bearing(direction, head)

            # append the prior `head' onto the worm, then
            # a new `head' for the given direction.
            worm.extend([head, direction(head)])

if __name__ == '__main__':
    main()
