import os
import re
import sqlite3
import logging
import uuid
import threading
import time
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
    "create_kafka_clients",
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


def _start_consumer_heartbeat(consumer, interval=600):
    """Lance un thread envoyant periodiquement poll(0) sur le consommateur."""

    def _loop():
        while getattr(consumer, "_hb_running", True):
            try:
                consumer.poll(0)
            except Exception as exc:  # pragma: no cover - log seulement
                logger.debug("Heartbeat Kafka en erreur: %s", exc)
            time.sleep(interval)

    consumer._hb_running = True
    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    consumer._hb_thread = thread


def create_kafka_clients(cfg: dict):
    """Crée un producteur et un consommateur Kafka."""
    from kafka import KafkaProducer, KafkaConsumer
    from kafka.errors import NoBrokersAvailable

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
    if (
        cfg.get("kafka_ca_cert")
        and cfg.get("kafka_privkey")
        and cfg.get("kafka_cert")
    ):
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
            **common,
            value_serializer=lambda v: v.encode("utf-8"),
            connections_max_idle_ms=3000000,
            request_timeout_ms=1900000,
            delivery_timeout_ms=2000000,
        )
        consumer = KafkaConsumer(
            "matrix.person.phone-number.reply",
            group_id=cfg.get("kafka_group_id", "sms-consumer"),
            session_timeout_ms=1800000,
            heartbeat_interval_ms=600000,
            connections_max_idle_ms=3000000,
            request_timeout_ms=1900000,
            **common,
            value_deserializer=lambda v: v.decode("utf-8") if v is not None else None,
            auto_offset_reset="latest",
            consumer_timeout_ms=1000,
        )
        try:
            consumer.poll(0)
        except Exception as exc:  # pragma: no cover - log seulement
            logger.debug("Première poll Kafka en erreur: %s", exc)

        _start_consumer_heartbeat(consumer)

        original_close = consumer.close

        def _close(*args, **kwargs):
            consumer._hb_running = False
            if hasattr(consumer, "_hb_thread"):
                consumer._hb_thread.join(timeout=1)
            original_close(*args, **kwargs)

        consumer.close = _close

        return producer, consumer
    except NoBrokersAvailable:
        logger.error("Aucun broker Kafka disponible")
        return None, None


def warmup_kafka(consumer, *, timeout_ms=1000, max_attempts=5):
    """Pré-initialise la connexion Kafka sans bloquer le thread principal."""

    def _run():
        attempts = 0
        while attempts < max_attempts and not consumer.assignment():
            try:
                consumer.poll(timeout_ms=timeout_ms)
            except Exception as exc:  # pragma: no cover - log seulement
                logger.debug("Warmup Kafka en erreur: %s", exc)
            attempts += 1

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread


def get_phone_from_kafka(baudin_id: str, cfg: dict, *, producer=None, consumer=None) -> str:
    """Interroge Kafka pour obtenir le numéro associé à un identifiant."""
    if not cfg.get("kafka_url"):
        return ""

    import time

    logger.info("Recherche du numéro via Kafka pour l'ID %s", baudin_id)

    close_clients = False
    if producer is None or consumer is None:
        producer, consumer = create_kafka_clients(cfg)
        close_clients = True
        if producer is None or consumer is None:
            return ""

    if not consumer.assignment():
        thread = warmup_kafka(consumer, timeout_ms=1000, max_attempts=20)
        thread.join()
        if not consumer.assignment():
            logger.warning("Aucune partition assignée après le warmup Kafka")
            if close_clients:
                producer.close()
                consumer.close()
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

        logger.debug(
            "Attente d'une réponse Kafka, expiration dans %.1fs",
            end - time.time(),
        )
        polled = False
        for message in consumer:
            polled = True
            headers = dict(message.headers or [])
            msg_id = headers.get("kafka_correlationId")
            if msg_id:
                received_cid = msg_id.decode("utf-8")

                logger.debug(
                    "Message reçu avec kafka_correlationId %s : %s",
                    received_cid,
                    message.value,
                )
            else:
                received_cid = None
                logger.debug("Message reçu sans correlation id : %s", message.value)

            if received_cid != correlation_id:
                logger.debug(
                    "Message ignoré (correlation id %s attendu, %s reçu)",
                    correlation_id,
                    received_cid,
                )
                continue

            if message.value:
                phone = message.value
                logger.info(
                    "Réponse reçue de Kafka: %s (kafka_correlationId %s)",
                    phone,
                    correlation_id,
                )
                if close_clients:
                    producer.close()
                    consumer.close()
                return phone

        if not polled:
            logger.debug("Aucun message reçu pendant cette tentative")

    logger.warning("Kafka n'a pas retourné de numéro pour %s", baudin_id)

    if close_clients:
        producer.close()
        consumer.close()
    return ""
