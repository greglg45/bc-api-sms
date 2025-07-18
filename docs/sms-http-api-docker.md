# SMS HTTP API Docker Guide

This guide explains how to build the Docker image for the example SMS HTTP API, run the container and send your first SMS.

## Build the image

```bash
docker build -t sms-api .
```

This command creates an image containing the API server from `examples/sms_http_api.py`.

## Run the container

Set the environment variables for your modem connection and start the container:

```bash
docker run -d \
  -e MODEM_URL="http://192.168.8.1/" \
  -e USERNAME=admin \
  -e PASSWORD=YOUR_PASSWORD \
  -p 8000:8000 sms-api
```

`MODEM_URL` is required and should point to your Huawei modem. `USERNAME` and `PASSWORD` supply login credentials. You can optionally set `HOST` and `PORT` to change the listening address (default `0.0.0.0:8000`).

The API server will now be reachable on the host at the chosen port.

## Send your first SMS

Prepare the JSON payload and use `curl` to call the API:

```bash
curl -X POST http://localhost:8000/sms \
  -H "Content-Type: application/json" \
  -d '{"to": ["+420123456789"], "text": "Hello from the API!"}'
```

If the request succeeds, the server responds with `OK`.

## Alternative usage

You can also run the API directly outside Docker using:

```bash
python examples/sms_http_api.py http://192.168.8.1/ --username admin --password YOUR_PASSWORD
```

See the script's docstring for additional options.
