#!/usr/bin/env python
import blessings
import sys
"""Human tests; made interesting with a 'video game'
"""

def main():
    play_whack_a_key()

def play_whack_a_key():
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
            if keycode.startswith('KEY_F') and len(keycode) >= len('KEY_F10'):
                # skip F10+
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
        lvl_multiplier = 4
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

if __name__ == '__main__':
    main()
