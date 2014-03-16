import collections
import curses
import struct


COLORS = set(['black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan',
              'white'])
COMPOUNDABLES = (COLORS |
                 set(['bold', 'underline', 'reverse', 'blink', 'dim', 'italic',
                      'shadow', 'standout', 'subscript', 'superscript']))


def derivative_colors(colors):
    """Return the names of valid color variants, given the base colors."""
    return set([('on_' + c) for c in colors] +
               [('bright_' + c) for c in colors] +
               [('on_bright_' + c) for c in colors])

COLORS.update(derivative_colors(COLORS))


class ParameterizingString(unicode):
    """A Unicode string which can be called to parametrize it as a terminal
    capability"""

    def __new__(cls, attr, normal):
        """Instantiate.

        :arg normal: If non-None, indicates that, once parametrized, this can
            be used as a ``FormattingString``. The value is used as the
            "normal" capability.

        """
        new = unicode.__new__(cls, attr)
        new._normal = normal
        return new

    def __call__(self, *args):
        try:
            # Re-encode the cap, because tparm() takes a bytestring in Python
            # 3. However, appear to be a plain Unicode string otherwise so
            # concats work.
            attr = curses.tparm(self.encode('latin1'), *args).decode('latin1')
            return FormattingString(attr=attr, normal=self._normal)
        except TypeError:
            # If the first non-int (i.e. incorrect) arg was a string, suggest
            # something intelligent:
            if len(args) == 1 and isinstance(args[0], basestring):
                raise TypeError(
                    'A native or nonexistent capability template received '
                    '%r when it was expecting ints. You probably misspelled a '
                    'formatting call like bright_red_on_white(...).' % (args,))
            # Somebody passed a non-string; I don't feel confident
            # guessing what they were trying to do.
            raise


class FormattingString(unicode):
    """A Unicode string which can be called using ``text``, returning a
    new string, ``attr`` + ``text`` + ``normal``::
        >> style = FormattingString(term.bright_blue, term.normal)
        >> style('Big Blue')
        '\x1b[94mBig Blue\x1b(B\x1b[m'
    """
    def __new__(cls, attr, normal):
        new = unicode.__new__(cls, attr)
        new._normal = normal
        return new

    def __call__(self, text):
        """Return string ``text``, joined by specified video attribute,
        (self), and followed by reset attribute sequence (term.normal).
        """
        if len(self):
            return u''.join((self, text, self._normal))
        return text


class NullCallableString(unicode):
    """A dummy callable Unicode to stand in for ``FormattingString`` and
    ``ParameterizingString`` for terminals that cannot perform styling.
    """
    def __new__(cls):
        new = unicode.__new__(cls, u'')
        return new

    def __call__(self, *args):
        """Return a Unicode or whatever you passed in as the first arg
        (hopefully a string of some kind).

        When called with an int as the first arg, return an empty Unicode. An
        int is a good hint that I am a ``ParameterizingString``, as there are
        only about half a dozen string-returning capabilities listed in
        terminfo(5) which accept non-int arguments, they are seldom used.

        When called with a non-int as the first arg (no no args at all), return
        the first arg, acting in place of ``FormattingString`` without
        any attributes.
        """
        if len(args) != 1 or isinstance(args[0], int):
            # I am acting as a ParameterizingString.

            # tparm can take not only ints but also (at least) strings as its
            # 2nd...nth argument. But we don't support callable parameterizing
            # capabilities that take non-ints yet, so we can cheap out here.
            #
            # TODO(erikrose): Go through enough of the motions in the
            # capability resolvers to determine which of 2 special-purpose
            # classes, NullParameterizableString or NullFormattingString,
            # to return, and retire this one.
            #
            # As a NullCallableString, even when provided with a parameter,
            # such as t.color(5), we must also still be callable, fe:
            # >>> t.color(5)('shmoo')
            #
            # is actually simplified result of NullCallable()(), so
            # turtles all the way down: we return another instance.

            return NullCallableString()
        return args[0]  # Should we force even strs in Python 2.x to be
                        # unicodes? No. How would I know what encoding to use
                        # to convert it?

def split_compound(compound):
    """Split a possibly compound format string into segments.

    >>> split_compound('bold_underline_bright_blue_on_red')
    ['bold', 'underline', 'bright_blue', 'on_red']

    """
    merged_segs = []
    # These occur only as prefixes, so they can always be merged:
    mergeable_prefixes = ['on', 'bright', 'on_bright']
    for s in compound.split('_'):
        if merged_segs and merged_segs[-1] in mergeable_prefixes:
            merged_segs[-1] += '_' + s
        else:
            merged_segs.append(s)
    return merged_segs


def resolve_capability(term, attr):
    """Return a Unicode string containing terminal sequence for
    capability (or term_sugar alias) ``attr`` of Terminal instance
    ``term`` by querying curses.tigetstr.

    If the terminal does not have any value for the capability, an empty
    Unicode string is returned.
    """
    code = curses.tigetstr(term._sugar.get(attr, attr))
    if code:
        # Decode sequences as latin1, as they are always 8-bit bytes.
        return code.decode('latin1')
    return u''


def resolve_attribute(term, attr):
    """Resolve a sugary or plain capability name, color, or compound
    formatting function name into a *callable* unicode string
    capability, ``ParameterizingString`` or ``FormattingString``.
    """
    if attr in COLORS:
        return resolve_color(term, attr)

    # Bold, underline, or something that takes no parameters
    if attr in COMPOUNDABLES:
        fmt_attr = resolve_capability(term, attr)
        return FormattingString(fmt_attr, term.normal)

    # A compound formatter, like "bold_green_on_red", recurse
    # into self, joining all returned compound attribute values.
    if all(fmt in COMPOUNDABLES for fmt in split_compound(attr)):
        fmt_attr = u''.join(resolve_attribute(term, ucs)  # RECURSIVE
                            for ucs in split_compound(attr))
        return FormattingString(fmt_attr, term.normal)

    fmt_attr = resolve_capability(term, attr)
    return ParameterizingString(fmt_attr, term.normal)


def resolve_color(term, color):
    """Resolve a color, to callable capability, valid ``color`` capabilities
    are format ``red``, or ``on_right_green``.
    """
    # NOTE(erikrose): Does curses automatically exchange red and blue and cyan
    # and yellow when a terminal supports setf/setb rather than setaf/setab?
    # I'll be blasted if I can find any documentation. The following
    # assumes it does.
    color_cap = (term._background_color if 'on_' in color else
                 term._foreground_color)

    # curses constants go up to only 7, so add an offset to get at the
    # bright colors at 8-15:
    offset = 8 if 'bright_' in color else 0
    base_color = color.rsplit('_', 1)[-1]
    if term.number_of_colors == 0:
        return NullCallableString()

    attr = 'COLOR_%s' % (base_color.upper(),)
    fmt_attr = color_cap(getattr(curses, attr) + offset)
    return FormattingString(fmt_attr, term.normal)
