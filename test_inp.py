#!/usr/bin/env python
import blessings

term = blessings.Terminal()
with term.cbreak():
  while True:
      print '* wait for 2s'
      inp = term.inkey(timeout=2.0)
      if inp is None:
        print 'timeout'
      elif inp.is_sequence:
        print 'fancy mbs "%s" -> %s' % (inp, inp.name)
        if inp.code == term.KEY_HOME:
          print 'no place like it!'
        else:
          print 'Pressed', repr(inp)
      elif inp in (u'q', u'Q'):
          break
      else:
        print "%s? doesn't impress me." % (inp,)
