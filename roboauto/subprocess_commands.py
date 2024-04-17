#!/usr/bin/env python3

"""subprocess_commands.py"""

# pylint: disable=C0116 missing-function-docstring

import os
import time
import subprocess
import signal

from roboauto.global_state import roboauto_state, roboauto_options
from roboauto.logger import print_out, print_err
from roboauto.utils import file_is_executable, json_dumps


def subprocess_run_command(program, error_print=True):
    try:
        process = subprocess.run(program, capture_output=True, check=False)
    except FileNotFoundError:
        program_name = program[0]
        print_err(f"command {program_name} does not exists")
        return False
    if process.returncode != 0:
        if error_print:
            print_err(process.stderr.decode(), end="", error=False, date=False)
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

    return message_stdout.decode()


def subprocess_generate_invoice(invoice_amout, invoice_label):
    invoice_generate_output = subprocess_run_command([
        roboauto_state["lightning_node_command"], "invoice",
        invoice_amout, invoice_label
    ])
    if invoice_generate_output is False:
        print_err("generating the invoice")
        return False

    return invoice_generate_output.decode()


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
    print_out(check_output.decode(), end="", date=False)
    print_out("invoice checked successfully")

    pay_command = [
        roboauto_state["lightning_node_command"], "pay",
        invoice, pay_label
    ]

    retries = 0
    with subprocess.Popen(pay_command, start_new_session=True) as pay_subprocess:
        while True:
            if maximum_retries is not None and retries > maximum_retries:
                print_err("maximum retries occured for pay command")
                return False

            print_out(string_checking)

            order_dic = order_dic_function(robot_dic, order_id)
            if order_dic is False or order_dic is None:
                return False

            order_response_json = order_dic["order_response_json"]

            order_status = order_response_json.get("status", False)
            if order_status is False:
                print_err(json_dumps(order_response_json), error=False, date=False)
                print_err(f"getting order_status of {robot_name} {order_id}")
                return False

            if is_paid_function(order_status):
                if not failure_function(order_status):
                    print_out(robot_name + " " + string_paid)
                    return_status = True
                else:
                    print_err(robot_name + " " + string_not_paid)
                    return_status = False
                try:
                    os.killpg(os.getpgid(pay_subprocess.pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass

                return return_status

            retries += 1
            time.sleep(roboauto_options["pay_interval"])

    return False
