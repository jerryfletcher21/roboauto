#!/usr/bin/env python3

"""order_data.py"""

# pylint: disable=C0116 missing-function-docstring


def get_type_string(target, reverse=False):
    types = {
        0: "buy",
        1: "sell",
        2: "all"
    }

    if not reverse:
        if target in types:
            return types[target]
        else:
            return "other"
    else:
        for type_id, type_string in types.items():
            if target == type_string:
                return type_id
        return -1


def get_all_currencies():
    return {
           1: "USD",
           2: "EUR",
           3: "JPY",
           4: "GBP",
           5: "AUD",
           6: "CAD",
           7: "CHF",
           8: "CNY",
           9: "HKD",
          10: "NZD",
          11: "SEK",
          12: "KRW",
          13: "SGD",
          14: "NOK",
          15: "MXN",
          16: "BYN",
          17: "RUB",
          18: "ZAR",
          19: "TRY",
          20: "BRL",
          21: "CLP",
          22: "CZK",
          23: "DKK",
          24: "HRK",
          25: "HUF",
          26: "INR",
          27: "ISK",
          28: "PLN",
          29: "RON",
          30: "ARS",
          31: "VES",
          32: "COP",
          33: "PEN",
          34: "UYU",
          35: "PYG",
          36: "BOB",
          37: "IDR",
          38: "ANG",
          39: "CRC",
          40: "CUP",
          41: "DOP",
          42: "GHS",
          43: "GTQ",
          44: "ILS",
          45: "JMD",
          46: "KES",
          47: "KZT",
          48: "MYR",
          49: "NAD",
          50: "NGN",
          51: "AZN",
          52: "PAB",
          53: "PHP",
          54: "PKR",
          55: "QAR",
          56: "SAR",
          57: "THB",
          58: "TTD",
          59: "VND",
          60: "XOF",
          61: "TWD",
          62: "TZS",
          63: "XAF",
          64: "UAH",
          65: "EGP",
          66: "LKR",
          67: "MAD",
          68: "AED",
          69: "TND",
          70: "ETB",
          71: "GEL",
          72: "UGX",
          73: "RSD",
          74: "IRT",
          75: "BDT",
          76: "ALL",
         300: "XAU",
        1000: "BTC"
    }


def get_currency_string(target, reverse=False):
    currencies = get_all_currencies()
    if not reverse:
        if target in currencies:
            return currencies[target]
        else:
            return "???"
    else:
        for currency_id, currency_string in currencies.items():
            if target.upper() == currency_string:
                return currency_id
        return -1


def get_fiat_payment_methods():
    return [
        "Revolut",
        "CashApp",
        "Zelle",
        "Strike",
        "WeChat Pay",
        "Instant SEPA",
        "Interac e-Transfer",
        "Wise",
        "Venmo",
        "Faster Payments",
        "Paypal Friends & Family",
        "LINE Pay",
        "Rakuten Pay",
        "PromptPay",
        "Bizum",
        "N26",
        "Tinkoff Bank",
        "TWINT",
        "Advcash",
        "BLIK",
        "MBWay",
        "W1TTY",
        "Verse",
        "Paysera",
        "Amazon GiftCard",
        "Ozon GiftCard",
        "AliPay",
        "GPay",
        "Bancolombia",
        "Pago Movil BDV",
        "SPEI",
        "PIX",
        "Pouch.ph",
        "PayID",
        "Paysafe",
        "Sber Bank",
        "PhonePe",
        "OVO",
        "HalCash",
        "Vivid",
        "Google Play Gift Code",
        "Apple Pay",
        "Steam",
        "Nequi",
        "ShakePay",
        "Sinpe",
        "DaviPlata",
        "CoDi",
        "TaiwanPay",
        "MaiCoin",
        "GoPay",
        "MercadoPago",
        "Monero",
        "USDT",
        "L-USDt",
        "Airtel Money",
        "MTN Money",
        "M-Pesa",
        "UPI",
        "MoMo",
        "Tigo Pesa",
        "Cash F2F",
        "Amazon USA GiftCard",
        "Amazon DE GiftCard",
        "Amazon AU GiftCard",
        "Amazon SA GiftCard",
        "Amazon ES GiftCard",
        "Amazon CA GiftCard",
        "Amazon CN GiftCard",
        "Amazon AE GiftCard",
        "Amazon FR GiftCard",
        "Amazon NL GiftCard",
        "Amazon IN GiftCard",
        "Amazon IT GiftCard",
        "Amazon JP GiftCard",
        "Amazon MX GiftCard",
        "Amazon PL GiftCard",
        "Amazon UK GiftCard",
        "Amazon SE GiftCard",
        "Amazon SG GiftCard",
        "Amazon TR GiftCard",
        "Tinkoff QR",
        "SBP",
        "Qiwi"
    ]


def get_swap_payment_methods():
    return [
        "On-Chain BTC",
        "On-Chain w/ Stowaway",
        "RBTC",
        "LBTC",
        "WBTC"
    ]


def get_order_string(target, reverse=False):
    status_dic = {
         0: "Waiting for maker bond",
         1: "Public",
         2: "Paused",
         3: "Waiting for taker bond",
         4: "Cancelled",
         5: "Expired",
         6: "Waiting for trade collateral and buyer invoice",
         7: "Waiting only for seller trade collateral",
         8: "Waiting only for buyer invoice",
         9: "Sending fiat - In chatroom",
        10: "Fiat sent - In chatroom",
        11: "In dispute",
        12: "Collaboratively cancelled",
        13: "Sending satoshis to buyer",
        14: "Sucessful trade",
        15: "Failed lightning network routing",
        16: "Wait for dispute resolution",
        17: "Maker lost dispute",
        18: "Taker lost dispute"
    }

    if not reverse:
        if target in status_dic:
            return status_dic[target]
        else:
            return "other"
    else:
        for status_id, status_string in status_dic.items():
            if target == status_string:
                return status_id
        return -1


def order_is_waiting_maker_bond(data):
    return data == 0


def order_is_public(data):
    return data == 1


def order_is_paused(data):
    return data == 2


def order_is_waiting_taker_bond(data):
    return data == 3


def order_is_cancelled(data):
    return data == 4


def order_is_expired(data):
    return data == 5


def order_is_waiting_seller_buyer(data):
    return data == 6


def order_is_waiting_seller(data):
    return data == 7


def order_is_waiting_buyer(data):
    return data == 8


def order_is_waiting_fiat_sent(data):
    return data == 9


def order_is_fiat_sent(data):
    return data == 10


def order_is_in_dispute(data):
    return data == 11


def order_is_collaborative_cancelled(data):
    return data == 12


def order_is_sending_to_buyer(data):
    return data == 13


def order_is_sucessful(data):
    return data == 14


def order_is_failed_routing(data):
    return data == 15


def order_is_waiting_dispute_resolution(data):
    return data == 16


def order_is_maker_lost_dispute(data):
    return data == 17


def order_is_taker_lost_dispute(data):
    return data == 18


def order_is_pending(data):
    return data in (6, 7, 8, 9, 10, 11, 13, 15, 16)


def order_is_in_chat(data):
    return data in (9, 10)


def order_is_finished(data):
    return data in (4, 12, 14, 17, 18)


def order_is_finished_for_seller(data):
    return data in (13, 15)


# robosats/api/models/order.py
def get_order_expiry_reason_string(target, reverse=False):
    expiry_reasons_dic = {
        0: "Expired not taken",
        1: "Maker bond not locked",
        2: "Escrow not locked",
        3: "Invoice not submitted",
        4: "Neither escrow locked or invoice submitted"
    }

    if not reverse:
        if target in expiry_reasons_dic:
            return expiry_reasons_dic[target]
        else:
            return "other"
    else:
        for expiry_reason, expiry_message in expiry_reasons_dic.items():
            if target == expiry_message:
                return expiry_reason
        return -1


def order_expired_is_not_taken(data):
    return data == 0


def order_expired_is_maker_bond_not_locked(data):
    return data == 1
