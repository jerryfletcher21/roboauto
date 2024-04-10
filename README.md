# roboauto

a [robosats](https://github.com/RoboSats/robosats) command-line interface

main function is keep-online, after you have imported one or more robots from
different coordinators, run `roboauto keep-online` to automatically recreate the
orders when they expire, and get notified if the order is taken, running the
message-notification script. an example for simplex is provided

## installation

#### local (preferred)
```
$ python3 -m venv robo
$ . robo/bin/activate
$ pip install -r requirements.txt
$ pip install .
```

#### global
```
$ pip install --break-system-packages -r requirements.txt
$ pip install --break-system-packages .
```

copy config/config.ini in ~/.config/roboauto/ and edit it

create scripts lightning-node and message-notification in ~/.config/roboauto/,
some examples are in data/

if you use core lightning and simplex for notifications:
```
cp data/lightning-node-core-lightning ~/.config/roboauto/lightning-node
cp data/message-notification-simplex ~/.config/roboauto/message-notification
```

source completions/roboauto.bash-completion in ~/.bashrc

## usage

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
# get notified when your offers get taken
$ roboauto keep-online
```

#### take an offer
```
# take a look at the book of all the coordinators
$ roboauto list-offers --all usd "strike"
exp ord-id PeerRobotName            sell usd   8h  3.00   4.00%  -      150     300 00:00:00 Strike
...

# lock the bond
$ roboauto take-order YourRobotName order-id
YourRobotName PeerRobotName order-id sell usd 200 4.00 Strike Waiting for taker bond
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
# roboauto escrow-pay YourRobotName

# see what your peer is saying
$ roboauto chat-print YourRobotName
1933/04/05 00:00:00 E PeerRobotName
Hello robot!

# chat with your peer
$ roboauto message-send YourRobotName 'how can I pay you?'
message sent correctly
now E YourRobotName
how can I pay you?

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

## roadmap

* handle rewards
* fast chat with websocket

## license

roboauto is released under the terms of the ISC license.
see [LICENSE](LICENSE) for more details.
