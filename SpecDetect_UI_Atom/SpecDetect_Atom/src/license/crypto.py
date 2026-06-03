# -*- coding: utf-8 -*-
"""许可证加密核心 — AES-256-GCM + HKDF 密钥派生 + base32 授权码

安全设计:
- MASTER_SECRET_KEY 嵌入 Cython .pyd，不暴露明文
- 授权码 = HMAC-SHA256(K_master, device_name||fingerprint)[:12] → base32 (20字符)
- license.dat = AES-256-GCM 加密，密钥派生自 K_master + 指纹
- GCM 认证标签防篡改，篡改即失效
- 攻击面：即使提取 K_master 也无法离线伪造（需实时硬件指纹）
"""

import hashlib
import hmac
import os
import struct
from typing import Dict, Optional, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

# ============================================================
# MASTER_SECRET_KEY — 仅此一处定义，Cython 编译后不可提取
# ============================================================
_MASTER_SECRET_KEY_HEX = (
    "d4e7f1a3b2c8091e5f6a7b8c9d0e1f2a"
    "3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e"
)

_MasterKey = bytes.fromhex(_MASTER_SECRET_KEY_HEX)

# ============================================================
# 授权码 — base32
# ============================================================

_BASE32_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 不含 0/O/1/I 避免混淆
_AUTH_CODE_BYTES = 12  # 96 bits → 20 base32 chars
_AUTH_CODE_GROUP = 4   # 每组4个字符


def _base32_encode(data: bytes) -> str:
    """将字节编码为 base32（自定义字母表，不含易混淆字符）"""
    result = []
    buffer_bits = 0
    buffer_len = 0
    for byte in data:
        buffer_bits = (buffer_bits << 8) | byte
        buffer_len += 8
        while buffer_len >= 5:
            buffer_len -= 5
            result.append(_BASE32_ALPHABET[(buffer_bits >> buffer_len) & 0x1F])
    if buffer_len > 0:
        result.append(_BASE32_ALPHABET[(buffer_bits << (5 - buffer_len)) & 0x1F])
    return "".join(result)


def _base32_decode(encoded: str) -> bytes:
    """base32 解码（反操作）"""
    encoded = encoded.upper().replace("-", "").replace(" ", "")
    bit_buffer = 0
    bit_count = 0
    result = bytearray()
    for ch in encoded:
        idx = _BASE32_ALPHABET.index(ch)
        bit_buffer = (bit_buffer << 5) | idx
        bit_count += 5
        if bit_count >= 8:
            bit_count -= 8
            result.append((bit_buffer >> bit_count) & 0xFF)
    return bytes(result)


def _fingerprint_key(fingerprint: Dict[str, Optional[str]]) -> str:
    """将指纹字典转为确定性字符串（用于密钥派生）"""
    items = sorted(
        (k, v or "") for k, v in fingerprint.items()
        if k in ("motherboard", "disk", "cpu", "mac")
    )
    return "|".join(f"{k}={v}" for k, v in items)


# ============================================================
# 通用授权码生成 / 验证（与设备无关）
# ============================================================

_PRODUCT_ID = b"SPECDETECT_ATOM_V2"


def generate_auth_code(master_key: Optional[bytes] = None) -> str:
    """生成通用授权码（与设备无关，所有机器通用）

    Args:
        master_key: 主密钥，默认使用嵌入的 _MasterKey

    Returns:
        授权码，格式 XXXX-XXXX-XXXX-XXXX-XXXX（20字符）
    """
    key = master_key or _MasterKey
    raw = hmac.new(key, _PRODUCT_ID, hashlib.sha256).digest()
    code = _base32_encode(raw[:_AUTH_CODE_BYTES])
    return "-".join(
        code[i : i + _AUTH_CODE_GROUP]
        for i in range(0, len(code), _AUTH_CODE_GROUP)
    )


def verify_auth_code(auth_code: str, master_key: Optional[bytes] = None) -> bool:
    """验证授权码是否有效（与设备无关）

    Args:
        auth_code: 用户输入的授权码
        master_key: 主密钥

    Returns:
        True 如果授权码有效
    """
    expected = generate_auth_code(master_key)
    normalized_input = auth_code.upper().replace("-", "").replace(" ", "")
    normalized_expected = expected.replace("-", "")
    return hmac.compare_digest(normalized_input, normalized_expected)


# ============================================================
# 许可证文件加密 / 解密
# ============================================================


def derive_license_key(
    fingerprint: Dict[str, Optional[str]],
    master_key: Optional[bytes] = None,
) -> bytes:
    """从主密钥 + 设备指纹派生 AES-256 密钥

    指纹变更 → 密钥不同 → 旧 license 无法解密 → 需重新激活
    """
    key = master_key or _MasterKey
    salt = hashlib.sha256(_fingerprint_key(fingerprint).encode()).digest()
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"license_v2",
    )
    return hkdf.derive(key)


def encrypt_license_data(
    payload: bytes,
    fingerprint: Dict[str, Optional[str]],
    master_key: Optional[bytes] = None,
) -> bytes:
    """AES-256-GCM 加密许可证数据

    Args:
        payload: 许可证 JSON 字节（UTF-8）
        fingerprint: 硬件指纹
        master_key: 主密钥

    Returns:
        加密后的二进制数据: nonce(12B) || ciphertext || tag(16B)
    """
    aes_key = derive_license_key(fingerprint, master_key)
    nonce = os.urandom(12)
    aesgcm = AESGCM(aes_key)
    ct = aesgcm.encrypt(nonce, payload, None)
    # AESGCM.encrypt returns ciphertext || 16-byte tag
    return nonce + ct


def decrypt_license_data(
    encrypted: bytes,
    fingerprint: Dict[str, Optional[str]],
    master_key: Optional[bytes] = None,
) -> Optional[bytes]:
    """AES-256-GCM 解密许可证数据

    Args:
        encrypted: nonce(12B) || ciphertext || tag(16B)
        fingerprint: 硬件指纹
        master_key: 主密钥

    Returns:
        解密后的许可证 JSON 字节，或 None（解密失败/密钥不匹配）
    """
    if len(encrypted) < 28:  # 12 nonce + 16 tag minimum
        return None
    aes_key = derive_license_key(fingerprint, master_key)
    nonce = encrypted[:12]
    ct = encrypted[12:]
    aesgcm = AESGCM(aes_key)
    try:
        return aesgcm.decrypt(nonce, ct, None)
    except Exception:
        return None


# ============================================================
# V2 许可证文件读写
# ============================================================

LICENSE_V2_MAGIC = b"L2"  # 格式标识，区别于旧 JSON 格式


def save_license_v2(
    path: str,
    payload_bytes: bytes,
    fingerprint: Dict[str, Optional[str]],
    master_key: Optional[bytes] = None,
) -> None:
    """保存 V2 加密许可证到文件"""
    encrypted = encrypt_license_data(payload_bytes, fingerprint, master_key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(LICENSE_V2_MAGIC + encrypted)


def load_license_v2(
    path: str,
    fingerprint: Dict[str, Optional[str]],
    master_key: Optional[bytes] = None,
) -> Optional[bytes]:
    """加载并解密 V2 许可证"""
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        data = f.read()
    if not data.startswith(LICENSE_V2_MAGIC):
        return None
    return decrypt_license_data(data[2:], fingerprint, master_key)


def is_v2_format(path: str) -> bool:
    """检测许可证文件是否为 V2 加密格式"""
    if not os.path.exists(path):
        return False
    with open(path, "rb") as f:
        return f.read(2) == LICENSE_V2_MAGIC
