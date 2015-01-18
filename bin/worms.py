#!/usr/bin/env python
"""
This is an example application for the 'blessed' Terminal library for python.

It is also an experiment in functional programming.
"""

from __future__ import division, print_function
from collections import namedtuple
from random import randrange
from functools import partial
from blessed import Terminal


# python 2/3 compatibility, provide 'echo' function as an
# alias for "print without newline and flush"
try:
    echo = partial(print, end='', flush=True)
    echo('begin.')
except TypeError:
    # TypeError: 'flush' is an invalid keyword argument for this function
    import sys

    def echo(object):
        sys.stdout.write(u'{}'.format(object))
        sys.stdout.flush()

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
LEFT = (0, -1)
left_of = lambda segment, term: Location(
    y=segment.y,
    x=max(0, segment.x - 1))

RIGHT = (0, 1)
right_of = lambda segment, term: Location(
    y=segment.y,
    x=min(term.width - 1, segment.x + 1))

UP = (-1, 0)
above = lambda segment, term: Location(
    y=max(0, segment.y - 1),
    x=segment.x)

DOWN = (1, 0)
below = lambda segment, term: Location(
    y=min(term.height - 1, segment.y + 1),
    x=segment.x)

# return a direction function that defines the new bearing for any matching
# keyboard code of inp_code; otherwise, the function for the current bearing.
next_bearing = lambda term, inp_code, bearing: {
    term.KEY_LEFT: left_of,
    term.KEY_RIGHT: right_of,
    term.KEY_UP: above,
    term.KEY_DOWN: below,
}.get(inp_code,
      # direction function given the current bearing
      {LEFT: left_of,
       RIGHT: right_of,
       UP: above,
       DOWN: below}[(bearing.y, bearing.x)])


# return new bearing given the movement f(x).
change_bearing = lambda f_mov, segment, term: Direction(
    f_mov(segment, term).y - segment.y,
    f_mov(segment, term).x - segment.x)

# direction-flipped check, reject traveling in opposite direction.
bearing_flipped = lambda dir1, dir2: (
    (0, 0) == (dir1.y + dir2.y, dir1.x + dir2.x)
)

# returns True if `loc' matches any (y, x) coordinates,
# within list `segments' -- such as a list composing a worm.
hit_any = lambda loc, segments: loc in segments

# same as above, but `locations' is also an array of (y, x) coordinates.
hit_vany = lambda locations, segments: any(
    hit_any(loc, segments) for loc in locations)

# returns True if segments are same position (hit detection)
hit = lambda src, dst: src.x == dst.x and src.y == dst.y

# returns new worm_length if current nibble is hit,
next_wormlength = lambda nibble, head, worm_length: (
    worm_length + nibble.value if hit(head, nibble.location)
    else worm_length)

# returns new speed if current nibble is hit,
next_speed = lambda nibble, head, speed, modifier: (
    speed * modifier if hit(head, nibble.location)
    else speed)

# when displaying worm head, show a different glyph for horizontal/vertical
head_glyph = lambda direction: (u':' if direction in (left_of, right_of)
                                else u'"')


# provide the next nibble -- continuously generate a random new nibble so
# long as the current nibble hits any location of the worm, otherwise
# return a nibble of the same location and value as provided.
def next_nibble(term, nibble, head, worm):
    l, v = nibble.location, nibble.value
    while hit_vany([head] + worm, nibble_locations(l, v)):
        l = Location(x=randrange(1, term.width - 1),
                     y=randrange(1, term.height - 1))
        v = nibble.value + 1
    return Nibble(l, v)


# generate an array of locations for the current nibble's location -- a digit
# such as '123' may be hit at 3 different (y, x) coordinates.
def nibble_locations(nibble_location, nibble_value):
    return [Location(x=nibble_location.x + offset,
                     y=nibble_location.y)
            for offset in range(0, 1 + len('{}'.format(nibble_value)) - 1)]


def main():
    term = Terminal()
    worm = [Location(x=term.width // 2, y=term.height // 2)]
    worm_length = 2
    bearing = Direction(*LEFT)
    direction = left_of
    nibble = Nibble(location=worm[0], value=0)
    color_nibble = term.black_on_green
    color_worm = term.yellow_reverse
    color_head = term.red_reverse
    color_bg = term.on_blue
    echo(term.move(1, 1))
    echo(color_bg(term.clear))

    # speed is actually a measure of time; the shorter, the faster.
    speed = 0.1
    modifier = 0.93
    inp = None

    with term.hidden_cursor(), term.key_mode(raw=True) as inkey:
        while inp not in (u'q', u'Q'):

            # delete the tail of the worm at worm_length
            if len(worm) > worm_length:
                echo(term.move(*worm.pop(0)))
                echo(color_bg(u' '))

            # compute head location
            head = worm.pop()

            # check for hit against self; hitting a wall results in the (y, x)
            # location being clipped, -- and death by hitting self (not wall).
            if hit_any(head, worm):
                break

            # get the next nibble, which may be equal to ours unless this
            # nibble has been struck by any portion of our worm body.
            n_nibble = next_nibble(term, nibble, head, worm)

            # get the next worm_length and speed, unless unchanged.
            worm_length = next_wormlength(nibble, head, worm_length)
            speed = next_speed(nibble, head, speed, modifier)

            if n_nibble != nibble:
                # erase the old one, careful to redraw the nibble contents
                # with a worm color for those portions that overlay.
                for (y, x) in nibble_locations(*nibble):
                    echo(term.move(y, x) + (color_worm if (y, x) == head
                                            else color_bg)(u' '))
                    echo(term.normal)
                # and draw the new,
                echo(term.move(*n_nibble.location) + (
                    color_nibble('{}'.format(n_nibble.value))))

            # display new worm head
            echo(term.move(*head) + color_head(head_glyph(direction)))

            # and its old head (now, a body piece)
            if worm:
                echo(term.move(*(worm[-1])))
                echo(color_worm(u' '))
            echo(term.move(*head))

            # wait for keyboard input, which may indicate
            # a new direction (up/down/left/right)
            inp = inkey(speed)

            # discover new direction, given keyboard input and/or bearing.
            nxt_direction = next_bearing(term, inp.code, bearing)

            # discover new bearing, given new direction compared to prev
            nxt_bearing = change_bearing(nxt_direction, head, term)

            # disallow new bearing/direction when flipped (running into
            # oneself, fe. travelling left while traveling right)
            if not bearing_flipped(bearing, nxt_bearing):
                direction = nxt_direction
                bearing = nxt_bearing

            # append the prior `head' onto the worm, then
            # a new `head' for the given direction.
            worm.extend([head, direction(head, term)])

            # re-assign new nibble,
            nibble = n_nibble

    echo(term.normal)
    score = (worm_length - 1) * 100
    echo(u''.join((term.move(term.height - 1, 1), term.normal)))
    echo(u''.join((u'\r\n', u'score: {}'.format(score), u'\r\n')))

if __name__ == '__main__':
    main()
