# -*- coding: utf-8 -*-
"""
设备预置模块

负责加载和解析设备预置信息 XML，以及响应模板管理
"""

import os
import re
import sys
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, List


class DevicePreset:
    """设备预置信息"""

    def __init__(self, mfid: str, equid: str):
        self.mfid = mfid
        self.equid = equid
        self.equname = ""
        self.equtype = ""
        self.equstatus = ""
        self.equimanu = ""
        self.equmodel = ""
        self.equsn = ""
        self.host = ""
        self.port = ""
        self.maxtasknumber = 1
        self.featurelist: List[Dict[str, Any]] = []

    @classmethod
    def from_xml_file(cls, filepath: str) -> 'DevicePreset':
        """从 XML 文件加载

        Args:
            filepath: XML 文件路径

        Returns:
            DevicePreset 实例
        """
        if not os.path.exists(filepath):
            return None

        try:
            # 尝试 gb2312 编码
            with open(filepath, 'r', encoding='gb2312') as f:
                content = f.read()
            root = ET.fromstring(content)
        except Exception:
            return None

        # 查找 result 节点
        result = root.find('.//srrc:result', {'srrc': 'http://www.srrc.org.cn'})
        if result is None:
            result = root.find('.//result')
        if result is None:
            result = root.find('.//{http://www.srrc.org.cn}result')
        if result is None:
            return None

        # 解析基本信息
        preset = cls(
            mfid=result.findtext('srrc:mfid', '', {'srrc': 'http://www.srrc.org.cn'}) or '',
            equid=result.findtext('srrc:equid', '', {'srrc': 'http://www.srrc.org.cn'}) or ''
        )

        preset.equname = result.findtext('srrc:equname', '', {'srrc': 'http://www.srrc.org.cn'}) or ''
        preset.equtype = result.findtext('srrc:equtype', '', {'srrc': 'http://www.srrc.org.cn'}) or ''
        preset.equstatus = result.findtext('srrc:equstatus', '', {'srrc': 'http://www.srrc.org.cn'}) or ''
        preset.equimanu = result.findtext('srrc:equimanu', '', {'srrc': 'http://www.srrc.org.cn'}) or ''
        preset.equmodel = result.findtext('srrc:equmodel', '', {'srrc': 'http://www.srrc.org.cn'}) or ''
        preset.equsn = result.findtext('srrc:equsn', '', {'srrc': 'http://www.srrc.org.cn'}) or ''
        preset.host = result.findtext('srrc:host', '', {'srrc': 'http://www.srrc.org.cn'}) or ''
        preset.port = result.findtext('srrc:port', '', {'srrc': 'http://www.srrc.org.cn'}) or ''
        maxtask = result.findtext('srrc:maxtasknumber', '', {'srrc': 'http://www.srrc.org.cn'}) or '1'
        preset.maxtasknumber = int(maxtask) if maxtask and maxtask.isdigit() else 1

        # 解析 featurelist
        featurelist = result.find('srrc:featurelist', {'srrc': 'http://www.srrc.org.cn'})
        if featurelist is None:
            featurelist = result.find('featurelist')

        if featurelist is not None:
            for feature in featurelist.findall('srrc:feature', {'srrc': 'http://www.srrc.org.cn'}):
                if feature is None:
                    continue
                code = feature.findtext('srrc:code', '', {'srrc': 'http://www.srrc.org.cn'}) or ''
                if code:
                    preset.featurelist.append({'code': code})

        return preset

    def to_dict(self) -> Dict[str, Any]:
        """转换为 dict"""
        return {
            'mfid': self.mfid,
            'equid': self.equid,
            'equname': self.equname,
            'equtype': self.equtype,
            'equstatus': self.equstatus,
            'equimanu': self.equimanu,
            'equmodel': self.equmodel,
            'equsn': self.equsn,
            'host': self.host,
            'port': self.port,
            'maxtasknumber': self.maxtasknumber,
            'featurelist': self.featurelist
        }

    def get_capabilities(self) -> List[str]:
        """获取设备能力列表"""
        return [f['code'] for f in self.featurelist]

    def has_capability(self, capability: str) -> bool:
        """检查是否有指定能力"""
        return capability in self.get_capabilities()


class DevicePresetManager:
    """设备预置管理器"""

    def __init__(self, config_dir: str = None):
        # 默认使用 legacy/devinfo 目录
        if config_dir is None:
            # 打包后 __file__ 指向临时目录，需要使用 exe 所在目录
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(os.path.abspath(sys.executable))
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_dir = os.path.join(base_dir, 'config', 'legacy', 'devinfo')

        self.config_dir = config_dir
        self._cache: Dict[str, DevicePreset] = {}
        self._xml_cache: Dict[str, str] = {}  # 原始 XML 字符串缓存

        # 模板相关 - 打包后使用 _MEIPASS 目录 (onedir模式) 或 exe 所在目录
        if getattr(sys, 'frozen', False):
            # onedir模式: sys._MEIPASS 是临时解压目录
            if hasattr(sys, '_MEIPASS'):
                template_base = sys._MEIPASS
            else:
                template_base = os.path.dirname(os.path.abspath(sys.executable))
        else:
            template_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._template_dir = os.path.join(template_base, 'preset', 'templates')
        self._envelope_template: str = ''  # 基础 Envelope 模板
        self._body_templates: Dict[str, str] = {}  # 接口 Body 模板
        self._error_template: str = ''  # 错误模板
        self._templates_loaded = False

    def _ensure_templates_loaded(self):
        """确保模板已加载"""
        if self._templates_loaded:
            return

        # 加载基础 Envelope 模板 (UTF-8)
        envelope_path = os.path.join(self._template_dir, '_envelope.xml')
        if os.path.exists(envelope_path):
            with open(envelope_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 移除注释部分
                content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
                self._envelope_template = content.strip()

        # 加载错误模板 (UTF-8)
        error_path = os.path.join(self._template_dir, '_error.xml')
        if os.path.exists(error_path):
            with open(error_path, 'r', encoding='utf-8') as f:
                content = f.read()
                content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
                self._error_template = content.strip()

        # 加载各接口 Body 模板 (UTF-8)
        interface_names = [
            'B_QueryDeviceInfo', 'B_FScan', 'B_PScan', 'B_MScan',
            'B_StopMeas', 'B_QueryFaciDevStat', 'B_SglFreqMeas'
        ]
        for name in interface_names:
            template_path = os.path.join(self._template_dir, f'{name}.xml')
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
                    self._body_templates[name] = content.strip()

        self._templates_loaded = True

    def load(self, mfid: str, equid: str) -> Optional[DevicePreset]:
        """加载设备预置 (结构化对象)

        Args:
            mfid: 设备厂商 ID
            equid: 设备 ID

        Returns:
            DevicePreset 实例或 None
        """
        key = f"{mfid}_{equid}"

        # 检查缓存
        if key in self._cache:
            return self._cache[key]

        # 构建文件路径
        filename = f"{mfid}_{equid}.xml"
        filepath = os.path.join(self.config_dir, filename)

        # 加载
        preset = DevicePreset.from_xml_file(filepath)
        if preset:
            self._cache[key] = preset

        return preset

    def load_responsebody(self, mfid: str, equid: str) -> str:
        """加载 <srrc:responsebody>...</srrc:responsebody> 原始 XML

        Args:
            mfid: 设备厂商 ID
            equid: 设备 ID

        Returns:
            <srrc:responsebody>...</srrc:responsebody> XML 字符串 (gb2312)
            如果不存在返回空字符串
        """
        key = f"{mfid}_{equid}"

        # 检查缓存
        if key in self._xml_cache:
            return self._xml_cache[key]

        # 构建文件路径
        filename = f"{mfid}_{equid}.xml"
        filepath = os.path.join(self.config_dir, filename)

        if not os.path.exists(filepath):
            return ''

        try:
            with open(filepath, 'r', encoding='gb2312', errors='replace') as f:
                content = f.read()

            # 提取 <srrc:responsebody>...</srrc:responsebody>
            match = re.search(r'(<srrc:responsebody>.*?</srrc:responsebody>)', content, re.DOTALL)
            if match:
                xml = match.group(1)
                self._xml_cache[key] = xml
                return xml
            else:
                return ''
        except Exception:
            return ''

    @staticmethod
    def inject_fields(xml: str, **fields) -> str:
        """向 XML 中注入动态字段

        Args:
            xml: 原始 XML 字符串
            fields: 要注入的字段，如 appid='123456', userid='RX_admin', taskid='xxx'

        Returns:
            注入后的 XML 字符串

        处理逻辑:
            1. 如果字段已存在，跳过
            2. 如果有 {placeholder} 格式，替换
            3. 如果没有且是 appid/userid，在 <srrc:mfid> 前插入
            4. 如果没有且是 taskid，替换或插入到 </srrc:result> 前
        """
        result = xml

        # 处理 appid
        if 'appid' in fields:
            if '<srrc:appid>' in result:
                # 替换现有值
                import re
                result = re.sub(r'<srrc:appid>[^<]*</srrc:appid>',
                               f'<srrc:appid>{fields["appid"]}</srrc:appid>', result)
            elif '{appid}' in result:
                # 替换占位符
                result = result.replace('{appid}', fields['appid'])
            else:
                # 插入到 mfid 前
                result = result.replace('<srrc:mfid>',
                    f'<srrc:appid>{fields["appid"]}</srrc:appid><srrc:mfid>')

        # 处理 userid
        if 'userid' in fields:
            if '<srrc:userid>' in result:
                import re
                result = re.sub(r'<srrc:userid>[^<]*</srrc:userid>',
                               f'<srrc:userid>{fields["userid"]}</srrc:userid>', result)
            elif '{userid}' in result:
                result = result.replace('{userid}', fields['userid'])
            else:
                result = result.replace('<srrc:mfid>',
                    f'<srrc:userid>{fields["userid"]}</srrc:userid><srrc:mfid>')

        # 处理 taskid
        if 'taskid' in fields:
            if '<srrc:taskid>' in result:
                import re
                result = re.sub(r'<srrc:taskid>[^<]*</srrc:taskid>',
                               f'<srrc:taskid>{fields["taskid"]}</srrc:taskid>', result)
            elif '{taskid}' in result:
                result = result.replace('{taskid}', fields['taskid'])
            else:
                result = result.replace('</srrc:result>',
                    f'<srrc:taskid>{fields["taskid"]}</srrc:taskid></srrc:result>')

        # 处理其他 {placeholder} 格式的字段
        for key, value in fields.items():
            if key not in ('appid', 'userid', 'taskid'):
                placeholder = f'{{{key}}}'
                if placeholder in result:
                    result = result.replace(placeholder, str(value))

        return result

    def build_response(self, interface_name: str, body_content: str = None, **fields) -> bytes:
        """构建完整的 SOAP 响应

        Args:
            interface_name: 接口名 (如 B_FScan, B_StopMeas)
            body_content: Body 内容，如果不提供则使用模板
            **fields: 要注入的动态字段

        Returns:
            HTTP 响应字节 (gb2312 编码)
        """
        self._ensure_templates_loaded()

        # 设置默认值
        fields.setdefault('bizrescd', 'BIZ-000001')
        fields.setdefault('bizrestext', '调用成功')

        # 获取 Body
        if body_content:
            body = body_content
        elif interface_name in self._body_templates:
            body = self._body_templates[interface_name]
        else:
            body = f'<srrc:error>Unknown interface: {interface_name}</srrc:error>'

        # 注入字段
        body = self.inject_fields(body, **fields)

        # 包装到 Envelope
        soap_body = self._envelope_template.replace('{body}', body)
        soap_body = soap_body.replace('{bizrescd}', fields['bizrescd'])
        soap_body = soap_body.replace('{bizrestext}', fields['bizrestext'])

        return self._build_http_response(soap_body)

    def build_error_response(self, error_msg: str,
                             error_code: str = 'BIZ-00002-conflict',
                             error_type: str = 'cancel',
                             biz_res_cd: str = None,
                             biz_res_text: str = None) -> bytes:
        """构建错误响应

        Args:
            error_msg: 错误描述 (映射到 <srrc:text>)
            error_code: 业务错误码 (默认 BIZ-00002-conflict)
            error_type: 错误类型 (默认 cancel)
            biz_res_cd: Header bizResCd (默认与 error_code 相同)
            biz_res_text: Header bizResText (默认与 error_msg 相同)

        Returns:
            HTTP 响应字节
        """
        self._ensure_templates_loaded()

        body = self._error_template \
            .replace('{error_type}', error_type) \
            .replace('{error_code}', error_code) \
            .replace('{error_text}', error_msg)

        soap_body = self._envelope_template.replace('{body}', body)
        soap_body = soap_body.replace('{bizrescd}', biz_res_cd or error_code)
        soap_body = soap_body.replace('{bizrestext}', biz_res_text or error_msg)

        return self._build_http_response(soap_body)

    def _build_http_response(self, soap_body: str) -> bytes:
        """构建 HTTP 响应

        Args:
            soap_body: SOAP Body 字符串 (UTF-8 编码)

        Returns:
            HTTP 响应字节 (UTF-8 编码)
        """
        response = f'HTTP/1.1 200 OK\r\nContent-Type: text/xml; charset=utf-8\r\nContent-Length: {len(soap_body.encode("utf-8"))}\r\nConnection: close\r\n\r\n{soap_body}'

        return response.encode('utf-8')

    def get_equid_for_mfid(self, mfid: str) -> str:
        """根据 mfid 查找对应的 equid

        扫描配置目录，查找文件名以 {mfid}_ 开头的 XML 文件，
        从中提取 equid。

        Args:
            mfid: 设备厂商 ID

        Returns:
            equid 字符串，未找到则返回空字符串
        """
        if not mfid or not os.path.exists(self.config_dir):
            return ''

        prefix = f"{mfid}_"
        for filename in os.listdir(self.config_dir):
            if filename.startswith(prefix) and filename.endswith('.xml'):
                # 文件名格式: {mfid}_{equid}.xml
                name = filename[:-4]  # 去掉 .xml
                equid = name[len(prefix):]  # 去掉 mfid_ 前缀
                return equid

        return ''

    def get_default(self) -> Optional[DevicePreset]:
        """获取默认设备预置

        扫描配置目录，返回第一个找到的设备预置
        """
        if not os.path.exists(self.config_dir):
            return None

        for filename in os.listdir(self.config_dir):
            if filename.endswith('.xml'):
                filepath = os.path.join(self.config_dir, filename)
                preset = DevicePreset.from_xml_file(filepath)
                if preset:
                    return preset

        return None
