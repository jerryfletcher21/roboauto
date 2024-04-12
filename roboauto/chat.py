#!/usr/bin/env python3

"""chat.py"""

# pylint: disable=C0116 missing-function-docstring

import re

from roboauto.logger import print_out, print_err
from roboauto.utils import \
    json_loads, string_from_multiline_format, token_get_base91, \
    roboauto_get_coordinator_url, string_to_multiline_format, \
    input_ask, file_json_write, date_to_format_and_time_zone
from roboauto.order_local import order_get_order_dic
from roboauto.requests_api import \
    response_is_error, requests_api_chat_post, requests_api_chat
from roboauto.robot import \
    robot_save_peer_gpg_public_key, robot_get_current_fingerprint, \
    robot_get_peer_fingerprint, robot_input_from_argv
from roboauto.gpg_key import \
    gpg_import_key, gpg_encrypt_sign_message, gpg_decrypt_check_message


def robot_requests_chat(robot_dir, token_base91, robot_url):
    multi_false = False, False

    order_dic = order_get_order_dic(robot_dir, error_print=False)
    if order_dic is False:
        print_err("robot does not have orders saved")
        return multi_false

    order_info = order_dic.get("order_info", False)
    if order_info is False:
        return multi_false

    order_id = order_info.get("order_id", False)
    if order_id is False:
        return multi_false

    chat_response_all = requests_api_chat(token_base91, order_id, robot_url)
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


def message_get(message_date, message_nick, message_print, status_char):
    return {
        "date": message_date,
        "nick": message_nick,
        "message": message_print,
        "status": status_char
    }


def chat_print_single_message(message_dic):
    message_date = message_dic["date"]
    message_nick = message_dic["nick"]
    message_print = message_dic["message"]
    status_char = message_dic["status"]

    print_out(f"{message_date} {status_char} {message_nick}")
    print_out(message_print)

    return True


def chat_print_encrypted_messages(chat_response_json, robot_dir, token):
    unsorted_messages = chat_response_json.get("messages", False)
    if unsorted_messages is False:
        print_err(chat_response_json, end="", error=False, date=False)
        print_err("chat response does not have messages")
        return False

    messages = sorted(unsorted_messages, key=lambda mex: mex["time"])

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

        message_date = date_to_format_and_time_zone(message_time)

        if re.match('^#', message_enc) is not None:
            status_char = "N"
            message_print = message_enc
        elif token is not False:
            decrypted_message = gpg_decrypt_check_message(
                message_enc, passphrase=token, error_print=False
            )
            if decrypted_message is not False:
                status_char = "E"
                message_print = decrypted_message
            else:
                status_char = "X"
                message_print = "error decrypting message"

        if first_message:
            first_message = False
        else:
            print_out("\n", end="")

        message_dic = message_get(
            message_date, message_nick, message_print, status_char
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
    robot_name = robot_dic["name"]
    robot_dir = robot_dic["dir"]
    token = robot_dic["token"]
    token_base91 = token_get_base91(token)
    robot_url = roboauto_get_coordinator_url(robot_dic["coordinator"])

    order_dic = order_get_order_dic(robot_dir)
    if order_dic is False:
        print_err(f"{robot_name} getting order dictionary")
        return False

    order_info = order_dic.get("order_info", False)
    if order_info is False:
        print_err(f"{robot_name} getting order info")
        return False

    order_id = order_info.get("order_id", False)
    if order_id is False:
        print_err(f"{robot_name} getting order id")
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
            chat_response, _ = robot_requests_chat(
                robot_dir, token_base91, robot_url
            )
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
        token_base91, order_id, robot_url, message_send
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
        "now", robot_name, message, status_char
    ))

    return True


def robot_send_chat_message_argv(argv):
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
