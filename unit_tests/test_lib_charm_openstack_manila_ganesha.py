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

from __future__ import absolute_import
from __future__ import print_function

import mock

import charms_openstack.test_utils as test_utils

import charm.openstack.manila_ganesha as manila_ganesha


class Helper(test_utils.PatchHelper):

    def setUp(self):
        super().setUp()
        self.patch_release(manila_ganesha.ManilaGaneshaCharm.release)


class TestOctaviaCharm(Helper):

    def test_request_ceph_permissions(self):
        self.patch_object(manila_ganesha, 'send_request_if_needed')
        c = manila_ganesha.ManilaGaneshaCharm()
        ceph = mock.MagicMock()
        ceph.get_local.return_value = None
        c.request_ceph_permissions(ceph)
        ceph.set_local.assert_called_once()
        self.send_request_if_needed.assert_called_once()
