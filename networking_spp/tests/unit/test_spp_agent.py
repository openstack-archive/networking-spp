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

from networking_spp.agent import spp_agent
from neutron.tests import base


class VhostTestCase(base.BaseTestCase):

    def setUp(self):
        super(VhostTestCase, self).setUp()
        self.vhost_id = random.randint(1, 99)
        self.sec_id = random.randint(1, 99)

    def test_nic_port_fun(self):
        result = "phy:%d" % (self.sec_id - 1)
        self.assertEqual(spp_agent._nic_port(self.sec_id), result)

    def test_vhost_port_fun(self):
        result = "vhost:%d" % self.vhost_id
        self.assertEqual(spp_agent._vhost_port(self.vhost_id), result)

    def test_rx_ring_port_fun(self):
        result = "ring:%d" % (self.vhost_id * 2)
        self.assertEqual(spp_agent._rx_ring_port(self.vhost_id), result)

    def test_tx_ring_port_fun(self):
        result = "ring:%d" % (self.vhost_id * 2 + 1)
        self.assertEqual(spp_agent._tx_ring_port(self.vhost_id), result)

    def test_vhostuser(self):
        vf = spp_agent.SppVf(self.sec_id, 'py_net', '127.0.0.1', 7777)
        vhostuser = spp_agent.Vhostuser(self.vhost_id, vf)
        self.assertEqual(vhostuser.vhost_id, self.vhost_id)
        self.assertEqual(vhostuser.vf, vf)
        self.assertEqual(vhostuser.phys_net, 'py_net')
        self.assertEqual(vhostuser.mac_address, 'unuse')


class SppVfTestCase(base.BaseTestCase):

    def setUp(self):
        super(SppVfTestCase, self).setUp()
        self.spp_vf = spp_agent.SppVf(1, 'phy_net', '127.0.0.1', 7777)

    @mock.patch('networking_spp.agent.spp_api.SppVfApi.make_component')
    @mock.patch('networking_spp.agent.spp_api.SppVfApi.port_add')
    @mock.patch('networking_spp.agent.spp_api.SppVfApi.get_status')
    def test_build_components_con1(self, m_g, m_port_add, m_mk_comp):
        self.spp_vf.info = {"components": [{"core": 2,
                                            "type": "forward",
                                            "name": "fw1",
                                            "rx_port": [{"port": "vhost:1"}],
                                            "tx_port": [{"port": "ring:1"}]}]}
        components = [{"core": 2,
                       "type": "forward",
                       "name": "fw1",
                       "rx_port": ["vhost:1"],
                       "tx_port": ["ring:1"]}]
        self.spp_vf.build_components(components)

        self.assertEqual(m_mk_comp.call_count, 0)
        self.assertEqual(m_port_add.call_count, 0)

    @mock.patch('networking_spp.agent.spp_api.SppVfApi.make_component')
    @mock.patch('networking_spp.agent.spp_api.SppVfApi.port_add')
    @mock.patch('networking_spp.agent.spp_api.SppVfApi.get_status')
    def test_build_components_con2(self, m_g, m_port_add, m_mk_comp):
        self.spp_vf.info = {"components": [{"core": 2,
                                            "type": "unuse"}]}
        components = [{"core": 2,
                       "type": "forward",
                       "name": "fw1",
                       "rx_port": ["vhost:1"],
                       "tx_port": ["ring:1"]}]
        self.spp_vf.build_components(components)

        self.assertEqual(m_mk_comp.call_count, 1)
        self.assertEqual(m_port_add.call_count, 2)

    def test_build_vhosts(self):
        components = [{"tx_port": ["vhost:3"]}]
        self.spp_vf.build_vhosts(components)

        self.assertEqual(self.spp_vf.vhostusers[3].vhost_id, 3)

    def test_init_vhost_mac_address_con1(self):
        info = {"classifier_table": [{"type": "mac",
                                      "port": "ring:12",
                                      "value": "12:ab:34:cd:56:ef"}]}
        self.spp_vf.info = info
        vhost_id = 12 // 2
        self.spp_vf.vhostusers[vhost_id] = mock.Mock()
        self.spp_vf.init_vhost_mac_address()

        self.assertEqual(self.spp_vf.vhostusers[vhost_id].mac_address,
                         '12:ab:34:cd:56:ef')

    def test_init_vhost_mac_address_con2(self):
        info = {"classifier_table": [{"type": "vlan",
                                      "port": "ring:12",
                                      "value": "100/12:ab:34:cd:56:ef"}]}
        self.spp_vf.info = info
        vhost_id = 12 // 2
        self.spp_vf.vhostusers[vhost_id] = mock.Mock()
        self.spp_vf.init_vhost_mac_address()

        self.assertEqual(self.spp_vf.vhostusers[vhost_id].mac_address,
                         '12:ab:34:cd:56:ef')


class SppAgentTestCase(base.BaseTestCase):

    def setUp(self):
        super(SppAgentTestCase, self).setUp()
        self.sec_id = 1
        self.vhost_id = 2
        self.conf = mock.Mock()
        self.agent = self._get_agent()

    @mock.patch('networking_spp.agent.spp_agent.SppAgent.'
                '_get_dpdk_port_mappings')
    @mock.patch('networking_spp.agent.spp_agent.SppAgent._conf_components')
    @mock.patch('networking_spp.agent.spp_agent.SppVf')
    @mock.patch('networking_spp.common.etcd_client.EtcdClient')
    @mock.patch('networking_spp.agent.spp_agent.SppAgent._report_state')
    @mock.patch('networking_spp.agent.spp_agent.eventlet')
    def _get_agent(self, a, b, c, d, e, f):
        return spp_agent.SppAgent(self.conf)

    def test_get_dpdk_port_mappings(self):
        # conditions
        self.agent.host = 'host1'
        key = '/spp/openstack/configuration/' + self.agent.host
        value = {key: '1'}
        self.agent.etcd.get.return_value = json.dumps(value)
        ret = self.agent._get_dpdk_port_mappings()

        self.agent.etcd.get.assert_called_with(key)
        self.assertEqual(ret, value)

    def test_conf_components(self):
        # conditions
        num_vhost = 3
        res = [{'name': 'forward_2_tx',
                'core': 2,
                'rx_port': ['ring:4'],
                'tx_port': ['vhost:2'],
                'type': 'forward'},
               {'name': 'forward_2_rx',
                'core': 3,
                'rx_port': ['vhost:2'],
                'tx_port': ['ring:5'],
                'type': 'forward'},
               {'name': 'forward_3_tx',
                'core': 4,
                'rx_port': ['ring:6'],
                'tx_port': ['vhost:3'],
                'type': 'forward'},
               {'name': 'forward_3_rx',
                'core': 5,
                'rx_port': ['vhost:3'],
                'tx_port': ['ring:7'],
                'type': 'forward'},
               {'name': 'forward_4_tx',
                'core': 6,
                'rx_port': ['ring:8'],
                'tx_port': ['vhost:4'],
                'type': 'forward'},
               {'name': 'forward_4_rx',
                'core': 7,
                'rx_port': ['vhost:4'],
                'tx_port': ['ring:9'],
                'type': 'forward'},
               {'name': 'classifier',
                'core': 8,
                'rx_port': ['phy:0'],
                'tx_port': ['ring:4', 'ring:6', 'ring:8'],
                'type': 'classifier_mac'},
               {'name': 'merger',
                'core': 9,
                'rx_port': ['ring:5', 'ring:7', 'ring:9'],
                'tx_port': ['phy:0'],
                'type': 'merge'}]

        cores = self.agent._get_cores("0x3fe")
        ret = self.agent._conf_components(self.sec_id,
                                          self.vhost_id,
                                          num_vhost, cores)
        self.assertEqual(ret, res)

    def test_set_classifier_table_con1(self):
        # conditions to exec if statement
        mac = '12:ab:34:cd:56:ef'
        vhost = mock.Mock()
        vhost.vf = mock.Mock()
        vhost.mac_address = mac
        self.agent.vhostusers[1] = vhost

        ret = self.agent.set_classifier_table(1, mac, None)
        self.assertEqual(ret, None)
        self.assertEqual(vhost.vf.set_classifier_table.call_count,
                         0)

    def test_set_classifier_table_con2(self):
        # conditions to exec correctly
        mac = '12:ab:34:cd:56:ef'
        vhost = mock.Mock()
        vhost.vf = mock.Mock()
        vhost.mac_address = 'unuse'
        self.agent.vhostusers[1] = vhost

        self.agent.set_classifier_table(1, mac, None)
        self.assertEqual(vhost.vf.set_classifier_table.call_count,
                         1)
        self.assertEqual(vhost.mac_address, mac)

    def test_set_classifier_table_with_vlan(self):
        mac = '12:ab:34:cd:56:ef'
        vhost = mock.Mock()
        vhost.vf = mock.Mock()
        vhost.mac_address = 'unuse'
        self.agent.vhostusers[1] = vhost

        self.agent.set_classifier_table(1, mac, 10)
        self.assertEqual(vhost.vf.port_add.call_count, 2)
        self.assertEqual(vhost.vf.port_del.call_count, 2)
        self.assertEqual(vhost.vf.set_classifier_table_with_vlan.call_count, 1)
        self.assertEqual(vhost.mac_address, mac)

    def test_clear_classifier_table_con1(self):
        # conditions to exec if statement
        mac = 'unuse'
        vhost = mock.Mock()
        vhost.vf = mock.Mock()
        vhost.mac_address = 'unuse'
        self.agent.vhostusers[1] = vhost

        ret = self.agent.clear_classifier_table(1, mac, None)
        self.assertEqual(ret, None)
        count = vhost.vf.clear_classifier_table.call_count
        self.assertEqual(count, 0)

    def test_clear_classifier_table_con2(self):
        # conditions to exec correctly
        mac = '12:ab:34:cd:56:ef'
        vhost = mock.Mock()
        vhost.vf = mock.Mock()
        vhost.mac_address = mac
        self.agent.vhostusers[1] = vhost

        self.agent.clear_classifier_table(1, mac, None)
        count = vhost.vf.clear_classifier_table.call_count
        self.assertEqual(count, 1)
        self.assertEqual(vhost.mac_address, 'unuse')

    def test_clear_classifier_table_with_vlan(self):
        mac = '12:ab:34:cd:56:ef'
        vhost = mock.Mock()
        vhost.vf = mock.Mock()
        vhost.mac_address = mac
        self.agent.vhostusers[1] = vhost

        self.agent.clear_classifier_table(1, mac, 10)
        self.assertEqual(vhost.vf.port_add.call_count, 2)
        self.assertEqual(vhost.vf.port_del.call_count, 2)
        cnt = vhost.vf.clear_classifier_table_with_vlan.call_count
        self.assertEqual(cnt, 1)
        self.assertEqual(vhost.mac_address, 'unuse')

    @mock.patch('networking_spp.agent.spp_agent.SppAgent.set_classifier_table')
    def test_plug_port(self, m_set):
        # conditions
        port_id = 111
        vhost_id = 1
        mac = '12:ab:34:cd:56:ef'
        self.agent.host = 'host1'
        key = '/spp/openstack/port_status/host1/111'

        self.agent._plug_port(port_id, vhost_id, mac, None)
        m_set.assert_called_with(vhost_id, mac, None)
        self.agent.etcd.put.assert_called_with(key, "up")

    @mock.patch('networking_spp.common.etcd_key.bind_port_key')
    @mock.patch('networking_spp.common.etcd_key.action_key')
    @mock.patch('networking_spp.common.etcd_key.port_status_key')
    @mock.patch('networking_spp.common.etcd_key.vhost_key')
    @mock.patch('networking_spp.agent.spp_agent.SppAgent.'
                'clear_classifier_table')
    def test_unplug_port(self,
                         m_clear,
                         m_vhost_key,
                         m_port_status_key,
                         m_action_key,
                         m_bind_port_key):

        # conditions
        port_id = 111
        vhost_id = 1
        mac = '12:ab:34:cd:56:ef'
        self.agent.host = 'host'
        vhostuser = mock.Mock()
        vhostuser.phys_net = 'phy_net'
        self.agent.vhostusers = {1: vhostuser}
        m_vhost_key.return_value = 'key'

        self.agent._unplug_port(port_id, vhost_id, mac, None)
        m_clear.assert_called_with(vhost_id, mac, None)
        m_vhost_key.assert_called_with('host', 'phy_net', vhost_id)
        self.agent.etcd.replace.assert_called_once()
        m_bind_port_key.assert_called_with('host', port_id)
        m_action_key.assert_called_with('host', port_id)
        m_port_status_key.assert_called_with('host', port_id)
        self.assertEqual(self.agent.etcd.delete.call_count, 3)

    def test_do_plug_unplug_con1(self):
        # conditions to exec the 1st if statement
        port_id = 111
        self.agent.etcd.get.return_value = None

        ret = self.agent._do_plug_unplug(port_id)
        self.assertEqual(ret, None)
        self.assertEqual(self.agent.etcd.get.call_count, 1)

    @mock.patch('networking_spp.agent.spp_agent.SppAgent._plug_port')
    def test_do_plug_unplug_con2(self, m_plug_port):
        # conditions to exec the 2nd if statement
        port_id = 111
        data = {"vhost_id": 1, 'mac_address': '12:34:56:78:90:ab'}
        value = json.dumps(data)
        self.agent.etcd.get.side_effect = [value, 'plug']

        self.agent._do_plug_unplug(port_id)
        m_plug_port.assert_called_with(port_id, 1, '12:34:56:78:90:ab', None)

    @mock.patch('networking_spp.agent.spp_agent.SppAgent._unplug_port')
    def test_do_plug_unplug_con3(self, m_unplug_port):
        # conditions to exec the else statement
        port_id = 111
        data = {"vhost_id": 1, 'mac_address': '12:34:56:78:90:ab',
                'vlan_id': 10}
        value = json.dumps(data)
        self.agent.etcd.get.side_effect = [value, 'unplug']

        self.agent._do_plug_unplug(port_id)
        m_unplug_port.assert_called_with(port_id, 1, '12:34:56:78:90:ab', 10)

    @mock.patch('networking_spp.common.etcd_key.action_host_prefix')
    @mock.patch('networking_spp.agent.spp_agent.SppAgent._do_plug_unplug')
    def test_port_plug_watch_con1(self, m_do, m_prefix):
        # conditions to exec if statement and for statement twice
        m_prefix.return_value = '/aa/bb/'
        self.agent.etcd.watch_prefix.return_value = [('/aa/bb/123', 'plug'),
                                                     ('/aa/bb/321', 'unplug')
                                                     ]
        self.agent.port_plug_watch()
        self.assertEqual(m_do.call_args_list[0][0][0], '123')
        self.assertEqual(m_do.call_args_list[1][0][0], '321')
        self.assertEqual(m_do.call_count, 2)

    @mock.patch('networking_spp.common.etcd_key.action_host_prefix')
    @mock.patch('networking_spp.agent.spp_agent.SppAgent._do_plug_unplug')
    def test_port_plug_watch_con2(self, m_do, m_prefix):
        # conditions to exec if statement and then raise exception
        m_prefix.return_value = '/aa/bb/'
        self.agent.etcd.watch_prefix.return_value = [('/aa/bb/123', 'plug'),
                                                     ('/aa/bb/321', 'unplug')
                                                     ]
        m_do.side_effect = Exception
        self.agent.port_plug_watch()
        self.assertEqual(m_do.call_count, 1)
        self.assertEqual(self.agent.port_plug_watch_failed, True)

    @mock.patch('networking_spp.common.etcd_key.action_host_prefix')
    @mock.patch('networking_spp.agent.spp_agent.SppAgent._do_plug_unplug')
    def test_recover(self, m_do, m_prefix):
        # conditions to exec if statement and for statement twice
        m_prefix.return_value = '/aa/bb/'
        self.agent.etcd.get_prefix.return_value = [('/aa/bb/123', 'plug'),
                                                   ('/aa/bb/321', 'unplug')
                                                   ]
        self.agent.recover()
        self.assertEqual(m_do.call_args_list[0][0][0], '123')
        self.assertEqual(m_do.call_args_list[1][0][0], '321')
        self.assertEqual(m_do.call_count, 2)

    def test_handle_signal(self):
        self.agent.shutdown_sem = mock.Mock()
        self.agent._handle_signal('si', 'fr')
        self.agent.shutdown_sem.release.assert_called_once()

    def test_wait_shutdown_con1(self):
        self.agent.port_plug_watch_failed = True
        ret = self.agent.wait_shutdown()
        self.assertEqual(ret, 1)

    def test_wait_shutdown_con2(self):
        self.agent.port_plug_watch_failed = False
        ret = self.agent.wait_shutdown()
        self.assertEqual(ret, 0)

    @mock.patch('networking_spp.agent.spp_agent.loopingcall')
    def test_start_report(self, m_loop):
        heartbeat = mock.Mock()
        heartbeat.start.return_value = None
        m_loop.FixedIntervalLoopingCall.return_value = heartbeat
        self.agent.start_report()
        heartbeat.start.assert_called_once()

    def test_start_state(self):
        # conditions
        self.agent.state_rpc = mock.Mock()
        self.agent.state_rpc.report_state.return_value = None
        self.agent.agent_state = {'host': 'host1', 'start_flag': True}
        self.agent._report_state()

        self.agent.state_rpc.report_state.assert_called_once()
        self.assertEqual(self.agent.agent_state, {'host': 'host1'})
