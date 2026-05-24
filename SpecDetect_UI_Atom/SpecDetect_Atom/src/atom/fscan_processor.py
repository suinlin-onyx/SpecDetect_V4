# -*- coding: utf-8 -*-
"""
RMCP FSCAN 数据类模块

仅存储解码后的数据，不涉及帧生成
帧生成由 streamsrc_frame.py 负责
解析由 rmcp_parser.py 负责
"""

from typing import List


class SpectrumData:
    """FSCAN 频谱数据类

    仅存储解码后的数据，不涉及帧生成
    """

    def __init__(self, band_info: dict = None):
        if band_info:
            self.band_id: int = band_info.get('counters', [0])[2]  # start_index
            self.start_index: int = band_info.get('counters', [0])[2]
            self.n_arrays: int = band_info.get('counters', [0])[0]
            self.levels_raw: List[int] = band_info.get('levels', [])  # int16 (0.1 dBm 单位)
            self.levels_dbm: List[float] = [v / 10.0 for v in self.levels_raw]  # 转为 dBm
            self.counters: List[int] = list(band_info.get('counters', [0, 0, 0, 0]))
            self.stc: int = band_info.get('stc', 0)
        else:
            self.band_id = 0
            self.start_index = 0
            self.n_arrays = 0
            self.levels_raw = []
            self.levels_dbm = []
            self.counters = [0, 0, 0, 0]
            self.stc = 0


class FScanProcessor:
    """FSCAN 数据处理器

    仅负责解码 RMCP FSCAN Payload → SpectrumData
    帧生成由 streamsrc_frame.py 负责
    """

    def decode_from_rmcp(self, fscan_data: dict) -> SpectrumData:
        """从 RMCP FSCAN 数据解码

        Args:
            fscan_data: parse_fscan_payload 返回的 dict

        Returns:
            SpectrumData 实例
        """
        return SpectrumData(fscan_data)

    def process_band(self, band_info: dict) -> SpectrumData:
        """处理单个频段数据

        Args:
            band_info: parse_fscan_payload 返回的 dict

        Returns:
            SpectrumData 实例
        """
        return self.decode_from_rmcp(band_info)
