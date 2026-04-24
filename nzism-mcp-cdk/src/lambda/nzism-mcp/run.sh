#!/bin/bash
exec python -m uvicorn server:app --host 0.0.0.0 --port 8080 --forwarded-allow-ips='*' --proxy-headers
