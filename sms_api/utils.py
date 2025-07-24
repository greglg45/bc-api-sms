import os
import re
import sqlite3
import logging
import uuid
from datetime import datetime


__all__ = [
    "parse_dbm",
    "get_signal_level",
    "ensure_logs_table",
    "log_request",
    "validate_request",
    "get_last_update_date",
    "get_current_version",
    "footer_html",
    "get_phone_from_kafka",
]


logger = logging.getLogger(__name__)


def parse_dbm(value):
    if value is None:
        return None
    match = re.search(r"-?\d+", str(value))
    return int(match.group()) if match else None


def get_signal_level(rsrp: int) -> int:
    if rsrp is None:
        return 0
    if rsrp >= -80:
        return 5
    if rsrp >= -90:
        return 4
    if rsrp >= -100:
        return 3
    if rsrp >= -110:
        return 2
    if rsrp >= -120:
        return 1
    return 0


def ensure_logs_table(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS logs ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "timestamp TEXT,"
        "phone TEXT,"
        "sender TEXT,"
        "message TEXT,"
        "response TEXT)"
    )
    cols = [row[1] for row in conn.execute("PRAGMA table_info(logs)")]
    if "sender" not in cols:
        conn.execute("ALTER TABLE logs ADD COLUMN sender TEXT")


def log_request(db_path, recipients, sender, text, response):
    conn = sqlite3.connect(db_path)
    ensure_logs_table(conn)
    conn.execute(
        "INSERT INTO logs(timestamp, phone, sender, message, response) VALUES (?,?,?,?,?)",
        (datetime.utcnow().isoformat(), ",".join(recipients), sender, text, response),
    )
    conn.commit()
    conn.close()


def validate_request(data):
    recipients = data.get("to")
    sender = data.get("from")
    text = data.get("text")

    if isinstance(sender, str):
        sender = sender.strip()

    if not isinstance(recipients, list) or not recipients:
        raise ValueError("'to' must be a non-empty list")
    for number in recipients:
        if not isinstance(number, str) or not re.fullmatch(r"\+?\d+", number):
            raise ValueError("invalid phone number in 'to'")
    if not isinstance(sender, str) or not sender:
        raise ValueError("'from' must be a non-empty string")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("'text' must be a non-empty string")
    return recipients, sender, text.strip()


def get_last_update_date() -> str:
    path = os.path.join(os.path.dirname(__file__), os.pardir, "docs", "mise-a-jour.md")
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.lstrip().startswith("-"):
                    m = re.search(r"\*\*(.+?)\*\*", line)
                    if m:
                        return m.group(1)
    except Exception:
        pass
    return datetime.utcnow().strftime("%d/%m/%Y")


def get_current_version() -> str:
    """Récupère la version actuelle du paquet."""
    path = os.path.join(
        os.path.dirname(__file__), os.pardir, "huawei_lte_api", "__init__.py"
    )
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if "__version__" in line:
                    m = re.search(r"'(.+?)'", line)
                    if m:
                        return m.group(1)
    except Exception:
        pass
    return "N/A"


def footer_html() -> str:
    date = get_last_update_date()
    version = get_current_version()
    return (
        "<footer class='text-center mt-4'>"
        f"Dernière mise à jour : {date} - Version {version} - &copy; DSI Baudinchateauneuf"
        "</footer>"
    )


def get_phone_from_kafka(baudin_id: str, cfg: dict) -> str:
    """Interroge Kafka pour obtenir le numéro associé à un identifiant."""
    if not cfg.get("kafka_url"):
        return ""

    logger.info("Recherche du numéro via Kafka pour l'ID %s", baudin_id)

    from kafka import KafkaProducer, KafkaConsumer
    from kafka.errors import NoBrokersAvailable
    import time

    common = {
        "bootstrap_servers": cfg["kafka_url"].split(","),
        "client_id": cfg.get("kafka_client_id", "sms"),
    }
    if cfg.get("kafka_username") and cfg.get("kafka_password"):
        common.update(
            {
                "sasl_mechanism": "SCRAM-SHA-512",
                "security_protocol": "SASL_SSL",
                "sasl_plain_username": cfg["kafka_username"],
                "sasl_plain_password": cfg["kafka_password"],
            }
        )
    if cfg.get("kafka_ca_cert") and cfg.get("kafka_privkey") and cfg.get("kafka_cert"):
        common.update(
            {
                "ssl_cafile": cfg["kafka_ca_cert"],
                "ssl_keyfile": cfg["kafka_privkey"],
                "ssl_certfile": cfg["kafka_cert"],
            }
        )

    try:
        logger.debug("Connexion à Kafka sur %s", cfg.get("kafka_url"))
        producer = KafkaProducer(
            **common, value_serializer=lambda v: v.encode("utf-8")
        )
        consumer = KafkaConsumer(
            "matrix.person.phone-number.reply",
            group_id=cfg.get("kafka_group_id", "sms-consumer"),
            **common,
            value_deserializer=lambda v: v.decode("utf-8"),
            auto_offset_reset="latest",
            # Stop iteration after 1s if no message was received so we can
            # exit the loop when the timeout is reached
            consumer_timeout_ms=1000,
        )
    except NoBrokersAvailable:
        logger.error("Aucun broker Kafka disponible")
        return ""

    correlation_id = str(uuid.uuid4())
    producer.send(
        "matrix.person.phone-number",
        key=None,
        value=baudin_id.upper(),
        headers=[
            ("kafka_correlationId", correlation_id.encode("utf-8")),
            ("kafka_replyTopic", b"matrix.person.phone-number.reply"),
            ("kafka_replyPartition", b"0"),
        ],
    )
    producer.flush()
    logger.debug(
        "Message envoyé pour %s avec kafka_correlationId %s",
        baudin_id.upper(),
        correlation_id,
    )

    end = time.time() + 30
    while time.time() < end:
        for message in consumer:
            headers = dict(message.headers or [])
            msg_id = headers.get("kafka_correlationId")
            if msg_id:
                received_cid = msg_id.decode("utf-8")
                logger.debug("Message reçu avec kafka_correlationId %s", received_cid)
            else:
                received_cid = None
            if (
                received_cid == correlation_id
                and message.value
            ):
                phone = message.value
                logger.info(
                    "Réponse reçue de Kafka: %s (kafka_correlationId %s)",
                    phone,
                    correlation_id,
                )
                producer.close()
                consumer.close()
                return phone

    logger.warning("Kafka n'a pas retourné de numéro pour %s", baudin_id)

    producer.close()
    consumer.close()
    return ""
