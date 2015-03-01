Growing Pains
=============

In the world of creating interactive and colorful text-mode applications,
there are a surprisingly great number of issues!  Blessings provides an
abstraction for the full terminal capability database.  When you begin
writing interactive applications with the intent of portability across
*any* terminal emulator, you will experience growing pains.  This chapter
intends to guide you through best practices and sensibilities to deal with
such issues.

8 and 16 colors
---------------

**Where 8 and 16 colors are used, they should be assumed to be the
`CGA Color Palette`_**.  Though the actual CGA Color Palette is not
used, their 24-bit true-color values are the closest approximations
across all common (classic and modern) hardware terminals and terminal
emulators.

A recent phenomenon for new emulators, and users of traditional emulators,
is to re-configure the base 16 colors to provide more "washed out" and
color schemes.

Furthermore, we are only recently getting LCD displays of colorspaces that
achieve close approximation to the original video terminals.  Some find these
values uncomfortably intense: this is because their original implementations
were meant to have their contrast and brightness lowered by hardware dials,
whereas today's LCD's typically display well only near full intensity.

Though one cannot *trust*, much less *query* through Terminal I/O routines
the colorspace of the remote terminal, **we can**:

- Trust that a close approximation of the `CGA Color Palette`_ for the base
  16 colors will be displayed for **most** users.

- Trust that users who have made the choice to adjust their palette have made
  the choice to do so, and are able to re-adjust such palettes as necessary
  to accommodate different programs (such as through the use of "Themes").

.. note::

   It has become popular to use dynamic system-wide color palette adjustments
   in software such as `f.lux <https://justgetflux.com/>`_, which adjust the
   system-wide "Color Profile" of the entire graphics display depending on the
   time of day.  One might assume that ``term.blue("text")`` may be
   **completely** invisible to such users during the night!

Where is brown, purple, or grey?
--------------------------------

There are **only 8 color names** on even a 16-color terminal:  The other eight
are "high intensity" versions of the first (in direct series).  The colors
brown, purple, and grey are not named in the first series.  They are, however
available!

- **brown**: **yellow is brown**, only high-intensity yellow
  (``bright_yellow``) is yellow!

- **purple**: **magenta is purple**.  In earlier, 4-bit color spaces, there
  were only black, cyan, magenta, and white of low and high intensity, such
  as found on a common home computer of the time such as the `ZX Spectrum
  <http://en.wikipedia.org/wiki/List_of_8-bit_computer_hardware_palettes#ZX_Spectrum>`_.

  Additional "colors" were only possible through dithering.  The color names
  cyan and magenta on later graphics adapters are carried over from its
  predecessors.  Although cyan remained true to its 3-bit predecessor,
  magenta shifted farther towards blue from red becoming purple, as true red
  was introduced as one of the base 8 colors.

- **grey**: there are actually **three shades of grey** (or American 'gray'),
  though the color attribute named 'grey' does not exist!  In ascending order
  of intensity, they are:

  - ``bold_black``: in lieu of the uselessness of a "intense black", this is
    color is instead mapped to "dark grey".
  - ``white``: white is actually mild compared to the true color 'white': this
    is more officially mapped to "common grey".
  - ``bright_white``: is pure white, ``#ffffff``.



white-on-black
~~~~~~~~~~~~~~

**The default foreground and background of attribute ``normal`` (sgr0) should
also be assumed as *white-on-black**.

For quite some time, the VT-family terminals produced by DEC (and its many
clones), and high-end terminals produced by companies such as Tektronix
dominated the computing world with the default colorscheme of
*green-on-black* and *amber-on-black* monochrome displays: **The inverse
(*black-on-white*) was a non-default configuration**.  Most famously in
"serious business", IBM 3270 clients exclusively used *white/green-on-black*
on both hardware and in software emulators, and is likely a driving factor
of the default *white-on-black* appearance of the first IBM Personal
Computer.

The less common *black-on-white* "ink paper" style of emulators is a valid
concern for those designing terminal interfaces.  The "color scheme" of
*black-on-white* directly conflicts with the intention of `bold is bright`_,
where ``term.bright_red('ATTENTION!')`` may become difficult to read,
as it appears as *pink on white*!

History of ink-paper inspired black-on-white
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Early home computers with color video adapters, such as the Commodore 64
provided *white-on-blue* as their basic video terminal configuration.  One can
only assume such appearances were provided to demonstrate their color
capabilities over competitors (such as the Apple ][).

More common, X11's xterm and the software HyperTerm bundle with MS Windows
provided an "ink on paper" *black-on-white* appearance as their default
configuration.  Two popular emulators continue to supply *black-on-white* by
default to this day: xorg's xterm and Apple's Terminal.app.

.. note:: Windows no longer supplies a terminal emulator: the "command prompt"
   as we know it now uses the msvcrt API routines to interact and does not
   make use of terminal sequences, even ignoring those sequences that MS-DOS
   family of systems previously interpreted through the ANSI.SYS driver,
   though it continues to default to *white-on-black*.

*White-on-black* monochrome displays were **very uncommon** until color
displays became affordable.  Namely due to the technical limitation that
multiple colors were required to display true white on CRT displays!

Meanwhile, color terminals were typically reserved for Home Computers or
Workstations, while hardware terminals continued to be in used in business as
appendages to mainframes and servers for quite some time.  As they were meant
to be low-cost thin clients, few hardware terminals "in the wild" provided
more than one color.  It was only until much later that Workstations and
Terminals met in the economy to provide an emulating terminal as one of
many applications offered on a multi-tasking Workstation.

bold is bright
--------------

**Where Bold is used, it should be assumed to be *Bright***.

Due to the influence of early graphics adapters naturally providing a set
of 8 "low-itensity" and an additional 8 of "high intensity", the term
"bold" for terminals sequences is synonymous with "high intensity" on
almost all circumanstances.

History of bold as "wide stroke"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In typography, the true translation of the term ``bold`` is that a font should
be displayed *with emphasis*.  In classical terms, this would be achieved by
pen "with a wider stroke", normally be re-writing over the same letters.  On a
teletype, this was similarly achieved by writing a character, backspacing,
then repeating the same character in a form called **overstriking**.  To bold
a character, ``C``, one would emit the sequence ``C^HC`` where ``^H`` is
backspace (0x08).  To underline ``C``, one would would emit ``C^H_``.

**Video terminals do not support overstriking**.  Though the mdoc format for
manual pages continue to emit characters for overstriking for the purpose of
bold and underline, translators such as troff or mandoc will instead emit
an appropriate terminal sequence.  In fact, many characters previously
displayable by combining ascii characters on teletypes, such as: ±, ⋲, ≉, ≠,
⩝, ⦵, ⦰, ¥, ¢, or ₭ were delegated to a `code page`_ or lost entirely until
the introduction of multibyte encodings.

Much like "ink paper" influence, "wide stroke" bold was introduced only much
later with the introduction of windowing systems when terminal emulators begin
suppling the alternative option of bold mapped to their font systems such as
TrueType.

clear_eos and setb
~~~~~~~~~~~~~~~~~~

In conclusion, *white-on-black* should be considered the default.  If there is
a need to **enforce** *white-on-black* for terminal clients suspected to be
defaulted as *black-on-white*, one would want to trust that a combination of
``term.home + term.white_on_black + term.clear`` should repaint the entire
emulator's window with the desired effect.

However, this cannot be trusted to all terminal emulators to perform
correctly!  Depending on your audience, you may instead ensure that the
entire screen (including whitespace) is painted using the ``on_black``
mnemonic.

Beware of customized colorschemes
---------------------------------

A recent phenomenon is for users to customize these first 16 colors of their
preferred emulator to colors of their own liking.  Though this has always been
possible with ``~/.XResources``, the introduction of PuTTy and iTerm2 to
interactively adjustment these colors have made this much more common.

This may cause your audience to see your intended interface in a wildly
different form.  Your intended presentation may appear "washed out", or even
mildly unreadable.

Users are certainly free to customize their colors however they like, but it
should be known that displaying ``term.black_on_red("DANGER!")`` to your users
may appear as "grey on pastel red", reducing the intended effect of intensity.

256 colors can avoid customization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The first instinct of a user who aliases ls(1) to ``ls -G`` or ``colorls``,
when faced with the particularly low intensity of the default ``blue`` attribute
is **to adjust their terminal emulator's color scheme for the base 16 colors**.

This is not necessary: the environment variable ``LSCOLORS`` may be redefined
to map an alternative color for blue, or to use ``bright_blue`` in its place.

Furthermore, all common terminal text editors such as emacs or vim may be be
configured with more-accurate "colorschemes" to make use of the 256-color
support found in most modern emulators.  Many readable shades of blue are
available, and many programs that emit such colors can be configured to emit
a higher or lower intensity variant from the full 256 color space through
program configuration.

Monochrome and reverse
----------------------

Note that ``reverse`` takes the current foreground and background colors and
reverses them.  In contrast, the compound formatter ``black_on_red`` would
fail to set the background *or* foreground color on a monochrome display,
resulting in the same stylization as ``normal`` -- it would not appear any
different!

If your userbase consists of monochrome terminals, you may wish to provide
"lightbars" and other such effects using the compound formatter
``red_reverse``.  In the literal sense of "set foreground attribute, then
swap foreground and background", this produces a similar effect on
**both** color and monochrome displays.

For text, very few ``{color}_on_{color}`` formatters are visible with the
base 16 colors, so you should generally wish for ``black_on_{color}``
anyway.  By using ``{color}_reverse`` you may be portable with monochrome
displays as well.

Multibyte Encodings and Code pages
----------------------------------

If you're going to work with terminals or terminal emulators that do not
support multibyte encodings, such as utf-8, you are writing 8-bit bytes
and often incorrectly assuming that the client maps it to the character
that you wish. Some modern terminal emulators, such as SyncTerm, distinctly
reject multibyte encodings, providing **only** direct single
byte-to-character mapping.  For such systems, you must instruct the client
to select the encoding, or use (unique to SyncTerm) sequences to direct
the client to change encodings.

The interpretation of "extended ascii" bytes, such ``ä`` (value 228, 0xE4)
may not be the letter a with umlaut (two dots) placed above.

ISO 2022 (code pages)
~~~~~~~~~~~~~~~~~~~~~

Control Sequence Inducers (CSI) exist to request a terminal to `switch
<http://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h2-Controls-beginning-with-ESC>`_.
code pages, it begins with ``\x1b(``, followed by a character representing
what terminals implemented as a bank of mapping characters.  Legacy
terminals had a "Character ROM" that mapped bytes beyond the ASCII
range to a glyph or character, which made up its "font" or
`code page`_.  A ROM of many code pages could be supplied, and a control
sequence could be used to "switch banks".

For example ``\x1b(U`` on the VGA Linux console switches to the `IBM CP437`_
`code page`_, allowing MS-DOS artwork to be displayed in its natural 8-bit
byte encoding on Linux (most distributions typically do not ship with the
original VGA console any longer).

The literal translation is of this sequence is, "Designate G0 Character Set
(ISO 2022, VT220) to Codepage ``U``" (Thomas E. Dickey).

A terminal that supports both multibyte encodings (utf-8) and legacy 8-bit
code pages (ISO 2022) may instruct the terminal to switch to ISO 2022 in
case it is currently in UTF-8 mode, using sequence ``\x1b%@``.  The literal
translation of this sequence is "Select default character set.  That is ISO
8859-1 (ISO 2022)" (Thomas E. Dickey).

utf-8
~~~~~

XXX

UTF-8 is dangerous for terminal emulators: What if a terminal sequence
contains utf-8 start bytes (...)

XXX

How can one be **assured** that the connecting client is capable of representing
UTF-8?  You can only really know by asking: either by inspecting environment
variables such as ``LANG``, or where not made available, by asking or through
configuration property of your application.  There are some terminal emulators
however, that honor the sequences to instruct a terminal to switch to UTF-8:
``\x1b%G`` activates UTF-8, and ``\x1b%@`` can be used again later to revert
back to ISO 2022 again as encoding/`code page`_ ISO 8859-1.

Meta sends Escape
-----------------

XXX

Backspace sends delete
----------------------

XXX

The misnomer of ANSI
--------------------

When people say 'ANSI Sequence', they are discussing:

- Standard ECMA-48: `Control Functions for Coded Character Sets
  <http://www.ecma-international.org/publications/standards/Ecma-048.htm>`_

- Is a misnomer for `ANSI X3.64
  <http://sydney.edu.au/engineering/it/~tapted/ansi.html>`_ from 1981, when
  the `American National Standards Institute <http://www.ansi.org/>`_ adopted
  the ECMA-48 as standard, which was later withdrawn in 1997 (so in this sense
  it is *not* an ANSI standard).

- The `ANSI.SYS <http://www.kegel.com/nansi/>`_ driver provided in MS-DOS and
  clones.  The popularity of the IBM Personal Computer and MS-DOS of the era,
  and its ability to display colored text further populated the idea that such
  text "is ansi".

- The `IBM CP437`_ `code page`_ (which provided "block art" characters) paired
  with ECMA-48 sequences supported by the MS-DOS ANSI.SYS driver to create
  artwork, known as `ansi art <http://sixteencolors.net/>`_.

  This is purely an American misnomer, because early IBM PC and clones in the
  European nations did not ship with the `IBM CP437`_ `code page`_ by default.

  Many people now mistake the difference between "ascii art" and "ansi art" to
  be whether or not they block art and other characters from the CP437 codepage,
  where even such "ascii art" may contain ECMA-48 color codes!

- The ``ansi`` terminal capability and its many descendants and clones
  in the `terminfo capability database
  <http://invisible-island.net/ncurses/terminfo.src.html>`_.  This is mostly
  due to terminals compatible with SCO UNIX, which was the successor of
  Microsoft's Xenix, likely brining some semblance of the dos ANSI.SYS
  driver capabilities.  SCO UNIX was one of the most successful commercial
  unix systems of its time providing 16 color support.

- `Select Graphics Rendition (SGR) <http://vt100.net/docs/vt510-rm/SGR>`_
  on vt100 clones, which includes the ability to emit many of the common
  sequences in ECMA-48.

- Any sequence started by the `Control-Sequence-Inducer (CSI)
  <http://invisible-island.net/xterm/ctlseqs/ctlseqs.html>`_ is often
  mistakenly termed as an "ANSI Escape Sequence" though not appearing in
  ECMA-48 or interpreted by the ANSI.SYS driver. The adjoining phrase
  "Escape Sequence" is so termed because it follows the ASCII character
  for the escape key (ESC, ``\x1b``).


.. `code page`: http://en.wikipedia.org/wiki/Code_page
.. `IBM CP437`: http://en.wikipedia.org/wiki/Code_page_437
.. `CGA Color Palette`: http://en.wikipedia.org/wiki/Color_Graphics_Adapter#With_an_RGBI_monitor
