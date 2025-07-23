from http.server import HTTPServer
import os
import sys
import subprocess
import shutil


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

    def restart(self):
        """Redémarre le service ou le processus."""
        if shutil.which("systemctl"):
            subprocess.run(["systemctl", "restart", "bc-api-sms.service"])
        else:
            os.execv(sys.executable, [sys.executable] + sys.argv)


__all__ = ["SMSHTTPServer"]
