Examples
========

A few programs are provided with blessed to help interactively
test the various API features, but also serve as examples of using
blessed to develop applications.

These examples are not distributed with the package -- they are
only available in the github repository.  You can retrieve them
by cloning the repository, or simply downloading the "raw" file
link.

editor.py
---------
https://github.com/jquast/blessed/blob/master/bin/editor.py

This program demonstrates using the directional keys and noecho input
mode. It acts as a (very dumb) fullscreen editor, with support for
saving a file, as well as including a rudimentary line-editor.

keymatrix.py
------------
https://github.com/jquast/blessed/blob/master/bin/keymatrix.py

This program displays a "gameboard" of all known special KEY_NAME
constants. When the key is depressed, it is highlighted, as well
as displaying the unicode sequence, integer code, and friendly-name
of any key pressed.

on_resize.py
------------
https://github.com/jquast/blessed/blob/master/bin/on_resize.py

This program installs a SIGWINCH signal handler, which detects
screen resizes while also polling for input, displaying keypresses.

This demonstrates how a program can react to screen resize events.

progress_bar.py
---------------
https://github.com/jquast/blessed/blob/master/bin/progress_bar.py

This program demonstrates a simple progress bar. All text is written
to stderr, to avoid the need to "flush" or emit newlines, and makes
use of the move_x (hpa) capability to "overstrike" the display a
scrolling progress bar.

.. _tprint.py:

tprint.py
---------
https://github.com/jquast/blessed/blob/master/bin/tprint.py

This program demonstrates how users may customize FormattingString
styles.  Accepting a string style, such as "bold" or "bright_red"
as the first argument, all subsequent arguments are displayed by
the given style.  This shows how a program could provide
user-customizable compound formatting names to configure a program's
styling.

worms.py
--------
https://github.com/jquast/blessed/blob/master/bin/worms.py

This program demonstrates how an interactive game could be made
with blessed.  It is similar to `NIBBLES.BAS
<https://github.com/tangentstorm/tangentlabs/blob/master/qbasic/NIBBLES.BAS>`_
or "snake" of early mobile platforms.

resize.py
---------
https://github.com/jquast/blessed/blob/master/bin/resize.py

This program demonstrates the :meth:`~.get_location` method,
behaving similar to `resize(1)
<https://github.com/joejulian/xterm/blob/master/resize.c>`_
: set environment and terminal settings to current window size.
The window size is determined by eliciting an answerback
sequence from the connecting terminal emulator.

.. _detect-multibyte.py:

detect-multibyte.py
-------------------
https://github.com/jquast/blessed/blob/master/bin/detect-multibyte.py

This program also demonstrates how the :meth:`~.get_location` method
can be used to reliably test whether the terminal emulator of the connecting
client is capable of rendering multibyte characters as a single cell.
