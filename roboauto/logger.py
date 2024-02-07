#!/usr/bin/env python3

# pylint: disable=C0114 missing-module-docstring
# pylint: disable=C0116 missing-function-docstring

import sys
import datetime

from roboauto.global_state import roboauto_options, roboauto_state


def get_date():
    return datetime.datetime.today().strftime(roboauto_options["date_format"])


def print_out(arg, end="\n", date=True):
    if roboauto_state["print_date"] and date:
        date_current = get_date()
        print("[" + date_current + "] ", end="")
    print(arg, end=end)


def print_stderr(error_string, arg, end="\n", date=True, error=True):
    if roboauto_state["print_date"] and date:
        date_current = get_date()
        print("[" + date_current + "] ", end="", file=sys.stderr)
    if error:
        print(error_string, end="", file=sys.stderr)
    print(arg, end=end, file=sys.stderr)


def print_war(arg, end="\n", date=True, error=True):
    print_stderr("warning: ", arg, end, date, error)


def print_err(arg, end="\n", date=True, error=True):
    print_stderr("error: ", arg, end, date, error)
