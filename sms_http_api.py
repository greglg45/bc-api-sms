#!/usr/bin/env python3
"""
Expose une API HTTP simple pour envoyer des SMS.

Exemple d'utilisation :
python3 sms_http_api.py http://192.168.8.1/ \
    --username admin --password PASSWORD \
    --host 0.0.0.0 --port 80
# Puis envoyez un SMS avec curl :
# curl -X POST -H "Content-Type: application/json" \
#      -d '{"to": ["+420123456789"], "from": "+420987654321", "text": "Hello"}' http://0.0.0.0:80/sms
Chaque requête est également enregistrée dans une base SQLite. Le chemin de cette base peut
être défini avec l'option ``--db`` ou la variable d'environnement ``SMS_API_DB``.
Par défaut, ``sms_api.db`` est utilisé.
"""

import json
import os
import logging
from argparse import ArgumentParser

from sms_api.server import SMSHTTPServer
from sms_api.handler import SMSHandler


def main():
    logging.basicConfig(level=logging.INFO)
    parser = ArgumentParser()
    parser.add_argument("url", type=str)
    parser.add_argument("--username", type=str)
    parser.add_argument("--password", type=str)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--db", type=str, default=os.getenv("SMS_API_DB", "sms_api.db"))
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.getenv("SMS_API_KEY"),
        help="Clé API requise dans l'en-tête X-API-KEY pour POST /sms",
    )
    parser.add_argument(
        "--certfile",
        type=str,
        help="Chemin du certificat TLS (active HTTPS s'il est fourni)",
    )
    parser.add_argument(
        "--keyfile",
        type=str,
        help="Chemin de la clé privée TLS",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Fichier de configuration modifiable via l'interface d'administration",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="Délai en secondes pour la connexion au modem",
    )
    parser.add_argument("--kafka-client-id", type=str, default=os.getenv("KAFKA_CLIENT_ID", "sms"))
    parser.add_argument("--kafka-url", type=str, default=os.getenv("KAFKA_URL", ""))
    parser.add_argument("--kafka-group-id", type=str, default=os.getenv("KAFKA_GROUP_ID", "sms-consumer"))
    parser.add_argument("--kafka-username", type=str, default=os.getenv("KAFKA_USERNAME", ""))
    parser.add_argument("--kafka-password", type=str, default=os.getenv("KAFKA_PASSWORD", ""))
    parser.add_argument("--kafka-ca-cert", type=str, default=os.getenv("KAFKA_CA_CERT", ""))
    parser.add_argument("--kafka-privkey", type=str, default=os.getenv("KAFKA_PRIVKEY", ""))
    parser.add_argument("--kafka-cert", type=str, default=os.getenv("KAFKA_CERT", ""))
    parser.add_argument("--sms-api-url", type=str, default=os.getenv("SMS_API_URL", ""))
    parser.add_argument("--sms-api-key", type=str, default=os.getenv("SMS_API_EXT_KEY", ""))

    args = parser.parse_args()

    config = {}
    if os.path.exists(args.config):
        try:
            with open(args.config, encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            config = {}

    url = config.get("modem_url", args.url)
    username = config.get("username", args.username)
    password = config.get("password", args.password)
    api_key = config.get("api_key", args.api_key)
    certfile = config.get("certfile", args.certfile)
    keyfile = config.get("keyfile", args.keyfile)
    timeout = int(config.get("timeout", args.timeout))
    kafka_client_id = config.get("kafka_client_id", args.kafka_client_id)
    kafka_url = config.get("kafka_url", args.kafka_url)
    kafka_group_id = config.get("kafka_group_id", args.kafka_group_id)
    kafka_username = config.get("kafka_username", args.kafka_username)
    kafka_password = config.get("kafka_password", args.kafka_password)
    kafka_ca_cert = config.get("kafka_ca_cert", args.kafka_ca_cert)
    kafka_privkey = config.get("kafka_privkey", args.kafka_privkey)
    kafka_cert = config.get("kafka_cert", args.kafka_cert)
    sms_api_url = config.get("sms_api_url", args.sms_api_url)
    sms_api_key = config.get("sms_api_key", args.sms_api_key)

    server = SMSHTTPServer(
        (args.host, args.port),
        SMSHandler,
        url,
        username,
        password,
        args.db,
        api_key=api_key,
        certfile=certfile,
        keyfile=keyfile,
        config_path=args.config,
        timeout=timeout,
        kafka_client_id=kafka_client_id,
        kafka_url=kafka_url,
        kafka_group_id=kafka_group_id,
        kafka_username=kafka_username,
        kafka_password=kafka_password,
        kafka_ca_cert=kafka_ca_cert,
        kafka_privkey=kafka_privkey,
        kafka_cert=kafka_cert,
        sms_api_url=sms_api_url,
        sms_api_key=sms_api_key,
    )

    if certfile and keyfile:
        import ssl

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=certfile, keyfile=keyfile)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        protocol = "https"
    else:
        protocol = "http"

    logging.info("Serving on %s://%s:%s", protocol, args.host, args.port)
    server.serve_forever()


if __name__ == "__main__":
    main()
