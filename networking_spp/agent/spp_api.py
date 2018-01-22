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

import json

from oslo_log import log as logging


LOG = logging.getLogger(__name__)


class SppVfApi(object):

    def __init__(self, spp_cm):
        self.spp_cm = spp_cm

    def _exec_command(self, sec_id, command):
        LOG.info("spp_vf(%d) command executed: %s", sec_id, command)
        res = self.spp_cm.sec_command(sec_id, command)
        ret = json.loads(res)
        result = ret["results"][0]
        if result["result"] == "error":
            msg = result["error_details"]["message"]
            raise RuntimeError("command %s error: %s" % (command, msg))
        return ret

    def get_status(self, sec_id):
        ret = self._exec_command(sec_id, "status")
        return ret["info"]

    def make_component(self, sec_id, comp_name, core_id, comp_type):
        command = ("component start {comp_name} {core_id} {comp_type}"
                   .format(**locals()))
        self._exec_command(sec_id, command)

    def port_add(self, sec_id, port, direction, comp_name,
                 op=None, vlan_id=None):
        command = ("port add {port} {direction} {comp_name}"
                   .format(**locals()))
        if op:
            command += " %s" % op
            if op == "add_vlantag":
                command += " %d 0" % vlan_id
        self._exec_command(sec_id, command)

    def port_del(self, sec_id, port, direction, comp_name):
        command = ("port del {port} {direction} {comp_name}"
                   .format(**locals()))
        self._exec_command(sec_id, command)

    def flush(self, sec_id):
        self._exec_command(sec_id, "flush")

    def cancel(self, sec_id):
        self._exec_command(sec_id, "cancel")

    def set_classifier_table(self, sec_id, mac_address, port):
        command = ("classifier_table add mac {mac_address} {port}"
                   .format(**locals()))
        self._exec_command(sec_id, command)

    def clear_classifier_table(self, sec_id, mac_address, port):
        command = ("classifier_table del mac {mac_address} {port}"
                   .format(**locals()))
        self._exec_command(sec_id, command)

    def set_classifier_table_with_vlan(self, sec_id, mac_address, port,
                                       vlan_id):
        command = ("classifier_table add vlan {vlan_id} {mac_address} {port}"
                   .format(**locals()))
        self._exec_command(sec_id, command)

    def clear_classifier_table_with_vlan(self, sec_id, mac_address, port,
                                         vlan_id):
        command = ("classifier_table del vlan {vlan_id} {mac_address} {port}"
                   .format(**locals()))
        self._exec_command(sec_id, command)
