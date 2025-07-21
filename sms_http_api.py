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

from argparse import ArgumentParser
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

import os
import re
import sqlite3
from datetime import datetime
import urllib.parse


from huawei_lte_api.Connection import Connection
from huawei_lte_api.Client import Client
from huawei_lte_api.enums.client import ResponseEnum

# OpenAPI specification describing the available endpoints. This is served at
# ``/openapi.json`` and used by the Swagger UI page.
OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {
        "title": "SMS HTTP API",
        "version": "1.0.0",
    },
    "paths": {
        "/sms": {
            "post": {
                "summary": "Send an SMS message",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "to": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "List of recipients",
                                    },
                                    "from": {
                                        "type": "string",
                                        "description": "Sender identifier",
                                    },
                                    "text": {
                                        "type": "string",
                                        "description": "Message body",
                                    },
                                },
                                "required": ["to", "from", "text"],
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "SMS sent",
                        "content": {
                            "text/plain": {"schema": {"type": "string", "example": "OK"}},
                        },
                    },
                    "400": {
                        "description": "Invalid request",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"error": {"type": "string"}},
                                }
                            }
                        },
                    },
                    "401": {"description": "Invalid API key"},
                    "500": {"description": "Failed to send SMS"},
                },
            }
        },
        "/health": {
            "get": {
                "summary": "Return modem status information",
                "responses": {
                    "200": {
                        "description": "Status information",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    },
                    "500": {"description": "Unable to retrieve status"},
                },
            }
        },
        "/readsms": {
            "get": {
                "summary": "List received SMS messages",
                "parameters": [
                    {
                        "in": "query",
                        "name": "json",
                        "required": False,
                        "schema": {"type": "string"},
                        "description": "Return JSON when present",
                    }
                ],
                "responses": {
                    "200": {
                        "description": "SMS list or HTML page",
                        "content": {
                            "application/json": {"schema": {"type": "array", "items": {"type": "object"}}},
                            "text/html": {"schema": {"type": "string"}},
                        },
                    }
                },
            }
        },
        "/readsms/delete": {
            "post": {
                "summary": "Delete SMS messages by id",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/x-www-form-urlencoded": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "ids": {
                                        "type": "array",
                                        "items": {"type": "integer"},
                                    }
                                },
                                "required": ["ids"],
                            }
                        }
                    },
                },
                "responses": {
                    "303": {"description": "Redirect to /readsms"}
                },
            }
        },
        "/logs": {
            "get": {
                "summary": "Show SMS send history",
                "responses": {
                    "200": {
                        "description": "HTML page with logs",
                        "content": {"text/html": {"schema": {"type": "string"}}},
                    }
                },
            }
        },
        "/logs/delete": {
            "post": {
                "summary": "Delete log entries",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/x-www-form-urlencoded": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "ids": {
                                        "type": "array",
                                        "items": {"type": "integer"},
                                    }
                                },
                                "required": ["ids"],
                            }
                        }
                    },
                },
                "responses": {"303": {"description": "Redirect to /logs"}},
            }
        },
    },
}


SIGNAL_LEVELS = {
    0: "     ",
    1: "▂    ",
    2: "▂▃   ",
    3: "▂▃▄  ",
    4: "▂▃▄▅ ",
    5: "▂▃▄▅▇",
}

NETWORK_TYPE_MAP = {
    "0": "No Service",
    "1": "GSM",
    "2": "GPRS",
    "3": "EDGE",
    "4": "WCDMA",
    "5": "HSDPA",
    "6": "HSUPA",
    "7": "HSPA",
    "8": "TDSCDMA",
    "9": "HSPA+",
    "10": "EVDO Rev.0",
    "11": "EVDO Rev.A",
    "12": "EVDO Rev.B",
    "13": "1xRTT",
    "14": "UMB",
    "15": "1xEVDV",
    "16": "3xRTT",
    "17": "HSPA+ 64QAM",
    "18": "HSPA+ MIMO",
    "19": "LTE",
    "41": "LTE CA",
    "101": "NR5G NSA",
    "102": "NR5G SA",
}


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
    elif rsrp >= -90:
        return 4
    elif rsrp >= -100:
        return 3
    elif rsrp >= -110:
        return 2
    elif rsrp >= -120:
        return 1
    else:
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
    """Validate JSON payload and return sanitized fields."""
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
    """Return the most recent update date from docs/mise-a-jour.md."""
    path = os.path.join(os.path.dirname(__file__), "docs", "mise-a-jour.md")
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

def footer_html() -> str:
    date = get_last_update_date()
    return (
        "<footer class='text-center mt-4'>"
        f"Dernière mise à jour : {date} - &copy; DSI Baudinchateauneuf"
        "</footer>"
    )

# Elements d'interface communs
NAVBAR_TEMPLATE = """
    <nav class='navbar navbar-dark bg-company'>
      <div class='container-fluid'>
        <button class='navbar-toggler' type='button' data-bs-toggle='offcanvas' data-bs-target='#menu' aria-controls='menu'>
          <span class='navbar-toggler-icon'></span>
        </button>
        <span class='navbar-brand ms-2'>API SMS BC</span>
      </div>
    </nav>
    <div class='offcanvas offcanvas-start' tabindex='-1' id='menu'>
      <div class='offcanvas-header'>
        <h5 class='offcanvas-title'>Menu</h5>
        <button type='button' class='btn-close' data-bs-dismiss='offcanvas' aria-label='Close'></button>
      </div>
      <div class='offcanvas-body'>
        <ul class='nav flex-column'>
          <li class='nav-item'><a class='nav-link' href='/'>Accueil</a></li>
          <li class='nav-item'><a class='nav-link' href='/logs'>Historique SMS</a></li>
          <li class='nav-item'><a class='nav-link' href='/readsms'>Lire SMS {SMS_BADGE}</a></li>
          <li class='nav-item'><a class='nav-link' href='/testsms'>Envoyer un SMS</a></li>
          <li class='nav-item'><a class='nav-link' href='/docs'>Documentation</a></li>
          <li class='nav-item'><a class='nav-link' href='/updates'>Mises à jour</a></li>
        </ul>
      </div>
    </div>
"""



class SMSHandler(BaseHTTPRequestHandler):
    def _get_sms_count(self) -> int:
        try:
            with Connection(
                self.server.modem_url,
                username=self.server.username,
                password=self.server.password,
            ) as connection:
                client = Client(connection)
                info = client.sms.sms_count()
                return int(info.get("LocalInbox", 0))
        except Exception:
            return 0

    def _navbar_html(self) -> str:
        count = self._get_sms_count()
        badge = f"<span class='badge bg-secondary ms-1'>{count}</span>"
        return NAVBAR_TEMPLATE.replace("{SMS_BADGE}", badge)

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json_error(self, status, message):
        self._send_json(status, {"error": message})

    def do_GET(self):

        if self.path == "/":
            self._serve_index()
            return
        if self.path == "/openapi.json":
            self._serve_openapi_json()
            return
        if self.path == "/swagger":
            self._serve_swagger()
            return
        if self.path == "/logs":
            self._serve_logs()
            return
        if self.path == "/testsms":
            self._serve_testsms()
            return
        if self.path == "/docs":
            self._serve_docs()
            return
        if self.path == "/updates":
            self._serve_updates()
            return
        if self.path == "/baudin.css":
            self._serve_css()
            return
        if self.path.startswith("/readsms"):
            self._serve_readsms()
            return
        if self.path != "/health":
            self.send_error(404, "Not found")

            return

        try:
            with Connection(
                self.server.modem_url,
                username=self.server.username,
                password=self.server.password,
            ) as connection:
                client = Client(connection)
                device_info = client.device.information()
                signal_info = client.device.signal()
                status_info = client.monitoring.status()
                network_type_raw = str(status_info.get("CurrentNetworkType", "0"))
                plmn_info = client.net.current_plmn()
                config = client.config_lan.config()

            rsrp = parse_dbm(signal_info.get("rsrp"))
            level = get_signal_level(rsrp)

            health = {
                "device_info": device_info,
                "signal": signal_info,
                "operator_name": plmn_info.get("FullName")
                or plmn_info.get("ShortName")
                or "Unknown",
                "network_type": NETWORK_TYPE_MAP.get(
                    network_type_raw, f"Unknown ({network_type_raw})"
                ),
                "ip_address": config.get("config", {})
                .get("dhcps", {})
                .get("ipaddress"),
                "signal_level": level,
                "signal_bars": SIGNAL_LEVELS.get(level),
            }

            body = json.dumps(health).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            self._json_error(500, str(exc))

    def _serve_index(self):
        html = """
        <html>
        <head>
            <meta charset='utf-8'>
            <title>Modem Health</title>
            <link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'>
            <link rel='stylesheet' href='baudin.css'>

            <script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>
            <style>
                .bg-company {background-color:#0060ac;}
                .btn-company {background-color:#0060ac;border-color:#0060ac;}
                .text-company {color:#0060ac;}
            </style>
            <script>
                async function loadHealth() {
                    const r = await fetch('/health');
                    const data = await r.json();
                    document.getElementById('health').textContent = JSON.stringify(data, null, 2);
                }
                window.onload = loadHealth;
            </script>
        </head>
        <body class='container-fluid px-3 py-4'>

            {NAVBAR}
            <div class='p-5 mb-4 bg-light rounded-3 text-center'>
                <h1 class='display-6 text-company mb-0'>Informations du modem</h1>
            </div>
            <div class='container'>
                <pre id='health' class='bg-light p-3 rounded'>Chargement...</pre>
            </div>

            {FOOTER}
        </body>
        </html>
        """.replace("{NAVBAR}", self._navbar_html()).replace("{FOOTER}", footer_html())
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_logs(self):
        conn = sqlite3.connect(self.server.db_path)
        conn.row_factory = sqlite3.Row
        ensure_logs_table(conn)
        rows = conn.execute(
            "SELECT id, timestamp, sender, phone, message, response FROM logs ORDER BY id DESC"
        ).fetchall()
        conn.close()

        html = [
            "<html><head><meta charset='utf-8'><title>Historique SMS</title>",
            "<link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'>",
            "<link rel='stylesheet' href='baudin.css'>",

            "<script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>",
            "<style>.bg-company{background-color:#0060ac;}.btn-company{background-color:#0060ac;border-color:#0060ac;}.text-company{color:#0060ac;}</style>",
            "<script>function selectAll(){document.querySelectorAll('.rowchk').forEach(c=>c.checked=true);}</script>",
            "</head><body class='container-fluid px-3 py-4'>",
            self._navbar_html(),
            "<div class='p-5 mb-4 bg-light rounded-3 text-center'>",
            "<h1 class='display-6 text-company mb-0'>Historique des SMS</h1>",
            "</div>",
            "<div class='container'>",
            "<form method='post' action='/logs/delete'>",
            "<table class='table table-striped'>",
            "<tr><th></th><th>Date/Heure</th><th>Expéditeur</th><th>Destinataire(s)</th><th>Message</th><th>Réponse</th></tr>",
        ]
        for row in rows:
            html.append(
                f"<tr><td><input type='checkbox' class='rowchk' name='ids' value='{row['id']}'></td><td>{row['timestamp']}</td><td>{row['sender'] or ''}</td><td>{row['phone']}</td><td>{row['message']}</td><td>{row['response']}</td></tr>"
            )
        html.extend(
            [
                "</table>",
                "<p><button type='button' class='btn btn-secondary me-2' onclick='selectAll()'>Sélectionner tout</button> <button type='submit' class='btn btn-danger'>Supprimer</button></p>",
                "</form>",
                "</div>" + footer_html() + "</body></html>",
            ]
        )
        body = "".join(html).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_readsms(self):
        parsed = urllib.parse.urlparse(self.path)
        want_json = parsed.query == "json" or "application/json" in self.headers.get("Accept", "")

        try:
            with Connection(
                self.server.modem_url,
                username=self.server.username,
                password=self.server.password,
            ) as connection:
                client = Client(connection)
                messages = [m.to_dict() for m in client.sms.get_messages()]
        except Exception as exc:
            if want_json:
                self._json_error(500, str(exc))
            else:
                body = f"<p>Erreur: {exc}</p>".encode('utf-8')
                self.send_response(500)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            return

        if want_json:
            self._send_json(200, messages)
            return

        html = [
            "<html><head><meta charset='utf-8'><title>SMS reçus</title>",
            "<link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'>",
            "<link rel='stylesheet' href='baudin.css'>",
            "<script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>",
            "<style>.bg-company{background-color:#0060ac;}.btn-company{background-color:#0060ac;border-color:#0060ac;}.text-company{color:#0060ac;}</style>",

            "<script>function selectAll(){document.querySelectorAll('.rowchk').forEach(c=>c.checked=true);}</script>",
            "</head><body class='container-fluid px-3 py-4'>",
            self._navbar_html(),
            "<div class='p-5 mb-4 bg-light rounded-3 text-center'>",
            "<h1 class='display-6 text-company mb-0'>SMS reçus</h1>",
            "</div>",
            "<div class='container'>",

            "<form method='post' action='/readsms/delete'>",
            "<table class='table table-striped'>",
            "<tr><th></th><th>Date/Heure</th><th>Expéditeur</th><th>Message</th></tr>",
        ]
        for m in messages:
            html.append(
                f"<tr><td><input type='checkbox' class='rowchk' name='ids' value='{m['Index']}'></td><td>{m['Date']}</td><td>{m['Phone']}</td><td>{m['Content']}</td></tr>"
            )
        html.extend([
            "</table>",
            "<p><button type='button' class='btn btn-secondary me-2' onclick='selectAll()'>Sélectionner tout</button> <button type='submit' class='btn btn-danger'>Supprimer</button></p>",
            "</form>",
            "</div>" + footer_html() + "</body></html>",
        ])

        body = "".join(html).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_testsms(self):
        html = """
        <html>
        <head>
            <meta charset='utf-8'>
            <title>Envoyer un SMS</title>
            <link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'>
            <link rel='stylesheet' href='baudin.css'>

            <script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>
            <style>
                .bg-company {background-color:#0060ac;}
                .btn-company {background-color:#0060ac;border-color:#0060ac;}
                .text-company {color:#0060ac;}
            </style>
            <script>
                async function sendSms(event) {
                    event.preventDefault();
                    const to = document.getElementById('to').value
                        .split(',')
                        .map(t => t.trim())
                        .filter(t => t);
                    const text = document.getElementById('text').value;
                    const apiKey = document.getElementById('apiKey').value.trim();
                    const payload = {to: to, from: 'test api web', text: text};
                    const headers = {'Content-Type': 'application/json'};
                    if (apiKey) {
                        headers['X-API-KEY'] = apiKey;
                    }
                    const resp = await fetch('/sms', {
                        method: 'POST',
                        headers: headers,
                        body: JSON.stringify(payload)
                    });
                    if (resp.ok) {
                        alert('SMS envoyé');
                    } else {
                        const msg = await resp.text();
                        alert('Erreur: ' + msg);
                    }
                }
            </script>
        </head>
        <body class='container-fluid px-3 py-4'>
            {NAVBAR}
            <div class='p-5 mb-4 bg-light rounded-3 text-center'>
                <h1 class='display-6 text-company mb-0'>Tester l\'envoi de SMS</h1>
            </div>
            <div class='container'>
            <form id='smsForm' onsubmit='sendSms(event)' class='mb-3'>
                <div class='mb-3'>
                    <label for='to' class='form-label'>Destinataire(s) (séparés par des virgules)</label>
                    <input type='text' id='to' class='form-control' required>
                </div>
                <div class='mb-3'>
                    <label for='text' class='form-label'>Message</label>
                    <textarea id='text' class='form-control' rows='4' required></textarea>
                </div>
                <div class='mb-3'>
                    <label for='apiKey' class='form-label'>Clé X-API-KEY</label>
                    <input type='text' id='apiKey' class='form-control'>
                </div>
                <button type='submit' class='btn btn-company'>Envoyer</button>
            </form>
            </div>
            {FOOTER}
        </body>
        </html>
        """.replace("{NAVBAR}", self._navbar_html()).replace("{FOOTER}", footer_html())
        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_docs(self):
        html = """
        <html>
        <head>
            <meta charset='utf-8'>
            <title>Documentation API</title>
            <link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'>
            <link rel='stylesheet' href='baudin.css'>

            <script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>
            <style>
                .bg-company {background-color:#0060ac;}
                .btn-company {background-color:#0060ac;border-color:#0060ac;}
                .text-company {color:#0060ac;}
            </style>
        </head>
        <body class='container-fluid px-3 py-4'>
            {NAVBAR}
            <div class='p-5 mb-4 bg-light rounded-3 text-center'>
                <h1 class='display-6 text-company mb-0'>Documentation de l\'API</h1>
            </div>
            <div class='container'>
                <p><a href='/swagger'>Swagger UI</a> - <a href='/openapi.json'>OpenAPI JSON</a></p>
                <table class='table table-striped'>
                    <thead>
                        <tr><th>Méthode</th><th>Endpoint</th><th>Requête</th><th>Réponse</th></tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>POST</td>
                            <td><code>/sms</code></td>
                            <td>
                                <pre>{"to": ["+33612345678"], "from": "expediteur", "text": "message"}</pre>
                            </td>
                            <td>200 OK avec <code>OK</code> ou JSON <code>{"error": str}</code></td>
                        </tr>
                        <tr>
                            <td>GET</td>
                            <td><code>/health</code></td>
                            <td>-</td>
                            <td>200 JSON sur l\'état du modem</td>
                        </tr>
                        <tr>
                            <td>GET</td>
                            <td><code>/readsms</code></td>
                            <td>Ajouter <code>?json</code> pour obtenir du JSON</td>
                            <td>200 HTML ou JSON</td>
                        </tr>
                        <tr>
                            <td>POST</td>
                            <td><code>/readsms/delete</code></td>
                            <td>Formulaire <code>ids=1&amp;ids=2...</code></td>
                            <td>303 redirige vers <code>/readsms</code></td>
                        </tr>
                        <tr>
                            <td>GET</td>
                            <td><code>/logs</code></td>
                            <td>-</td>
                            <td>200 HTML</td>
                        </tr>
                        <tr>
                            <td>POST</td>
                            <td><code>/logs/delete</code></td>
                            <td>Formulaire <code>ids=1&amp;ids=2...</code></td>
                            <td>303 redirige vers <code>/logs</code></td>
                        </tr>
                    </tbody>
                </table>
            </div>
            {FOOTER}
        </body>
        </html>
        """.replace("{NAVBAR}", self._navbar_html()).replace("{FOOTER}", footer_html())
        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_updates(self):
        path = os.path.join(os.path.dirname(__file__), "docs", "mise-a-jour.md")
        try:
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            lines = ["Impossible de charger le journal des mises à jour."]

        html_lines = ["<html><head><meta charset='utf-8'><title>Mises à jour</title>",
                      "<link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'>",
                      "<link rel='stylesheet' href='baudin.css'>",
                      "<script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>",
                      "<style>.bg-company{background-color:#0060ac;}.btn-company{background-color:#0060ac;border-color:#0060ac;}.text-company{color:#0060ac;}</style>",
                      "</head><body class='container-fluid px-3 py-4'>",
                      "{NAVBAR}",
                      "<div class='p-5 mb-4 bg-light rounded-3 text-center'>",
                      "<h1 class='display-6 text-company mb-0'>Journal des mises à jour</h1>",
                      "</div>",
                      "<div class='container'>"]
        in_list = False
        for line in lines:
            if line.startswith('#'):
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                level = line.count('#')
                html_lines.append(f"<h{level}>{line.strip('#').strip()}</h{level}>")
            elif line.startswith('-'):
                if not in_list:
                    html_lines.append('<ul>')
                    in_list = True
                html_lines.append(f"<li>{line[1:].strip()}</li>")
            else:
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                stripped = line.strip()
                if stripped:
                    html_lines.append(f"<p>{stripped}</p>")
        if in_list:
            html_lines.append('</ul>')
        html_lines.append('</div>' + footer_html() + '</body></html>')
        html = "".join(html_lines).replace("{NAVBAR}", self._navbar_html())
        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_css(self):
        path = os.path.join(os.path.dirname(__file__), 'baudin.css')
        try:
            with open(path, 'rb') as f:
                css = f.read()
        except Exception:
            css = b''
        self.send_response(200)
        self.send_header('Content-Type', 'text/css')
        self.send_header('Content-Length', str(len(css)))
        self.end_headers()
        self.wfile.write(css)

    def _serve_openapi_json(self):
        body = json.dumps(OPENAPI_SPEC, indent=2).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_swagger(self):
        html = f"""
        <html>
        <head>
            <meta charset='utf-8'>
            <title>Swagger UI</title>
            <link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'>
            <link rel='stylesheet' href='baudin.css'>
            <link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/swagger-ui-dist/swagger-ui.css'>
            <script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>
            <script src='https://cdn.jsdelivr.net/npm/swagger-ui-dist/swagger-ui-bundle.js'></script>
            <style>.bg-company{{background-color:#0060ac;}}</style>
        </head>
        <body class='container-fluid px-3 py-4'>
            {self._navbar_html()}
            <div id='swagger-ui'></div>
            <script>
            window.onload = function() {{
                SwaggerUIBundle({{
                    url: '/openapi.json',
                    dom_id: '#swagger-ui'
                }});
            }};
            </script>
            {footer_html()}
        </body>
        </html>
        """
        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _delete_logs(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        params = urllib.parse.parse_qs(body)
        ids = params.get("ids", [])
        conn = sqlite3.connect(self.server.db_path)
        conn.row_factory = sqlite3.Row
        ensure_logs_table(conn)
        if ids:
            # Use executemany with parameterized queries to avoid SQL injection
            conn.executemany(
                "DELETE FROM logs WHERE id = ?",
                [(log_id,) for log_id in ids],
            )
            conn.commit()
        conn.close()
        self.send_response(303)
        self.send_header("Location", "/logs")
        self.end_headers()

    def _delete_sms(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        params = urllib.parse.parse_qs(body)
        ids = params.get("ids", [])

        try:
            with Connection(
                self.server.modem_url,
                username=self.server.username,
                password=self.server.password,
            ) as connection:
                client = Client(connection)
                for sms_id in ids:
                    try:
                        client.sms.delete_sms(int(sms_id))
                    except Exception:
                        pass
        except Exception:
            pass

        self.send_response(303)
        self.send_header("Location", "/readsms")
        self.end_headers()


    def do_POST(self):
        if self.path == "/logs/delete":
            self._delete_logs()
            return
        if self.path == "/readsms/delete":
            self._delete_sms()
            return
        if self.path != "/sms":

            self._json_error(404, "Not found")

            return

        if self.server.api_key is not None:
            provided_key = self.headers.get("X-API-KEY")
            if provided_key != self.server.api_key:
                self._json_error(401, "Invalid API key")
                return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body.decode("utf-8"))

        except json.JSONDecodeError:
            self._json_error(400, "Invalid JSON body")
            return

        try:
            recipients, sender, text = validate_request(data)
        except ValueError as exc:
            self._json_error(400, str(exc))

            return

        try:

            with Connection(
                self.server.modem_url,
                username=self.server.username,
                password=self.server.password,
            ) as connection:
                client = Client(connection)
                resp = client.sms.send_sms(recipients, text)
            log_request(self.server.db_path, recipients, sender, text, str(resp))

            if resp == ResponseEnum.OK.value:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")
            else:

                self._json_error(500, "Failed to send SMS")

        except Exception as exc:

            log_request(self.server.db_path, recipients, sender, text, str(exc))

            self._json_error(500, str(exc))


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
    ):

        super().__init__(server_address, handler_class)
        self.modem_url = modem_url
        self.username = username
        self.password = password
        self.db_path = db_path
        self.api_key = api_key


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
