#!/usr/bin/env python3
"""
Exemple de code montrant comment envoyer un code USSD. Vous pouvez essayer avec :

python3 send_ussd.py http://admin:PASSWORD@192.168.8.1/ *4*0#

Certains codes USSD nécessitent d'en envoyer plusieurs à la suite.
Pour cela, vous pouvez les séparer par des espaces :

python3 send_ussd.py http://admin:PASSWORD@192.168.8.1/ *4# 7 1
"""
import time
import itertools
import threading
from argparse import ArgumentParser
from huawei_lte_api.Client import Client
from huawei_lte_api.Connection import Connection
from huawei_lte_api.enums.client import ResponseEnum


parser = ArgumentParser(
    prog='send_ussd',
    description='Send ussd codes to the router and print the response',
)
parser.add_argument('url', type=str)
parser.add_argument('--username', type=str)
parser.add_argument('--password', type=str)
parser.add_argument(
    'codes', metavar='code',
    type=str, nargs='+', help='USSD code to send'
)
parser.add_argument('--timeout', type=int, default=15)
args = parser.parse_args()
MAX_WAIT_TIME = args.timeout
DONE = False


def animate() -> None:
    """Ajoute une animation de chargement simple pendant l'attente de la réponse."""
    for c in itertools.cycle(['|', '/', '-', '\\']):
        if DONE:
            time.sleep(0.1)
            print('\r                   \r', end='', flush=True)
            return
        print(
            '\r\033[1mUSSD Code Running ' + c + '\033[0m', end='', flush=True
        )
        time.sleep(0.1)


with Connection(
    args.url, username=args.username, password=args.password
) as connection:
    client = Client(connection)
    for code in args.codes:
        DONE, wait_time = [False, 0]

        # Envoyer le code USSD.
        try:
            res = client.ussd.send(code)
            if str(res) == ResponseEnum.OK.value:
                print(f'\033[95m> {code}\033[0m')
                t = threading.Thread(target=animate)
                t.start()
            else:
                print('Error: Cannot send USSD code')
                break
        except Exception as e:
            raise e

        # Attendre la réponse du fournisseur de service.
        while int(client.ussd.status().get('result', '1')) >= 1:
            if wait_time >= MAX_WAIT_TIME:
                DONE = True
                t.join()
                print('Error: Timeout Limit Exceeded')
                break
            wait_time += 1
            time.sleep(1)
        if DONE:
            break
        DONE = True
        t.join()

        # Afficher la réponse.
        response = client.ussd.get()
        if response:
            print(response.get('content', ''))
        else:
            print('Error: Cannot get USSD response')
