# Copyright 2017 NTT
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import eventlet
eventlet.monkey_patch()

import json
import netaddr
import signal
import sys

from neutron_lib.agent import topics
from neutron_lib import context
from oslo_config import cfg
from oslo_log import log as logging
from oslo_service import loopingcall

from networking_spp.agent import config  # noqa
from networking_spp.agent import spp_api
from networking_spp.common import etcd_client
from networking_spp.common import etcd_config  # noqa
from networking_spp.common import etcd_key
from neutron.agent import rpc as agent_rpc
from neutron.common import config as common_config


LOG = logging.getLogger(__name__)

AGENT_TYPE_SPP = 'SPP neutron agent'
SPP_AGENT_BINARY = 'neutron-spp-agent'


class Vhostuser(object):

    def __init__(self, vhost_id, vf):
        self.vhost_id = vhost_id
        self.vf = vf
        self.phys_net = vf.phys_net
        self.mac_address = "unuse"

        # port del/add target
        # tx/rx is component's point of view
        #
        # for del_vlantag
        self.tx_port = None
        self.tx_comp = None
        #
        # for add_vlantag
        self.rx_port = None
        self.rx_comp = None


class SppVf(spp_api.SppVfApi):

    def __init__(self, sec_id, phys_net, api_ip_addr, api_port):
        super(SppVf, self).__init__(sec_id, api_ip_addr, api_port)

        self.phys_net = phys_net
        self.vhostusers = {}

    def init_components(self, components):
        self.get_status()
        self.build_components(components)
        self.build_vhosts(components)
        self.init_vhost_mac_address()

    def build_components(self, components):
        exist_comps = {}
        for comp in self.info["components"]:
            if comp["type"] != "unuse":
                exist_comps[comp["name"]] = comp

        for comp in components:
            comp_name = comp["name"]
            core_id = comp["core"]
            exist_rx_port = []
            exist_tx_port = []
            if comp_name not in exist_comps:
                self.make_component(comp_name, core_id, comp["type"])
            else:
                for port in exist_comps[comp_name]["rx_port"]:
                    exist_rx_port.append(port["port"])
                for port in exist_comps[comp_name]["tx_port"]:
                    exist_tx_port.append(port["port"])

            for port in comp["tx_port"]:
                if port not in exist_tx_port:
                    self.port_add(port, "tx", comp_name)
            for port in comp["rx_port"]:
                if port not in exist_rx_port:
                    self.port_add(port, "rx", comp_name)

        # to output info after build to debug LOG.
        self.get_status()

    def _get_vhost(self, port):
        if_type, if_num = port.split(":")
        if if_type != "vhost":
            return None
        if_num = int(if_num)
        if if_num not in self.vhostusers:
            self.vhostusers[if_num] = Vhostuser(if_num, self)
        return self.vhostusers[if_num]

    def build_vhosts(self, components):
        port_tx = {}
        port_rx = {}
        for comp in components:
            for port in comp["tx_port"]:
                port_tx[port] = comp
            for port in comp["rx_port"]:
                port_rx[port] = comp

        for port, comp in port_tx.items():
            vhost = self._get_vhost(port)
            if vhost is None:
                continue
            if comp["type"] == "forward":
                vhost.tx_port = comp["rx_port"][0]
                vhost.tx_comp = port_tx[vhost.tx_port]["name"]
            else:
                vhost.tx_port = port
                vhost.tx_comp = comp["name"]

        for port, comp in port_rx.items():
            vhost = self._get_vhost(port)
            if vhost is None:
                continue
            vhost.rx_port = port
            vhost.rx_comp = comp["name"]

    def init_vhost_mac_address(self):
        table = self.info.get("classifier_table", [])
        for vhost in self.vhostusers.values():
            for entry in table:
                if (entry["type"] in ["mac", "vlan"] and
                        entry["port"] == vhost.tx_port):
                    mac_string = entry["value"]
                    if entry["type"] == "vlan":
                        _vlan_id, mac_string = mac_string.split('/')
                    # match format of neutron standard
                    mac = str(netaddr.EUI(mac_string,
                                          dialect=netaddr.mac_unix_expanded))
                    vhost.mac_address = mac


class SppAgent(object):

    def __init__(self, conf):

        self.conf = conf
        self.host = self.conf.host
        self.api_ip_addr = self.conf.spp.api_ip_addr
        self.api_port = self.conf.spp.api_port
        self.etcd = etcd_client.EtcdClient(self.conf.spp.etcd_host,
                                           self.conf.spp.etcd_port)
        self.spp_configuration = self.get_spp_configuration()

        self.vhostusers = {}
        sec_id = 1
        for mapping in self.spp_configuration['vf']:
            phys_net = mapping['physical_network']
            components = mapping['components']
            vf = SppVf(sec_id, phys_net, self.api_ip_addr, self.api_port)
            vf.init_components(components)
            self.vhostusers.update(vf.vhostusers)
            sec_id += 1

        self.plug_sem = eventlet.semaphore.Semaphore()
        self.shutdown_sem = eventlet.semaphore.Semaphore(value=0)
        self.port_plug_watch_failed = False
        eventlet.spawn_n(self.port_plug_watch)
        # to start port_plug_watch first
        eventlet.sleep(0)
        self.recover()
        self.start_report()

    def get_spp_configuration(self):
        value = self.etcd.get(etcd_key.configuration_key(self.host))
        mappings = json.loads(value)
        LOG.info("SPP configuration: %s", mappings)
        return mappings

    def set_classifier_table(self, vhost_id, mac_address, vlan_id):
        vhost = self.vhostusers[vhost_id]
        if vhost.mac_address == mac_address:
            LOG.debug("classifier table already set: %d: %s",
                      vhost_id, mac_address)
            return

        vf = vhost.vf
        if vlan_id is None:
            vf.set_classifier_table(mac_address, vhost.tx_port)
        else:
            vf.port_del(vhost.rx_port, "rx", vhost.rx_comp)
            vf.port_add(vhost.rx_port, "rx", vhost.rx_comp,
                        "add_vlantag", vlan_id)
            vf.port_del(vhost.tx_port, "tx", vhost.tx_comp)
            vf.port_add(vhost.tx_port, "tx", vhost.tx_comp, "del_vlantag")
            vf.set_classifier_table_with_vlan(mac_address, vhost.tx_port,
                                              vlan_id)
        vhost.mac_address = mac_address

    def clear_classifier_table(self, vhost_id, mac_address, vlan_id):
        vhost = self.vhostusers[vhost_id]
        if vhost.mac_address == "unuse":
            LOG.debug("classifier table already clear: %d", vhost_id)
            return

        vf = vhost.vf
        if vlan_id is None:
            vf.clear_classifier_table(mac_address, vhost.tx_port)
        else:
            vf.port_del(vhost.rx_port, "rx", vhost.rx_comp)
            vf.port_add(vhost.rx_port, "rx", vhost.rx_comp)
            vf.port_del(vhost.tx_port, "tx", vhost.tx_comp)
            vf.port_add(vhost.tx_port, "tx", vhost.tx_comp)
            vf.clear_classifier_table_with_vlan(mac_address, vhost.tx_port,
                                                vlan_id)
        vhost.mac_address = "unuse"

    def _plug_port(self, port_id, vhost_id, mac_address, vlan_id):
        LOG.info("plug port %s: mac: %s, vhost: %d, vlan_id: %s", port_id,
                 mac_address, vhost_id, vlan_id)

        self.set_classifier_table(vhost_id, mac_address, vlan_id)

        key = etcd_key.port_status_key(self.host, port_id)
        self.etcd.put(key, "up")

    def _unplug_port(self, port_id, vhost_id, mac_address, vlan_id):
        LOG.info("unplug port %s: mac: %s, vhost: %d, vlan_id: %s", port_id,
                 mac_address, vhost_id, vlan_id)

        self.clear_classifier_table(vhost_id, mac_address, vlan_id)

        phys_net = self.vhostusers[vhost_id].phys_net
        key = etcd_key.vhost_key(self.host, phys_net, vhost_id)
        self.etcd.replace(key, port_id, 'None')
        delete_keys = [etcd_key.bind_port_key(self.host, port_id),
                       etcd_key.action_key(self.host, port_id),
                       etcd_key.port_status_key(self.host, port_id)]
        for key in delete_keys:
            self.etcd.delete(key)

    def _do_plug_unplug(self, port_id):
        with self.plug_sem:
            value = self.etcd.get(etcd_key.bind_port_key(self.host, port_id))
            if value is None:
                # this can happen under port_plug_watch and recover race
                # condition.
                LOG.debug("already deleted %s", port_id)
                return
            data = json.loads(value)
            vhost_id = data['vhost_id']
            mac_address = data['mac_address']
            vlan_id = data.get('vlan_id')
            # get action again to get the newest value
            op = self.etcd.get(etcd_key.action_key(self.host, port_id))
            if op == "plug":
                self._plug_port(port_id, vhost_id, mac_address, vlan_id)
            else:
                self._unplug_port(port_id, vhost_id, mac_address, vlan_id)

    def port_plug_watch(self):
        LOG.info("SPP port_plug_watch stated")
        prefix = etcd_key.action_host_prefix(self.host)
        try:
            for key, value in self.etcd.watch_prefix(prefix):
                if value in ["plug", "unplug"]:
                    LOG.debug("SPP port_plug_watch: %s %s", key, value)
                    port_id = key[len(prefix):]
                    self._do_plug_unplug(port_id)
        except Exception as e:
            # basically operation should not be failed.
            # it may be critical error. so shutdown agent.
            LOG.error("Failed to plug/unplug: %s", e)
            self.port_plug_watch_failed = True
            self.shutdown_sem.release()

    def recover(self):
        LOG.debug("recover start")
        prefix = etcd_key.action_host_prefix(self.host)
        for key, value in self.etcd.get_prefix(prefix):
            LOG.debug("  %s: %s", key, value)
            if value in ["plug", "unplug"]:
                port_id = key[len(prefix):]
                self._do_plug_unplug(port_id)

    def _handle_signal(self, signum, frame):
        LOG.info("signal recieved.")
        self.shutdown_sem.release()

    def wait_shutdown(self):
        LOG.info("Agent initialized successfully, now running... ")

        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        # sleep until signal recieved
        self.shutdown_sem.acquire()

        LOG.info("Agent shutdown done")
        if self.port_plug_watch_failed:
            return 1
        else:
            return 0

    def start_report(self):
        self.state_rpc = agent_rpc.PluginReportStateAPI(topics.REPORTS)
        self.context = context.get_admin_context_without_session()
        self.agent_state = {
            'binary': SPP_AGENT_BINARY,
            'host': self.host,
            'topic': 'N/A',
            'agent_type': AGENT_TYPE_SPP,
            'start_flag': True}

        report_interval = self.conf.AGENT.report_interval
        if report_interval:
            heartbeat = loopingcall.FixedIntervalLoopingCall(
                self._report_state)
            heartbeat.start(interval=report_interval)

    def _report_state(self):
        try:
            self.state_rpc.report_state(self.context,
                                        self.agent_state)
            self.agent_state.pop('start_flag', None)
        except Exception:
            LOG.exception("Failed reporting state!")


def main():
    common_config.init(sys.argv[1:])
    common_config.setup_logging()
    try:
        agent = SppAgent(cfg.CONF)
    except Exception:
        LOG.exception("Agent Initialization Failed")
        return 1
    return agent.wait_shutdown()


if __name__ == "__main__":
    sys.exit(main())
