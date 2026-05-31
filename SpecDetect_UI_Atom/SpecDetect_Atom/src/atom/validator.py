# -*- coding: utf-8 -*-
"""
数据审查模块

负责 RMCP 和 streamsrc 数据验证，分层过滤不符合规范的数据
Defense in depth: RMCP 层 + streamsrc 层双端验证
"""

from log.logger import log, LogTag

# ============================================================================
# Layer 1: n_bd_type 白名单 (RMCP 层)
# ============================================================================

# mode -> n_bd_type 白名单
_MODE_BD_TYPE_WHITELIST = {
    'fscan':  {15},           # FSCAN
    'mscan':  {14},           # SGLFREQ (单频点)
    'sglfreq': {11},          # IFANALYSIS
    'pscan':  {16},           # DSCAN
}


def validate_bd_type(mode: str, n_bd_type: int) -> bool:
    """Layer 1: n_bd_type 白名单验证

    Args:
        mode: 当前业务模式 (fscan/mscan/sglfreq/pscan)
        n_bd_type: RMCP 帧的 n_bd_type 值

    Returns:
        True: n_bd_type 在白名单中，放行
        False: n_bd_type 不在白名单中，丢弃
    """
    whitelist = _MODE_BD_TYPE_WHITELIST.get(mode, set())
    if n_bd_type not in whitelist:
        log(f"[FILTER] n_bd_type={n_bd_type} (0x{n_bd_type:02X}) 不在 {mode} 白名单 {whitelist}，丢弃",
            tag=LogTag.FILTER)
        return False
    return True


def get_allowed_bd_types(mode: str) -> set:
    """获取指定 mode 允许的 n_bd_type 集合"""
    return _MODE_BD_TYPE_WHITELIST.get(mode, set())


# ============================================================================
# Layer 2: 数据结构验证 (RMCP 层)
# ============================================================================

def validate_band_structure(band: dict) -> bool:
    """Layer 2: RMCP 回调数据结构验证

    验证 counters、n_arrays、levels 的合理性

    Args:
        band: parse_rmcp_callback_frame 返回的 band_info 字典

    Returns:
        True: 数据结构合法
        False: 数据结构异常，丢弃
    """
    # 1. counters 验证
    counters = band.get('counters', [])
    if not counters or len(counters) < 4:
        log(f"[FILTER] validate_band_structure: counters={counters} 异常，长度不足4",
            tag=LogTag.FILTER)
        return False

    start_idx = counters[2]

    # 2. start_index 范围验证 (FSCAN: 0/512/1024)
    mode = band.get('_mode', 'fscan')
    if mode == 'fscan':
        if start_idx not in (0, 512, 1024):
            log(f"[FILTER] validate_band_structure: start_idx={start_idx} 不在 (0/512/1024) 范围内",
                tag=LogTag.FILTER)
            return False

    # 3. n_arrays 范围验证
    n_arrays = band.get('n_arrays', 0)
    if n_arrays <= 0 or n_arrays > 10000:
        log(f"[FILTER] validate_band_structure: n_arrays={n_arrays} 超出范围 (1-10000)",
            tag=LogTag.FILTER)
        return False

    # 4. levels 数据验证
    levels = band.get('levels', [])
    if not levels:
        log(f"[FILTER] validate_band_structure: levels 为空",
            tag=LogTag.FILTER)
        return False

    if len(levels) != n_arrays:
        log(f"[FILTER] validate_band_structure: levels长度={len(levels)} != n_arrays={n_arrays}",
            tag=LogTag.FILTER)
        return False

    # 5. levels 值范围验证 (全量检查)
    # int16 完整范围: -32768 ~ +32767
    # 放宽到 -1500 ~ +1500，覆盖绝大多数实际场景
    for i, v in enumerate(levels):
        if v < -1500 or v > 1500:
            log(f"[FILTER] validate_band_structure: levels[{i}]={v} 超出范围 (-1500~+1500)",
                tag=LogTag.FILTER)
            return False

    return True


# ============================================================================
# Layer 3: streamsrc 帧封装前验证 (streamsrc 层)
# ============================================================================

# FSCAN indicator 与 start_index 的映射
_FSCAN_INDICATOR_MAP = {
    0:    0x0026,   # Band1
    512:  0x0126,   # Band2
    1024: 0x0168,   # Band3
}


def validate_fscan_frame_params(band: dict, mode: str) -> bool:
    """Layer 3: FSCAN 封帧前参数验证

    在 build_fscan_frame() 之前调用，确保数据合法

    Args:
        band: 频段数据字典
        mode: 业务模式

    Returns:
        True: 参数合法，可以封帧
        False: 参数异常，不封帧
    """
    if mode != 'fscan':
        return True  # 非 FSCAN 模式不验证

    counters = band.get('counters', [0, 0, 0, 0])
    if len(counters) < 4:
        log(f"[FILTER] validate_fscan_frame_params: counters 长度不足4",
            tag=LogTag.FILTER)
        return False

    start_idx = counters[2]

    # 1. indicator 与 start_index 匹配验证
    expected_indicator = _FSCAN_INDICATOR_MAP.get(start_idx)
    if expected_indicator is None:
        log(f"[FILTER] validate_fscan_frame_params: start_idx={start_idx} 无对应 indicator",
            tag=LogTag.FILTER)
        return False

    # 2. levels 数量与 start_index 对应关系验证
    n_arrays = band.get('n_arrays', 0)
    if start_idx == 0 or start_idx == 512:
        # Band1/Band2: 512点
        if n_arrays != 512:
            log(f"[FILTER] validate_fscan_frame_params: Band{1 if start_idx==0 else 2} n_arrays={n_arrays} != 512",
                tag=LogTag.FILTER)
            return False
    elif start_idx == 1024:
        # Band3: 417点
        if n_arrays != 417:
            log(f"[FILTER] validate_fscan_frame_params: Band3 n_arrays={n_arrays} != 417",
                tag=LogTag.FILTER)
            return False

    # 3. levels 数据完整性验证
    levels = band.get('levels', [])
    if len(levels) != n_arrays:
        log(f"[FILTER] validate_fscan_frame_params: levels长度={len(levels)} != n_arrays={n_arrays}",
            tag=LogTag.FILTER)
        return False

    return True


def validate_mscan_frame_params(band: dict, mode: str) -> bool:
    """Layer 3: MSCAN 封帧前参数验证

    Args:
        band: 频段数据字典
        mode: 业务模式

    Returns:
        True: 参数合法
        False: 参数异常
    """
    if mode != 'mscan':
        return True

    levels = band.get('levels', [])
    if not levels:
        log(f"[FILTER] validate_mscan_frame_params: levels 为空", tag=LogTag.FILTER)
        return False

    # MSCAN 单频点：应该只有1个 level
    if len(levels) != 1:
        log(f"[FILTER] validate_mscan_frame_params: levels数量={len(levels)} != 1",
            tag=LogTag.FILTER)
        return False

    raw_level = levels[0]
    # MScan raw_level 是原始 int16 计数器值，范围 -32768~32767
    # 不做 dBm 范围验证，直接放行
    return True


def validate_sglfreq_frame_params(band: dict, mode: str) -> bool:
    """Layer 3: SglFreq 封帧前参数验证

    Args:
        band: 频段数据字典
        mode: 业务模式

    Returns:
        True: 参数合法
        False: 参数异常
    """
    if mode != 'sglfreq':
        return True

    levels = band.get('levels', [])
    n_arrays = band.get('n_arrays', 0)

    # SglFreq IFANALYSIS: 1601 点 (raw dBμV×100, 含首点标记)
    if n_arrays <= 0 or n_arrays > 2000:
        log(f"[FILTER] validate_sglfreq_frame_params: n_arrays={n_arrays} 超出范围",
            tag=LogTag.FILTER)
        return False

    if len(levels) != n_arrays:
        log(f"[FILTER] validate_sglfreq_frame_params: levels长度={len(levels)} != n_arrays={n_arrays}",
            tag=LogTag.FILTER)
        return False

    # 抽样验证 levels 范围 (raw dBμV×100, 可低至 -40dBμV = -4000)
    for i, v in enumerate(levels[:min(50, len(levels))]):
        if v < -4000:
            log(f"[FILTER] validate_sglfreq_frame_params: levels[{i}]={v} 超出范围",
                tag=LogTag.FILTER)
            return False

    return True


def validate_pscan_frame_params(band: dict, mode: str) -> bool:
    """Layer 3: PScan 封帧前参数验证

    Args:
        band: 频段数据字典
        mode: 业务模式

    Returns:
        True: 参数合法
        False: 参数异常
    """
    if mode != 'pscan':
        return True

    levels = band.get('levels', [])
    n_arrays = band.get('n_arrays', 0)

    # PScan: 1441 点或更多
    if n_arrays <= 0:
        log(f"[FILTER] validate_pscan_frame_params: n_arrays={n_arrays} 异常",
            tag=LogTag.FILTER)
        return False

    if len(levels) != n_arrays:
        log(f"[FILTER] validate_pscan_frame_params: levels长度={len(levels)} != n_arrays={n_arrays}",
            tag=LogTag.FILTER)
        return False

    # 抽样验证 levels 范围
    # PScan 编码与 FScan 不同，范围 ~0-15000
    for i, v in enumerate(levels[:min(50, len(levels))]):
        if v < -2000 or v > 15000:
            log(f"[FILTER] validate_pscan_frame_params: levels[{i}]={v} 超出范围",
                tag=LogTag.FILTER)
            return False

    return True


def validate_frame_params(band: dict, mode: str) -> bool:
    """Layer 3: 分发验证入口

    Args:
        band: 频段数据字典
        mode: 业务模式

    Returns:
        True: 参数合法，可以封帧
        False: 参数异常，不封帧
    """
    if mode == 'fscan':
        return validate_fscan_frame_params(band, mode)
    elif mode == 'mscan':
        return validate_mscan_frame_params(band, mode)
    elif mode == 'sglfreq':
        return validate_sglfreq_frame_params(band, mode)
    elif mode == 'pscan':
        return validate_pscan_frame_params(band, mode)
    return True  # 未知模式不验证
