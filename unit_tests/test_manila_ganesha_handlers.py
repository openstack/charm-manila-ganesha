# Copyright 2018 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# import json
# import mock

# import charm.openstack.manila_ganesha as manila_ganesha
import reactive.manila_ganesha as handlers

import charms_openstack.test_utils as test_utils


class TestRegisteredHooks(test_utils.TestRegisteredHooks):

    def test_hooks(self):
        defaults = [
            'charm.installed',
            'amqp.connected',
            'shared-db.connected',
            'config.changed',
            'update-status',
            'upgrade-charm',
            'certificates.available',
        ]
        hook_set = {
            'when': {
                'ceph_connected': ('ceph.connected',),
                'setup_manila': ('manila-plugin.available',),
                'configure_ident_username': ('identity-service.connected',),
                'render_things': ('ceph.available',
                                  'amqp.available',
                                  'manila-plugin.available',
                                  'shared-db.available',
                                  'identity-service.available'),
                'cluster_connected': ('ha.connected',
                                      'ganesha-pool-configured',
                                      'config.rendered',),
                'enable_services_in_non_ha': ('config.rendered',),
            },
            'when_not': {
                'ceph_connected': ('ceph.available',),
                'configure_ident_username': ('identity-service.available',),
                'configure_ganesha': ('ganesha-pool-configured',),
                'enable_services_in_non_ha': ('ha.connected',),
            },
            'when_all': {
                'configure_ganesha': ('config.rendered',
                                      'ceph.pools.available',),
            }
        }
        # test that the hooks were registered via the
        # reactive.manila_ganesha_handlers
        self.registered_hooks_test_helper(handlers, hook_set, defaults)
