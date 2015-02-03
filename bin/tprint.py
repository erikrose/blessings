#!/usr/bin/env python

import argparse

from blessings import Terminal


parser = argparse.ArgumentParser(
    description='displays argument as specified style')

parser.add_argument('style', type=str, help='style formatter')
parser.add_argument('text', type=str, nargs='+')


term = Terminal()
args = parser.parse_args()

style = getattr(term, args.style)

print(style(' '.join(args.text)))
