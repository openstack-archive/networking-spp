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

from networking_spp.common import etcd_key
from networking_spp.service_drivers import taas
from neutron.tests import base
from neutron_lib import exceptions as n_exc


class SppTaasDriverTestCase(base.BaseTestCase):

    def setUp(self):
        super(SppTaasDriverTestCase, self).setUp()
        self.service_plugin = mock.Mock()
        self.driver = taas.SppTaasDriver(self.service_plugin)
        self.driver.etcd = mock.Mock()

    def test_create_tap_service_con1(self):
        context = mock.Mock()
        context.tap_service = {'port_id': '123'}
        context._plugin_context = mock.Mock()
        port = {'binding:host_id': 'host1'}
        self.driver.etcd.get.return_value = {'key': 'value'}
        self.driver.service_plugin._get_port_details = mock.Mock()
        self.driver.service_plugin._get_port_details.return_value = port

        self.driver.create_tap_service_postcommit(context)

        self.driver.service_plugin._get_port_details.assert_called_with(
            context._plugin_context, '123')

    def test_create_tap_service_con2(self):
        context = mock.Mock()
        context.tap_service = {'port_id': '123'}
        context._plugin_context = mock.Mock()
        port = {'binding:host_id': None}
        self.driver.etcd.get.return_value = {'key': 'value'}
        self.driver.service_plugin._get_port_details = mock.Mock()
        self.driver.service_plugin._get_port_details.return_value = port

        self.assertRaises(taas.PortNotBound,
                          self.driver.create_tap_service_postcommit, context)

    def test_create_tap_service_con3(self):
        context = mock.Mock()
        context.tap_service = {'port_id': '123'}
        context._plugin_context = mock.Mock()
        port = {'binding:host_id': 'host1'}
        self.driver.etcd.get.return_value = None
        self.driver.service_plugin._get_port_details = mock.Mock()
        self.driver.service_plugin._get_port_details.return_value = port

        self.assertRaises(taas.PortNotBound,
                          self.driver.create_tap_service_postcommit, context)

    def test_get_mirror_con1(self):
        prefix = etcd_key.mirror_prefix('host1')
        self.driver.etcd.get_prefix.return_value = [
            (prefix + "0", "tf1"), (prefix + "1", "tf2")]

        ret = self.driver._get_mirror('host1', 'tf3')

        self.assertEqual(None, ret)

    @mock.patch('networking_spp.service_drivers.taas.LOG.debug')
    def test_get_mirror_con2(self, mocked_debug):
        prefix = etcd_key.mirror_prefix('host1')
        self.driver.etcd.get_prefix.return_value = [
            (prefix + "0", "tf1"), (prefix + "1", "None")]

        ret = self.driver._get_mirror('host1', 'tf3')

        self.driver.etcd.replace.assert_called_with(prefix + "1", "None",
                                                    'tf3')
        self.assertEqual("1", ret)
        mocked_debug.assert_called()

    def test_free_mirror(self):
        self.driver._free_mirror('host1', '2')

        self.driver.etcd.put.assert_called_with(
            etcd_key.mirror_key('host1', '2'), 'None')

    def test_create_tap_flow_con1(self):
        context = mock.Mock()
        context.tap_flow = {'source_port': '123'}
        self.driver.service_plugin._get_port_details = mock.Mock()
        port = {'binding:host_id': None}
        self.driver.service_plugin._get_port_details.return_value = port

        self.assertRaises(taas.PortNotBound,
                          self.driver.create_tap_flow_postcommit, context)

    def test_create_tap_flow_con2(self):
        context = mock.Mock()
        context.tap_flow = {'source_port': '123', 'tap_service_id': 'abc'}
        self.driver.service_plugin._get_port_details = mock.Mock()
        port = {'binding:host_id': 'host1'}
        self.driver.service_plugin._get_port_details.return_value = port
        self.driver.service_plugin.get_tap_service = mock.Mock()
        ts = {'port_id': '456'}
        self.driver.service_plugin.get_tap_service.return_value = ts
        self.driver.etcd.get.side_effect = ['aaa', None]

        self.assertRaises(taas.NotSameHost,
                          self.driver.create_tap_flow_postcommit, context)

    def test_create_tap_flow_con3(self):
        context = mock.Mock()
        context.tap_flow = {'source_port': '123', 'tap_service_id': 'abc',
                            'id': 'tf1', 'direction': 'IN'}
        self.driver.service_plugin._get_port_details = mock.Mock()
        port = {'binding:host_id': 'host1'}
        self.driver.service_plugin._get_port_details.return_value = port
        self.driver.service_plugin.get_tap_service = mock.Mock()
        ts = {'port_id': '456'}
        self.driver.service_plugin.get_tap_service.return_value = ts
        self.driver.etcd.get.side_effect = ['aaa', 'aaa']
        self.driver._get_mirror = mock.Mock(return_value=None)

        self.assertRaises(taas.NoMirrorAvailable,
                          self.driver.create_tap_flow_postcommit, context)

    def test_create_tap_flow_con4(self):
        context = mock.Mock()
        context.tap_flow = {'source_port': '123', 'tap_service_id': 'abc',
                            'id': 'tf1', 'direction': 'OUT'}
        self.driver.service_plugin._get_port_details = mock.Mock()
        port = {'binding:host_id': 'host1'}
        self.driver.service_plugin._get_port_details.return_value = port
        self.driver.service_plugin.get_tap_service = mock.Mock()
        ts = {'port_id': '456'}
        self.driver.service_plugin.get_tap_service.return_value = ts
        self.driver.etcd.get.side_effect = ['aaa', 'aaa']
        self.driver._get_mirror = mock.Mock(return_value=None)

        self.assertRaises(taas.NoMirrorAvailable,
                          self.driver.create_tap_flow_postcommit, context)

    def test_create_tap_flow_con5(self):
        context = mock.Mock()
        context.tap_flow = {'source_port': '123', 'tap_service_id': 'abc',
                            'id': 'tf1', 'direction': 'BOTH'}
        self.driver.service_plugin._get_port_details = mock.Mock()
        port = {'binding:host_id': 'host1'}
        self.driver.service_plugin._get_port_details.return_value = port
        self.driver.service_plugin.get_tap_service = mock.Mock()
        ts = {'port_id': '456'}
        self.driver.service_plugin.get_tap_service.return_value = ts
        self.driver.etcd.get.side_effect = ['aaa', 'aaa']
        self.driver._get_mirror = mock.Mock()
        self.driver._get_mirror.side_effect = ['0', None]
        self.driver._free_mirror = mock.Mock()

        self.assertRaises(taas.NoMirrorAvailable,
                          self.driver.create_tap_flow_postcommit, context)
        self.driver._free_mirror.assert_called_once()

    @mock.patch('networking_spp.service_drivers.taas.LOG.debug')
    def test_create_tap_flow_con6(self, mocked_debug):
        context = mock.Mock()
        context.tap_flow = {'source_port': '123', 'tap_service_id': 'abc',
                            'id': 'tf1', 'direction': 'BOTH'}
        self.driver.service_plugin._get_port_details = mock.Mock()
        port = {'binding:host_id': 'host1'}
        self.driver.service_plugin._get_port_details.return_value = port
        self.driver.service_plugin.get_tap_service = mock.Mock()
        ts = {'port_id': '456'}
        self.driver.service_plugin.get_tap_service.return_value = ts
        self.driver.etcd.get.side_effect = ['aaa', 'aaa']
        self.driver._get_mirror = mock.Mock()
        self.driver._get_mirror.side_effect = ['0', '1']
        value = {"service_port": "456", "source_port": "123",
                 "mirror_in": 0, "mirror_out": 1}
        self.driver.etcd.watch_once = mock.Mock(return_value=('k', 'up'))

        self.driver.create_tap_flow_postcommit(context)

        k, v = self.driver.etcd.put.call_args_list[0][0]
        self.assertEqual(etcd_key.tap_info_key('host1', 'tf1'), k)
        self.assertEqual(value, json.loads(v))
        k, v = self.driver.etcd.put.call_args_list[1][0]
        self.assertEqual(etcd_key.tap_action_key('host1', 'tf1'), k)
        self.assertEqual("plug", v)
        mocked_debug.assert_called()

    @mock.patch('networking_spp.service_drivers.taas.LOG.warning')
    def test_create_tap_flow_con7(self, mocked_warning):
        context = mock.Mock()
        context.tap_flow = {'source_port': '123', 'tap_service_id': 'abc',
                            'id': 'tf1', 'direction': 'OUT'}
        self.driver.service_plugin._get_port_details = mock.Mock()
        port = {'binding:host_id': 'host1'}
        self.driver.service_plugin._get_port_details.return_value = port
        self.driver.service_plugin.get_tap_service = mock.Mock()
        ts = {'port_id': '456'}
        self.driver.service_plugin.get_tap_service.return_value = ts
        self.driver.etcd.get.side_effect = ['aaa', 'aaa']
        self.driver._get_mirror = mock.Mock(return_value='2')
        value = {"service_port": "456", "source_port": "123",
                 "mirror_in": None, "mirror_out": 2}
        self.driver.etcd.watch_once = mock.Mock(return_value=(None, None))

        self.driver.create_tap_flow_postcommit(context)

        k, v = self.driver.etcd.put.call_args_list[0][0]
        self.assertEqual(etcd_key.tap_info_key('host1', 'tf1'), k)
        self.assertEqual(value, json.loads(v))
        k, v = self.driver.etcd.put.call_args_list[1][0]
        self.assertEqual(etcd_key.tap_action_key('host1', 'tf1'), k)
        self.assertEqual("plug", v)
        mocked_warning.assert_called()

    def test_delete_tap_flow_con1(self):
        context = mock.Mock()
        context.tap_flow = {'source_port': '123', 'id': 'tf1'}
        self.driver.service_plugin._get_port_details = mock.Mock()
        port = {'binding:host_id': None}
        self.driver.service_plugin._get_port_details.return_value = port

        self.driver.delete_tap_flow_postcommit(context)

        self.driver.etcd.get.assert_not_called()

    def test_delete_tap_flow_con2(self):
        context = mock.Mock()
        context.tap_flow = {'source_port': '123', 'id': 'tf1'}
        self.driver.service_plugin._get_port_details = mock.Mock(
            side_effect=n_exc.PortNotFound(port_id="port_id"))

        self.driver.delete_tap_flow_postcommit(context)

        self.driver.etcd.get.assert_not_called()

    def test_delete_tap_flow_con3(self):
        context = mock.Mock()
        context.tap_flow = {'source_port': '123', 'id': 'tf1'}
        self.driver.service_plugin._get_port_details = mock.Mock()
        port = {'binding:host_id': 'host1'}
        self.driver.service_plugin._get_port_details.return_value = port
        self.driver.etcd.get.return_value = 'aaa'

        self.driver.delete_tap_flow_postcommit(context)

        key = etcd_key.tap_action_key('host1', 'tf1')
        self.driver.etcd.put.assert_called_with(key, "unplug")
