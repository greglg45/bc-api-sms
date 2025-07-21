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

import os
from argparse import ArgumentParser

from sms_api.server import SMSHTTPServer
from sms_api.handler import SMSHandler


def main():
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

    args = parser.parse_args()

    server = SMSHTTPServer(
        (args.host, args.port),
        SMSHandler,
        args.url,
        args.username,
        args.password,
        args.db,
        api_key=args.api_key,
    )

    if args.certfile and args.keyfile:
        import ssl

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=args.certfile, keyfile=args.keyfile)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        protocol = "https"
    else:
        protocol = "http"

    print(f"Serving on {protocol}://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
