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

from networking_spp.mech_driver import mech_spp
from neutron.tests import base
from neutron_lib.api.definitions import portbindings
from neutron_lib import constants
from neutron_lib.plugins.ml2 import api


class SppMechanismTestCase(base.BaseTestCase):

    def setUp(self):
        super(SppMechanismTestCase, self).setUp()
        self.driver = mech_spp.SppMechanismDriver()
        self.driver.etcd = mock.Mock()
        self.context = mock.Mock()

    @mock.patch('networking_spp.mech_driver.mech_spp.'
                'SppMechanismDriver._spp_agent_alive')
    def test_bind_port_agent_conf(self, mocked_spp_agent_alive):
        self.driver.etcd.get.return_value = None
        self.driver.bind_port(self.context)
        mocked_spp_agent_alive.aseert_not_called()

    @mock.patch('networking_spp.mech_driver.mech_spp.'
                'LOG.warn')
    def test_bind_port_spp_agent_alive(self, mocked_warn):
        agent_conf = [{'physical_network': 'phy_net'}]
        self.driver.etcd.get.return_value = json.dumps(agent_conf)
        self.context.host_agents.return_value = []
        self.driver.bind_port(self.context)
        mocked_warn.aseert_called()

    @mock.patch('networking_spp.mech_driver.mech_spp.'
                'SppMechanismDriver._spp_agent_alive')
    @mock.patch('networking_spp.mech_driver.mech_spp.'
                'SppMechanismDriver._try_to_bind')
    def test_bind_port_call_try_to_bind(self, mocked_try_to_bind,
                                        mocked_spp_agent_alive):
        # conditions to call _try_to_bind
        agent_conf = [{'physical_network': 'phy_net'}]
        self.driver.etcd.get.return_value = json.dumps(agent_conf)
        mocked_spp_agent_alive.return_value = True
        segment = {api.NETWORK_TYPE: constants.TYPE_FLAT,
                   api.PHYSICAL_NETWORK: 'phy_net'}
        self.context.segments_to_bind = [segment]
        self.driver.bind_port(self.context)
        mocked_try_to_bind.aseert_called()

    @mock.patch('networking_spp.mech_driver.mech_spp.'
                'SppMechanismDriver._spp_agent_alive')
    @mock.patch('networking_spp.mech_driver.mech_spp.'
                'SppMechanismDriver._try_to_bind')
    def test_bind_port_call_try_to_bind_vlan(self, mocked_try_to_bind,
                                             mocked_spp_agent_alive):
        # conditions to call _try_to_bind
        agent_conf = [{'physical_network': 'phy_net'}]
        self.driver.etcd.get.return_value = json.dumps(agent_conf)
        mocked_spp_agent_alive.return_value = True
        segment = {api.NETWORK_TYPE: constants.TYPE_VLAN,
                   api.PHYSICAL_NETWORK: 'phy_net'}
        self.context.segments_to_bind = [segment]
        self.driver.bind_port(self.context)
        mocked_try_to_bind.aseert_called()

    @mock.patch('networking_spp.mech_driver.mech_spp.'
                'SppMechanismDriver._spp_agent_alive')
    @mock.patch('networking_spp.mech_driver.mech_spp.'
                'SppMechanismDriver._try_to_bind')
    def test_bind_port_not_call_try_to_bind(self, mocked_try_to_bind,
                                            mocked_spp_agent_alive):
        # conditions not to call _try_to_bind
        agent_conf = []
        self.driver.etcd.get.return_value = json.dumps(agent_conf)
        mocked_spp_agent_alive.return_value = True
        segment = {api.NETWORK_TYPE: 'value', api.PHYSICAL_NETWORK: 'value'}
        self.context.segments_to_bind = [segment]
        self.driver.bind_port(self.context)
        mocked_try_to_bind.aseert_not_called()

    @mock.patch('networking_spp.mech_driver.mech_spp.'
                'SppMechanismDriver._unplug_port')
    def test_update_port_postcommit_con1(self, mocked_unplug_port):
        # conditions to call _unplug_port
        self.context.original_host = True
        self.context.original_vif_type = 'vhostuser'
        self.context.host = ''
        self.context.current = {'id': 'value'}
        self.context.vif_type = 'unbound'

        self.driver.update_port_postcommit(self.context)
        mocked_unplug_port.assert_called()

    @mock.patch('networking_spp.mech_driver.mech_spp.'
                'SppMechanismDriver._unplug_port')
    def test_update_port_postcommit_con2(self, mocked_unplug_port):
        # conditions not to call _unplug_port
        self.context.original_host = None
        self.context.original_vif_type = ''
        self.context.host = ''
        self.context.vif_type = 'unbound'

        self.driver.update_port_postcommit(self.context)
        mocked_unplug_port.assert_not_called()

    @mock.patch('networking_spp.mech_driver.mech_spp.'
                'SppMechanismDriver._unplug_port')
    def test_update_port_postcommit_con3(self, mocked_unplug_port):
        # conditions to call _unplug_port
        self.context.original_host = True
        self.context.original_vif_type = 'binding_failed'
        self.context.host = ''
        self.context.current = {'id': 'value'}

        self.driver.update_port_postcommit(self.context)
        mocked_unplug_port.assert_called()

    @mock.patch('networking_spp.mech_driver.mech_spp.'
                'SppMechanismDriver._unplug_port')
    def test_delete_port_postcommit_con1(self, mocked_unplug_port):
        # conditions to call _unplug_port
        self.context.host = 'host'
        self.context.vif_type = 'vhostuser'
        self.context.current = dict(id='value')

        self.driver.delete_port_postcommit(self.context)
        mocked_unplug_port.assert_called()

    @mock.patch('networking_spp.mech_driver.mech_spp.'
                'SppMechanismDriver._unplug_port')
    def test_delete_port_postcommit_con2(self, mocked_unplug_port):
        # conditions not to call _unplug_port
        self.context.host = 'host'
        self.context.vif_type = ''

        self.driver.delete_port_postcommit(self.context)
        mocked_unplug_port.assert_not_called()

    @mock.patch('networking_spp.mech_driver.mech_spp.'
                'SppMechanismDriver._unplug_port')
    def test_delete_port_postcommit_con3(self, mocked_unplug_port):
        # conditions to call _unplug_port
        self.context.host = 'host'
        self.context.vif_type = 'binding_failed'
        self.context.current = dict(id='value')

        self.driver.delete_port_postcommit(self.context)
        mocked_unplug_port.assert_called()

    def _get(self, key):
        if key:
            return key

    def _put(self, key, action):
        if key:
            return action + key

    @mock.patch('networking_spp.common.etcd_key.action_key')
    def test_unplug_port_con1(self, mocked_action_key):

        # conditions to call etcd.put
        mocked_action_key.return_value = 'key'
        self.driver.etcd.get.side_effect = self._get
        self.driver.etcd.put.side_effect = self._put
        self.driver._unplug_port('host', '1')
        self.driver.etcd.put.assert_called()

    @mock.patch('networking_spp.common.etcd_key.action_key')
    def test_unplug_port_con2(self, mocked_action_key):

        # conditions not to call etcd.put
        mocked_action_key.return_value = None
        self.driver.etcd.get.side_effect = self._get
        self.driver.etcd.put.side_effect = self._put
        self.driver._unplug_port('host', '1')
        self.driver.etcd.put.assert_not_called()

    @mock.patch('networking_spp.common.etcd_key.port_status_key')
    @mock.patch('networking_spp.mech_driver.mech_spp.LOG.debug')
    def test_wait_plug_port_con1(self, mocked_debug,
                                 mocked_port_status_key):
        # conditions to return True
        mocked_port_status_key.return_value = 'key'
        mocked_debug.return_value = None
        self.driver.etcd.watch_once.return_value = ('key', 'up')
        value = self.driver._wait_plug_port('host', '1')
        self.assertEqual(value, True)

    @mock.patch('networking_spp.common.etcd_key.port_status_key')
    def test_wait_plug_port_con2(self, mocked_port_status_key):

        # conditions to return None
        mocked_port_status_key.return_value = ''
        self.driver.etcd.watch_once.return_value = (None, None)
        value = self.driver._wait_plug_port('host', '1')
        self.assertEqual(value, None)

    @mock.patch('networking_spp.common.etcd_key.action_key')
    @mock.patch('networking_spp.common.etcd_key.bind_port_key')
    def test_add_bind_port(self, mocked_bind_port_key,
                           mocked_action_key):

        # conditions not to call etcd.put
        self.context.current = {'mac_address': '00:00:00:00:00:00',
                                'id': 'AAAABBBB'}
        self.context.host = 'host1'
        mocked_action_key.side_effect = lambda host, port: host + port
        mocked_bind_port_key.side_effect = lambda host, port: host + port
        self.driver.etcd.put.side_effect = self._put
        self.driver._add_bind_port(self.context, '1', None)
        args, w = self.driver.etcd.put.call_args
        self.assertEqual(args[0], 'host1AAAABBBB')
        self.assertEqual(self.driver.etcd.put.call_count, 2)

    @mock.patch('networking_spp.mech_driver.mech_spp.'
                'SppMechanismDriver._wait_plug_port')
    @mock.patch('networking_spp.mech_driver.mech_spp.'
                'SppMechanismDriver._add_bind_port')
    @mock.patch('networking_spp.common.etcd_key.vhost_phys_prefix')
    def test_try_to_bind(self,
                         mocked_vhost_phys_prefix,
                         mocked_add_bind_port,
                         mocked_wait_plug_port):
        # conditions to find vhost
        self.context.current = {'mac_address': '00:00:00:00:00:00',
                                'id': '5678BBBB'}
        self.context.host = 'host1'
        segment = {api.NETWORK_TYPE: constants.TYPE_FLAT,
                   api.PHYSICAL_NETWORK: 'phy1',
                   api.SEGMENTATION_ID: None,
                   api.ID: 'id'}
        mocked_vhost_phys_prefix.side_effect = \
            lambda a, b: '/x/y/%s/%s/' % (a, b)
        value = [('/x/y/host1/phy1/1', '1234AAAA'),
                 ('/x/y/host1/phy1/2', 'EEEE4444'),
                 ('/x/y/host1/phy1/3', 'None')]
        self.driver.etcd.get.return_value = None
        self.driver.etcd.get_prefix.return_value = value
        self.driver.etcd.replace.return_value = True
        mocked_wait_plug_port.return_value = True
        mocked_add_bind_port.return_value = None

        self.driver._try_to_bind(self.context, segment)
        self.context.set_binding.assert_called()

        args, wagrs = self.context.set_binding.call_args
        vif_type = args[1]
        expected_vif_type = 'vhostuser'
        self.assertEqual(vif_type, expected_vif_type)
        vif_details = args[2]
        sock_path = "/tmp/sock3"
        mode = portbindings.VHOST_USER_MODE_SERVER
        expected_vif_details = {portbindings.CAP_PORT_FILTER: False,
                                portbindings.VHOST_USER_MODE: mode,
                                portbindings.VHOST_USER_SOCKET: sock_path}
        self.assertEqual(vif_details, expected_vif_details)

    @mock.patch('networking_spp.mech_driver.mech_spp.LOG.warn')
    @mock.patch('networking_spp.common.etcd_key.vhost_phys_prefix')
    def test_try_to_bind_not_vhost(self, mocked_vhost_phys_prefix,
                                   mocked_warn):
        # conditions not to find vhost
        self.context.current = {'mac_address': '00:00:00:00:00:00',
                                'id': '5678BBBB'}
        self.context.host = 'host1'
        segment = {api.NETWORK_TYPE: constants.TYPE_FLAT,
                   api.PHYSICAL_NETWORK: 'phy1',
                   api.ID: 'id'}
        mocked_vhost_phys_prefix.side_effect = \
            lambda a, b: '/x/y/%s/%s/' % (a, b)
        value = [('/x/y/host1/phy1/1', '1234AAAA'),
                 ('/x/y/host1/phy1/2', 'EEEE4444'),
                 ('/x/y/host1/phy1/3', '99999999')]
        self.driver.etcd.get.return_value = None
        self.driver.etcd.get_prefix.return_value = value
        self.driver.etcd.replace.return_value = True

        self.driver._try_to_bind(self.context, segment)
        mocked_warn.assert_called()
