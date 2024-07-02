#!/usr/bin/env python3

"""subprocess_commands.py"""

# pylint: disable=C0116 missing-function-docstring

import os
import time
import subprocess
import select
import signal

from roboauto.global_state import roboauto_state, roboauto_options
from roboauto.logger import print_out, print_err
from roboauto.utils import file_is_executable, json_dumps, get_uint


def subprocess_run_command(program, error_print=True):
    try:
        process = subprocess.run(program, capture_output=True, check=False, text=True)
    except FileNotFoundError:
        program_name = program[0]
        print_err(f"command {program_name} does not exists")
        return False
    if process.returncode != 0:
        if error_print:
            print_err(process.stderr, end="", error=False, date=False)
        return False

    return process.stdout


def message_notification_send(event, message):
    if not file_is_executable(roboauto_state["message_notification_command"]):
        print_err("message notification command not found, no messages will be sent")
        return False

    message_stdout = subprocess_run_command([
        roboauto_state["message_notification_command"],
        event, message
    ])
    if message_stdout is False:
        print_err(f"sending message {event}")
        return False

    return message_stdout


def subprocess_generate_invoice(invoice_amout, invoice_label):
    invoice_generate_output = subprocess_run_command([
        roboauto_state["lightning_node_command"], "invoice",
        invoice_amout, invoice_label
    ])
    if invoice_generate_output is False:
        print_err("generating the invoice")
        return False

    return invoice_generate_output


def subprocess_readline_with_timeout(process, timeout):
    if not hasattr(process, "stdout"):
        print_err("subprocess does not have stdout")
        return False
    if process.stdout is None:
        print_err("subprocess stdout is None")
        return False
    if not hasattr(process.stdout, "fileno"):
        print_err("subprocess stdout does not have fileno")
        return False
    if not hasattr(process.stdout, "readline"):
        print_err("subprocess stdout does not have readline")
        return False

    ready = select.select([process.stdout.fileno()], [], [], timeout)
    if ready[0]:
        return process.stdout.readline()
    else:
        return None


def subprocess_kill(process):
    if not hasattr(process, "pid"):
        return False

    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    except OSError:
        pass

    return True


def subprocess_pay_invoice_and_check(
    robot_dic, order_id,
    invoice, amount_satoshis_string,
    pay_label, is_paid_function,
    string_checking, string_paid, string_not_paid,
    order_dic_function, failure_function,
    maximum_retries=None
):
    robot_name = robot_dic["name"]

    check_output = subprocess_run_command([
        roboauto_state["lightning_node_command"], "check",
        invoice, amount_satoshis_string
    ])
    if check_output is False:
        print_err(
            "lightning-node check returned false, invoice will not be paid"
        )
        return False
    print_out(check_output, end="", date=False)
    print_out("invoice checked successfully")

    pay_command = [
        roboauto_state["lightning_node_command"], "pay",
        invoice, pay_label
    ]

    subprocess_running = True
    retries_total = 0
    retries_after_failed = 0
    with subprocess.Popen(
        pay_command,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True, text=True
    ) as pay_subprocess:
        read_line = subprocess_readline_with_timeout(pay_subprocess, 4)
        if read_line is None or read_line is False:
            if read_line is None:
                print_err(
                    "process read timeout, check lightning node script, " +
                    "it should print out the subprocess pid"
                )
            subprocess_kill(pay_subprocess)
            return False
        pay_pid = get_uint(read_line.strip())
        if pay_pid is False:
            print_err("pay command did not return a pid")
            subprocess_kill(pay_subprocess)
            return False

        while True:
            if subprocess_running:
                try:
                    os.kill(pay_pid, 0)
                except OSError:
                    _, stderr = pay_subprocess.communicate()
                    print_err(stderr, end="", date=False, error=False)
                    print_err("pay subprocess ended")
                    subprocess_running = False
            if not subprocess_running:
                maximum_retries_after_failed = 4
                if retries_after_failed >= maximum_retries_after_failed:
                    print_err("maximum retries after pay command failed")
                    subprocess_kill(pay_subprocess)
                    return False
                retries_after_failed += 1

            if maximum_retries is not None and retries_total > maximum_retries:
                print_err("maximum retries occured for pay command")
                subprocess_kill(pay_subprocess)
                return False
            retries_total += 1

            print_out(string_checking)

            order_dic = order_dic_function(robot_dic, order_id)
            if order_dic is False or order_dic is None or isinstance(order_dic, str):
                subprocess_kill(pay_subprocess)
                return False

            order_response_json = order_dic["order_response_json"]

            order_status = order_response_json.get("status", False)
            if order_status is False:
                print_err(json_dumps(order_response_json), error=False, date=False)
                print_err(f"getting order_status of {robot_name} {order_id}")
                subprocess_kill(pay_subprocess)
                return False

            if is_paid_function(order_status):
                if not failure_function(order_status):
                    print_out(robot_name + " " + string_paid)
                    return_output = order_dic
                else:
                    print_err(robot_name + " " + string_not_paid)
                    return_output = False

                subprocess_kill(pay_subprocess)
                return return_output

            time.sleep(roboauto_options["pay_interval"])
