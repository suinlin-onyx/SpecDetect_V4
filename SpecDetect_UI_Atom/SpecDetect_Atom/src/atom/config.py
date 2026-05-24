# -*- coding: utf-8 -*-
"""
配置加载模块

支持从 JSON 文件加载配置，支持从 XML 覆盖合并
"""

import json
import os
import sys
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any


def _load_from_xml(xml_path: str) -> Dict[str, Any]:
    """从 XML 文件加载全部配置

    Args:
        xml_path: XML 配置文件路径

    Returns:
        配置字典
    """
    if not os.path.exists(xml_path):
        return {}

    try:
        # 使用 gb2312 编码读取
        with open(xml_path, 'r', encoding='gb2312') as f:
            content = f.read()
        tree = ET.fromstring(content)
        root = tree

        config = {}

        # 解析 system/svc
        svc = root.find('.//svc')
        if svc is not None:
            config['atom_protocol'] = svc.get('atomprotocol', '')
            config['atom_extend'] = svc.get('extend', '')
            config['put_equ_stat_url'] = svc.get('mputequstaturl', '')
            config['put_time_interval'] = svc.get('puttimeinterval', '60')
            config['judge_busy_by_max_task_num'] = svc.get('judgebusybymaxtasknum', 'false')
            config['show_log'] = svc.get('showlog', 'false')
            config['soap_port'] = int(svc.get('port', '8282'))

        # 解析 streamsrc
        streamsrc = root.find('.//streamsrc')
        if streamsrc is not None:
            config['streamsrc_ip'] = streamsrc.get('ip', '127.0.0.1')
            config['streamsrc_port'] = int(streamsrc.get('port', '18012'))

        # 解析 rxinfo
        rxinfo = root.find('.//rxinfo')
        if rxinfo is not None:
            config['station_id'] = rxinfo.get('id', '')
            config['station_name'] = rxinfo.get('staname', '')
            config['device_host'] = rxinfo.get('serverip', '')
            config['device_port'] = int(rxinfo.get('serverport', '1449'))

        # 解析 log
        logger = root.find('.//log/logger')
        if logger is not None:
            config['log_trace'] = logger.get('trace', 'false')
            config['log_debug'] = logger.get('debug', 'true')
            config['log_info'] = logger.get('info', 'true')
            config['log_notice'] = logger.get('notice', 'true')
            config['log_warning'] = logger.get('warning', 'true')
            config['log_error'] = logger.get('error', 'true')

        return config
    except Exception as e:
        print(f"XML 解析失败: {e}")
        return {}


def _load_devinfo_presets(devinfo_dir: str) -> list:
    """从 devinfo 目录加载所有设备预置

    Args:
        devinfo_dir: devinfo 目录路径

    Returns:
        [{'key': xxx, 'mfid': xxx, 'equid': xxx, 'station': {...}, 'device_info': {...}}, ...]
    """
    if not os.path.exists(devinfo_dir):
        return []

    presets = []

    try:
        for filename in os.listdir(devinfo_dir):
            if not filename.endswith('.xml'):
                continue

            xml_path = os.path.join(devinfo_dir, filename)
            preset = _load_single_devinfo(xml_path, filename)
            if preset:
                presets.append(preset)
    except Exception as e:
        print(f"加载 devinfo 目录失败: {e}")

    return presets


def _load_single_devinfo(xml_path: str, filename: str) -> Optional[Dict[str, Any]]:
    """加载单个 devinfo XML 文件

    Args:
        xml_path: XML 文件路径
        filename: 文件名（用于提取 mfid_equid）

    Returns:
        预置信息字典
    """
    if not os.path.exists(xml_path):
        return None

    try:
        with open(xml_path, 'r', encoding='gb2312') as f:
            content = f.read()
        root = ET.fromstring(content)

        preset = {}

        # 从文件名提取 mfid 和 equid（格式: mfid_equid.xml）
        name_parts = filename[:-4].split('_')  # 去掉 .xml
        if len(name_parts) >= 2:
            preset['mfid'] = name_parts[0]
            preset['equid'] = '_'.join(name_parts[1:])
            # 生成 key: mfid_equid
            preset['key'] = f"{preset['mfid']}_{preset['equid']}"

        # 解析 rxinfo/station（所有属性）
        station = root.find('.//station')
        if station is not None:
            preset['station'] = {
                'id': station.get('id', ''),
                'name': station.get('staname', ''),
                'serverip': station.get('serverip', ''),
                'serverport': int(station.get('serverport', '1449')),
                'protocol': station.get('protocol', 'rmcp'),
                'testself': station.get('testself', 'no'),
                'btelnet': station.get('btelnet', 'no'),
                'reconn': station.get('reconn', 'no'),
                'querytask': station.get('querytask', 'no'),
                'statusip': station.get('statusip', ''),
                'statusport': station.get('statusport', ''),
                'longitude': station.get('longitude', ''),
                'latitude': station.get('latitude', ''),
                'audioopenval': station.get('audioopenval', ''),
                'audiocloseval': station.get('audiocloseval', '')
            }

        # 解析 rxinfo/device（所有属性和子元素）
        device_elem = root.find('.//device')
        if device_elem is not None:
            preset['device_info'] = {
                'id': device_elem.get('id', ''),
                'name': device_elem.get('name', ''),
                'maxtaskcount': int(device_elem.get('maxtaskcount', '1')),
                'analogaudio': device_elem.get('analogaudio', 'false')
            }

            # 解析 func 列表（设备支持的功能）
            funcs = []
            for func in device_elem.findall('.//func'):
                func_info = {
                    'atomfuncname': func.get('atomfuncname', ''),
                    'rxfuncid': func.get('rxfuncid', ''),
                    'params': []
                }
                for param in func.findall('.//item'):
                    func_info['params'].append({
                        'rxparamname': param.get('rxparamname', ''),
                        'atomparamname': param.get('atomparamname', ''),
                        'rxparamunit': param.get('rxparamunit', ''),
                        'atomparamunit': param.get('atomparamunit', ''),
                        'rxparamdefault': param.get('rxparamdefault', '')
                    })
                funcs.append(func_info)
            preset['device_info']['funcs'] = funcs

        # 解析 srrc:result 设备信息（用于 B_QueryDeviceInfo 响应）
        # 使用完整命名空间 URI 方式查找
        srrc_ns = 'http://www.srrc.org.cn'
        srrc_result = root.find(f'.//{{{srrc_ns}}}result')
        if srrc_result is None:
            # 尝试从 Body 中找
            body = root.find(f'.//{{{srrc_ns}}}responsebody')
            if body is not None:
                srrc_result = body.find(f'{{{srrc_ns}}}result')

        if srrc_result is not None:
            srrc_ns = 'http://www.srrc.org.cn'
            preset['srrc_info'] = {
                'mfid': srrc_result.findtext(f'{{{srrc_ns}}}mfid', ''),
                'equid': srrc_result.findtext(f'{{{srrc_ns}}}equid', ''),
                'equname': srrc_result.findtext(f'{{{srrc_ns}}}equname', ''),
                'equtype': srrc_result.findtext(f'{{{srrc_ns}}}equtype', ''),
                'equstatus': srrc_result.findtext(f'{{{srrc_ns}}}equstatus', ''),
                'equimanu': srrc_result.findtext(f'{{{srrc_ns}}}equimanu', ''),
                'equmodel': srrc_result.findtext(f'{{{srrc_ns}}}equmodel', ''),
                'equsn': srrc_result.findtext(f'{{{srrc_ns}}}equsn', ''),
            }

        return preset
    except Exception as e:
        print(f"加载 devinfo 文件失败 {filename}: {e}")
        return None


class Config:
    """配置类"""

    _instance: Optional['Config'] = None
    _config: Dict[str, Any] = {}
    _config_file: str = ''

    def __init__(self, config_file: str = None):
        if config_file:
            self.load(config_file)

    @classmethod
    def get_instance(cls) -> 'Config':
        """获取单例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def load(cls, config_file: str) -> 'Config':
        """加载配置文件

        Args:
            config_file: JSON 配置文件路径

        Returns:
            Config 实例
        """
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"配置文件不存在: {config_file}")

        cls._config_file = config_file

        with open(config_file, 'r', encoding='utf-8') as f:
            cls._config = json.load(f)

        # 确保 presets 中的每个条目都有 key
        device_presets = cls._config.get('device', {}).get('presets', [])
        for p in device_presets:
            if 'key' not in p and 'mfid' in p and 'equid' in p:
                p['key'] = f"{p['mfid']}_{p['equid']}"

        # 检查是否启用 legacy XML 配置
        use_legacy_xml_raw = cls._config.get('use_legacy_xml', True)
        use_legacy_xml = cls._get_value(use_legacy_xml_raw) if isinstance(use_legacy_xml_raw, dict) else use_legacy_xml_raw

        if use_legacy_xml:
            legacy_xml_raw = cls._config.get('legacy_xml_path', '')
            legacy_xml = cls._get_value(legacy_xml_raw) if isinstance(legacy_xml_raw, dict) else legacy_xml_raw
            if legacy_xml:
                # 转换为绝对路径
                base_dir = os.path.dirname(os.path.abspath(config_file))
                xml_abs_path = os.path.join(base_dir, legacy_xml)

                if os.path.exists(xml_abs_path):
                    xml_config = _load_from_xml(xml_abs_path)

                    # 合并 XML 配置到 JSON（XML 优先级更高）
                    cls._merge_config(xml_config)

                    # 可选：更新 JSON 文件（保持简洁值格式）
                    # cls._save_config()  # 注释掉避免覆盖带注释模板

            # 加载 devinfo 目录
            devinfo_path_raw = cls._config.get('legacy_devinfo_path', '')
            devinfo_path = cls._get_value(devinfo_path_raw) if isinstance(devinfo_path_raw, dict) else devinfo_path_raw
            if devinfo_path:
                devinfo_abs_path = os.path.join(base_dir, devinfo_path)
                if os.path.exists(devinfo_abs_path):
                    device_presets = _load_devinfo_presets(devinfo_abs_path)
                    print(f"已加载 {len(device_presets)} 个设备预置")

                    # 合并到 device 配置中
                    if 'device' not in cls._config:
                        cls._config['device'] = {}

                    # 分离：presets_to_save 不含 device_info, key
                    # 保留 srrc_info（用于 B_QueryDeviceInfo 响应）
                    presets_to_save = []
                    for p in device_presets:
                        p_copy = p.copy()
                        p_copy.pop('device_info', None)
                        p_copy.pop('key', None)
                        presets_to_save.append(p_copy)

                    cls._config['device']['presets'] = presets_to_save

                    # 回写到 settings.json
                    cls._save_config()

                    # 恢复完整的 device_presets（包含 device_info）到内存
                    cls._config['device']['presets'] = device_presets

        if cls._instance is None:
            cls._instance = cls.__new__(cls)
            cls._instance._config = cls._config
        else:
            cls._instance._config = cls._config

        return cls._instance

    @classmethod
    def _merge_config(cls, xml_config: Dict[str, Any]):
        """合并 XML 配置到主配置"""
        # atom 配置
        if 'atom' not in cls._config:
            cls._config['atom'] = {}
        atom = cls._config['atom']
        if 'soap_port' in xml_config:
            cls._set_value(atom, 'soap_port', xml_config['soap_port'])
        if 'streamsrc_ip' in xml_config:
            cls._set_value(atom, 'streamsrc_ip', xml_config['streamsrc_ip'])
        if 'streamsrc_port' in xml_config:
            cls._set_value(atom, 'streamsrc_port', xml_config['streamsrc_port'])
        if 'atom_protocol' in xml_config:
            cls._set_value(atom, 'protocol', xml_config['atom_protocol'])

        # device 配置
        if 'device' not in cls._config:
            cls._config['device'] = {}
        device = cls._config['device']
        if 'device_host' in xml_config:
            cls._set_value(device, 'host', xml_config['device_host'])
        if 'device_port' in xml_config:
            cls._set_value(device, 'port', xml_config['device_port'])

        # session 配置
        if 'session' not in cls._config:
            cls._config['session'] = {}
        session = cls._config['session']
        if 'put_time_interval' in xml_config:
            cls._set_value(session, 'put_time_interval', int(xml_config['put_time_interval']))
        if 'judge_busy_by_max_task_num' in xml_config:
            cls._set_value(session, 'judge_busy_by_max_task_num', xml_config['judge_busy_by_max_task_num'] == 'true')

        # station 信息
        if 'station_id' in xml_config:
            cls._config['station'] = {
                'id': xml_config.get('station_id', ''),
                'name': xml_config.get('station_name', '')
            }

        # log 配置
        if 'log' not in cls._config:
            cls._config['log'] = {}
        log = cls._config['log']
        if 'log_debug' in xml_config:
            cls._set_value(log, 'debug', xml_config['log_debug'] == 'true')
        if 'log_info' in xml_config:
            cls._set_value(log, 'info', xml_config['log_info'] == 'true')
        if 'log_warning' in xml_config:
            cls._set_value(log, 'warning', xml_config['log_warning'] == 'true')
        if 'log_error' in xml_config:
            cls._set_value(log, 'error', xml_config['log_error'] == 'true')

    @classmethod
    def _save_config(cls):
        """保存配置到 JSON 文件"""
        if not cls._config_file:
            return

        try:
            with open(cls._config_file, 'w', encoding='utf-8') as f:
                json.dump(cls._config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"配置保存失败: {e}")

    @classmethod
    def _get_value(cls, obj: Any) -> Any:
        """获取配置值，支持两种格式：
        1. {"value": xxx, "desc": "..."} -> 返回 xxx
        2. 直接值 -> 直接返回
        """
        if isinstance(obj, dict) and 'value' in obj:
            return obj['value']
        return obj

    @classmethod
    def _set_value(cls, section: dict, key: str, value: Any):
        """设置配置值，保留 desc 注释"""
        if key in section and isinstance(section[key], dict) and 'desc' in section[key]:
            section[key] = {'value': value, 'desc': section[key]['desc']}
        else:
            section[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值

        支持点号分隔的路径，如 'atom.soap_port'

        Args:
            key: 配置键
            default: 默认值

        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        # 处理 value/desc 格式
        return self.__class__._get_value(value)

    def get_atom_config(self) -> Dict[str, Any]:
        """获取 Atom 配置"""
        return self._config.get('atom', {})

    def get_device_config(self) -> Dict[str, Any]:
        """获取设备配置"""
        return self._config.get('device', {})

    def get_session_config(self) -> Dict[str, Any]:
        """获取 Session 配置"""
        return self._config.get('session', {})

    def get_log_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self._config.get('log', {})

    @property
    def atom_host(self) -> str:
        return self.get('atom.host', '127.0.0.1')

    @property
    def atom_protocol(self) -> str:
        return self.get('atom.protocol', 'boer')

    @property
    def soap_port(self) -> int:
        return self.get('atom.soap_port', 8282)

    @property
    def soap_appid(self) -> str:
        return self.get('soap.appid', '123456')

    @property
    def soap_userid(self) -> str:
        return self.get('soap.userid', 'RX_admin')

    @property
    def streamsrc_ip(self) -> str:
        return self.get('atom.streamsrc_ip', '127.0.0.1')

    @property
    def streamsrc_port(self) -> int:
        return self.get('atom.streamsrc_port', 18012)

    @property
    def device_host(self) -> str:
        return self.get('device.host', '100.72.95.36')

    @property
    def device_port(self) -> int:
        return self.get('device.port', 1449)

    @property
    def stale_timeout(self) -> int:
        return self.get('session.stale_timeout', 30)

    @property
    def idle_timeout(self) -> int:
        return self.get('session.idle_timeout', 30)

    @property
    def max_sessions(self) -> int:
        return self.get('session.max_sessions', 5)

    @property
    def log_level(self) -> str:
        return self.get('log.level', 'INFO')

    @property
    def log_dir(self) -> str:
        if getattr(sys, 'frozen', False):
            # 打包后 exe 运行时，日志写到 exe 同级目录
            # 使用多种方式获取 exe 目录，确保跨 Windows 版本兼容
            exe_path = getattr(sys, 'executable', None)
            if exe_path:
                exe_dir = os.path.dirname(os.path.abspath(exe_path))
            else:
                # 备用方案：使用 _MEIPASS 或当前目录
                exe_dir = getattr(sys, '_MEIPASS', os.getcwd())
            log_dir_relative = self.get('log.dir', 'logs')
            # 如果是相对路径，拼到 exe 目录下
            if not os.path.isabs(log_dir_relative):
                return os.path.join(exe_dir, log_dir_relative)
            return log_dir_relative
        else:
            # 开发模式使用相对路径
            return self.get('log.dir', './logs')

    @property
    def station_id(self) -> str:
        return self.get('station.id', '')

    @property
    def station_name(self) -> str:
        return self.get('station.name', '')

    @property
    def device_presets(self) -> list:
        """获取设备预置列表"""
        return self.get('device.presets', [])

    def get_device_preset(self, key: str) -> Optional[Dict[str, Any]]:
        """根据 key（文件名不含扩展名）获取设备预置"""
        for preset in self.device_presets:
            if preset.get('key') == key:
                return preset
        return None

    def get_default_device_preset(self) -> Optional[Dict[str, Any]]:
        """获取默认设备预置（第一个）"""
        presets = self.device_presets
        return presets[0] if presets else None


def load_config(config_file: str = None) -> Config:
    """便捷函数：加载配置"""
    if config_file is None:
        if getattr(sys, 'frozen', False):
            # 打包后 exe 运行时，从 exe 同级 config 目录加载
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            config_file = os.path.join(exe_dir, 'config', 'settings.json')
        else:
            # 开发模式
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_file = os.path.join(base_dir, 'config', 'settings.json')

    return Config.load(config_file)


def get_config() -> Config:
    """便捷函数：获取配置单例"""
    return Config.get_instance()
