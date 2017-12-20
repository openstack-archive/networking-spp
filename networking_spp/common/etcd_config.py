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


etcd_opts = [
    cfg.StrOpt('etcd_host', default='',
               help=_("Etcd host")),
    cfg.IntOpt('etcd_port', default=2379,
               help=_("Etcd port")),
]


cfg.CONF.register_opts(etcd_opts, 'spp')
