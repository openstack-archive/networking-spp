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

    def __init__(self, name, vf):
        self.name = name
        self.vf = vf
        self.phys_net = vf.phys_net
        self.mac_address = "unuse"

        # port name and component name handled for del_vlantag
        self.del_vlan_port = None
        self.del_vlan_comp = None

        # port name and component name handled for add_vlantag
        self.add_vlan_port = None
        self.add_vlan_comp = None

        # setting for taas
        # component name handled when vhost is service port
        self.dst_comp = None

        # port(ring) name and component name handled when vhost is source port
        self.in_ring = None
        self.in_comp = None
        self.out_ring = None
        self.out_comp = None


class SppVf(spp_api.SppVfApi):

    def __init__(self, sec_id, phys_net, api_ip_addr, api_port):
        super(SppVf, self).__init__(sec_id, api_ip_addr, api_port)

        self.phys_net = phys_net
        self.vhostusers = {}

    def init_components(self, components):
        self.get_status()
        self.build_vhosts(components)
        self.build_components(components)
        self.init_vhost_mac_address()

    def build_components(self, components):
        exist_comps = {}
        for comp in self.info["components"]:
            if comp["type"] != "unuse":
                exist_comps[comp["name"]] = comp

        for comp in components:
            comp_name = comp["name"]
            if comp_name not in exist_comps:
                # if component does not exist, make component and add its
                # ports according to the configuration.
                self.make_component(comp_name, comp["core"], comp["type"])
                for port in comp["tx_port"]:
                    self.port_add(port, "tx", comp_name)
                for port in comp["rx_port"]:
                    self.port_add(port, "rx", comp_name)
                continue

            # if component exists, add its ports if not added yet.
            # the complication is that wiring may be different from
            # the configuration by taas operation.
            exist_rx_port = []
            exist_tx_port = []
            for port in exist_comps[comp_name]["rx_port"]:
                exist_rx_port.append(port["port"])
            for port in exist_comps[comp_name]["tx_port"]:
                exist_tx_port.append(port["port"])

            if comp["type"] == "classifier_mac":
                # classifier_mac is not affected by taas.
                # add ports according to the configuration if not added.
                for port in comp["tx_port"]:
                    if port not in exist_tx_port:
                        self.port_add(port, "tx", comp_name)
                if not exist_rx_port:
                    port = comp["rx_port"][0]
                    self.port_add(port, "rx", comp_name)
            elif comp["type"] == "forward":
                # tx_port may differ from the configuration by taas.
                # if not added, add a port according to the configuration.
                # note that if it was under taas operation, it will be
                # recovered later.
                if not exist_tx_port:
                    port = comp["tx_port"][0]
                    self.port_add(port, "tx", comp_name)
                # rx_port is not affected by taas.
                if not exist_rx_port:
                    port = comp["rx_port"][0]
                    self.port_add(port, "rx", comp_name)
            else:  # "type" == "merge"
                # merge type is used the following two cases.
                # * forwarder of vhost: tx_port is vhost
                # * merger to physical nic: tx_port is phys
                port = comp["tx_port"][0]
                # tx_port is not affected by taas both cases.
                if not exist_tx_port:
                    self.port_add(port, "tx", comp_name)
                # rx_port
                if port.startswith("vhost"):
                    # rx_port may differ from the configuration by taas.
                    # if not added, add a port according to the configuration.
                    # note that if it was under taas operation, it will be
                    # recovered later.
                    if not exist_rx_port:
                        port = comp["rx_port"][0]
                        self.port_add(port, "rx", comp_name)
                else:  # phys
                    # this case is not affected by taas.
                    # add ports according to the configuration if not added.
                    for port in comp["rx_port"]:
                        if port not in exist_rx_port:
                            self.port_add(port, "rx", comp_name)

        # to output info after build to debug LOG.
        self.get_status()

    def build_vhosts(self, components):
        tx_port_to_comp = {}
        rx_port_to_comp = {}
        for comp in components:
            for port in comp["tx_port"]:
                tx_port_to_comp[port] = comp
            for port in comp["rx_port"]:
                rx_port_to_comp[port] = comp

        for port in tx_port_to_comp.keys():
            if_type, if_num = port.split(":")
            if if_type == "vhost":
                if_num = int(if_num)
                self.vhostusers[if_num] = Vhostuser(port, self)

        for vhost in self.vhostusers.values():
            # tx side component of vhost
            comp = tx_port_to_comp[vhost.name]
            if comp["type"] == "forward":
                # change type forward to merge for mirror(taas) support.
                # there is no problem to use merge even if taas is not used.
                comp["type"] = "merge"
            if comp["type"] == "merge":
                #                          del_vlan target
                # vhost -- tx[merge]rx -- ring -- tx[classifier]rx -- phys
                #
                vhost.del_vlan_port = comp["rx_port"][0]
                vhost.del_vlan_comp = (tx_port_to_comp[vhost.del_vlan_port]
                                       ["name"])
                # setting for taas
                vhost.dst_comp = comp["name"]
                vhost.in_comp = comp["name"]
                vhost.in_ring = vhost.del_vlan_port
            else:  # "type" == "classifier_mac"
                #   del_vlan target
                # vhost -- tx[classifier]rx -- phys
                #
                vhost.del_vlan_port = vhost.name
                vhost.del_vlan_comp = comp["name"]
                # note: taas is not supported this configuration.

            # rx side component of vhost
            comp = rx_port_to_comp[vhost.name]
            if comp["type"] == "forward":
                #                            add_vlan target
                # vhost -- rx[forward]tx -- ring -- rx[merge]tx -- phys
                #
                vhost.add_vlan_port = comp["tx_port"][0]
                vhost.add_vlan_comp = (rx_port_to_comp[vhost.add_vlan_port]
                                       ["name"])
                # setting for taas
                vhost.out_comp = comp["name"]
                vhost.out_ring = vhost.add_vlan_port
            else:  # "type" == "merge"
                #  add_vlan target
                # vhost -- rx[merge]tx -- phys
                #
                vhost.add_vlan_port = vhost.name
                vhost.add_vlan_comp = comp["name"]
                # note: taas is not supported this configuration.

    def init_vhost_mac_address(self):
        table = self.info.get("classifier_table", [])
        for vhost in self.vhostusers.values():
            for entry in table:
                if (entry["type"] in ["mac", "vlan"] and
                        entry["port"] == vhost.del_vlan_port):
                    mac_string = entry["value"]
                    if entry["type"] == "vlan":
                        _vlan_id, mac_string = mac_string.split('/')
                    # match format of neutron standard
                    mac = str(netaddr.EUI(mac_string,
                                          dialect=netaddr.mac_unix_expanded))
                    vhost.mac_address = mac


class Mirror(object):

    def __init__(self, comp, ports, proc):
        self.comp = comp
        self.proc = proc
        self.ring_a = ports[0]  # connect to service side
        self.ring_b = ports[1]  # connect to source side


class SppMirror(spp_api.SppMirrorApi):

    def __init__(self, sec_id, api_ip_addr, api_port):
        super(SppMirror, self).__init__(sec_id, api_ip_addr, api_port)

        self.mirrors = []

    def _num_to_name(self, num):
        return "mirror_%d" % num

    def init_components(self, components):
        self.get_status()

        exist_comps = {}
        for comp in self.info["components"]:
            if comp["type"] != "unuse":
                exist_comps[comp["name"]] = comp

        for i in range(len(components)):
            comp_name = self._num_to_name(i)
            if comp_name not in exist_comps:
                core_id = components[i]["core"]
                self.make_component(comp_name, core_id)
            ports = components[i]["ports"]
            self.mirrors.append(Mirror(comp_name, ports, self))


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

        self.mirror = None
        mirror_components = self.spp_configuration.get('mirror')
        if mirror_components:
            self.mirror = SppMirror(sec_id, self.api_ip_addr, self.api_port)
            self.mirror.init_components(mirror_components)

        self.plug_sem = eventlet.semaphore.Semaphore()
        self.shutdown_sem = eventlet.semaphore.Semaphore(value=0)
        self.port_plug_watch_failed = False
        eventlet.spawn_n(self.port_plug_watch)
        # to start port_plug_watch first
        eventlet.sleep(0)
        if self.mirror:
            eventlet.spawn_n(self.tap_plug_watch)
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
            vf.set_classifier_table(mac_address, vhost.del_vlan_port)
        else:
            vf.port_del(vhost.add_vlan_port, "rx", vhost.add_vlan_comp)
            vf.port_add(vhost.add_vlan_port, "rx", vhost.add_vlan_comp,
                        "add_vlantag", vlan_id)
            vf.port_del(vhost.del_vlan_port, "tx", vhost.del_vlan_comp)
            vf.port_add(vhost.del_vlan_port, "tx", vhost.del_vlan_comp,
                        "del_vlantag")
            vf.set_classifier_table_with_vlan(mac_address,
                                              vhost.del_vlan_port,
                                              vlan_id)
        vhost.mac_address = mac_address

    def clear_classifier_table(self, vhost_id, mac_address, vlan_id):
        vhost = self.vhostusers[vhost_id]
        if vhost.mac_address == "unuse":
            LOG.debug("classifier table already clear: %d", vhost_id)
            return

        vf = vhost.vf
        if vlan_id is None:
            vf.clear_classifier_table(mac_address, vhost.del_vlan_port)
        else:
            vf.port_del(vhost.add_vlan_port, "rx", vhost.add_vlan_comp)
            vf.port_add(vhost.add_vlan_port, "rx", vhost.add_vlan_comp)
            vf.port_del(vhost.del_vlan_port, "tx", vhost.del_vlan_comp)
            vf.port_add(vhost.del_vlan_port, "tx", vhost.del_vlan_comp)
            vf.clear_classifier_table_with_vlan(mac_address,
                                                vhost.del_vlan_port,
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

        if self.mirror:
            self._unplug_tap_port(port_id)

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

    def _port_id_to_vhost(self, port_id):
        key = etcd_key.bind_port_key(self.host, port_id)
        val = self.etcd.get(key)
        if val:
            data = json.loads(val)
            return self.vhostusers[data['vhost_id']]

    def _ring_add(self, proc, ring, direction, comp):
        if not proc.port_exist(ring, direction, comp):
            proc.port_add(ring, direction, comp)

    def _ring_del(self, proc, ring, direction, comp):
        if proc.port_exist(ring, direction, comp):
            proc.port_del(ring, direction, comp)

    def _attach_ring(self, ring, rx_proc, rx_comp, tx_proc, tx_comp):
        self._ring_add(rx_proc, ring, "rx", rx_comp)
        self._ring_add(tx_proc, ring, "tx", tx_comp)

    def _detach_ring(self, ring, rx_proc, rx_comp, tx_proc, tx_comp):
        self._ring_del(tx_proc, ring, "tx", tx_comp)
        self._ring_del(rx_proc, ring, "rx", rx_comp)

    def _change_connection(self, ring, direction,
                           del_proc, del_comp, add_proc, add_comp):
        self._ring_del(del_proc, ring, direction, del_comp)
        self._ring_add(add_proc, ring, direction, add_comp)

    # tap-in construction
    #
    #                       rx ---(original)
    #                    +--------+
    # dst_vhost rx --- tx|dst_comp|
    #                    +--------+ (1)attach
    #                       rx --- ring_a --- tx
    #                                       +------+
    #                                       |mirror|rx --+
    #                        (2)attach      +------+     |
    #                       rx --- ring_b --- tx         |
    #                    +--------+                      |
    # src_vhost rx --- tx|in_comp |rx ...................+-- in_ring --tx[..]
    #                    +--------+    (3)change connection
    #
    def _construct_tap_in(self, mirror, dst_vhost, src_vhost):
        self._attach_ring(mirror.ring_a,
                          dst_vhost.vf, dst_vhost.dst_comp,
                          mirror.proc, mirror.comp)
        self._attach_ring(mirror.ring_b,
                          src_vhost.vf, src_vhost.in_comp,
                          mirror.proc, mirror.comp)
        self._change_connection(src_vhost.in_ring, "rx",
                                src_vhost.vf, src_vhost.in_comp,
                                mirror.proc, mirror.comp)

    # tap-in destruction: reverse operation of construction
    def _destruct_tap_in(self, mirror, dst_vhost, src_vhost):
        self._change_connection(src_vhost.in_ring, "rx",
                                mirror.proc, mirror.comp,
                                src_vhost.vf, src_vhost.in_comp)
        self._detach_ring(mirror.ring_b,
                          src_vhost.vf, src_vhost.in_comp,
                          mirror.proc, mirror.comp)
        self._detach_ring(mirror.ring_a,
                          dst_vhost.vf, dst_vhost.dst_comp,
                          mirror.proc, mirror.comp)

    # tap-out construction
    #
    #                       rx ---(original)
    #                    +--------+
    # dst_vhost rx --- tx|dst_comp|
    #                    +--------+ (1)attach
    #                       rx --- ring_a --- tx
    #                                       +------+
    #                               +---- rx|mirror|tx --+
    #                   (3)attach ring_b    +------+     |
    #                               |                    |
    #                    +--------+ +                    |
    # src_vhost tx --- rx|out_comp|tx ...................+-- out_ring --rx[..]
    #                    +--------+    (2)change connection
    #
    def _construct_tap_out(self, mirror, dst_vhost, src_vhost):
        self._attach_ring(mirror.ring_a,
                          dst_vhost.vf, dst_vhost.dst_comp,
                          mirror.proc, mirror.comp)
        self._change_connection(src_vhost.out_ring, "tx",
                                src_vhost.vf, src_vhost.out_comp,
                                mirror.proc, mirror.comp)
        self._attach_ring(mirror.ring_b,
                          mirror.proc, mirror.comp,
                          src_vhost.vf, src_vhost.out_comp)

    # tap-out destruction: reverse operation of construction
    def _destruct_tap_out(self, mirror, dst_vhost, src_vhost):
        self._detach_ring(mirror.ring_b,
                          mirror.proc, mirror.comp,
                          src_vhost.vf, src_vhost.out_comp)
        self._change_connection(src_vhost.out_ring, "tx",
                                mirror.proc, mirror.comp,
                                src_vhost.vf, src_vhost.out_comp)
        self._detach_ring(mirror.ring_a,
                          dst_vhost.vf, dst_vhost.dst_comp,
                          mirror.proc, mirror.comp)

    def _plug_tap(self, tap_flow_id, mirror_in, mirror_out, dst_vhost,
                  src_vhost):
        if mirror_in is not None:
            self._construct_tap_in(self.mirror.mirrors[mirror_in],
                                   dst_vhost, src_vhost)

        if mirror_out is not None:
            self._construct_tap_out(self.mirror.mirrors[mirror_out],
                                    dst_vhost, src_vhost)

        key = etcd_key.tap_status_key(self.host, tap_flow_id)
        self.etcd.put(key, "up")

    def _unplug_tap(self, tap_flow_id, mirror_in, mirror_out, dst_vhost,
                    src_vhost):
        if mirror_in is not None:
            self._destruct_tap_in(self.mirror.mirrors[mirror_in],
                                  dst_vhost, src_vhost)
            key = etcd_key.mirror_key(self.host, mirror_in)
            self.etcd.put(key, 'None')

        if mirror_out is not None:
            self._destruct_tap_out(self.mirror.mirrors[mirror_out],
                                   dst_vhost, src_vhost)
            key = etcd_key.mirror_key(self.host, mirror_out)
            self.etcd.put(key, 'None')

        delete_keys = [etcd_key.tap_info_key(self.host, tap_flow_id),
                       etcd_key.tap_action_key(self.host, tap_flow_id),
                       etcd_key.tap_status_key(self.host, tap_flow_id)]
        for key in delete_keys:
            self.etcd.delete(key)

    def _do_tap_plug_unplug(self, tap_flow_id):
        with self.plug_sem:
            key = etcd_key.tap_info_key(self.host, tap_flow_id)
            value = self.etcd.get(key)
            if value is None:
                # this can happen under tap_plug_watch and recover race
                # condition.
                LOG.debug("already deleted %s", tap_flow_id)
                return
            tap_info = json.loads(value)
            mirror_in = tap_info['mirror_in']
            mirror_out = tap_info['mirror_out']
            dst_vhost = self._port_id_to_vhost(tap_info['service_port'])
            src_vhost = self._port_id_to_vhost(tap_info['source_port'])
            if dst_vhost is None or src_vhost is None:
                return
            self.mirror.get_status()
            dst_vhost.vf.get_status()
            if src_vhost.vf != dst_vhost.vf:
                src_vhost.vf.get_status()
            # get action again to get the newest value
            op = self.etcd.get(etcd_key.tap_action_key(self.host, tap_flow_id))
            if op == "plug":
                self._plug_tap(tap_flow_id, mirror_in, mirror_out,
                               dst_vhost, src_vhost)
            else:
                self._unplug_tap(tap_flow_id, mirror_in, mirror_out,
                                 dst_vhost, src_vhost)

    def _unplug_tap_port(self, port_id):
        prefix = etcd_key.tap_info_host_prefix(self.host)
        for key, value in self.etcd.get_prefix(prefix):
            tap_flow_id = key[len(prefix):]
            tap_info = json.loads(value)
            if (port_id != tap_info['service_port'] and
                    port_id != tap_info['source_port']):
                continue
            mirror_in = tap_info['mirror_in']
            mirror_out = tap_info['mirror_out']
            dst_vhost = self._port_id_to_vhost(tap_info['service_port'])
            src_vhost = self._port_id_to_vhost(tap_info['source_port'])
            if dst_vhost is None or src_vhost is None:
                continue
            self.mirror.get_status()
            dst_vhost.vf.get_status()
            if src_vhost.vf != dst_vhost.vf:
                src_vhost.vf.get_status()
            self._unplug_tap(tap_flow_id, mirror_in, mirror_out,
                             dst_vhost, src_vhost)

    def tap_plug_watch(self):
        LOG.info("SPP tap_plug_watch stated")
        prefix = etcd_key.tap_action_host_prefix(self.host)
        try:
            for key, value in self.etcd.watch_prefix(prefix):
                if value in ["plug", "unplug"]:
                    LOG.debug("SPP tap_plug_watch: %s %s", key, value)
                    tap_flow_id = key[len(prefix):]
                    self._do_tap_plug_unplug(tap_flow_id)
        except Exception as e:
            # basically operation should not be failed.
            # it may be critical error. so shutdown agent.
            LOG.error("Failed to tap plug/unplug: %s", e)
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

        prefix = etcd_key.tap_action_host_prefix(self.host)
        for key, value in self.etcd.get_prefix(prefix):
            LOG.debug("  %s: %s", key, value)
            if value in ["plug", "unplug"]:
                tap_flow_id = key[len(prefix):]
                self._do_tap_plug_unplug(tap_flow_id)

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
