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
import sys

SPP_ROOT = "/spp/openstack/"


def config_path(host):
    return SPP_ROOT + "configuration/" + host


def vhost_path(host, phys_net, vhost):
    return SPP_ROOT + "vhost/%s/%s/%d" % (host, phys_net, vhost)


def main():
    if len(sys.argv) < 5:
        print("usage: spp-config-build dpdk_port_mappings"
              " host etcd_host etcd_port")
        return 1
    dpdk_port_mappings = sys.argv[1]
    host = sys.argv[2]
    etcd_host = sys.argv[3]
    etcd_port = sys.argv[4]

    confs = []
    for map in dpdk_port_mappings.split(','):
        pci, phys, num, core_mask = map.split('#')
        conf = {'physical_network': phys, 'pci_address': pci,
                'num_vhost': int(num), 'core_mask': core_mask}
        confs.append(conf)

    etcd = etcd3.client(etcd_host, etcd_port)
    etcd.put(config_path(host), json.dumps(confs))

    num = 0
    for conf in confs:
        phys = conf['physical_network']
        for i in range(conf['num_vhost']):
            etcd.put(vhost_path(host, phys, num), 'None')
            num += 1


if __name__ == "__main__":
    sys.exit(main())
