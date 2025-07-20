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
ExecStart=/data/bc-api-sms/venv/bin/python examples/sms_http_api.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## Enable and start the service
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bc-api-sms.service
```
