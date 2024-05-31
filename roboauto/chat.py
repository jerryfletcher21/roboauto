#!/usr/bin/env python3

"""chat.py"""

# pylint: disable=C0116 missing-function-docstring

import re

from roboauto.logger import print_out, print_err
from roboauto.date_utils import date_convert_time_zone_and_format_string
from roboauto.utils import \
    json_loads, string_from_multiline_format, string_to_multiline_format, \
    input_ask, file_json_write
from roboauto.order_local import order_robot_get_last_order_id
from roboauto.requests_api import \
    response_is_error, requests_api_chat_post, requests_api_chat
from roboauto.robot import \
    robot_save_peer_gpg_public_key, robot_get_current_fingerprint, \
    robot_get_peer_fingerprint, robot_input_from_argv, robot_var_from_dic
from roboauto.gpg_key import \
    gpg_import_key, gpg_encrypt_sign_message, gpg_decrypt_check_message


def robot_requests_chat(robot_dic):
    multi_false = False, False

    robot_name, _, robot_dir, _, _, token_base91, robot_url = robot_var_from_dic(robot_dic)

    order_id = order_robot_get_last_order_id(robot_dic)
    if order_id is False:
        return multi_false

    chat_response_all = requests_api_chat(token_base91, order_id, robot_url, robot_name)
    if response_is_error(chat_response_all):
        return multi_false
    chat_response = chat_response_all.text
    chat_response_json = json_loads(chat_response)
    if chat_response_json is False:
        print_err(chat_response, end="", error=False, date=False)
        print_err("chat response is not json")
        return multi_false

    bad_request = chat_response_json.get("bad_request", False)
    if bad_request is not False:
        print_err(bad_request, date=False, error=False)
        print_err("getting chat messages")
        return multi_false

    chat_response_file = robot_dir + "/chat-response"
    if not file_json_write(chat_response_file, chat_response_json):
        return multi_false

    peer_public_key = string_from_multiline_format(
        chat_response_json.get("peer_pubkey", False)
    )
    if peer_public_key is False:
        print_err("getting peer public key")
        return multi_false

    peer_fingerprint = gpg_import_key(peer_public_key)
    if peer_fingerprint is False:
        return multi_false

    if robot_save_peer_gpg_public_key(
        robot_dir, peer_public_key, peer_fingerprint, set_default=True
    ) is False:
        return multi_false

    return chat_response, chat_response_json


def message_get(message_date, message_nick, message_print, status_char, signature_error):
    return {
        "date": message_date,
        "nick": message_nick,
        "message": message_print,
        "status": status_char,
        "signature_error": signature_error
    }


def chat_print_single_message(message_dic):
    message_date = message_dic["date"]
    message_nick = message_dic["nick"]
    message_print = message_dic["message"]
    status_char = message_dic["status"]
    signature_error = message_dic["signature_error"]

    print_out(f"{message_date} {status_char} {message_nick}", end="")
    if signature_error is not None:
        print_out(f" {signature_error}", end="")
    print_out("\n", end="")
    print_out(message_print)

    return True


def chat_print_encrypted_messages(robot_dic, chat_response_json):
    robot_name, _, robot_dir, token, _, _, _ = robot_var_from_dic(robot_dic)

    unsorted_messages = chat_response_json.get("messages", False)
    if unsorted_messages is False:
        print_err(chat_response_json, end="", error=False, date=False)
        print_err("chat response does not have messages")
        return False

    messages = sorted(unsorted_messages, key=lambda mex: mex["time"])

    current_fingerprint = robot_get_current_fingerprint(robot_dir)
    if current_fingerprint is False:
        print_err("current key fingerprint is not present")
        return False

    peer_fingerprint = robot_get_peer_fingerprint(robot_dir, error_print=False)
    if peer_fingerprint is False:
        print_err("peer key fingerprint is not present")
        return False

    decrypted_messages = []

    first_message = True
    for message in messages:
        message_enc = string_from_multiline_format(message.get("message", False))
        if message_enc is False:
            print_err("getting encrypted message")
            return False

        message_time = message.get("time", False)
        if message_time is False:
            print_err("getting message time")
            return False

        message_nick = message.get("nick", False)
        if message_nick is False:
            print_err("getting message nick")
            return False

        message_date = date_convert_time_zone_and_format_string(message_time)

        signature_error = None
        if re.match('^#', message_enc) is not None:
            status_char = "N"
            message_print = message_enc
        elif token is not False:
            if message_nick == robot_name:
                signature_fingerprint = current_fingerprint
            else:
                signature_fingerprint = peer_fingerprint
            decrypted_message, signature_error = gpg_decrypt_check_message(
                message_enc, signature_fingerprint, passphrase=token, error_print=False
            )
            if decrypted_message is not False:
                message_print = decrypted_message
            else:
                message_print = "error decrypting message"
            if signature_error is None:
                status_char = "E"
            else:
                status_char = "X"
        else:
            print_err("token is False")
            return False

        if first_message:
            first_message = False
        else:
            print_out("\n", end="")

        message_dic = message_get(
            message_date, message_nick, message_print, status_char, signature_error
        )
        if message_dic is False:
            return False

        if chat_print_single_message(message_dic) is False:
            return False

        decrypted_messages.append(message_dic)

    decrypted_messages_file = robot_dir + "/messages-decrypted"
    if not file_json_write(decrypted_messages_file, decrypted_messages):
        return False

    return True


def robot_send_chat_message(robot_dic, message):
    robot_name, _, robot_dir, token, _, token_base91, robot_url = robot_var_from_dic(robot_dic)

    order_id = order_robot_get_last_order_id(robot_dic)
    if order_id is False:
        return False

    if re.match('^#', message) is not None:
        status_char = "N"
        message_send = message
    else:
        status_char = "E"
        current_fingerprint = robot_get_current_fingerprint(robot_dir)
        if current_fingerprint is False:
            return False

        peer_fingerprint = robot_get_peer_fingerprint(robot_dir, error_print=False)
        if peer_fingerprint is False:
            print_out("peer gpg key not yet present, searching it")
            chat_response, _ = robot_requests_chat(robot_dic)
            if chat_response is False:
                return False
            peer_fingerprint = robot_get_peer_fingerprint(robot_dir)
            if peer_fingerprint is False:
                return False

        message_send = string_to_multiline_format(gpg_encrypt_sign_message(
            message,
            [peer_fingerprint, current_fingerprint],
            current_fingerprint,
            passphrase=token
        ))
        if message_send is False:
            return False

    chat_response_post_all = requests_api_chat_post(
        token_base91, order_id, robot_url, robot_name, message_send
    )
    if response_is_error(chat_response_post_all):
        print_err(f"{robot_name} sending message")
        return False
    chat_response_post = chat_response_post_all.text
    chat_response_post_json = json_loads(chat_response_post)
    if chat_response_post_json is False:
        print_err(chat_response_post, end="\n", error=False, date=False)
        print_err("chat response is not json")
        return False

    print_out("message sent correctly")
    chat_print_single_message(message_get(
        "now", robot_name, message, status_char, None
    ))

    return True


def robot_send_chat_message_argv(argv: list):
    robot_dic, argv = robot_input_from_argv(argv)
    if robot_dic is False:
        return False

    if len(argv) < 1:
        message = input_ask("message: ")
    else:
        message = argv[0]
        argv = argv[1:]

    if message == "":
        print_err("message can not be empty")
        return False

    if not robot_send_chat_message(robot_dic, message):
        return False

    return True
