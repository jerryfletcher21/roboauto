# Roboauto

A [robosats](https://github.com/RoboSats/robosats) command-line interface.

Roboauto aims to be a full robosats client, and an alternative to the main
web client.

Robots are divided in 4 directories: active, pending, paused and inactive.

Active are all the robots that have an active offer not yet taken.

Pending are robots that have pending offers.

Paused are robots that do not currently have an online offer, for example
robots just generated, and robots that have a paused offer.

Inactive are old robots that have a completed offer.

Main command of roboauto is `keep-online`, and it is mainly intended for
makers with multiple offers. To run this action it requires a lightning
node, or a wallet that exposes apis for creating and paying invoices.
After you have generated robots from different coordinators, and created
make offers, `roboauto keep-online` will automatically recreate offers
when they expire, and notify the user when an order is taken, by running
the `message-notification` script. Optionally it will also automatically
pay escrow/send invoice of taken orders.

Examples scripts for simplex and mutt are provided.

To run `roboauto keep-online` in the background it is recommended to
use tmux (or others terminal multiplexers), akin to joinmarket
[yieldgenerator](https://github.com/JoinMarket-Org/joinmarket-clientserver/blob/master/docs/YIELDGENERATOR.md#how-to-run-yield-generator-in-background)

Roboauto can also be used without a lightning node.

## Installation

#### Local (suggested)
```
$ python3 -m venv robo
$ . robo/bin/activate
$ pip install -r requirements.txt
$ pip install .
```

#### Global
```
$ pip install --break-system-packages -r requirements.txt
$ pip install --break-system-packages .
```

## Configuration

Copy `config/config.ini` to `~/.config/roboauto/config.ini` and edit it.

Roboauto can work without a lightning node, but the main function
`keep-online` requires one.

If you have one, create the script `~/.config/roboauto/lightning-node`.

If you want message notifications create the script
`~/.config/roboauto/message-notification`.

Some examples for `lightning-node` and `message-notification` are in
`data/`.

`lightning-node` should support 3 actions:
* check: takes an invoice and an amount and exits with an error status
  if the invoice is not for the correct amount
* pay: takes an invoice and a label, starts the pay command in the
  background and prints his pid
* invoice: takes an amount and a label, create the invoice and prints it
  to stdout

`message-notification` takes an event and a message, and should send a
message notification.

If you use core lightning and simplex for notifications:
```
cp data/lightning-node-core-lightning ~/.config/roboauto/lightning-node
cp data/message-notification-simplex ~/.config/roboauto/message-notification
```

Source completions/roboauto.bash-completion in `~/.bashrc`

If the bash completion package is installed there are better completions in
`create-order`, `recreate-order` and `change-order-expire`

## Usage

#### documentation
```
$ roboauto --help
$ roboauto --verbose-help
```

#### generate robot and order
```
# generate a robot with a coordinator
$ roboauto generate-robot --exp
RobotName

# create the order and lock the bond
$ roboauto create-order RobotName type=sell currency=eur min_amount=300 max_amount=900 payment_method="Instant SEPA" premium=5
RobotName order-id sell eur 300-900 5.00 Instant SEPA Waiting for maker bond
invoice checked successfully
checking if order is bonded...
checking if order is bonded...
RobotName bonded successfully, order is public
RobotName order created successfully

# if you have roboauto keep-online running
# (will add to waiting queue if orders this hour exceed maximum orders per hour)
# $ roboauto create-order --no-bond RobotName type=sell currency=eur min_amount=300 max_amount=900 payment_method="Instant SEPA" premium=5

# print the token if you want to import it in the robosats website
$ roboauto print-token RobotName
************************************
```

#### or import robot from robosats website to roboauto
```
$ roboauto import-robot --exp
insert robot name:
insert token:
```

#### then keep generated and imported robots online (with tmux, it will keep running)
```
# get notified when your offers get taken and recreate them when they expire
# if you want to also pay escrow/send invoice check seconds_pending_order in config.ini
$ roboauto keep-online
# or with more logs
# $ roboauto keep-online --verbosity=1
```

#### take an offer
```
# take a look at the books of all the coordinators
$ roboauto list-offers --all usd "strike"
exp ord-id Active   PeerRobotName            sell usd   8h  3.00   4.00%  -      150     300 00:00:00 Strike
...

# lock the bond
$ roboauto take-order YourRobotName order-id 200
YourRobotName PeerRobotName order-id sell usd 150-300 4.00 Strike Waiting for taker bond
invoice checked successfully
checking if order is bonded...
checking if order is bonded...
YourRobotName bonded successfully, order is taken
YourRobotName order-id taken successfully

# submit the invoice
$ roboauto invoice-send YourRobotName
YourRobotName order-id sell usd 200 4.00 Strike Waiting for trade collateral and buyer invoice
YourRobotName order-id invoice sent successfully
# or pay the escrow if you are the seller
# $ roboauto escrow-pay YourRobotName

# or pay the bond and pay the escrow/send the invoice automatically
# $ roboauto take-order --fully YourRobotName order-id 200

# see what your peer is saying
$ roboauto chat-print YourRobotName
1933/04/05 00:00:00 E PeerRobotName
Hello robot!

# chat with your peer
$ roboauto message-send YourRobotName 'Hello! How can I pay you?'
message sent correctly
now E YourRobotName
Hello! How can I pay you?

...

# check the order status to see if the seller confirmed the payment
$ roboauto order-info --simple YourRobotName | jq -r '.status_string'

# confirm you have received the payment
$ roboauto confirm-send YourRobotName

# rate the robosats coordinator 5 stars!
$ roboauto rate-coordinator 5
YourRobotName order-id sell usd 200 4.00 Strike Sucessful trade
YourRobotName order-id robosats rated 5 stars
```

#### without a lightning node
```
# take and order and print the bond invoice
$ roboauto take-order --no-node YourRobotName order-id 0.01
YourRobotName PeerRobotName order-id sell btc 0.01-0.03 0.40 On-Chain BTC Waiting for taker bond
lnbc...
# pay the bond invoice with an external wallet

## if you are the seller

# get the escrow invoice
$ roboauto escrow-pay --no-node YourRobotName
YourRobotName PeerRobotName order-id sell btc 0.01 0.40 On-Chain BTC Waiting only for seller trade collateral
lnbc...
# pay the escrow invoice with an external wallet

## if you are the buyer

# get the correct invoice amount
# robosats only specifies the full amount, the correct invoice should
# take into account the budget ppm, that should be subtracted from the
# full amount
# roboauto invoice-amount-calculate calculates the correct amount

# with default budget ppm
$ roboauto invoice-amount-calculate "$(roboauto order-info YourRobotName | jq -r '.order_response_json.trade_satoshis')"
correct-invoice-amount

# with specified budget ppm
$ roboauto invoice-amount-calculate --budget-ppm=2000 "$(roboauto order-info YourRobotName | jq -r '.order_response_json.trade_satoshis')"
correct-invoice-amount

# generate the invoice with an external wallet and submit it
$ roboauto invoice-send YourRobotName invoice
YourRobotName PeerRobotName order-id sell btc 0.01 0.40 On-Chain BTC Waiting only for buyer invoice
YourRobotName order-id invoice sent successfully

# if you have used a different budget ppm than the default one above, it
# should also be used here
$ roboauto invoice-send --budget-ppm=2000 YourRobotName invoice
YourRobotName PeerRobotName order-id sell btc 0.01 0.40 On-Chain BTC Waiting only for buyer invoice
YourRobotName order-id invoice sent successfully
```

## Features

- [X] simple apis: info historical limits price ticks
- [X] import robot
- [X] generate robot
- [X] list the books of the coordinators
- [X] robot info
- [X] update stealth option
- [X] order info
- [X] create/recreate order
- [X] cancel order
- [X] take order
- [X] toggle pause for order
- [X] pay escrow, send invoice/address for order
- [X] print chat and send messages
- [X] second/undo confirmations of payments
- [X] start dispute
- [X] submit dispute statement
- [X] rate coordinator
- [X] claim rewards
- [X] keep online orders, recreate them when they expire
- [X] change orders next time they expire
- [X] send message notification when an order is taken
- [X] set a maximum of offer per hour
- [X] different tor circuit for each robot
- [X] automatically pay escrow/send invoice
- [X] handle expired/unpaid invoices
- [X] use without a lightning node
- [X] core lightning
- [X] lnd
- [ ] eclair, ldk, other nodes or wallets with apis
- [ ] other message notification, ex telegram, nostr
- [ ] action like keep-online to use without a lightning node
- [ ] fast chat with websocket

## License

Roboauto is released under the terms of the ISC license.
See [LICENSE](LICENSE) for more details.
