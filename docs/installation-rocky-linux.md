# Installation on Rocky Linux

## Prerequisites
- Python 3 and pip
- git
- systemd (default on Rocky Linux)

Install basic packages:
```bash
sudo dnf install -y python3 python3-virtualenv git
```

## Clone the repository
```bash
sudo git clone https://github.com/greglg45/bc-api-sms.git /data/bc-api-sms
cd /data/bc-api-sms
```

## Set up the Python environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Sample `systemd` service
Create `/etc/systemd/system/bc-api-sms.service` with the following content:
```ini
[Unit]
Description=bc-api-sms HTTP API
After=network.target

[Service]
Type=simple
WorkingDirectory=/data/bc-api-sms

# Adjust the URL and credentials for your router
ExecStart=/data/bc-api-sms/venv/bin/python sms_http_api.py \
    http://192.168.8.1/ --username admin --password <PASSWORD> \
    --host 0.0.0.0 --port 80 --api-key <CLEF>

Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## Enable and start the service
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bc-api-sms.service
```

## Updating an existing clone

If an older copy of the repository already exists on the server, pull the
latest changes and reinstall the Python requirements:

```bash
cd /data/bc-api-sms
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart bc-api-sms.service
```

This brings the clone up to date and restarts the `bc-api-sms` service with the
new code.
