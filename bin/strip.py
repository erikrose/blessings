#!/usr/bin/env python3
"""Example scrip that strips input of terminal sequences."""
import sys

import blessed


def main():
    """Program entry point."""
    term = blessed.Terminal()
    for line in sys.stdin:
        print(term.strip_seqs(line))


if __name__ == '__main__':
    main()
