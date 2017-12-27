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
import random

from networking_spp.agent import spp_api
from neutron.tests import base


class SppVfApiTestCase(base.BaseTestCase):

    def setUp(self):
        super(SppVfApiTestCase, self).setUp()
        self.spp_cm = mock.Mock()
        self.spp_api = spp_api.SppVfApi(self.spp_cm)
        self.sec_id = random.randint(1, 99)

    def test_exec_command_con1(self):
        res = {'results': [{'result': 'ok'}]}
        self.spp_cm.sec_command.return_value = json.dumps(res)
        ret = self.spp_api._exec_command(self.sec_id, 'command')
        self.spp_cm.sec_command.assert_called_with(self.sec_id, 'command')
        self.assertEqual(ret, res)

    def test_exec_command_con2(self):
        res = {'results': [{'result': 'error',
                            'error_details': {'message': 'test_message'}
                            }
                           ]
               }
        self.spp_cm.sec_command.return_value = json.dumps(res)
        self.assertRaises(RuntimeError,
                          lambda:
                          self.spp_api._exec_command(self.sec_id, 'command'))

    @mock.patch('networking_spp.agent.spp_api.SppVfApi'
                '._exec_command')
    def test_get_status(self, m_exec_command):
        m_exec_command.return_value = dict(info='info1')
        ret = self.spp_api.get_status(self.sec_id)
        self.assertEqual(ret, 'info1')
        m_exec_command.assert_called_with(self.sec_id, "status")

    @mock.patch('networking_spp.agent.spp_api.SppVfApi'
                '._exec_command')
    def test_make_component(self, m_exec_command):
        comp_name = 'cn'
        core_id = 'ci'
        comp_type = 'ct'
        command = "component start %s %s %s" % (comp_name, core_id, comp_type)
        self.spp_api.make_component(self.sec_id, comp_name, core_id, comp_type)
        m_exec_command.assert_called_with(self.sec_id, command)

    @mock.patch('networking_spp.agent.spp_api.SppVfApi'
                '._exec_command')
    def test_port_add(self, m_exec_command):
        port = 'port'
        direction = 'd'
        comp_name = 'cn'
        command = "port add %s %s %s" % (port, direction, comp_name)
        self.spp_api.port_add(self.sec_id, port, direction, comp_name)
        m_exec_command.assert_called_with(self.sec_id, command)

    @mock.patch('networking_spp.agent.spp_api.SppVfApi'
                '._exec_command')
    def test_flush(self, m_exec_command):
        self.spp_api.flush(self.sec_id)
        m_exec_command.assert_called_with(self.sec_id, 'flush')

    @mock.patch('networking_spp.agent.spp_api.SppVfApi'
                '._exec_command')
    def test_cancel(self, m_exec_command):
        self.spp_api.cancel(self.sec_id)
        m_exec_command.assert_called_with(self.sec_id, 'cancel')

    @mock.patch('networking_spp.agent.spp_api.SppVfApi'
                '._exec_command')
    @mock.patch('networking_spp.agent.spp_api.SppVfApi'
                '.flush')
    def test_set_classifier_table(self, m_flush, m_exec_command):
        mac = 'mac'
        port = 'port'
        command = "classifier_table add mac %s %s" % (mac, port)
        self.spp_api.set_classifier_table(self.sec_id, mac, port)
        m_exec_command.assert_called_with(self.sec_id, command)
        m_flush.assert_called_with(self.sec_id)

    @mock.patch('networking_spp.agent.spp_api.SppVfApi'
                '._exec_command')
    @mock.patch('networking_spp.agent.spp_api.SppVfApi'
                '.flush')
    def test_clear_classifier_table(self, m_flush, m_exec_command):
        mac = 'mac'
        port = 'port'
        command = "classifier_table del mac %s %s" % (mac, port)
        self.spp_api.clear_classifier_table(self.sec_id, mac, port)
        m_exec_command.assert_called_with(self.sec_id, command)
        m_flush.assert_called_with(self.sec_id)
