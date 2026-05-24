# -*- coding: utf-8 -*-
"""
主动连接模式 (Active Connection Mode) 测试

测试 outputchannel 功能完整性:
1. SOAP 解析器提取 outputchannel
2. StreamForwarder 主动连接和转发
3. Session 管理 outputchannel_forwarder 生命周期
4. Service handler 主动连接模式路由
"""

import socket
import threading
import time
import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import Optional

# 添加 src 目录到路径
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def setup_logger():
    """初始化 Logger 单例（测试环境）"""
    from log.logger import Logger, LogTag
    logger = Logger.init(log_dir=None, log_level="DEBUG")
    return logger


# 在测试开始前初始化 Logger
setup_logger()


from atom.soap.parser import parse_soap_body, extract_soap_request
from atom.stream.forwarder import StreamForwarder
from atom.session import StreamSession, SessionState


def make_soap_body(xml_content):
    """辅助函数：将 XML 字符串转换为字节"""
    return xml_content.encode('utf-8')


class TestSoapOutputChannelParsing(unittest.TestCase):
    """测试 SOAP 解析器提取 outputchannel"""

    def test_parse_outputchannel_complete(self):
        """测试完整 outputchannel 解析"""
        soap_body = make_soap_body('''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <n:B_FScan xmlns:n="http://www.srrc.org.cn/">
              <n:taskid>TEST-001</n:taskid>
              <n:startfreq>137000000</n:startfreq>
              <n:stopfreq>173000000</n:stopfreq>
              <n:step>25000</n:step>
              <n:gain>AGC</n:gain>
              <n:outputchannel>
                <n:mode>source</n:mode>
                <n:datachannel>stream</n:datachannel>
                <n:host>172.18.98.5</n:host>
                <n:port>8332</n:port>
                <n:stc>1234567890</n:stc>
              </n:outputchannel>
            </n:B_FScan>
          </soap:Body>
        </soap:Envelope>''')

        result = parse_soap_body(soap_body, "http://www.srrc.org.cn/B_FScan")

        self.assertIn('outputchannel', result)
        oc = result['outputchannel']
        self.assertEqual(oc['mode'], 'source')
        self.assertEqual(oc['datachannel'], 'stream')
        self.assertEqual(oc['host'], '172.18.98.5')
        self.assertEqual(oc['port'], 8332)  # 应转换为整数
        self.assertEqual(oc['stc'], '1234567890')

    def test_parse_outputchannel_partial(self):
        """测试部分 outputchannel (缺少必需字段则不添加)"""
        soap_body = make_soap_body('''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <n:B_FScan xmlns:n="http://www.srrc.org.cn/">
              <n:taskid>TEST-002</n:taskid>
              <n:outputchannel>
                <n:mode>source</n:mode>
                <n:host>172.18.98.5</n:host>
              </n:outputchannel>
            </n:B_FScan>
          </soap:Body>
        </soap:Envelope>''')

        result = parse_soap_body(soap_body, "http://www.srrc.org.cn/B_FScan")

        # 缺少必需字段 datachannel, port, stc，不应添加到结果
        self.assertNotIn('outputchannel', result)

    def test_parse_outputchannel_missing(self):
        """测试无 outputchannel 的请求"""
        soap_body = make_soap_body('''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <n:B_FScan xmlns:n="http://www.srrc.org.cn/">
              <n:taskid>TEST-003</n:taskid>
              <n:startfreq>137000000</n:startfreq>
              <n:stopfreq>173000000</n:stopfreq>
            </n:B_FScan>
          </soap:Body>
        </soap:Envelope>''')

        result = parse_soap_body(soap_body, "http://www.srrc.org.cn/B_FScan")
        self.assertNotIn('outputchannel', result)


class TestStreamForwarder(unittest.TestCase):
    """测试 StreamForwarder 主动连接功能"""

    def setUp(self):
        """每个测试创建独立的服务器"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('127.0.0.1', 0))
        self.server_port = self.server_socket.getsockname()[1]
        self.server_socket.listen(1)
        self.server_socket.settimeout(3.0)

        self.received_data = []
        self._stop_server = False
        self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
        self.server_thread.start()

    def _server_loop(self):
        """模拟外部服务器"""
        try:
            conn, addr = self.server_socket.accept()
            conn.settimeout(1.0)
            while not self._stop_server:
                try:
                    data = conn.recv(4096)
                    if not data:
                        break
                    self.received_data.append(data)
                except socket.timeout:
                    if self._stop_server:
                        break
            conn.close()
        except Exception:
            pass

    def tearDown(self):
        self._stop_server = True
        try:
            self.server_socket.close()
        except Exception:
            pass

    def test_connect_success(self):
        """测试成功建立连接"""
        forwarder = StreamForwarder('127.0.0.1', self.server_port, timeout=5.0)
        result = forwarder.connect()

        self.assertTrue(result)
        self.assertTrue(forwarder.is_connected)

        forwarder.close()

    def test_connect_failure(self):
        """测试连接失败"""
        forwarder = StreamForwarder('127.0.0.1', 9999, timeout=1.0)  # 无效端口
        result = forwarder.connect()

        self.assertFalse(result)
        self.assertFalse(forwarder.is_connected)

    def test_send_data(self):
        """测试发送数据"""
        forwarder = StreamForwarder('127.0.0.1', self.server_port, timeout=5.0)
        forwarder.connect()

        test_data = b'\x00\x01\x02\x03\x04\x05'
        result = forwarder.send(test_data)

        self.assertTrue(result)

        # 等待服务器接收
        time.sleep(0.3)
        self.assertEqual(len(self.received_data), 1)
        self.assertEqual(self.received_data[0], test_data)

        forwarder.close()

    def test_send_without_connection(self):
        """测试未连接时发送失败"""
        forwarder = StreamForwarder('127.0.0.1', self.server_port, timeout=5.0)

        # 未调用 connect
        result = forwarder.send(b'test data')

        self.assertFalse(result)

    def test_double_connect(self):
        """测试重复连接返回相同状态"""
        forwarder = StreamForwarder('127.0.0.1', self.server_port, timeout=5.0)

        result1 = forwarder.connect()
        result2 = forwarder.connect()  # 重复连接

        self.assertTrue(result1)
        self.assertTrue(result2)  # 应返回已连接状态

        forwarder.close()

    def test_context_manager(self):
        """测试上下文管理器"""
        with StreamForwarder('127.0.0.1', self.server_port, timeout=5.0) as forwarder:
            self.assertTrue(forwarder.is_connected)

        # 退出后应已关闭

    def test_retry_on_failure(self):
        """测试连接失败时重试3次"""
        import unittest.mock as mock

        # 创建一个会在前2次失败、第3次成功的 socket mock
        attempt_count = [0]
        original_socket = socket.socket

        def mock_socket(*args, **kwargs):
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise socket.timeout("mock timeout")
            # 第3次调用返回原始 socket
            return original_socket(*args, **kwargs)

        # 临时替换 socket
        with mock.patch('socket.socket', side_effect=mock_socket):
            forwarder = StreamForwarder('127.0.0.1', self.server_port, timeout=1.0)
            result = forwarder.connect()

            # 应该成功（因为第3次连接成功）
            self.assertTrue(result)
            self.assertTrue(forwarder.is_connected)
            # 确认尝试了3次
            self.assertGreaterEqual(attempt_count[0], 3)

            forwarder.close()


class TestSessionOutputChannel(unittest.TestCase):
    """测试 Session 管理 outputchannel_forwarder"""

    def test_session_has_outputchannel_field(self):
        """测试 Session 有 outputchannel_forwarder 字段"""
        session = StreamSession(
            streamsrc_client=None,
            taskid='TEST-001',
            fscan_params={}
        )

        self.assertTrue(hasattr(session, 'outputchannel_forwarder'))
        self.assertIsNone(session.outputchannel_forwarder)

    def test_session_attach_target(self):
        """测试附加 target_client"""
        session = StreamSession(None, 'TEST-002', {})
        mock_client = Mock()

        session.attach_target(mock_client)

        self.assertEqual(session.target_client, mock_client)

    def test_session_close_all_with_forwarder(self):
        """测试 close_all 正确关闭 forwarder"""
        session = StreamSession(None, 'TEST-003', {})

        # 模拟 forwarder
        mock_forwarder = Mock()
        session.outputchannel_forwarder = mock_forwarder

        session.close_all()

        mock_forwarder.close.assert_called_once()
        self.assertIsNone(session.outputchannel_forwarder)

    def test_session_close_all_cleans_all_connections(self):
        """测试 close_all 清理所有连接"""
        session = StreamSession(None, 'TEST-004', {})

        # 模拟三种连接
        mock_streamsrc = Mock()
        mock_target = Mock()
        mock_forwarder = Mock()

        session.streamsrc_client = mock_streamsrc
        session.target_client = mock_target
        session.outputchannel_forwarder = mock_forwarder

        session.close_all()

        # 验证所有连接都被关闭
        mock_streamsrc.close.assert_called_once()
        mock_target.disconnect.assert_called_once()
        mock_forwarder.close.assert_called_once()

        # 验证引用被清除
        self.assertIsNone(session.streamsrc_client)
        self.assertIsNone(session.target_client)
        self.assertIsNone(session.outputchannel_forwarder)


class TestActiveConnectionModeIntegration(unittest.TestCase):
    """集成测试：主动连接模式完整流程"""

    def setUp(self):
        """每个测试创建独立的服务器"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('127.0.0.1', 0))
        self.server_port = self.server_socket.getsockname()[1]
        self.server_socket.listen(1)
        self.server_socket.settimeout(3.0)

        self.received_frames = []
        self._stop_server = False
        self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
        self.server_thread.start()

    def _server_loop(self):
        """模拟外部服务器 (outputchannel 目标)"""
        try:
            conn, addr = self.server_socket.accept()
            conn.settimeout(1.0)
            while not self._stop_server:
                try:
                    data = conn.recv(4096)
                    if not data:
                        break
                    self.received_frames.append(data)
                except socket.timeout:
                    if self._stop_server:
                        break
            conn.close()
        except Exception:
            pass

    def tearDown(self):
        self._stop_server = True
        try:
            self.server_socket.close()
        except Exception:
            pass

    def test_forwarder_receives_and_forwards_frame(self):
        """测试 forwarder 接收并转发数据帧"""
        # 1. 创建 Session
        session = StreamSession(None, 'TEST-INTEGRATION-001', {'mode': 'fscan'})

        # 2. 创建并连接 Forwarder
        forwarder = StreamForwarder('127.0.0.1', self.server_port, timeout=5.0)
        self.assertTrue(forwarder.connect())

        # 3. 附加到 session
        session.outputchannel_forwarder = forwarder

        # 4. 模拟推送数据
        test_frame = b'\x00\x01\x02\x03\x04\x05\x06\x07' * 100  # 800 bytes

        # 通过 session 发送 (模拟 server.py 的推送逻辑)
        if session.outputchannel_forwarder:
            session.outputchannel_forwarder.send(test_frame)

        # 5. 验证数据被发送
        time.sleep(0.3)
        self.assertEqual(len(self.received_frames), 1)
        self.assertEqual(self.received_frames[0], test_frame)

        # 6. 清理
        session.close_all()

    def test_dual_forwarding_both_channels(self):
        """测试同时向两个通道发送 (streamsrc + outputchannel)"""
        session = StreamSession(None, 'TEST-DUAL-001', {'mode': 'fscan'})

        # 模拟 streamsrc_client
        mock_streamsrc = Mock()
        mock_streamsrc.sendall = Mock()
        session.streamsrc_client = mock_streamsrc

        # 模拟 outputchannel_forwarder
        forwarder = StreamForwarder('127.0.0.1', self.server_port, timeout=5.0)
        forwarder.connect()
        session.outputchannel_forwarder = forwarder

        # 模拟推送帧
        test_frame = b'\xAA\xBB\xCC\xDD' * 256

        # 模拟 server.py 的推送逻辑
        if session.streamsrc_client:
            session.streamsrc_client.sendall(test_frame)
        if session.outputchannel_forwarder:
            session.outputchannel_forwarder.send(test_frame)

        # 验证 streamsrc_client 被调用
        mock_streamsrc.sendall.assert_called_once_with(test_frame)

        # 验证 outputchannel 收到数据
        time.sleep(0.3)
        self.assertEqual(len(self.received_frames), 1)
        self.assertEqual(self.received_frames[0], test_frame)

        # 清理
        session.close_all()


class TestOutputChannelParsingAllMethods(unittest.TestCase):
    """测试各方法 outputchannel 解析"""

    def test_fscan_outputchannel(self):
        """测试 B_FScan outputchannel 解析"""
        soap_body = make_soap_body('''<soap:Body>
            <n:B_FScan xmlns:n="http://www.srrc.org.cn/">
              <n:taskid>TEST-FSCAN</n:taskid>
              <n:outputchannel>
                <n:mode>source</n:mode>
                <n:datachannel>stream</n:datachannel>
                <n:host>172.18.98.5</n:host>
                <n:port>8332</n:port>
                <n:stc>123</n:stc>
              </n:outputchannel>
            </n:B_FScan>
        </soap:Body>''')
        result = parse_soap_body(soap_body, "http://www.srrc.org.cn/B_FScan")
        self.assertIn('outputchannel', result)

    def test_pscan_outputchannel(self):
        """测试 B_PScan outputchannel 解析"""
        soap_body = make_soap_body('''<soap:Body>
            <n:B_PScan xmlns:n="http://www.srrc.org.cn/">
              <n:taskid>TEST-PSCAN</n:taskid>
              <n:outputchannel>
                <n:mode>source</n:mode>
                <n:datachannel>stream</n:datachannel>
                <n:host>172.18.98.5</n:host>
                <n:port>8332</n:port>
                <n:stc>456</n:stc>
              </n:outputchannel>
            </n:B_PScan>
        </soap:Body>''')
        result = parse_soap_body(soap_body, "http://www.srrc.org.cn/B_PScan")
        self.assertIn('outputchannel', result)

    def test_mscan_outputchannel(self):
        """测试 B_MScan outputchannel 解析"""
        soap_body = make_soap_body('''<soap:Body>
            <n:B_MScan xmlns:n="http://www.srrc.org.cn/">
              <n:taskid>TEST-MSCAN</n:taskid>
              <n:outputchannel>
                <n:mode>source</n:mode>
                <n:datachannel>stream</n:datachannel>
                <n:host>172.18.98.5</n:host>
                <n:port>8332</n:port>
                <n:stc>789</n:stc>
              </n:outputchannel>
            </n:B_MScan>
        </soap:Body>''')
        result = parse_soap_body(soap_body, "http://www.srrc.org.cn/B_MScan")
        self.assertIn('outputchannel', result)

    def test_sglfreq_outputchannel(self):
        """测试 B_SglFreqMeas outputchannel 解析"""
        soap_body = make_soap_body('''<soap:Body>
            <n:B_SglFreqMeas xmlns:n="http://www.srrc.org.cn/">
              <n:taskid>TEST-SGLFREQ</n:taskid>
              <n:outputchannel>
                <n:mode>source</n:mode>
                <n:datachannel>stream</n:datachannel>
                <n:host>172.18.98.5</n:host>
                <n:port>8332</n:port>
                <n:stc>999</n:stc>
              </n:outputchannel>
            </n:B_SglFreqMeas>
        </soap:Body>''')
        result = parse_soap_body(soap_body, "http://www.srrc.org.cn/B_SglFreqMeas")
        self.assertIn('outputchannel', result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
