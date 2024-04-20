#!/usr/bin/env python3

"""logger.py"""

# pylint: disable=C0116 missing-function-docstring

import sys

from roboauto.global_state import roboauto_state
from roboauto.date_utils import date_get_current


def print_and_log(arg, end="\n", file=None, terminal=True):
    if terminal:
        if file is None:
            print(arg, end=end)
        else:
            print(arg, end=end, file=file)

    if roboauto_state["should_log"] is True:
        if roboauto_state["logger"] is None:
            try:
                # pylint: disable=R1732 consider-using-with
                roboauto_state["logger"] = open(
                    roboauto_state["log_file"], "a", encoding="utf8"
                )
            except OSError:
                return False

        print(arg, end=end, file=roboauto_state["logger"])

    return True


def print_out(arg, end="\n", date=True, terminal=True):
    string_print = arg

    if roboauto_state["should_log"] and date:
        date_current = date_get_current()
        string_print = "[" + date_current + "] " + string_print

    print_and_log(string_print, end=end, terminal=terminal)


def print_stderr(error_string, arg, end="\n", date=True, error=True, terminal=True):
    string_print = arg

    if error:
        string_print = error_string + string_print

    if roboauto_state["should_log"] and date:
        date_current = date_get_current()
        string_print = "[" + date_current + "] " + string_print

    print_and_log(string_print, end=end, file=sys.stderr, terminal=terminal)


def print_war(arg, end="\n", date=True, error=True, terminal=True):
    print_stderr("warning: ", arg, end=end, date=date, error=error, terminal=terminal)


def print_err(arg, end="\n", date=True, error=True, terminal=True):
    print_stderr("error: ", arg, end=end, date=date, error=error, terminal=terminal)
