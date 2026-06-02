# -*- coding: utf-8 -*-
from license.manager import (
    verify_license, verify_license_data, generate_license, hash_fingerprint,
    activate_with_code,
)
from license.hardware import collect_fingerprint

__all__ = [
    'verify_license',
    'verify_license_data',
    'generate_license',
    'hash_fingerprint',
    'activate_with_code',
    'collect_fingerprint',
]
