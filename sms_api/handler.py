import json
import os
import sqlite3
import urllib.parse
from http.server import BaseHTTPRequestHandler
import html
import threading
import subprocess
import logging

from huawei_lte_api.Connection import Connection
from huawei_lte_api.Client import Client
from huawei_lte_api.enums.client import ResponseEnum

from .utils import (
    parse_dbm,
    get_signal_level,
    ensure_logs_table,
    log_request,
    validate_request,
    footer_html,
    get_phone_from_kafka,
)

OPENAPI_PATH = os.path.join(os.path.dirname(__file__), os.pardir, "openapi.json")

logger = logging.getLogger(__name__)

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

NAVBAR_TEMPLATE = """
    <nav class='navbar navbar-dark bg-company'>
      <div class='container-fluid'>
        <button class='navbar-toggler' type='button' data-bs-toggle='offcanvas' data-bs-target='#menu' aria-controls='menu'>
          <span class='navbar-toggler-icon'></span>
        </button>
        <span class='navbar-brand ms-2'>API SMS BC</span>
        <button id='updateBtn' class='btn btn-link text-warning ms-auto me-2 d-none' onclick='promptUpdate()'>Mise à jour disponible</button>
        <button id='themeToggle' class='btn btn-link text-light' onclick='toggleTheme()'>🌙</button>
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
          <li class='nav-item'><a class='nav-link' href='/sendsms'>Envoyer un SMS</a></li>
          <li class='nav-item'><a class='nav-link' href='/docs'>Documentation</a></li>
          <li class='nav-item'><a class='nav-link' href='/admin'>Administration</a></li>
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
                timeout=self.server.timeout,
            ) as connection:
                client = Client(connection)
                info = client.sms.sms_count()
                return int(info.get("LocalInbox", 0))
        except Exception:
            return 0

    def _get_sent_count(self) -> int:
        conn = sqlite3.connect(self.server.db_path)
        ensure_logs_table(conn)
        count = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
        conn.close()
        return int(count)

    def _get_last_sender(self) -> str:
        conn = sqlite3.connect(self.server.db_path)
        conn.row_factory = sqlite3.Row
        ensure_logs_table(conn)
        row = conn.execute(
            "SELECT sender FROM logs WHERE sender IS NOT NULL AND sender != '' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        if row:
            return row["sender"]
        return ""

    def _serve_dashboard(self):
        data = {
            "sent_total": self._get_sent_count(),
            "received_total": self._get_sms_count(),
            "last_sender": self._get_last_sender(),
        }
        self._send_json(200, data)

    def _serve_sms_count(self):
        self._send_json(200, {"count": self._get_sms_count()})

    def _serve_phone(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        baudin_id = params.get("id", [""])[0].strip()
        if not baudin_id:
            self._json_error(400, "id manquant")
            return
        cfg = {
            "kafka_client_id": self.server.kafka_client_id,
            "kafka_url": self.server.kafka_url,
            "kafka_group_id": self.server.kafka_group_id,
            "kafka_username": self.server.kafka_username,
            "kafka_password": self.server.kafka_password,
            "kafka_ca_cert": self.server.kafka_ca_cert,
            "kafka_privkey": self.server.kafka_privkey,
            "kafka_cert": self.server.kafka_cert,
        }
        phone = get_phone_from_kafka(
            baudin_id,
            cfg,
            producer=self.server.kafka_producer,
            consumer=self.server.kafka_consumer,
        )
        if phone:
            self._send_json(200, {"phone": phone})
        else:
            self._json_error(404, "Numero introuvable")

    def _navbar_html(self) -> str:
        badge = "<span id='smsBadge' class='badge bg-secondary ms-1'>-</span>"
        script = (
            "<script>"
            "async function updateSmsBadge(){try{const r=await fetch('/sms_count');"
            "const j=await r.json();"
            "document.getElementById('smsBadge').textContent=j.count;}catch(e){"
            "document.getElementById('smsBadge').textContent='?';}}"
            "async function checkUpdate(){try{const r=await fetch('/check_update');"
            "const j=await r.json();if(j.update_available){document.getElementById('updateBtn').classList.remove('d-none');}}catch(e){}}"
            "function promptUpdate(){if(confirm('Lancer la mise à jour ?')){fetch('/update',{method:'POST'}).then(()=>alert('Mise à jour lancée'));}}"
            "updateSmsBadge();setInterval(updateSmsBadge,5000);checkUpdate();"
            "</script>"
        )
        return NAVBAR_TEMPLATE.replace("{SMS_BADGE}", badge) + script

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
        path = urllib.parse.urlparse(self.path).path

        if path == "/":
            self._serve_index()
            return
        if path == "/openapi.json":
            self._serve_openapi_json()
            return
        if path == "/swagger":
            self._serve_swagger()
            return
        if path == "/logs":
            self._serve_logs()
            return
        if path == "/admin":
            self._serve_admin()
            return
        if path == "/sendsms":
            self._serve_sendsms()
            return
        if path == "/docs":
            self._serve_docs()
            return
        if path == "/updates":
            self._serve_updates()
            return
        if path == "/check_update":
            self._check_update()
            return
        if path == "/theme.js":
            self._serve_js()
            return
        if path == "/baudin.css":
            self._serve_css()
            return
        if path == "/dashboard":
            self._serve_dashboard()
            return
        if path == "/sms_count":
            self._serve_sms_count()
            return
        if path == "/phone":
            self._serve_phone()
            return
        if path.startswith("/readsms"):
            self._serve_readsms()
            return
        if path != "/health":
            self.send_error(404, "Not found")

            return

        try:
            with Connection(
                self.server.modem_url,
                username=self.server.username,
                password=self.server.password,
                timeout=self.server.timeout,
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
            <script src='theme.js'></script>
            <style>
                .bg-company {background-color:#0060ac;}
                .btn-company {background-color:#0060ac;border-color:#0060ac;color:#fff;}
                .text-company {color:#0060ac;}
            </style>
            <script>
                async function loadData() {
                    const [healthResp, dashResp] = await Promise.all([
                        fetch('/health'),
                        fetch('/dashboard')
                    ]);
                    const health = await healthResp.json();
                    const dashboard = await dashResp.json();
                    document.getElementById('health').textContent = JSON.stringify(health, null, 2);
                    document.getElementById('sentCount').textContent = dashboard.sent_total;
                    document.getElementById('receivedCount').textContent = dashboard.received_total;
                    document.getElementById('lastSender').textContent = dashboard.last_sender || 'N/A';
                    const networkInfo = `${health.operator_name.toUpperCase()} ${health.network_type} ${health.signal_bars}`;
                    document.getElementById('networkInfo').textContent = networkInfo;
                }
                window.onload = loadData;
            </script>
        </head>
        <body class='container-fluid px-3 py-4'>

            {NAVBAR}
            <div class='container mb-4'>
                <div class='row text-center'>
                    <div class='col'>
                        <div class='p-3 bg-light rounded'>SMS envoyés : <span id='sentCount'>-</span></div>
                    </div>
                    <div class='col'>
                        <div class='p-3 bg-light rounded'>SMS reçus : <span id='receivedCount'>-</span></div>
                    </div>
                    <div class='col'>
                        <div class='p-3 bg-light rounded'>Dernier expéditeur : <span id='lastSender'>-</span></div>
                    </div>
                    <div class='col'>
                        <div class='p-3 bg-light rounded'>Réseau : <span id='networkInfo'>-</span></div>
                    </div>
                </div>
            </div>
            <div class='p-5 mb-4 bg-body-tertiary rounded-3 text-center'>
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

        html_lines = [
            "<html><head><meta charset='utf-8'><title>Historique SMS</title>",
            "<link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'>",
            "<link rel='stylesheet' href='baudin.css'>",

            "<script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>",
            "<script src='theme.js'></script>",
            "<style>.bg-company{background-color:#0060ac;}.btn-company{background-color:#0060ac;border-color:#0060ac;}.text-company{color:#0060ac;}</style>",
            "<script>function selectAll(){document.querySelectorAll('.rowchk').forEach(c=>c.checked=true);}</script>",
            "</head><body class='container-fluid px-3 py-4'>",
            self._navbar_html(),
            "<div class='p-5 mb-4 bg-body-tertiary rounded-3 text-center'>",
            "<h1 class='display-6 text-company mb-0'>Historique des SMS</h1>",
            "</div>",
            "<div class='container'>",
            "<form method='post' action='/logs/delete'>",
            "<table class='table table-striped'>",
            "<tr><th></th><th>Date/Heure</th><th>Expéditeur</th><th>Destinataire(s)</th><th>Message</th><th>Réponse</th></tr>",
        ]
        for row in rows:
            html_lines.append(
                (
                    "<tr>"
                    "<td><input type='checkbox' class='rowchk' name='ids' value='"
                    f"{row['id']}'></td>"
                    f"<td>{html.escape(row['timestamp'])}</td>"
                    f"<td>{html.escape(row['sender'] or '')}</td>"
                    f"<td>{html.escape(row['phone'])}</td>"
                    f"<td>{html.escape(row['message'])}</td>"
                    f"<td>{html.escape(row['response'])}</td>"
                    "</tr>"
                )
            )
        html_lines.extend(
            [
                "</table>",
                (
                    "<p><button type='button' class='btn btn-secondary me-2' onclick='selectAll()'>"
                    "Sélectionner tout</button> <button type='submit' class='btn btn-danger'>Supprimer</button></p>"
                ),
                "</form>",
                "</div>" + footer_html() + "</body></html>",
            ]
        )
        body = "".join(html_lines).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_readsms(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        want_json = (
            "json" in params
            or parsed.query == "json"
            or "application/json" in self.headers.get("Accept", "")
        )

        try:
            with Connection(
                self.server.modem_url,
                username=self.server.username,
                password=self.server.password,
                timeout=self.server.timeout,
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

        html_lines = [
            "<html><head><meta charset='utf-8'><title>SMS reçus</title>",
            "<link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'>",
            "<link rel='stylesheet' href='baudin.css'>",
            "<script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>",
            "<script src='theme.js'></script>",
            "<style>.bg-company{background-color:#0060ac;}.btn-company{background-color:#0060ac;border-color:#0060ac;}.text-company{color:#0060ac;}</style>",

            "<script>function selectAll(){document.querySelectorAll('.rowchk').forEach(c=>c.checked=true);}</script>",
            "</head><body class='container-fluid px-3 py-4'>",
            self._navbar_html(),
            "<div class='p-5 mb-4 bg-body-tertiary rounded-3 text-center'>",
            "<h1 class='display-6 text-company mb-0'>SMS reçus</h1>",
            "</div>",
            "<div class='container'>",

            "<form method='post' action='/readsms/delete'>",
            "<table class='table table-striped'>",
            "<tr><th></th><th>Date/Heure</th><th>Expéditeur</th><th>Message</th></tr>",
        ]
        for m in messages:
            html_lines.append(
                (
                    "<tr>"
                    "<td><input type='checkbox' class='rowchk' name='ids' value='"
                    f"{m['Index']}'></td>"
                    f"<td>{html.escape(m['Date'])}</td>"
                    f"<td>{html.escape(m['Phone'])}</td>"
                    f"<td>{html.escape(m.get('Content') or '')}</td>"
                    "</tr>"
                )
            )
        html_lines.extend([
            "</table>",
            (
                "<p><button type='button' class='btn btn-secondary me-2' onclick='selectAll()'>"
                "Sélectionner tout</button> <button type='submit' class='btn btn-danger'>Supprimer</button></p>"
            ),
            "</form>",
            "</div>" + footer_html() + "</body></html>",
        ])

        body = "".join(html_lines).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_sendsms(self):
        html = """
        <html>
        <head>
            <meta charset='utf-8'>
            <title>Envoyer un SMS</title>
            <link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'>
            <link rel='stylesheet' href='baudin.css'>

            <script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>
            <script src='theme.js'></script>
            <style>
                .bg-company {background-color:#0060ac;}
                .btn-company {background-color:#0060ac;border-color:#0060ac;color:#fff;}
                .text-company {color:#0060ac;}
            </style>
            <script>
                async function searchBaudin() {
                    const id = document.getElementById('baudinId').value.trim();
                    if (!id) return;
                    try {
                        const r = await fetch('/phone?id=' + encodeURIComponent(id));
                        let phone = 'Introuvable';
                        if (r.ok) {
                            const j = await r.json();
                            phone = j.phone || 'Introuvable';
                        }
                        document.getElementById('foundPhone').textContent = phone;
                        document.getElementById('baudinResult').style.display = 'block';
                        const btn = document.getElementById('addPhoneBtn');
                        if (phone && phone !== 'Introuvable' && phone !== 'Erreur') {
                            btn.style.display = 'inline-block';
                        } else {
                            btn.style.display = 'none';
                        }
                    } catch(e) {
                        document.getElementById('foundPhone').textContent = 'Erreur';
                        document.getElementById('baudinResult').style.display = 'block';
                        document.getElementById('addPhoneBtn').style.display = 'none';
                    }
                }

                function addPhone() {
                    const phone = document.getElementById('foundPhone').textContent.trim();
                    if (!phone || phone === 'Introuvable' || phone === 'Erreur') return;
                    const to = document.getElementById('to');
                    if (to.value.trim()) {
                        to.value = to.value.trim() + ',' + phone;
                    } else {
                        to.value = phone;
                    }
                    document.getElementById('addPhoneBtn').style.display = 'none';
                }

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
            <div class='p-5 mb-4 bg-body-tertiary rounded-3 text-center'>
                <h1 class='display-6 text-company mb-0'>Envoyer un SMS</h1>
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
                <button class='btn btn-company mb-3 w-100' type='button' data-bs-toggle='collapse' data-bs-target='#baudinSearch' aria-expanded='false' aria-controls='baudinSearch'>
                    🔎 Recherche avancée via Kafka
                </button>
                <div class='collapse mb-3' id='baudinSearch'>
                    <div class='row g-3'>
                        <div class='col-md-6'>
                            <div class='card card-body h-100'>
                                <div class='mb-3'>
                                    <label for='baudinId' class='form-label'>Identifiant Baudin</label>
                                    <div class='input-group'>
                                        <input type='text' id='baudinId' class='form-control'>
                                        <button type='button' class='btn btn-secondary' onclick='searchBaudin()'>Rechercher</button>
                                    </div>
                                </div>
                                <div id='baudinResult' class='mb-3' style='display:none;'>
                                    <span id='foundPhone'></span>
                                    <button type='button' id='addPhoneBtn' class='btn btn-company btn-sm ms-2' onclick='addPhone()'>Ajouter</button>
                                </div>
                            </div>
                        </div>
                        <div class='col-md-6'>
                            <div class='card card-body h-100'>
                                <p class='text-muted mb-0'>Recherche de groupe à venir...</p>
                            </div>
                        </div>
                    </div>
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

    def _serve_admin(self):
        try:
            with open(self.server.config_path, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
        html_page = f"""
        <html>
        <head>
            <meta charset='utf-8'>
            <title>Administration</title>
            <link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'>
            <link rel='stylesheet' href='baudin.css'>
            <script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>
            <script src='theme.js'></script>
            <style>.bg-company{{background-color:#0060ac;}}</style>
        </head>
        <body class='container-fluid px-3 py-4'>
            {self._navbar_html()}
            <div class='p-5 mb-4 bg-body-tertiary rounded-3 text-center'>
                <h1 class='display-6 text-company mb-0'>Administration</h1>
            </div>
            <div class='container'>
            <form method='post' action='/admin/save'>
                <div class='mb-3'>
                    <label for='modem_url' class='form-label'>URL du modem</label>
                    <input type='text' name='modem_url' id='modem_url' class='form-control' value='{html.escape(cfg.get("modem_url", self.server.modem_url))}'>
                </div>
                <div class='mb-3'>
                    <label for='username' class='form-label'>Utilisateur</label>
                    <input type='text' name='username' id='username' class='form-control' value='{html.escape(cfg.get("username", self.server.username or ""))}'>
                </div>
                <div class='mb-3'>
                    <label for='password' class='form-label'>Mot de passe</label>
                    <input type='password' name='password' id='password' class='form-control' value='{html.escape(cfg.get("password", self.server.password or ""))}'>
                </div>
                <div class='mb-3'>
                    <label for='api_key' class='form-label'>Clé API</label>
                    <input type='text' name='api_key' id='api_key' class='form-control' value='{html.escape(cfg.get("api_key", self.server.api_key or ""))}'>
                </div>
                <div class='mb-3'>
                    <label for='certfile' class='form-label'>Certificat TLS</label>
                    <input type='text' name='certfile' id='certfile' class='form-control' value='{html.escape(cfg.get("certfile", self.server.certfile or ""))}'>
                </div>
                <div class='mb-3'>
                    <label for='keyfile' class='form-label'>Clé privée TLS</label>
                    <input type='text' name='keyfile' id='keyfile' class='form-control' value='{html.escape(cfg.get("keyfile", self.server.keyfile or ""))}'>
                </div>
                <div class='mb-3'>
                    <label for='kafka_client_id' class='form-label'>KAFKA_CLIENT_ID</label>
                    <input type='text' name='kafka_client_id' id='kafka_client_id' class='form-control' value='{html.escape(cfg.get("kafka_client_id", self.server.kafka_client_id))}'>
                </div>
                <div class='mb-3'>
                    <label for='kafka_url' class='form-label'>KAFKA_URL</label>
                    <input type='text' name='kafka_url' id='kafka_url' class='form-control' value='{html.escape(cfg.get("kafka_url", self.server.kafka_url))}'>
                </div>
                <div class='mb-3'>
                    <label for='kafka_group_id' class='form-label'>KAFKA_GROUP_ID</label>
                    <input type='text' name='kafka_group_id' id='kafka_group_id' class='form-control' value='{html.escape(cfg.get("kafka_group_id", self.server.kafka_group_id))}'>
                </div>
                <div class='mb-3'>
                    <label for='kafka_username' class='form-label'>KAFKA_USERNAME</label>
                    <input type='text' name='kafka_username' id='kafka_username' class='form-control' value='{html.escape(cfg.get("kafka_username", self.server.kafka_username))}'>
                </div>
                <div class='mb-3'>
                    <label for='kafka_password' class='form-label'>KAFKA_PASSWORD</label>
                    <input type='text' name='kafka_password' id='kafka_password' class='form-control' value='{html.escape(cfg.get("kafka_password", self.server.kafka_password))}'>
                </div>
                <div class='mb-3'>
                    <label for='kafka_ca_cert' class='form-label'>KAFKA_CA_CERT</label>
                    <input type='text' name='kafka_ca_cert' id='kafka_ca_cert' class='form-control' value='{html.escape(cfg.get("kafka_ca_cert", self.server.kafka_ca_cert))}'>
                </div>
                <div class='mb-3'>
                    <label for='kafka_privkey' class='form-label'>KAFKA_PRIVKEY</label>
                    <input type='text' name='kafka_privkey' id='kafka_privkey' class='form-control' value='{html.escape(cfg.get("kafka_privkey", self.server.kafka_privkey))}'>
                </div>
                <div class='mb-3'>
                    <label for='kafka_cert' class='form-label'>KAFKA_CERT</label>
                    <input type='text' name='kafka_cert' id='kafka_cert' class='form-control' value='{html.escape(cfg.get("kafka_cert", self.server.kafka_cert))}'>
                </div>
                <button type='submit' class='btn btn-company me-2'>Enregistrer</button>
                <button type='button' class='btn btn-danger' onclick="fetch('/admin/restart', {{method:'POST'}}).then(()=>alert('Redémarrage...'))">Redémarrer</button>
            </form>
            </div>
            {footer_html()}
        </body>
        </html>
        """
        body = html_page.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _save_admin(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        params = urllib.parse.parse_qs(body)
        cfg = {
            'modem_url': params.get('modem_url', [''])[0],
            'username': params.get('username', [''])[0],
            'password': params.get('password', [''])[0],
            'api_key': params.get('api_key', [''])[0],
            'certfile': params.get('certfile', [''])[0],
            'keyfile': params.get('keyfile', [''])[0],
            'kafka_client_id': params.get('kafka_client_id', [''])[0],
            'kafka_url': params.get('kafka_url', [''])[0],
            'kafka_group_id': params.get('kafka_group_id', [''])[0],
            'kafka_username': params.get('kafka_username', [''])[0],
            'kafka_password': params.get('kafka_password', [''])[0],
            'kafka_ca_cert': params.get('kafka_ca_cert', [''])[0],
            'kafka_privkey': params.get('kafka_privkey', [''])[0],
            'kafka_cert': params.get('kafka_cert', [''])[0],
        }
        try:
            with open(self.server.config_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2)
        except Exception:
            pass
        self.server.modem_url = cfg['modem_url']
        self.server.username = cfg['username']
        self.server.password = cfg['password']
        self.server.api_key = cfg['api_key'] or None
        self.server.certfile = cfg['certfile'] or None
        self.server.keyfile = cfg['keyfile'] or None
        self.server.kafka_client_id = cfg['kafka_client_id'] or "sms"
        self.server.kafka_url = cfg['kafka_url']
        self.server.kafka_group_id = cfg['kafka_group_id'] or "sms-consumer"
        self.server.kafka_username = cfg['kafka_username']
        self.server.kafka_password = cfg['kafka_password']
        self.server.kafka_ca_cert = cfg['kafka_ca_cert']
        self.server.kafka_privkey = cfg['kafka_privkey']
        self.server.kafka_cert = cfg['kafka_cert']
        self.send_response(303)
        self.send_header('Location', '/admin')
        self.end_headers()

    def _restart_service(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Redemarrage...')
        try:
            self.wfile.flush()
        except Exception:
            pass
        self.server.restart()

    def _check_update(self):
        repo_dir = os.path.join(os.path.dirname(__file__), os.pardir)
        try:
            branch = (
                subprocess.check_output(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir
                )
                .decode()
                .strip()
            )
            logger.debug("Vérification des mises à jour sur la branche %s", branch)
            subprocess.run(["git", "fetch"], cwd=repo_dir, check=False)
            ahead = int(
                subprocess.check_output(
                    ["git", "rev-list", "--count", f"HEAD..origin/{branch}"],
                    cwd=repo_dir,
                )
                .decode()
                .strip()
            )
            available = ahead > 0
            logger.debug("Commits en attente: %s", ahead)
        except Exception:
            available = False
        self._send_json(200, {"update_available": available})

    def _run_update(self):
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "install.sh")
        script = os.path.abspath(script)
        logger.info("Lancement de la mise à jour avec %s", script)
        try:
            subprocess.Popen(["bash", script], cwd=os.path.dirname(script))
            logger.info("Script de mise à jour démarré")
            self._send_json(200, {"status": "started"})
        except Exception as exc:
            logger.error("Erreur lors du lancement de la mise à jour: %s", exc)
            self._json_error(500, str(exc))

    def _serve_docs(self):
        html = """
        <html>
        <head>
            <meta charset='utf-8'>
            <title>Documentation API</title>
            <link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'>
            <link rel='stylesheet' href='baudin.css'>

            <script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>
            <script src='theme.js'></script>
            <style>
                .bg-company {background-color:#0060ac;}
                .btn-company {background-color:#0060ac;border-color:#0060ac;}
                .text-company {color:#0060ac;}
            </style>
        </head>
        <body class='container-fluid px-3 py-4'>
            {NAVBAR}
            <div class='p-5 mb-4 bg-body-tertiary rounded-3 text-center'>
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
                                <small>En-tête <code>X-API-KEY</code> requis</small>
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
        path = os.path.join(os.path.dirname(__file__), os.pardir, "docs", "mise-a-jour.md")
        try:
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            lines = ["Impossible de charger le journal des mises à jour."]

        html_lines = ["<html><head><meta charset='utf-8'><title>Mises à jour</title>",
                      "<link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'>",
                      "<link rel='stylesheet' href='baudin.css'>",
                      "<script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>",
                      "<script src='theme.js'></script>",
                      "<style>.bg-company{background-color:#0060ac;}.btn-company{background-color:#0060ac;border-color:#0060ac;}.text-company{color:#0060ac;}</style>",
                      "</head><body class='container-fluid px-3 py-4'>",
                      "{NAVBAR}",
                      "<div class='p-5 mb-4 bg-body-tertiary rounded-3 text-center'>",
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
        path = os.path.join(os.path.dirname(__file__), os.pardir, 'baudin.css')
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

    def _serve_js(self):
        path = os.path.join(os.path.dirname(__file__), os.pardir, 'theme.js')
        try:
            with open(path, 'rb') as f:
                js = f.read()
        except Exception:
            js = b''
        self.send_response(200)
        self.send_header('Content-Type', 'application/javascript')
        self.send_header('Content-Length', str(len(js)))
        self.end_headers()
        self.wfile.write(js)

    def _serve_openapi_json(self):
        try:
            with open(OPENAPI_PATH, 'rb') as f:
                body = f.read()
        except Exception:
            body = b"{}"
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
            <script src='theme.js'></script>
            <script src='https://cdn.jsdelivr.net/npm/swagger-ui-dist/swagger-ui-bundle.js'></script>
            <style>.bg-company{{background-color:#0060ac;}}</style>
        </head>
        <body class='container-fluid px-3 py-4'>
            {self._navbar_html()}
            <p class='mt-3'>L'en-tête <code>X-API-KEY</code> est requis pour l'opération POST <code>/sms</code>.</p>
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
                timeout=self.server.timeout,
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
        path = urllib.parse.urlparse(self.path).path
        if path == "/logs/delete":
            self._delete_logs()
            return
        if path == "/readsms/delete":
            self._delete_sms()
            return
        if path == "/admin/save":
            self._save_admin()
            return
        if path == "/admin/restart":
            self._restart_service()
            return
        if path == "/update":
            self._run_update()
            return
        if path != "/sms":

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
                timeout=self.server.timeout,
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
