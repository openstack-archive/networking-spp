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

from oslo_config import cfg

from networking_spp._i18n import _
from neutron.conf.agent import common


spp_opts = [
    cfg.IntOpt('primary_sock_port', default=5555,
               help=_("SPP primary socket port number")),
    cfg.IntOpt('secondary_sock_port', default=6666,
               help=_("SPP secondary socket port number")),
]


cfg.CONF.register_opts(spp_opts, 'spp')
common.register_agent_state_opts_helper(cfg.CONF)
