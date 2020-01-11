#!/usr/bin/env python
import math
import colorsys
import time
import sys
import blessed
# todo: if we use unicode shaded blocks, we can do monotone/single color
 
def plasma (term):
    result = ''
    for y in range(term.height):
        for x in range (term.width):
            hue = (4.0
                   + math.sin((x + (time.time() * 5)) / 19.0)
                   + math.sin((y + (time.time() * 5)) / 9.0)
                   + math.sin((x + y) / 25.0)
                   + math.sin(math.sqrt(x**2.0 + y**2.0) / 8.0))
            rgb = colorsys.hsv_to_rgb(hue / 8.0, 1, 1)
            xyz = int(round(rgb[0]*255)), int(round(rgb[1]*255)), int(round(rgb[2]*255))
            result += term.on_color_rgb(*xyz) + ' '
    return result
 
if __name__=="__main__":
    term = blessed.Terminal()
    with term.cbreak(), term.hidden_cursor():
        while True:
            print(term.home + plasma(term), end='')
            sys.stdout.flush()
            inp = term.inkey(timeout=0.2)
            if inp == '\x09':
                term.number_of_colors = {
                    4: 8,
                    8: 16,
                    16: 256,
                    256: 1 << 24,
                    1 << 24: 4,
                }[term.number_of_colors]
