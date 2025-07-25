from http.server import HTTPServer
import os
import sys
import subprocess
import shutil
import logging

from .utils import create_kafka_clients


class SMSHTTPServer(HTTPServer):
    def __init__(
        self,
        server_address,
        handler_class,
        modem_url,
        username,
        password,
        db_path,
        api_key=None,
        certfile=None,
        keyfile=None,
        config_path="config.json",
        timeout=5,
        kafka_client_id="sms",
        kafka_url="",
        kafka_group_id="sms-consumer",
        kafka_username="",
        kafka_password="",
        kafka_ca_cert="",
        kafka_privkey="",
        kafka_cert="",
        sms_api_url="",
        sms_api_key="",
    ):
        super().__init__(server_address, handler_class)
        self.modem_url = modem_url
        self.username = username
        self.password = password
        self.db_path = db_path
        self.api_key = api_key
        self.certfile = certfile
        self.keyfile = keyfile
        self.config_path = config_path
        self.timeout = timeout
        self.kafka_client_id = kafka_client_id
        self.kafka_url = kafka_url
        self.kafka_group_id = kafka_group_id
        self.kafka_username = kafka_username
        self.kafka_password = kafka_password
        self.kafka_ca_cert = kafka_ca_cert
        self.kafka_privkey = kafka_privkey
        self.kafka_cert = kafka_cert
        self.sms_api_url = sms_api_url
        self.sms_api_key = sms_api_key

        self.kafka_producer = None
        self.kafka_consumer = None
        if self.kafka_url:
            cfg = {
                "kafka_client_id": self.kafka_client_id,
                "kafka_url": self.kafka_url,
                "kafka_group_id": self.kafka_group_id,
                "kafka_username": self.kafka_username,
                "kafka_password": self.kafka_password,
                "kafka_ca_cert": self.kafka_ca_cert,
                "kafka_privkey": self.kafka_privkey,
                "kafka_cert": self.kafka_cert,
            }
            self.kafka_producer, self.kafka_consumer = create_kafka_clients(cfg)
            if self.kafka_producer is None:
                logging.getLogger(__name__).warning(
                    "Impossible de se connecter à Kafka, la fonctionnalité sera desactivée"
                )
            else:
                from .utils import warmup_kafka

                warmup_kafka(self.kafka_consumer)

    def restart(self):
        """Redémarre le service ou le processus."""
        if shutil.which("systemctl"):
            subprocess.run(["systemctl", "restart", "bc-api-sms.service"])
        else:
            os.execv(sys.executable, [sys.executable] + sys.argv)


__all__ = ["SMSHTTPServer"]
