import json
from functools import lru_cache

from .config import DATA_DIR


@lru_cache
def load_registry():
    with open(DATA_DIR / "banks.json", encoding="utf-8") as f:
        return json.load(f)


@lru_cache
def load_keywords():
    with open(DATA_DIR / "keywords.json", encoding="utf-8") as f:
        return json.load(f)


def banks():
    return load_registry()["banks"]


def national():
    return load_registry()["national"]


def get_bank(bank_id):
    for b in banks():
        if b["id"] == bank_id:
            return b
    return None


def host_is_official(host, bank):
    """True if host is one of the bank's domains or a subdomain of one."""
    host = host.lower().strip(".")
    for d in bank["domains"]:
        if host == d or host.endswith("." + d):
            return True
    return False


def official_bank_for_host(host):
    for b in banks():
        if host_is_official(host, b):
            return b
    return None
