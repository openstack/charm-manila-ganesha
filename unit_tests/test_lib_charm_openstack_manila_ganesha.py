# Copyright 209 Canonical Ltd
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

import mock

import charms_openstack.test_utils as test_utils

import charm.openstack.manila_ganesha as manila_ganesha


class Helper(test_utils.PatchHelper):

    def setUp(self):
        super().setUp()
        self.patch_release(manila_ganesha.ManilaGaneshaCharm.release)


class TestManilaGaneshaCharm(Helper):

    def test_request_ceph_permissions(self):
        self.patch_object(manila_ganesha, 'send_request_if_needed')
        c = manila_ganesha.ManilaGaneshaCharm()
        ceph = mock.MagicMock()
        ceph.get_local.return_value = None
        c.request_ceph_permissions(ceph)
        ceph.set_local.assert_called_once()
        self.send_request_if_needed.assert_called_once()

    def test_access_ip_without_vip(self):
        self.patch_object(manila_ganesha, 'is_clustered')
        self.patch_object(manila_ganesha.ch_net_ip, 'get_relation_ip')
        self.patch_object(manila_ganesha.ch_net_ip, 'is_address_in_network')
        self.is_clustered.return_value = False
        self.get_relation_ip.return_value = "10.0.0.1"
        c = manila_ganesha.ManilaGaneshaCharm()
        self.assertEqual(c.access_ip, "10.0.0.1")
        self.is_clustered.assert_called_once()
        self.get_relation_ip.assert_called_once_with('tenant-storage')
        self.is_address_in_network.assert_not_called()

    def test_access_ip_with_vip(self):
        self.patch_object(manila_ganesha, 'config')
        self.patch_object(manila_ganesha, 'is_clustered')
        self.patch_object(manila_ganesha.ch_net_ip, 'get_relation_ip')
        self.patch_object(manila_ganesha.ch_net_ip, 'is_address_in_network')
        self.patch_object(manila_ganesha.ch_net_ip, 'resolve_network_cidr')
        self.config.return_value = {'vip': '10.0.0.10'}
        self.is_clustered.return_value = True
        self.get_relation_ip.return_value = "10.0.0.1"
        self.resolve_network_cidr.return_value = '10.0.0.0/24'
        c = manila_ganesha.ManilaGaneshaCharm()
        self.assertEqual(c.access_ip, "10.0.0.10")
        self.is_clustered.assert_called_once()
        self.get_relation_ip.assert_called_once_with('tenant-storage')
        self.is_address_in_network.assert_called_once_with(
            '10.0.0.0/24', '10.0.0.10')
