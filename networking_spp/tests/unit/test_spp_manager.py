# Copyright (c) 2017 NTT
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import json
import mock

from networking_spp.agent import spp_manager
from networking_spp.agent.spp_manager import SPP_PRIMATY_SERVICE
from neutron.tests import base


class SppManagerTestCase(base.BaseTestCase):

    def setUp(self):
        super(SppManagerTestCase, self).setUp()
        self.sec_ids = [1, 2]
        self.pri_sock_port = 5555
        self.sec_sock_port = 6666

        # make a SppConnectionManager object
        with mock.patch('socket.socket'):
            with mock.patch('eventlet.semaphore'):
                self.manager = \
                    spp_manager.SppConnectionManager(self.sec_ids,
                                                     self.pri_sock_port,
                                                     self.sec_sock_port)

        self.init_sec_conn = {self.sec_ids[0]: None,
                              self.sec_ids[1]: None}

    def test_accept_primary_con1(self):
        # conditions to exec if statement and assert in first time
        self.manager.pri_conn = mock.Mock()
        self.manager.pri_conn.return_value = 'CONN'
        self.manager.pri_sock.accept.return_value = ('CONN', 'IP')
        self.manager.pri_conn.close.side_effect = KeyboardInterrupt

        self.assertRaises(KeyboardInterrupt,
                          lambda: self.manager.accept_primary()
                          )
        self.assertIsInstance(self.manager.pri_conn, mock.Mock)

    def test_accept_primary_con2(self):
        # conditions to exec if statement and assert in second time
        self.manager.pri_conn = mock.Mock()
        self.manager.pri_conn.return_value = 'CONN'
        self.manager.pri_sock.accept.side_effect = \
            [('CONN', 'IP'), KeyboardInterrupt]

        self.assertRaises(KeyboardInterrupt,
                          lambda: self.manager.accept_primary()
                          )
        self.assertEqual(self.manager.pri_conn, 'CONN')

    def test_accept_primary_con3(self):
        # conditions to exec else statement and assert in second time
        self.manager.pri_conn = mock.Mock()
        self.manager.pri_conn.return_value = None
        self.manager.pri_sock.accept.side_effect = \
            [('CONN', 'IP'), KeyboardInterrupt]

        self.assertRaises(KeyboardInterrupt,
                          lambda: self.manager.accept_primary()
                          )
        self.assertEqual(self.manager.pri_conn, 'CONN')

    @mock.patch('networking_spp.agent.spp_manager.SppConnectionManager'
                '._get_process_id_from_response')
    def test_accept_secondary_con1(self, m_get_res):
        # conditions to exec if statement and assert in second time
        m_get_res.return_value = None
        self.manager.sec_sock.accept.side_effect = \
            [(mock.Mock(), 'IP'), KeyboardInterrupt]

        self.assertRaises(KeyboardInterrupt,
                          lambda: self.manager.accept_secondary()
                          )
        self.assertEqual(self.manager.sec_conn, self.init_sec_conn)

    @mock.patch('networking_spp.agent.spp_manager.SppConnectionManager'
                '._get_process_id_from_response')
    def test_accept_secondary_con2(self, m_get_res):
        # conditions to exec the 1st elif statement and assert in second time
        m_get_res.return_value = 3
        self.manager.sec_sem = [1, 2]
        self.manager.sec_sock.accept.side_effect = \
            [(mock.Mock(), 'IP'), KeyboardInterrupt]

        self.assertRaises(KeyboardInterrupt,
                          lambda: self.manager.accept_secondary()
                          )
        self.assertEqual(self.manager.sec_conn, self.init_sec_conn)

    @mock.patch('networking_spp.agent.spp_manager.SppConnectionManager'
                '._get_process_id_from_response')
    def test_accept_secondary_con3(self, m_get_res):
        # conditions to exec the 2nd elif statement and assert in second time
        m_get_res.return_value = 1
        self.manager.sec_conn = {1: mock.Mock(), 2: mock.Mock()}
        conn = mock.Mock()
        self.manager.sec_sock.accept.side_effect = \
            [(conn, 'IP'), KeyboardInterrupt]

        self.assertRaises(KeyboardInterrupt,
                          lambda: self.manager.accept_secondary()
                          )
        self.assertEqual(self.manager.sec_conn[1], conn)

    @mock.patch('networking_spp.agent.spp_manager.SppConnectionManager'
                '._get_process_id_from_response')
    def test_accept_secondary_con4(self, m_get_res):
        # conditions to exec the last else statement and assert in second time
        m_get_res.return_value = 1
        self.manager.sec_conn = {1: None, 2: mock.Mock()}
        conn = mock.Mock()
        self.manager.sec_sock.accept.side_effect = \
            [(conn, 'IP'), KeyboardInterrupt]

        self.assertRaises(KeyboardInterrupt,
                          lambda: self.manager.accept_secondary()
                          )
        self.assertEqual(self.manager.sec_conn[1], conn)

    def test_cont_recv_con1(self):
        # conditions to exec if statement and return data
        conn = mock.Mock()
        length = spp_manager.MSG_SIZE - 1
        res = ''.ljust(length, 'a')
        conn.recv.return_value = res
        ret = self.manager._cont_recv(conn)

        self.assertEqual(ret, res)

    def test_cont_recv_con2(self):
        # conditions not to exec if statement and to assert second time
        conn = mock.Mock()
        length = spp_manager.MSG_SIZE
        res = ''.ljust(length, 'a')
        conn.recv.side_effect = [res, KeyboardInterrupt]

        self.assertRaises(KeyboardInterrupt,
                          lambda: self.manager._cont_recv(conn)
                          )

    def test_cont_recv_con3(self):
        # conditions to exec except statement but if statement
        conn = mock.Mock()
        conn.recv.side_effect = IndexError

        self.assertRaises(IndexError,
                          lambda: self.manager._cont_recv(conn)
                          )

    @mock.patch('networking_spp.agent.spp_manager.'
                'SppConnectionManager._cont_recv')
    def test_sec_command_con1(self, m_cont_recv):

        # conditions to exec the first if statement
        length = spp_manager.MSG_SIZE
        sec_con1 = mock.Mock()
        sec_con1.recv.return_value = ''.ljust(length, 'a')
        self.manager.sec_conn = {1: sec_con1, 2: mock.Mock()}
        self.manager.sec_command(1, 'command')

        m_cont_recv.assert_called_with(sec_con1)

    def test_sec_command_con2(self):

        # conditions to exec the second if statement
        length = spp_manager.MSG_SIZE - 1
        sec_con1 = mock.Mock()
        res = ''.ljust(length, 'a')
        sec_con1.recv.return_value = res
        self.manager.sec_conn = {1: sec_con1, 2: mock.Mock()}
        ret = self.manager.sec_command(1, 'command')

        self.assertEqual(ret, res)

    def test_sec_command_con3(self):

        # conditions to exec the raise statement
        sec_con1 = mock.Mock()
        sec_con1.recv.return_value = None
        self.manager.sec_conn = {1: sec_con1, 2: mock.Mock()}

        self.assertRaises(RuntimeError,
                          lambda: self.manager.sec_command(1, 'command')
                          )

    def test_get_process_id_from_response_con1(self):

        # conditions to exec if statement
        data = {"results": [{"result": 'failed'}]}
        res = json.dumps(data)
        ret = self.manager._get_process_id_from_response(res)

        self.assertEqual(ret, None)

    def test_get_process_id_from_response_con2(self):

        # conditions not to exec if statement
        data = {"results": [{"result": "success"}], "client_id": 2}
        res = json.dumps(data)
        ret = self.manager._get_process_id_from_response(res)

        self.assertEqual(ret, 2)

    @mock.patch('networking_spp.agent.spp_manager._start_primary')
    @mock.patch('networking_spp.agent.spp_manager._is_service_active')
    @mock.patch('networking_spp.agent.spp_manager._wait_service_initialized')
    def test_ensure_spp_services_running_con1(self,
                                              m_wait_service,
                                              m_is_service_active,
                                              m_start_primary,
                                              ):
        # conditions to exec if statement
        m_is_service_active.return_value = True
        spp_manager.ensure_spp_services_running(self.sec_ids, self.manager)

        self.assertEqual(m_wait_service.call_count, len(self.sec_ids))

    @mock.patch('networking_spp.agent.spp_manager._start_primary')
    @mock.patch('networking_spp.agent.spp_manager._is_service_active')
    @mock.patch('networking_spp.agent.spp_manager._wait_service_initialized')
    @mock.patch('networking_spp.agent.spp_manager._service_start')
    def test_ensure_spp_services_running_con2(self,
                                              m_service_start,
                                              m_wait_service,
                                              m_is_service_active,
                                              m_start_primary,
                                              ):
        # conditions to exec else statement
        m_is_service_active.return_value = False
        spp_manager.ensure_spp_services_running(self.sec_ids, self.manager)

        self.assertEqual(m_wait_service.call_count, len(self.sec_ids))
        self.assertEqual(m_service_start.call_count, len(self.sec_ids))

    @mock.patch('networking_spp.agent.spp_manager._service_start')
    @mock.patch('networking_spp.agent.spp_manager._is_service_active')
    @mock.patch('networking_spp.agent.spp_manager._wait_service_initialized')
    def test_start_primary_con1(self,
                                m_wait_service,
                                m_is_service_active,
                                m_service_start,
                                ):
        # conditions to exec if statement
        m_is_service_active.return_value = True
        spp_manager._start_primary(self.sec_ids, self.manager)

        self.assertEqual(m_service_start.call_count, 0)
        self.assertEqual(m_wait_service.call_count, 1)

    @mock.patch('networking_spp.agent.spp_manager._service_start')
    @mock.patch('networking_spp.agent.spp_manager._is_service_active')
    @mock.patch('networking_spp.agent.spp_manager._wait_service_initialized')
    def test_start_primary_con2(self,
                                m_wait_service,
                                m_is_service_active,
                                m_service_start,
                                ):
        # conditions to exec else statement
        m_is_service_active.return_value = False
        spp_manager._start_primary(self.sec_ids, self.manager)

        self.assertEqual(m_service_start.call_count, 1)
        self.assertEqual(m_wait_service.call_count, 1)

    @mock.patch('networking_spp.agent.spp_manager._service_start')
    @mock.patch('networking_spp.agent.spp_manager._is_service_active')
    @mock.patch('networking_spp.agent.spp_manager._wait_service_initialized')
    def test_start_primary_con3(self,
                                m_wait_service,
                                m_is_service_active,
                                m_service_start,
                                ):
        # conditions to exec else statement and then if statement
        m_is_service_active.side_effect = \
            lambda s: False if s == SPP_PRIMATY_SERVICE else True
        spp_manager._start_primary(self.sec_ids, self.manager)

        self.assertEqual(m_service_start.call_count, 0)
        self.assertEqual(m_wait_service.call_count, 0)

    def test_wait_service_initialized(self):
        def dummy(sec):
            pass

        # exec try statement
        self.assertEqual(None, spp_manager._wait_service_initialized(dummy, 2))
