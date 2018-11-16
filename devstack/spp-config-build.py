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

    def_confs = {}
    if component_conf:
        with open(component_conf, 'r') as f:
            def_confs = yaml.load(f)

    def_vfs = def_confs.get('vf', [])
    confs = []
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
        conf = {'physical_network': phys, 'pci_address': pci,
                'num_vhost': num_vhost, 'core_mask': core_mask,
                'components': components}
        confs.append(conf)
        sec_id += 1
        vhost_id += num_vhost

    etcd = etcd3.client(etcd_host, etcd_port)
    etcd.put(config_path(host), json.dumps({'vf': confs}))

    num = 0
    for conf in confs:
        phys = conf['physical_network']
        for i in range(conf['num_vhost']):
            etcd.put(vhost_path(host, phys, num), 'None')
            num += 1


if __name__ == "__main__":
    sys.exit(main())
