# -*- coding: utf-8 -*-
"""Tests string formatting functions."""
import curses


def test_parameterizing_string_args(monkeypatch):
    """Test ParameterizingString as a callable """
    from blessed.formatters import (ParameterizingString,
                                    FormattingString)

    # first argument to tparm() is the sequence name, returned as-is;
    # subsequent arguments are usually Integers.
    tparm = lambda *args: u'~'.join(
        arg.decode('latin1') if not num else '%s' % (arg,)
        for num, arg in enumerate(args)).encode('latin1')

    monkeypatch.setattr(curses, 'tparm', tparm)

    # given,
    pstr = ParameterizingString(name=u'cap', attr=u'seqname', normal=u'norm')

    # excersize __new__
    assert pstr._name == u'cap'
    assert pstr._normal == u'norm'
    assert str(pstr) == u'seqname'

    # excersize __call__
    zero = pstr(0)
    assert type(zero) is FormattingString
    assert zero == u'seqname~0'
    assert zero('text') == u'seqname~0textnorm'

    # excersize __call__ with multiple args
    onetwo = pstr(1, 2)
    assert type(onetwo) is FormattingString
    assert onetwo == u'seqname~1~2'
    assert onetwo('text') == u'seqname~1~2textnorm'


def test_parameterizing_string_type_error(monkeypatch):
    """Test ParameterizingString TypeError"""
    from blessed.formatters import (ParameterizingString)

    def tparm_raises_TypeError(*args):
        raise TypeError('custom_err')

    monkeypatch.setattr(curses, 'tparm', tparm_raises_TypeError)

    # given,
    pstr = ParameterizingString(name=u'cap', attr=u'seqname', normal=u'norm')

    # ensure TypeError when given a string raises custom exception
    try:
        pstr('XYZ')
        assert False, "previous call should have raised TypeError"
    except TypeError, err:
        assert (err.args[0] == (  # py3x
            "A native or nonexistent capability template, "
            "'cap' received invalid argument ('XYZ',): "
            "custom_err. You probably misspelled a "
            "formatting call like `bright_red'") or
            err.args[0] == (
                "A native or nonexistent capability template, "
                "u'cap' received invalid argument ('XYZ',): "
                "custom_err. You probably misspelled a "
                "formatting call like `bright_red'"))

    # ensure TypeError when given an integer raises its natural exception
    try:
        pstr(0)
        assert False, "previous call should have raised TypeError"
    except TypeError, err:
        assert err.args[0] == "custom_err"


def test_formattingstring(monkeypatch):
    """Test FormattingString"""
    from blessed.formatters import (FormattingString)

    # given, with arg
    pstr = FormattingString(attr=u'attr', normal=u'norm')

    # excersize __call__,
    assert pstr._normal == u'norm'
    assert str(pstr) == u'attr'
    assert pstr('text') == u'attrtextnorm'

    # given, without arg
    pstr = FormattingString(attr=u'', normal=u'norm')
    assert pstr('text') == u'text'


def test_nullcallablestring(monkeypatch):
    """Test NullCallableString"""
    from blessed.formatters import (NullCallableString)

    # given, with arg
    pstr = NullCallableString()

    # excersize __call__,
    assert str(pstr) == u''
    assert pstr('text') == u'text'
    assert pstr('text', 1) == u''
    assert pstr('text', 'moretext') == u''
    assert pstr(99, 1) == u''
    assert pstr() == u''
    assert pstr(0) == u''
