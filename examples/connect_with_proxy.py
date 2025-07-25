#!/usr/bin/env python3

"""
Exemple de code montrant comment se connecter à votre routeur via un proxy. Vous pouvez essayer en exécutant :
python3 connect_with_proxy.py http://admin:PASSWORD@192.168.8.1/
"""
from argparse import ArgumentParser

import requests

from huawei_lte_api.Client import Client
from huawei_lte_api.Connection import Connection

parser = ArgumentParser()
parser.add_argument('url', type=str)
parser.add_argument('--username', type=str)
parser.add_argument('--password', type=str)
args = parser.parse_args()

my_custom_session = requests.Session()
my_custom_session.proxies = {
  "http": "http://10.10.1.10:3128",  # Proxy HTTP
  "https": "https://10.10.1.10:1080",  # Proxy HTTPS
}

with my_custom_session, Connection(
        args.url,
        username=args.username,
        password=args.password,
        requests_session=my_custom_session
) as connection:
    client = Client(connection)
    print(client.device.information())
