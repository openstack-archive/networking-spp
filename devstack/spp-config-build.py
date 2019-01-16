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


import etcd3
import json
import os
import sys
import yaml

SPP_ROOT = "/spp/openstack/"


def config_path(host):
    return SPP_ROOT + "configuration/" + host


def vhost_path(host, phys_net, vhost):
    return SPP_ROOT + "vhost/%s/%s/%d" % (host, phys_net, vhost)


def mirror_path(host, mirror_id):
    return SPP_ROOT + "mirror/%s/%d" % (host, mirror_id)


def get_cores(core_mask):
    mask = int(core_mask, base=16)
    cores = []
    for i in range(32):
        if mask & (1 << i):
            cores.append(i)
    cores.pop(0)
    return cores


# port name conventions
def _nic_port(sec_id):
    return "phy:%d" % (sec_id - 1)


def _vhost_port(vhost_id):
    return "vhost:%d" % vhost_id


def _rx_ring_port(vhost_id):
    return "ring:%d" % (vhost_id * 2)


def _tx_ring_port(vhost_id):
    return "ring:%d" % (vhost_id * 2 + 1)


def conf_components(sec_id, start_vhost_id, num_vhost, cores):
    components = []
    tx_port = []
    rx_port = []
    for vhost_id in range(start_vhost_id, start_vhost_id + num_vhost):
        components.append({"core": cores.pop(0),
                           "type": "forward",
                           "name": "forward_%d_tx" % vhost_id,
                           "rx_port": [_rx_ring_port(vhost_id)],
                           "tx_port": [_vhost_port(vhost_id)]})
        components.append({"core": cores.pop(0),
                           "type": "forward",
                           "name": "forward_%d_rx" % vhost_id,
                           "rx_port": [_vhost_port(vhost_id)],
                           "tx_port": [_tx_ring_port(vhost_id)]})

        tx_port.append(_rx_ring_port(vhost_id))
        rx_port.append(_tx_ring_port(vhost_id))

    components.append({"core": cores.pop(0),
                       "type": "classifier_mac",
                       "name": "classifier",
                       "rx_port": [_nic_port(sec_id)],
                       "tx_port": tx_port})
    components.append({"core": cores.pop(0),
                       "type": "merge",
                       "name": "merger",
                       "rx_port": rx_port,
                       "tx_port": [_nic_port(sec_id)]})
    return components


def mirror_components(num_vhost, num_mirror, cores):
    ring_id = num_vhost * 2
    components = []
    for i in range(num_mirror):
        components.append({"core": cores.pop(0),
                           "ports": ["ring:%d" % ring_id,
                                     "ring:%d" % (ring_id + 1)]})
        ring_id += 2
    return components


def main():
    dpdk_port_mappings = os.environ.get("DPDK_PORT_MAPPINGS")
    host = os.environ.get("SPP_HOST")
    etcd_host = os.environ.get("ETCD_HOST")
    etcd_port = os.environ.get("ETCD_PORT")
    if (dpdk_port_mappings is None or host is None or
            etcd_host is None or etcd_port is None):
        print("DPDK_PORT_MAPPINGS, SPP_HOST, ETCD_HOST and ETCD_PORT"
              " must be defined.")
        return 1
    component_conf = os.environ.get("SPP_COMPONENT_CONF")
    spp_mirror = os.environ.get("SPP_MIRROR")

    def_vfs = []
    def_mirror = {}
    if component_conf:
        with open(component_conf, 'r') as f:
            def_confs = yaml.load(f)
            def_vfs = def_confs['vf']
            if spp_mirror:
                def_mirror = def_confs['mirror']

    vfs = []
    sec_id = 1
    vhost_id = 0
    for map in dpdk_port_mappings.split(','):
        pci, phys, num_vhost, core_mask = map.split('#')
        num_vhost = int(num_vhost)
        cores = get_cores(core_mask)
        if def_vfs:
            components = def_vfs[sec_id - 1]['components']
        else:
            components = conf_components(sec_id, vhost_id, num_vhost, cores)
        vf = {'physical_network': phys, 'pci_address': pci,
              'num_vhost': num_vhost, 'core_mask': core_mask,
              'components': components}
        vfs.append(vf)
        sec_id += 1
        vhost_id += num_vhost

    host_conf = {'vf': vfs}
    if spp_mirror:
        if def_mirror:
            mirror = def_mirror
        else:
            num_mirror, core_mask = spp_mirror.split('#')
            num_mirror = int(num_mirror)
            cores = get_cores(core_mask)
            mirror = mirror_components(vhost_id, num_mirror, cores)
        host_conf['mirror'] = mirror

    etcd = etcd3.client(etcd_host, etcd_port)
    etcd.put(config_path(host), json.dumps(host_conf))

    num = 0
    for vf in vfs:
        phys = vf['physical_network']
        for i in range(vf['num_vhost']):
            etcd.put(vhost_path(host, phys, num), 'None')
            num += 1

    if spp_mirror:
        for i in range(len(mirror)):
            etcd.put(mirror_path(host, i), 'None')


if __name__ == "__main__":
    sys.exit(main())
