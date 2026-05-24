# -*- coding: utf-8 -*-
"""硬件指纹采集 — 主板、硬盘、CPU、MAC 地址"""

import logging
import re
import subprocess
import uuid
from typing import Dict, List, Optional

_logger = logging.getLogger(__name__)

_CACHE: Dict[str, Optional[str]] = {}
_CACHE_MACS: Optional[List[str]] = None

_SAFE_ID = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_WMIC_TIMEOUT = 10
_FLAGS = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0


def _wmic(cls: str, prop: str, extra: str = '') -> Optional[str]:
    """WMIC 查询硬件属性，失败时回退到 PowerShell，都失败返回 None"""
    if not _SAFE_ID.match(cls) or not _SAFE_ID.match(prop):
        raise ValueError(f"Invalid hardware identifier: {cls}.{prop}")

    for attempt in (
        _run_wmic(cls, prop, extra),
        _run_powershell(cls, prop),
    ):
        if attempt:
            return attempt
    return None


def _run_wmic(cls: str, prop: str, extra: str = '') -> Optional[str]:
    target = f'{cls} {extra}'.strip()
    try:
        result = subprocess.run(
            ['wmic', target, 'get', prop],
            capture_output=True, text=True, timeout=_WMIC_TIMEOUT,
            creationflags=_FLAGS
        )
        lines = result.stdout.strip().split('\n')
        for line in lines[1:]:
            value = line.strip()
            if value:
                return value
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
        pass
    return None


def _run_powershell(cls: str, prop: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ['powershell', '-Command', f'(Get-WmiObject Win32_{cls}).{prop}'],
            capture_output=True, text=True, timeout=_WMIC_TIMEOUT,
            creationflags=_FLAGS
        )
        value = result.stdout.strip()
        if value:
            return value
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
        pass
    return None


def get_motherboard_serial() -> Optional[str]:
    """获取主板序列号"""
    if 'mb' not in _CACHE:
        _CACHE['mb'] = _wmic('baseboard', 'serialnumber')
        if _CACHE['mb'] is None:
            _logger.warning('无法获取主板序列号')
    return _CACHE['mb']


def get_disk_serial() -> Optional[str]:
    """获取系统盘（Index=0）物理序列号，失败不降级"""
    if 'disk' not in _CACHE:
        _CACHE['disk'] = _wmic('diskdrive', 'serialnumber', extra='where Index=0')
        if _CACHE['disk'] is None:
            _logger.warning('无法获取系统盘序列号')
    return _CACHE['disk']


def get_cpu_id() -> Optional[str]:
    """获取 CPU 序列号"""
    if 'cpu' not in _CACHE:
        _CACHE['cpu'] = _wmic('cpu', 'processorid')
        if _CACHE['cpu'] is None:
            _logger.warning('无法获取 CPU 序列号')
    return _CACHE['cpu']


def get_mac_list() -> List[str]:
    """获取所有物理网卡 MAC 地址（去除分隔符，大写）

    VM 注意：无物理网卡时 uuid.getnode() 可能返回 0，会被过滤。
    """
    global _CACHE_MACS
    if _CACHE_MACS is not None:
        return _CACHE_MACS

    macs: List[str] = []
    try:
        result = subprocess.run(
            ['wmic', 'nic', 'where', 'PhysicalAdapter=True', 'get', 'MACAddress'],
            capture_output=True, text=True, timeout=_WMIC_TIMEOUT,
            creationflags=_FLAGS
        )
        for line in result.stdout.strip().split('\n')[1:]:
            mac = line.strip().replace(':', '').replace('-', '').upper()
            if mac:
                macs.append(mac)
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
        pass

    if not macs:
        fallback = uuid.getnode()
        if fallback == 0:
            _logger.warning('无物理网卡且 uuid.getnode() 返回 0，MAC 指纹不可用')
        else:
            macs.append(format(fallback, '012X'))

    _CACHE_MACS = macs
    return _CACHE_MACS


def collect_fingerprint() -> Dict[str, Optional[str]]:
    """采集全部硬件指纹，MAC 取第一个物理网卡"""
    macs = get_mac_list()
    return {
        'motherboard': get_motherboard_serial(),
        'disk': get_disk_serial(),
        'cpu': get_cpu_id(),
        'mac': macs[0] if macs else None,
    }
