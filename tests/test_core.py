# -*- coding: utf-8 -*-
"""Core blessed Terminal() tests."""
import StringIO
import sys

from accessories import (
    as_subprocess,
    TestTerminal,
    unicode_cap,
    all_terms
)


def test_export_only_Terminal():
    """Ensure only Terminal instance is exported for import * statements."""
    import blessed
    assert blessed.__all__ == ['Terminal']


def test_null_location(all_terms):
    """Make sure ``location()`` with no args just does position restoration."""
    @as_subprocess
    def child(kind):
        t = TestTerminal(stream=StringIO.StringIO(), force_styling=True)
        with t.location():
            pass
        expected_output = u''.join((unicode_cap('sc'),
                                    unicode_cap('rc')))
        assert (t.stream.getvalue() == expected_output)

    child(all_terms)


def test_null_fileno():
    """Make sure ``Terminal`` works when ``fileno`` is ``None``."""
    @as_subprocess
    def child():
        # This simulates piping output to another program.
        out = StringIO.StringIO()
        out.fileno = None
        t = TestTerminal(stream=out)
        assert (t.save == u'')

    child()


def test_number_of_colors_without_tty():
    """``number_of_colors`` should return 0 when there's no tty."""
    @as_subprocess
    def child_256_nostyle():
        t = TestTerminal(stream=StringIO.StringIO())
        assert (t.number_of_colors == 0)

    @as_subprocess
    def child_256_forcestyle():
        t = TestTerminal(stream=StringIO.StringIO(), force_styling=True)
        assert (t.number_of_colors == 256)

    @as_subprocess
    def child_8_forcestyle():
        t = TestTerminal(kind='ansi', stream=StringIO.StringIO(),
                         force_styling=True)
        assert (t.number_of_colors == 8)

    @as_subprocess
    def child_0_forcestyle():
        t = TestTerminal(kind='vt220', stream=StringIO.StringIO(),
                         force_styling=True)
        assert (t.number_of_colors == 0)

    child_0_forcestyle()
    child_8_forcestyle()
    child_256_forcestyle()
    child_256_nostyle()


def test_number_of_colors_with_tty():
    """``number_of_colors`` should work."""
    @as_subprocess
    def child_256():
        t = TestTerminal()
        assert (t.number_of_colors == 256)

    @as_subprocess
    def child_8():
        t = TestTerminal(kind='ansi')
        assert (t.number_of_colors == 8)

    @as_subprocess
    def child_0():
        t = TestTerminal(kind='vt220')
        assert (t.number_of_colors == 0)

    child_0()
    child_8()
    child_256()


def test_init_descriptor_always_initted(all_terms):
    """Test height and width with non-tty Terminals."""
    @as_subprocess
    def child(kind):
        t = TestTerminal(kind=kind, stream=StringIO.StringIO())
        assert t._init_descriptor == sys.__stdout__.fileno()
        assert (isinstance(t.height, int))
        assert (isinstance(t.width, int))

    child(all_terms)


def test_force_styling_none(all_terms):
    """If ``force_styling=None`` is used, don't ever do styling."""
    @as_subprocess
    def child(kind):
        t = TestTerminal(kind=kind, force_styling=None)
        assert (t.save == '')
        assert (t.color(9) == '')
        assert (t.bold('oi') == 'oi')

    child(all_terms)


def test_setupterm_singleton_issue33():
    """A warning is emitted if a new terminal ``kind`` is used per process."""
    @as_subprocess
    def child():
        import warnings
        warnings.filterwarnings("error", category=UserWarning)

        # instantiate first terminal, of type xterm-256color
        term = TestTerminal(force_styling=True)

        try:
            # a second instantiation raises UserWarning
            term = TestTerminal(kind="vt220", force_styling=True)
            assert not term.is_a_tty or False, 'Should have thrown exception'

        except UserWarning:
            eerr = sys.exc_info()[1]
            assert (err.args[0].startswith(
                    'A terminal of kind "vt220" has been requested')
                    ), err.args[0]
            assert ('a terminal of kind "xterm-256color" will '
                    'continue to be returned' in err.args[0]), err.args[0]
        finally:
            del warnings

    child()


def test_setupterm_invalid_issue39():
    """A warning is emitted if TERM is invalid."""
    # https://bugzilla.mozilla.org/show_bug.cgi?id=878089

    # if TERM is unset, defaults to 'unknown', which should
    # fail to lookup and emit a warning, only.
    @as_subprocess
    def child():
        import warnings
        warnings.filterwarnings("error", category=UserWarning)

        try:
            term = TestTerminal(kind='unknown', force_styling=True)
            assert not term.is_a_tty and not term.does_styling, (
                'Should have thrown exception')
            assert (term.number_of_colors == 0)
        except UserWarning:
            err = sys.exc_info()[1]
            assert err.args[0] == 'Failed to setupterm(kind=unknown)'
        finally:
            del warnings

    child()
