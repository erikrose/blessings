Location
========

If you just want to move and aren't worried about returning, do something like
this:

    >>> print(term.move_xy(10, 1) + 'Hi, mom!')

There are four direct movement capabilities:

``move_xy(x, y)``
  Position cursor at given **x**, **y**.
``move_x(x)``
  Position cursor at column **x**.
``move_y(y)``
  Position cursor at row **y**.
``home``
  Position cursor at (0, 0).

And four relative capabilities:

``move_up`` or ``move_up(y)``
  Position cursor 1 or **y** cells above the current position.
``move_down`` or ``move_down(y)``
  Position cursor 1 or **y** cells below the current position.
``move_left`` or ``move_left(x)``
  Position cursor 1 or **x** cells left of the current position.
``move_right`` or ``move_right(x)``
  Position cursor 1 or **x** cells right of the current position.

.. note:: ``move_down``, if printed directly, is often valued as *\\n*, which additionally returns
    the carriage to column 0, and, depending on your terminal emulator, may also destroy any
    characters to end of line. ``move_down(1)`` is always a safe non-destructive one-notch movement
    in the downward direction.

context manager
---------------

A context manager, :meth:`~.Terminal.location` is provided to move the cursor
to an *(x, y)* screen position and *restore the previous position* on exit:

.. code-block:: python

    with term.location(0, term.height - 1):
        print('Here is the bottom.')

    print('This is back where I came from.')

All parameters to :meth:`~.Terminal.location` are **optional**, we can use
it without any arguments at all to restore the cursor location:

.. code-block:: python

    with term.location():
        print(term.move_xy(1, 1) + 'Hi Mom!' + term.clear_eol)

.. note:: calls to :meth:`~.Terminal.location` may not be nested.

Finding The Cursor
------------------

We can determine the cursor's current position at anytime using :meth:`~.get_location`.

This uses a kind of "answer back" sequence that your terminal emulator responds to.  Because the
terminal may not respond, or may take some time to respond, the :paramref:`~.get_location.timeout`
keyword argument can be specified to return coordinates (-1, -1) after a blocking timeout:

    >>> term.get_location(timeout=5)
    (32, 0)

The return value of :meth:`~.Terminal.get_location` mirrors the arguments of
:meth:`~Terminal.location`:

.. code-block:: python

    with term.location(12, 12):
         val = term.get_location()
    print(val)

Produces output, ``(12, 12)``

Although this wouldn't be suggested in most applications because of its latency, it certainly
simplifies many applications, and, can also be timed, to make a determination of the round-trip
time, perhaps even the bandwidth constraints, of a remote terminal!
