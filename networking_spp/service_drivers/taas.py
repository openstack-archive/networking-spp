# Copyright (c) 2018 NTT
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import json

from networking_spp.common import etcd_client
from networking_spp.common import etcd_config  # noqa
from networking_spp.common import etcd_key
from neutron_lib import exceptions as n_exc
from neutron_taas.services.taas import service_drivers as taas_service_drivers
from oslo_config import cfg
from oslo_log import helpers as log_helpers
from oslo_log import log


LOG = log.getLogger(__name__)

WAIT_TAP_TIMEOUT = 30


class PortNotBound(n_exc.BadRequest):
    message = _("Port %(port_id)s is not bound on SPP network host")


class NotSameHost(n_exc.BadRequest):
    message = _("Source port's host must be same as Service port's host")


class NoMirrorAvailable(n_exc.Conflict):
    message = _("No mirror available on the host %(host)s")


class SppTaasDriver(taas_service_drivers.TaasBaseDriver):

    def __init__(self, service_plugin):
        LOG.debug("Loading SppTaasDriver.")
        super(SppTaasDriver, self).__init__(service_plugin)
        self.etcd = etcd_client.EtcdClient(cfg.CONF.spp.etcd_host,
                                           cfg.CONF.spp.etcd_port)

    @log_helpers.log_method_call
    def create_tap_service_precommit(self, context):
        # nothing to do
        pass

    def _check_bind_port(self, host, port_id):
        if (host is None or
                self.etcd.get(etcd_key.bind_port_key(host, port_id)) is None):
            raise PortNotBound(port_id=port_id)

    @log_helpers.log_method_call
    def create_tap_service_postcommit(self, context):
        # check port bound to SPP
        port_id = context.tap_service['port_id']
        port = self.service_plugin._get_port_details(context._plugin_context,
                                                     port_id)
        self._check_bind_port(port['binding:host_id'], port_id)
        # that's all. check only at the moment.

    @log_helpers.log_method_call
    def delete_tap_service_precommit(self, context):
        # nothing to do
        pass

    @log_helpers.log_method_call
    def delete_tap_service_postcommit(self, context):
        # nothing to do
        pass

    @log_helpers.log_method_call
    def create_tap_flow_precommit(self, context):
        # nothing to do
        pass

    def _get_mirror(self, host, tf_id):
        prefix = etcd_key.mirror_prefix(host)
        mirror_id = None
        for key, value in self.etcd.get_prefix(prefix):
            if value == 'None':
                if self.etcd.replace(key, 'None', tf_id):
                    mirror_id = key[len(prefix):]
                    LOG.debug("mirror %s assigned for tap_flow %s",
                              mirror_id, tf_id)
                    break
        return mirror_id

    def _free_mirror(self, host, mirror_id):
        self.etcd.put(etcd_key.mirror_key(host, mirror_id), 'None')

    @log_helpers.log_method_call
    def create_tap_flow_postcommit(self, context):
        # check source port bound to SPP
        tf = context.tap_flow
        src_port_id = tf['source_port']
        src_port = self.service_plugin._get_port_details(
            context._plugin_context, src_port_id)
        host = src_port['binding:host_id']
        self._check_bind_port(host, src_port_id)

        # check service port bound to SPP on the same host
        ts = self.service_plugin.get_tap_service(context._plugin_context,
                                                 tf['tap_service_id'])
        svc_port_id = ts['port_id']
        if self.etcd.get(etcd_key.bind_port_key(host, svc_port_id)) is None:
            raise NotSameHost()

        # assign mirror(s)
        mirror_in = None
        mirror_out = None
        tf_id = tf['id']
        direction = tf['direction']
        if direction == 'IN' or direction == 'BOTH':
            mirror_in = self._get_mirror(host, tf_id)
            if mirror_in is None:
                raise NoMirrorAvailable(host=host)
        if direction == 'OUT' or direction == 'BOTH':
            mirror_out = self._get_mirror(host, tf_id)
            if mirror_out is None:
                if mirror_in:
                    self._free_mirror(host, mirror_in)
                raise NoMirrorAvailable(host=host)

        # request tap setup
        value = {"service_port": svc_port_id,
                 "source_port": src_port_id,
                 "mirror_in": int(mirror_in) if mirror_in else None,
                 "mirror_out": int(mirror_out) if mirror_out else None}
        key = etcd_key.tap_info_key(host, tf_id)
        self.etcd.put(key, json.dumps(value))
        key = etcd_key.tap_action_key(host, tf_id)
        self.etcd.put(key, "plug")

        # wait tap setup done
        key = etcd_key.tap_status_key(host, tf_id)
        k, v = self.etcd.watch_once(key, timeout=WAIT_TAP_TIMEOUT)
        if k and v == "up":
            LOG.debug("tap_flow %s plug done.", tf_id)
        else:
            LOG.warning("tap_flow %s plug not complete.", tf_id)
            # NOTE: if it only takes time, it may not be a problem.
            # but if there is agent's problem, user is only availble
            # to delete the tap_flow.

    @log_helpers.log_method_call
    def delete_tap_flow_precommit(self, context):
        # nothing to do
        pass

    @log_helpers.log_method_call
    def delete_tap_flow_postcommit(self, context):
        tf = context.tap_flow
        src_port_id = tf['source_port']
        host = None
        try:
            src_port = self.service_plugin._get_port_details(
                context._plugin_context, src_port_id)
            host = src_port['binding:host_id']
        except n_exc.PortNotFound:
            pass
        if host is None:
            # port is already deleted or unbound. in this case,
            # tap unplug was already done by agent. so nothing to do.
            return

        key = etcd_key.tap_action_key(host, tf['id'])
        if self.etcd.get(key) is not None:
            # NOTE: if service port is deleted or unbound, tap
            # unplug was done by agent. in this case, the key
            # has been deleted already. if key exists, request
            # unplug.
            self.etcd.put(key, "unplug")
