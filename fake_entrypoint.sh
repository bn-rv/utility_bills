#!/usr/bin/env sh

while true; do printf 'HTTP/1.1 200 OK\r\nContent-Length: 12\r\nContent-Type: text/plain\r\n\r\nHello world' | nc -l -p 8000; done

exec "$@"
