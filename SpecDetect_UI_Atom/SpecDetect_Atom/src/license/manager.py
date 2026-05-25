# -*- coding: utf-8 -*-
"""许可证管理 — 生成、验证、签名"""

import hashlib
import hmac
import json
import os
import socket
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from license.hardware import collect_fingerprint

PRODUCT_SECRET = b'SpecDetect_Atom_v1.0_internal_secret_key'

LICENSE_FILENAME = 'license.dat'
MATCH_REQUIRED = 2
MATCH_KEYS = ('motherboard', 'disk', 'cpu', 'mac')


def _sign(data: str) -> str:
    return hmac.new(PRODUCT_SECRET, data.encode(), hashlib.sha256).hexdigest()


def hash_fingerprint(fp: Dict[str, Optional[str]]) -> Dict[str, Optional[str]]:
    """对硬件指纹做 SHA256 哈希，None 值保持为 None"""
    return {
        k: hashlib.sha256(v.encode()).hexdigest() if v else None
        for k, v in fp.items()
    }


def _verify_signature(data: dict) -> bool:
    stored_sig = data.get('signature', '')
    payload = {k: v for k, v in data.items() if k != 'signature'}
    payload_str = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hmac.compare_digest(_sign(payload_str), stored_sig)


def _find_license_path(license_path: Optional[str] = None) -> str:
    if license_path:
        return license_path

    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        return os.path.join(exe_dir, 'config', LICENSE_FILENAME)

    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        cfg = os.path.join(current, 'config')
        if os.path.isdir(cfg):
            return os.path.join(cfg, LICENSE_FILENAME)
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    raise FileNotFoundError("找不到项目根目录的 config/ 文件夹，无法定位许可证文件")


def _verify_devices(devices: List[Dict[str, Any]]) -> bool:
    """核心：用当前硬件指纹与已注册设备列表比对（4 选 2）"""
    current_fp = hash_fingerprint(collect_fingerprint())

    for device in devices:
        stored_fp: Dict[str, Optional[str]] = device.get('fingerprint', {})
        matches = 0
        for key in MATCH_KEYS:
            cur_val = current_fp.get(key)
            sto_val = stored_fp.get(key)
            if cur_val is not None and sto_val is not None and cur_val == sto_val:
                matches += 1
        if matches >= MATCH_REQUIRED:
            return True

    return False


def verify_license(license_path: Optional[str] = None) -> bool:
    """从 license.dat 文件验证当前设备是否已授权

    对每个已注册设备，比对 4 项硬件指纹（主板/硬盘/CPU/MAC）。
    跳过不可用的标识符（None），4 项中 ≥ 2 项匹配即视为授权通过。

    Returns:
        True 如果至少一个已注册设备匹配 ≥ 2 项
    """
    path = _find_license_path(license_path)
    if not os.path.exists(path):
        return False

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data: Dict[str, Any] = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False

    return verify_license_data(data)


def verify_license_data(data: dict) -> bool:
    """用内存中的许可证数据验证当前设备（用于嵌入式许可证）

    Args:
        data: 已加载的许可证字典（须包含 signature 和 devices）

    Returns:
        True 如果至少一个已注册设备匹配 ≥ 2 项
    """
    if not _verify_signature(data):
        return False

    devices: List[Dict[str, Any]] = data.get('devices', [])
    if not devices:
        return False

    return _verify_devices(devices)


def generate_license(
    license_path: Optional[str] = None,
    device_name: str = '',
    merge: bool = False
) -> Tuple[str, Dict[str, Optional[str]]]:
    """为当前设备生成/追加许可证

    Args:
        license_path: 许可证文件路径，默认 config/license.dat
        device_name: 设备名称，默认取主机名
        merge: 是否追加到已有许可证（默认覆盖）

    Returns:
        (许可证文件路径, 当前硬件指纹哈希)

    Raises:
        ValueError: 设备已注册、设备名冲突、或已有许可证被篡改
    """
    path = _find_license_path(license_path)

    current_fp = hash_fingerprint(collect_fingerprint())
    hostname = device_name or socket.gethostname()

    new_device: Dict[str, Any] = {
        'name': hostname,
        'fingerprint': current_fp,
        'registered_at': datetime.now().isoformat()
    }

    if merge and os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            raise ValueError('许可证文件已损坏，无法读取')

        if not _verify_signature(data):
            raise ValueError('已有许可证签名无效，可能已被篡改')

        devices: List[Dict[str, Any]] = data.setdefault('devices', [])

        existing_names = {d.get('name', '') for d in devices}
        existing_fps = {
            json.dumps(d.get('fingerprint', {}), sort_keys=True)
            for d in devices
        }
        new_fp_str = json.dumps(current_fp, sort_keys=True)

        if new_fp_str in existing_fps:
            raise ValueError('设备已注册（指纹匹配已存在的设备）')
        if hostname in existing_names:
            raise ValueError(f'设备名 "{hostname}" 已存在，请使用 --name 指定其他名称')

        devices.append(new_device)
    else:
        data = {
            'version': 1,
            'devices': [new_device]
        }

    data.pop('signature', None)
    payload = json.dumps(data, sort_keys=True, ensure_ascii=False)
    data['signature'] = _sign(payload)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return path, current_fp
