# Copyright (c) 2017 NTT
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
from neutron_lib.api.definitions import portbindings
from neutron_lib import constants
from neutron_lib import context
from neutron_lib.plugins.ml2 import api
from oslo_config import cfg
from oslo_log import log


LOG = log.getLogger(__name__)

# TODO(oda): define in common place
AGENT_TYPE_SPP = 'SPP neutron agent'
WAIT_PLUG_TIMEOUT = 20


class SppMechanismDriver(api.MechanismDriver):

    def initialize(self):
        self.context = context.get_admin_context()
        self.etcd = etcd_client.EtcdClient(cfg.CONF.spp.etcd_host,
                                           cfg.CONF.spp.etcd_port)

    def _try_to_bind(self, context, segment):
        port_id = context.current['id']
        if self.etcd.get(etcd_key.bind_port_key(context.host, port_id)):
            # check already tried to bind at first.
            return
        phys = segment[api.PHYSICAL_NETWORK]
        prefix = etcd_key.vhost_phys_prefix(context.host, phys)
        vhost_id = None
        for key, value in self.etcd.get_prefix(prefix):
            if value == 'None':
                if self.etcd.replace(key, 'None', port_id):
                    vhost_id = key[len(prefix):]
                    LOG.debug("vhost %s assigned for port %s", vhost_id,
                              port_id)
                    break
        if not vhost_id:
            LOG.warn("no vhost available for port %s", port_id)
            return

        self._add_bind_port(context, vhost_id, segment[api.SEGMENTATION_ID])
        if not self._wait_plug_port(context.host, port_id):
            return

        vif_type = 'vhostuser'
        sock_path = "/tmp/sock%s" % vhost_id
        mode = portbindings.VHOST_USER_MODE_SERVER
        vif_details = {portbindings.CAP_PORT_FILTER: False,
                       portbindings.VHOST_USER_MODE: mode,
                       portbindings.VHOST_USER_SOCKET: sock_path}
        context.set_binding(segment[api.ID], vif_type, vif_details,
                            status=constants.PORT_STATUS_ACTIVE)

    def _spp_agent_alive(self, context):
        agents = context.host_agents(AGENT_TYPE_SPP)
        if agents:
            return agents[0]['alive']
        return False

    def bind_port(self, context):
        agent_conf = self.etcd.get(etcd_key.configuration_key(context.host))
        if not agent_conf:
            # spp is not configured on the host
            return
        agent_conf = json.loads(agent_conf)
        phys_nets = [conf['physical_network'] for conf in agent_conf]
        if not self._spp_agent_alive(context):
            LOG.warn("spp_agent of %s down", context.host)
            return

        for segment in context.segments_to_bind:
            if (segment[api.NETWORK_TYPE] in [constants.TYPE_FLAT,
                                              constants.TYPE_VLAN]
                    and segment[api.PHYSICAL_NETWORK] in phys_nets):
                self._try_to_bind(context, segment)
                return

    def _add_bind_port(self, context, vhost_id, vlan_id):
        port = context.current
        value = {'mac_address': port['mac_address'], 'vhost_id': int(vhost_id)}
        if vlan_id is not None:
            value['vlan_id'] = vlan_id
        value = json.dumps(value)
        key = etcd_key.bind_port_key(context.host, port['id'])
        self.etcd.put(key, value)
        key = etcd_key.action_key(context.host, port['id'])
        self.etcd.put(key, "plug")

    def _wait_plug_port(self, host, port_id):
        key = etcd_key.port_status_key(host, port_id)
        k, v = self.etcd.watch_once(key, timeout=WAIT_PLUG_TIMEOUT)
        if k and v == "up":
            LOG.debug("port %s plug done.", port_id)
            return True

    def _unplug_port(self, host, port_id):
        key = etcd_key.action_key(host, port_id)
        value = self.etcd.get(key)
        if value:
            self.etcd.put(key, "unplug")

    def update_port_postcommit(self, context):
        if (context.original_host and not context.host
                and context.original_vif_type in ('vhostuser',
                                                  'binding_failed')):
            self._unplug_port(context.original_host, context.current['id'])

    def delete_port_postcommit(self, context):
        if (context.host
                and context.vif_type in ('vhostuser', 'binding_failed')):
            self._unplug_port(context.host, context.current['id'])
