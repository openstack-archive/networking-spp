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

from networking_spp.agent import spp_agent
from neutron.tests import base


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
                                            "rx_port": [{"port": "vhost:2"}],
                                            "tx_port": [{"port": "ring:2"}]}]}
        components = [{"core": 2,
                       "type": "forward",
                       "name": "fw2",
                       "rx_port": ["vhost:1"],
                       "tx_port": ["ring:1"]}]
        self.spp_vf.build_components(components)
        self.assertEqual(m_mk_comp.call_count, 1)
        self.assertEqual(m_port_add.call_count, 2)
        m_port_add.assert_called_with("vhost:1", "rx", "fw2")

    @mock.patch('networking_spp.agent.spp_api.SppVfApi.make_component')
    @mock.patch('networking_spp.agent.spp_api.SppVfApi.port_add')
    @mock.patch('networking_spp.agent.spp_api.SppVfApi.get_status')
    def test_build_components_con2(self, m_g, m_port_add, m_mk_comp):
        self.spp_vf.info = {"components": [{"core": 2,
                                            "type": "classifier_mac",
                                            "name": "fw3",
                                            "rx_port": [],
                                            "tx_port": [{"port": "ring:1"}]}]}
        components = [{"core": 2,
                       "type": "classifier_mac",
                       "name": "fw3",
                       "rx_port": ["vhost:2"],
                       "tx_port": ["ring:1", "ring:2", "ring:3"]}]
        self.spp_vf.build_components(components)
        self.assertEqual(m_mk_comp.call_count, 0)
        self.assertEqual(m_port_add.call_count, 3)
        m_port_add.assert_called_with("vhost:2", "rx", "fw3")

    @mock.patch('networking_spp.agent.spp_api.SppVfApi.make_component')
    @mock.patch('networking_spp.agent.spp_api.SppVfApi.port_add')
    @mock.patch('networking_spp.agent.spp_api.SppVfApi.get_status')
    def test_build_components_con3(self, m_g, m_port_add, m_mk_comp):
        self.spp_vf.info = {"components": [{"core": 2,
                                            "type": "forward",
                                            "name": "fw4",
                                            "rx_port": [],
                                            "tx_port": []}]}
        components = [{"core": 2,
                       "type": "forward",
                       "name": "fw4",
                       "rx_port": ["vhost:3"],
                       "tx_port": ["ring:3"]}]
        self.spp_vf.build_components(components)
        self.assertEqual(m_mk_comp.call_count, 0)
        self.assertEqual(m_port_add.call_count, 2)
        m_port_add.assert_called_with("vhost:3", "rx", "fw4")

    @mock.patch('networking_spp.agent.spp_api.SppVfApi.make_component')
    @mock.patch('networking_spp.agent.spp_api.SppVfApi.port_add')
    @mock.patch('networking_spp.agent.spp_api.SppVfApi.get_status')
    def test_build_components_con4(self, m_g, m_port_add, m_mk_comp):
        self.spp_vf.info = {"components": [{"core": 2,
                                            "type": "forward",
                                            "name": "fw5",
                                            "rx_port": [],
                                            "tx_port": []}]}
        components = [{"core": 2,
                       "type": "merge",
                       "name": "fw5",
                       "rx_port": ["ring:1"],
                       "tx_port": ["vhost:1"]}]
        self.spp_vf.build_components(components)
        self.assertEqual(m_mk_comp.call_count, 0)
        self.assertEqual(m_port_add.call_count, 2)
        m_port_add.assert_called_with("ring:1", "rx", "fw5")

    @mock.patch('networking_spp.agent.spp_api.SppVfApi.make_component')
    @mock.patch('networking_spp.agent.spp_api.SppVfApi.port_add')
    @mock.patch('networking_spp.agent.spp_api.SppVfApi.get_status')
    def test_build_components_con5(self, m_g, m_port_add, m_mk_comp):
        self.spp_vf.info = {"components": [{"core": 2,
                                            "type": "forward",
                                            "name": "fw6",
                                            "rx_port": [{"port": "phys:2"}],
                                            "tx_port": []}]}
        components = [{"core": 2,
                       "type": "merge",
                       "name": "fw6",
                       "rx_port": ["phys:1", "phys:3", "phys:2"],
                       "tx_port": ["phys:5"]}]
        self.spp_vf.build_components(components)
        self.assertEqual(m_mk_comp.call_count, 0)
        self.assertEqual(m_port_add.call_count, 3)
        m_port_add.assert_called_with("phys:3", "rx", "fw6")

    def test_build_vhosts_con1(self):
        components = [{"type": "forward",
                       "name": "fw0",
                       "rx_port": ["ring:0"],
                       "tx_port": ["vhost:0"]},
                      {"type": "forward",
                       "name": "fw1",
                       "rx_port": ["vhost:0"],
                       "tx_port": ["ring:1"]},
                      {"type": "classifier_mac",
                       "name": "cls1",
                       "rx_port": ["phy:0"],
                       "tx_port": ["ring:0"]},
                      {"type": "merge",
                       "name": "merge1",
                       "rx_port": ["ring:1"],
                       "tx_port": ["phy:0"]}]
        self.spp_vf.build_vhosts(components)

        vhost = self.spp_vf.vhostusers[0]
        self.assertEqual(vhost.name, "vhost:0")
        self.assertEqual(vhost.del_vlan_port, "ring:0")
        self.assertEqual(vhost.del_vlan_comp, "cls1")
        self.assertEqual(vhost.add_vlan_port, "ring:1")
        self.assertEqual(vhost.add_vlan_comp, "merge1")
        self.assertEqual(vhost.dst_comp, "fw0")
        self.assertEqual(vhost.in_ring, "ring:0")
        self.assertEqual(vhost.in_comp, "fw0")
        self.assertEqual(vhost.out_ring, "ring:1")
        self.assertEqual(vhost.out_comp, "fw1")

    def test_build_vhosts_con2(self):
        components = [{"type": "classifier_mac",
                       "name": "cls2",
                       "rx_port": ["phy:1"],
                       "tx_port": ["vhost:1"]},
                      {"type": "merge",
                       "name": "merge2",
                       "rx_port": ["vhost:1"],
                       "tx_port": ["phy:1"]}]
        self.spp_vf.build_vhosts(components)
        vhost = self.spp_vf.vhostusers[1]
        self.assertEqual(vhost.name, "vhost:1")
        self.assertEqual(vhost.del_vlan_port, "vhost:1")
        self.assertEqual(vhost.del_vlan_comp, "cls2")
        self.assertEqual(vhost.add_vlan_port, "vhost:1")
        self.assertEqual(vhost.add_vlan_comp, "merge2")
        self.assertEqual(vhost.dst_comp, None)
        self.assertEqual(vhost.in_ring, None)
        self.assertEqual(vhost.in_comp, None)
        self.assertEqual(vhost.out_ring, None)
        self.assertEqual(vhost.out_comp, None)

    def test_init_vhost_mac_address_con1(self):
        info = {"classifier_table": [{"type": "mac",
                                      "port": "ring:12",
                                      "value": "12:ab:34:cd:56:ef"}]}
        self.spp_vf.info = info
        self.spp_vf.vhostusers[0] = mock.Mock()
        self.spp_vf.vhostusers[0].del_vlan_port = "ring:12"
        self.spp_vf.init_vhost_mac_address()

        self.assertEqual(self.spp_vf.vhostusers[0].mac_address,
                         '12:ab:34:cd:56:ef')

    def test_init_vhost_mac_address_con2(self):
        info = {"classifier_table": [{"type": "vlan",
                                      "port": "ring:12",
                                      "value": "100/12:ab:34:cd:56:ef"}]}
        self.spp_vf.info = info
        self.spp_vf.vhostusers[0] = mock.Mock()
        self.spp_vf.vhostusers[0].del_vlan_port = "ring:12"
        self.spp_vf.init_vhost_mac_address()

        self.assertEqual(self.spp_vf.vhostusers[0].mac_address,
                         '12:ab:34:cd:56:ef')


class SppMirrorTestCase(base.BaseTestCase):

    def setUp(self):
        super(SppMirrorTestCase, self).setUp()
        self.spp_mirror = spp_agent.SppMirror(1, '127.0.0.1', 7778)

    @mock.patch('networking_spp.agent.spp_api.SppVfApiCommon.get_status')
    @mock.patch('networking_spp.agent.spp_api.SppVfApiCommon.make_component')
    def test_init_components(self, m_mk_comp, m_get):
        self.spp_mirror.info = {"components": [{"core": 2,
                                                "type": "forward",
                                                "name": "fw1",
                                                "ports": [7777, 7778]},
                                               {"core": 2,
                                                "type": "unuse",
                                                "name": "fw3",
                                                "ports": [7777, 7778]},
                                               {"core": 2,
                                                "type": "forward",
                                                "name": "fw4",
                                                "ports": [7777, 7778]}
                                               ]}
        components = [{"core": 3,
                       "type": "forward",
                       "name": "fw5",
                       "ports": [7777, 7778]}]

        self.spp_mirror.init_components(components)
        mirror = spp_agent.Mirror("mirror_0", [7777, 7778], self.spp_mirror)
        self.assertEqual(m_mk_comp.call_count, 1)
        m_mk_comp.assert_called_with('mirror_0', 3, 'mirror')
        self.assertEqual(len(self.spp_mirror.mirrors), 1)
        self.assertEqual(self.spp_mirror.mirrors[0].comp, mirror.comp)
        self.assertEqual(self.spp_mirror.mirrors[0].proc, mirror.proc)
        self.assertEqual(self.spp_mirror.mirrors[0].ring_b, mirror.ring_b)
        self.assertEqual(self.spp_mirror.mirrors[0].ring_b, mirror.ring_b)


class SppAgentTestCase(base.BaseTestCase):

    def setUp(self):
        super(SppAgentTestCase, self).setUp()
        self.sec_id = 1
        self.vhost_id = 2
        self.conf = mock.Mock()
        self.agent = self._get_agent()

    @mock.patch('networking_spp.agent.spp_agent.SppMirror')
    @mock.patch('networking_spp.agent.spp_agent.SppAgent.'
                'get_spp_configuration')
    @mock.patch('networking_spp.agent.spp_agent.SppVf')
    @mock.patch('networking_spp.common.etcd_client.EtcdClient')
    @mock.patch('networking_spp.agent.spp_agent.SppAgent._report_state')
    @mock.patch('networking_spp.agent.spp_agent.eventlet')
    def _get_agent(self, a, b, c, d, e, f):
        return spp_agent.SppAgent(self.conf)

    def test_get_spp_configuration(self):
        # conditions
        self.agent.host = 'host1'
        key = '/spp/openstack/configuration/' + self.agent.host
        value = {key: '1'}
        self.agent.etcd.get.return_value = json.dumps(value)
        ret = self.agent.get_spp_configuration()

        self.agent.etcd.get.assert_called_with(key)
        self.assertEqual(ret, value)

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

    @mock.patch('networking_spp.agent.spp_agent.SppAgent._unplug_tap_port')
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
                         m_bind_port_key,
                         m_unplug_tap_port):

        # conditions
        port_id = 111
        vhost_id = 1
        mac = '12:ab:34:cd:56:ef'
        self.agent.host = 'host'
        vhostuser = mock.Mock()
        vhostuser.phys_net = 'phy_net'
        self.agent.vhostusers = {1: vhostuser}
        m_vhost_key.return_value = 'key'
        self.agent.mirror = True

        self.agent._unplug_port(port_id, vhost_id, mac, None)
        m_unplug_tap_port.assert_called_with(port_id)
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

    @mock.patch('networking_spp.agent.spp_agent.SppAgent._do_tap_plug_unplug')
    @mock.patch('networking_spp.common.etcd_key.action_host_prefix')
    @mock.patch('networking_spp.agent.spp_agent.SppAgent._do_plug_unplug')
    def test_recover(self, m_do, m_prefix, m_tap):
        # conditions to exec if statement and for statement twice
        m_prefix.return_value = '/aa/bb/'
        self.agent.etcd.get_prefix.return_value = [('/aa/bb/123', 'plug'),
                                                   ('/aa/bb/321', 'unplug')
                                                   ]
        self.agent.recover()
        self.assertEqual(m_do.call_args_list[0][0][0], '123')
        self.assertEqual(m_do.call_args_list[1][0][0], '321')
        self.assertEqual(m_do.call_count, 2)
        self.assertEqual(m_tap.call_count, 2)

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

    @mock.patch('networking_spp.common.etcd_key.bind_port_key')
    def test_port_id_to_vhost(self, m_bind_port_key):
        port_id = 111
        value = {'vhost_id': 0}
        self.agent.vhostusers = {0: 'vhost'}
        self.agent.etcd.get.return_value = json.dumps(value)
        self.assertEqual(self.agent._port_id_to_vhost(port_id), 'vhost')

    def test_ring_add(self):
        proc = mock.Mock()
        proc.port_exist.return_value = False
        self.agent._ring_add(proc, 'ring', 'direction', 'comp')
        proc.port_add.assert_called_with('ring', 'direction', 'comp')

    def test_ring_del(self):
        proc = mock.Mock()
        proc.port_exist.return_value = True
        self.agent._ring_del(proc, 'ring', 'direction', 'comp')
        proc.port_del.assert_called_with('ring', 'direction', 'comp')

    def test_attach_ring(self):
        self.agent._ring_add = mock.Mock()
        self.agent._attach_ring('r', 'rx_p', 'rx_c', 'tx_p', 'tx_c')
        self.assertEqual(self.agent._ring_add.call_count, 2)

    def test_detach_ring(self):
        self.agent._ring_del = mock.Mock()
        self.agent._detach_ring('r', 'rx_p', 'rx_c', 'tx_p', 'tx_c')
        self.assertEqual(self.agent._ring_del.call_count, 2)

    def test_change_connection(self):
        self.agent._ring_add = mock.Mock()
        self.agent._ring_del = mock.Mock()
        self.agent._change_connection('r', 'dir', 'd_p', 'd_c', 'a_p', 'a_c')
        self.agent._ring_del.assert_called_with('d_p', 'r', 'dir', 'd_c')
        self.agent._ring_add.assert_called_with('a_p', 'r', 'dir', 'a_c')

    def test_construct_tap_in(self):
        self.agent._attach_ring = mock.Mock()
        self.agent._change_connection = mock.Mock()
        mirror = mock.Mock()
        d_vhost = mock.Mock()
        s_vhost = mock.Mock()
        self.agent._construct_tap_in(mirror, d_vhost, s_vhost)
        self.assertEqual(self.agent._attach_ring.call_count, 2)
        self.assertEqual(self.agent._change_connection.call_count, 1)

    def test_destruct_tap_in(self):
        self.agent._detach_ring = mock.Mock()
        self.agent._change_connection = mock.Mock()
        mirror = mock.Mock()
        d_vhost = mock.Mock()
        s_vhost = mock.Mock()
        self.agent._destruct_tap_in(mirror, d_vhost, s_vhost)
        self.assertEqual(self.agent._detach_ring.call_count, 2)
        self.assertEqual(self.agent._change_connection.call_count, 1)

    def test_construct_tap_out(self):
        self.agent._attach_ring = mock.Mock()
        self.agent._change_connection = mock.Mock()
        mirror = mock.Mock()
        d_vhost = mock.Mock()
        s_vhost = mock.Mock()
        self.agent._construct_tap_out(mirror, d_vhost, s_vhost)
        self.assertEqual(self.agent._attach_ring.call_count, 2)
        self.assertEqual(self.agent._change_connection.call_count, 1)

    def test_destruct_tap_out(self):
        self.agent._detach_ring = mock.Mock()
        self.agent._change_connection = mock.Mock()
        mirror = mock.Mock()
        d_vhost = mock.Mock()
        s_vhost = mock.Mock()
        self.agent._destruct_tap_out(mirror, d_vhost, s_vhost)
        self.assertEqual(self.agent._detach_ring.call_count, 2)
        self.assertEqual(self.agent._change_connection.call_count, 1)

    @mock.patch('networking_spp.common.etcd_key.tap_status_key')
    def test_plug_tap(self, m_tap_status_key):
        self.agent._construct_tap_in = mock.Mock()
        self.agent._construct_tap_out = mock.Mock()
        mirror_in = mock.Mock()
        mirror_out = mock.Mock()
        m_tap_status_key.return_value = 'key'
        self.agent.etcd.put = mock.Mock()
        self.agent.host = 'host'
        self.agent._plug_tap(1, mirror_in, mirror_out, 'd_vhost', 's_vhost')
        self.assertEqual(self.agent._construct_tap_in.call_count, 1)
        self.assertEqual(self.agent._construct_tap_out.call_count, 1)
        m_tap_status_key.assert_called_with('host', 1)
        self.agent.etcd.put.assert_called_with('key', 'up')

    @mock.patch('networking_spp.common.etcd_key.mirror_key')
    @mock.patch('networking_spp.common.etcd_key.tap_info_key')
    @mock.patch('networking_spp.common.etcd_key.tap_action_key')
    @mock.patch('networking_spp.common.etcd_key.tap_status_key')
    def test_unplug_tap(self,
                        m_tap_status_key,
                        m_tap_action_key,
                        m_tap_info_key,
                        m_mirror_key):
        self.agent._destruct_tap_in = mock.Mock()
        self.agent._destruct_tap_out = mock.Mock()
        mirror_in = mock.Mock()
        mirror_out = mock.Mock()
        m_tap_status_key.return_value = 'key1'
        m_tap_action_key.return_value = 'key2'
        m_tap_info_key.return_value = 'key3'
        m_mirror_key.return_value = 'key4'
        keys = ['key3', 'key2', 'key1']
        self.agent.etcd.put = mock.Mock()
        self.agent.etcd.delete = mock.Mock()
        self.agent.host = 'host'
        self.agent._unplug_tap(1, mirror_in, mirror_out, 'd_vhost', 's_vhost')
        self.assertEqual(self.agent._destruct_tap_in.call_count, 1)
        self.assertEqual(self.agent._destruct_tap_out.call_count, 1)

        for i in range(2):
            args = self.agent.etcd.put.call_args_list[i]
            self.assertEqual(args[0], ('key4', 'None'))

        for i in range(3):
            args, kwargs = self.agent.etcd.delete.call_args_list[i]
            self.assertEqual(args[0], keys[i])

    @mock.patch('networking_spp.common.etcd_key.tap_info_key')
    def test_do_tap_plug_unplug_con1(self, m_tap_info_key):
        # conditions to exec the 1st if statement and make it return None
        tap_flow_id = 3
        self.agent.etcd.get.return_value = None
        self.agent._port_id_to_vhost = mock.Mock()
        ret = self.agent._do_tap_plug_unplug(tap_flow_id)
        self.assertEqual(ret, None)
        self.agent._port_id_to_vhost.assert_not_called()

    @mock.patch('networking_spp.common.etcd_key.tap_info_key')
    def test_do_tap_plug_unplug_con2(self, m_tap_info_key):
        # conditions to exec the 2nd if statement and make it return None
        tap_flow_id = 3
        data = {"mirror_in": 'in',
                "mirror_out": 'out',
                "service_port": 'service',
                "source_port": 'source'}
        value = json.dumps(data)
        self.agent.etcd.get.return_value = value
        self.agent._port_id_to_vhost = mock.Mock()
        self.agent.mirror.get_status = mock.Mock()
        self.agent._port_id_to_vhost.side_effect = [None, 'source']
        ret = self.agent._do_tap_plug_unplug(tap_flow_id)
        var1 = self.agent._port_id_to_vhost.call_args_list[0][0][0]
        var2 = self.agent._port_id_to_vhost.call_args_list[1][0][0]
        self.assertEqual(var1, u'service')
        self.assertEqual(var2, u'source')
        self.assertEqual(ret, None)
        self.agent.mirror.get_stauts.assert_not_called()

    @mock.patch('networking_spp.common.etcd_key.tap_info_key')
    def test_do_tap_plug_unplug_con3(self, m_tap_info_key):
        # conditions to exec the 3rd and 4th if statement
        tap_flow_id = 3
        data = {"mirror_in": 'in',
                "mirror_out": 'out',
                "service_port": 'service',
                "source_port": 'source'}
        value = json.dumps(data)
        self.agent.etcd.get.side_effect = [value, 'plug']
        self.agent._port_id_to_vhost = mock.Mock()
        self.agent._plug_tap = mock.Mock()
        self.agent.mirror.get_status = mock.Mock()

        vf = mock.Mock()
        vf.get_status.return_value = None

        dst_vhost = mock.Mock()
        dst_vhost.vf = mock.Mock()
        dst_vhost.vf.get_status = mock.Mock()
        dst_vhost.vf.get_status.return_value = None
        src_vhost = mock.Mock()
        src_vhost.vf = mock.Mock()
        src_vhost.vf.get_status = mock.Mock()
        src_vhost.vf.get_status.return_value = None
        self.agent._port_id_to_vhost.side_effect = [dst_vhost, src_vhost]

        ret = self.agent._do_tap_plug_unplug(tap_flow_id)
        self.assertEqual(ret, None)
        src_vhost.vf.get_status.assert_called()
        self.agent._plug_tap.assert_called_with(tap_flow_id,
                                                'in',
                                                'out',
                                                dst_vhost,
                                                src_vhost)

    @mock.patch('networking_spp.common.etcd_key.tap_info_key')
    def test_do_tap_plug_unplug_con4(self, m_tap_info_key):
        # conditions to exec the 1st else statement and make it return None
        tap_flow_id = 3
        data = {"mirror_in": 'in',
                "mirror_out": 'out',
                "service_port": 'service',
                "source_port": 'source'}
        value = json.dumps(data)
        self.agent.etcd.get.side_effect = [value, 'unplug']
        self.agent._port_id_to_vhost = mock.Mock()
        self.agent._unplug_tap = mock.Mock()
        self.agent.mirror.get_status = mock.Mock()

        dst_vhost = mock.Mock()
        dst_vhost.vf = mock.Mock()
        dst_vhost.vf.get_status = mock.Mock()
        dst_vhost.vf.get_status.return_value = None
        src_vhost = mock.Mock()
        src_vhost.vf = mock.Mock()
        src_vhost.vf.get_status = mock.Mock()
        src_vhost.vf.get_status.return_value = None
        self.agent._port_id_to_vhost.side_effect = [dst_vhost, src_vhost]

        ret = self.agent._do_tap_plug_unplug(tap_flow_id)
        self.assertEqual(ret, None)
        self.agent._unplug_tap.assert_called_with(tap_flow_id,
                                                  'in',
                                                  'out',
                                                  dst_vhost,
                                                  src_vhost)

    @mock.patch('networking_spp.common.etcd_key.tap_info_host_prefix')
    def test_unplug_tap_port_con1(self, m_tap_info_host_prefix):
        # conditions to exec the 1st if statement then continue
        port_id = 4
        data = {"mirror_in": 'in',
                "mirror_out": 'out',
                "service_port": 3,
                "source_port": 5}
        value = json.dumps(data)
        m_tap_info_host_prefix.return_value = 'key'
        self.agent.etcd.get.return_value = None
        self.agent._port_id_to_vhost = mock.Mock()
        self.agent._unplug_tap = mock.Mock()
        self.agent.etcd.get_prefix = mock.Mock()
        self.agent.etcd.get_prefix.return_value = [('key8', value)]
        self.agent._unplug_tap_port(port_id)
        self.agent._port_id_to_vhost.assert_not_called()
        self.agent._unplug_tap.assert_not_called()

    @mock.patch('networking_spp.common.etcd_key.tap_info_host_prefix')
    def test_unplug_tap_port_con2(self, m_tap_info_host_prefix):
        # conditions to exec the 2nd if statement then continue
        port_id = 4
        data = {"mirror_in": 'in',
                "mirror_out": 'out',
                "service_port": 4,
                "source_port": 5}
        value = json.dumps(data)
        m_tap_info_host_prefix.return_value = 'key'
        self.agent.etcd.get.return_value = None
        self.agent._port_id_to_vhost = mock.Mock()
        self.agent._unplug_tap = mock.Mock()
        self.agent.etcd.get_prefix = mock.Mock()
        self.agent.etcd.get_prefix.return_value = [('key8', value)]
        self.agent._port_id_to_vhost.side_effect = [None, 'src_vhost']

        self.agent._unplug_tap_port(port_id)
        self.agent._unplug_tap.assert_not_called()

    @mock.patch('networking_spp.common.etcd_key.tap_info_host_prefix')
    def test_unplug_tap_port_con3(self, m_tap_info_host_prefix):
        # conditions to exec the 3nd if statement
        port_id = 4
        data = {"mirror_in": 'in',
                "mirror_out": 'out',
                "service_port": 4,
                "source_port": 5}
        value = json.dumps(data)
        m_tap_info_host_prefix.return_value = 'key'
        self.agent.etcd.get.return_value = None
        self.agent._port_id_to_vhost = mock.Mock()
        self.agent._unplug_tap = mock.Mock()
        self.agent.etcd.get_prefix = mock.Mock()
        self.agent.etcd.get_prefix.return_value = [('key8', value)]

        dst_vhost = mock.Mock()
        dst_vhost.vf = mock.Mock()
        dst_vhost.vf.get_status = mock.Mock()
        dst_vhost.vf.get_status.return_value = None
        src_vhost = mock.Mock()
        src_vhost.vf = mock.Mock()
        src_vhost.vf.get_status = mock.Mock()
        src_vhost.vf.get_status.return_value = None
        self.agent._port_id_to_vhost.side_effect = [dst_vhost, src_vhost]

        self.agent._unplug_tap_port(port_id)
        src_vhost.vf.get_status.assert_called()
        self.agent._unplug_tap.assert_called_with('8',
                                                  u'in',
                                                  u'out',
                                                  dst_vhost,
                                                  src_vhost)

    @mock.patch('networking_spp.agent.spp_agent.SppAgent._do_tap_plug_unplug')
    @mock.patch('networking_spp.common.etcd_key.tap_action_host_prefix')
    def test_tap_plug_watch_con1(self, m_prefix, m_tap):
        # conditions to exec if statement and for statement twice
        m_prefix.return_value = '/aa/bb/'
        self.agent.etcd.watch_prefix.return_value = [('/aa/bb/123', 'plug'),
                                                     ('/aa/bb/321', 'unplug')]
        self.agent.tap_plug_watch()
        self.assertEqual(m_tap.call_count, 2)
        self.assertEqual(m_tap.call_args_list[0][0][0], '123')
        self.assertEqual(m_tap.call_args_list[1][0][0], '321')

    @mock.patch('networking_spp.agent.spp_agent.SppAgent._do_tap_plug_unplug')
    @mock.patch('networking_spp.common.etcd_key.tap_action_host_prefix')
    def test_tap_plug_watch_con2(self, m_prefix, m_tap):
        # conditions to exec except statement
        m_prefix.return_value = '/aa/bb/'
        self.agent.etcd.watch_prefix.return_value = Exception
        self.agent.port_plug_watch_failed = False
        self.agent.tap_plug_watch()
        self.assertEqual(self.agent.port_plug_watch_failed, True)
