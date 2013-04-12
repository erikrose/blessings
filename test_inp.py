#!/usr/bin/env python
import blessings

term = blessings.Terminal()
with term.cbreak():
  while True:
      inp = term.inkey(timeout=1.0)
      if inp is None:
        print 'timeout'
      elif inp.is_sequence:
        if inp.code == term.KEY_HOME:
          print 'no place like it!'
        else:
          print 'input seq: %r, code=%d, name=%s' % (inp, inp.code, inp.name)
      elif inp in (u'q', u'Q'):
          break
      else:
        print "%s? doesn't impress me." % (inp,)
