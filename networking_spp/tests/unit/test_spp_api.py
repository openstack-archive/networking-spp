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

import mock
import random

from networking_spp.agent import spp_api
from neutron.tests import base


class SppVfApiTestCase(base.BaseTestCase):

    def setUp(self):
        super(SppVfApiTestCase, self).setUp()
        self.sec_id = random.randint(1, 99)
        self.api_ip_addr = "127.0.0.1"
        self.api_port = 7777
        self.spp_api = spp_api.SppVfApi(self.sec_id, self.api_ip_addr,
                                        self.api_port)

    @mock.patch('requests.request')
    def test_send_request_con1(self, m_request):
        method = "METHOD"
        url = "/url"
        data = {"data": "data"}
        path = self.spp_api.host_url + self.spp_api.proc_url + url
        ret = mock.Mock()
        ret.status_code = 204
        m_request.return_value = ret
        self.spp_api.send_request(method, url, data)
        m_request.assert_called_with(method, path, json=data)

    @mock.patch('networking_spp.agent.spp_api.SppVfApi'
                '.send_request')
    def test_get_status(self, m_send_request):
        m_send_request.return_value = 'info1'
        self.spp_api.get_status()
        self.assertEqual(self.spp_api.info, 'info1')
        m_send_request.assert_called_with("GET", "")

    @mock.patch('networking_spp.agent.spp_api.SppVfApi'
                '.send_request')
    def test_make_component(self, m_send_request):
        comp_name = 'cn'
        core_id = 'ci'
        comp_type = 'ct'
        data = {"name": comp_name, "core": core_id, "type": comp_type}
        self.spp_api.make_component(comp_name, core_id, comp_type)
        m_send_request.assert_called_with("POST", "/components", data)

    @mock.patch('networking_spp.agent.spp_api.SppVfApi'
                '.send_request')
    def test_port_add(self, m_send_request):
        port = 'port'
        direction = 'd'
        comp_name = 'cn'
        data = {"action": "attach", "port": port, "dir": direction}
        path = "/components/%s/ports" % comp_name
        self.spp_api.port_add(port, direction, comp_name)
        m_send_request.assert_called_with("PUT", path, data)

    @mock.patch('networking_spp.agent.spp_api.SppVfApi'
                '.send_request')
    def test_port_add_add_vlantag(self, m_send_request):
        port = 'port'
        direction = 'd'
        comp_name = 'cn'
        op = 'add_vlantag'
        vlan_id = 10
        data = {"action": "attach", "port": port, "dir": direction,
                "vlan": {"operation": "add", "id": vlan_id, "pcp": 0}}
        path = "/components/%s/ports" % comp_name
        self.spp_api.port_add(port, direction, comp_name, op, vlan_id)
        m_send_request.assert_called_with("PUT", path, data)

    @mock.patch('networking_spp.agent.spp_api.SppVfApi'
                '.send_request')
    def test_port_add_del_vlantag(self, m_send_request):
        port = 'port'
        direction = 'd'
        comp_name = 'cn'
        op = 'del_vlantag'
        data = {"action": "attach", "port": port, "dir": direction,
                "vlan": {"operation": "del"}}
        path = "/components/%s/ports" % comp_name
        self.spp_api.port_add(port, direction, comp_name, op)
        m_send_request.assert_called_with("PUT", path, data)

    @mock.patch('networking_spp.agent.spp_api.SppVfApi'
                '.send_request')
    def test_port_del(self, m_send_request):
        port = 'port'
        direction = 'd'
        comp_name = 'cn'
        data = {"action": "detach", "port": port, "dir": direction}
        path = "/components/%s/ports" % comp_name
        self.spp_api.port_del(port, direction, comp_name)
        m_send_request.assert_called_with("PUT", path, data)

    def test_port_exist_con1(self):
        self.spp_api.info = {
            "components": [{"name": "con1",
                            "rx_port": [{"port": "ring:1"}],
                            "tx_port": [{"port": "vhost:1"}]}]}
        self.assertTrue(self.spp_api.port_exist("ring:1", "rx", "con1"))

    def test_port_exist_con2(self):
        self.spp_api.info = {
            "components": [{"name": "con1",
                            "rx_port": [{"port": "ring:1"}],
                            "tx_port": [{"port": "vhost:1"}]}]}
        self.assertFalse(self.spp_api.port_exist("ring:1", "tx", "con1"))

    @mock.patch('networking_spp.agent.spp_api.SppVfApi'
                '.send_request')
    def test_set_classifier_table(self, m_send_request):
        mac = 'mac'
        port = 'port'
        data = {"action": "add", "type": "mac", "mac_address": mac,
                "port": port}
        self.spp_api.set_classifier_table(mac, port)
        m_send_request.assert_called_with("PUT", "/classifier_table", data)

    @mock.patch('networking_spp.agent.spp_api.SppVfApi'
                '.send_request')
    def test_clear_classifier_table(self, m_send_request):
        mac = 'mac'
        port = 'port'
        data = {"action": "del", "type": "mac", "mac_address": mac,
                "port": port}
        self.spp_api.clear_classifier_table(mac, port)
        m_send_request.assert_called_with("PUT", "/classifier_table", data)

    @mock.patch('networking_spp.agent.spp_api.SppVfApi'
                '.send_request')
    def test_set_classifier_table_with_vlan(self, m_send_request):
        mac = 'mac'
        port = 'port'
        vlan_id = 10
        data = {"action": "add", "type": "vlan", "mac_address": mac,
                "port": port, "vlan": vlan_id}
        self.spp_api.set_classifier_table_with_vlan(mac, port, vlan_id)
        m_send_request.assert_called_with("PUT", "/classifier_table", data)

    @mock.patch('networking_spp.agent.spp_api.SppVfApi'
                '.send_request')
    def test_clear_classifier_table_with_vlan(self, m_send_request):
        mac = 'mac'
        port = 'port'
        vlan_id = 10
        data = {"action": "del", "type": "vlan", "mac_address": mac,
                "port": port, "vlan": vlan_id}
        self.spp_api.clear_classifier_table_with_vlan(mac, port, vlan_id)
        m_send_request.assert_called_with("PUT", "/classifier_table", data)


class SppMirrorApiTestCase(base.BaseTestCase):

    def setUp(self):
        super(SppMirrorApiTestCase, self).setUp()
        self.sec_id = random.randint(1, 99)
        self.api_ip_addr = "127.0.0.1"
        self.api_port = 7777
        self.spp_api = spp_api.SppMirrorApi(self.sec_id, self.api_ip_addr,
                                            self.api_port)

    @mock.patch('networking_spp.agent.spp_api.SppMirrorApi'
                '.send_request')
    def test_make_component(self, m_send_request):
        comp_name = 'cn'
        core_id = 'ci'
        data = {"name": comp_name, "core": core_id, "type": "mirror"}
        self.spp_api.make_component(comp_name, core_id)
        m_send_request.assert_called_with("POST", "/components", data)
