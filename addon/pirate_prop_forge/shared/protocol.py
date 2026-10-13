"""Protocolo entre el plugin y el worker de IA: una linea JSON por mensaje (stdin/stdout, UTF-8).

plugin -> worker:  {"id": n, "cmd": "hello"|"generate"|"cancel"|"status"|"shutdown", ...}
worker -> plugin:  {"event": "ready"|"progress"|"result"|"error"|"cooldown"|"cooldown_done"|"log", "id": n, ...}
"""
import json

PROTOCOL_VERSION = 1


def encode(message):
    return json.dumps(message, ensure_ascii=False, separators=(",", ":"))


def decode(line):
    line = line.strip()
    if not line:
        return None
    try:
        msg = json.loads(line)
    except ValueError:
        return None
    return msg if isinstance(msg, dict) else None


def error(job_id, code, message, **extra):
    return dict({"event": "error", "id": job_id, "code": code, "message": message}, **extra)
