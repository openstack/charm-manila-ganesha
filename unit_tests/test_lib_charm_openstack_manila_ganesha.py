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

from unittest import mock

import charms_openstack.test_utils as test_utils

import charm.openstack.manila_ganesha as manila_ganesha


class Helper(test_utils.PatchHelper):

    def setUp(self):
        super().setUp()
        self.patch_release(manila_ganesha.ManilaGaneshaCharm.release)


class TestTlsCertificatesAdapter(Helper):

    def test__resolve_file_name(self):
        self.patch('os.path.exists', name='os_path_exists')
        self.os_path_exists.return_value = False
        relation = mock.MagicMock()
        a = manila_ganesha.TlsCertificatesAdapter(relation)
        self.assertEqual(a._resolve_file_name('some-path'), None)
        self.os_path_exists.return_value = True
        self.assertEqual(a._resolve_file_name('some-path'), 'some-path')

    def test_certfile_property(self):
        relation = mock.MagicMock()
        a = manila_ganesha.TlsCertificatesAdapter(relation)
        self.patch_object(a,
                          '_resolve_file_name',
                          name='mock_resolve_file_name')
        self.mock_resolve_file_name.return_value = None
        self.assertEqual(a.certfile, None)
        self.mock_resolve_file_name.return_value = 'the-certfile'
        self.assertEqual(a.certfile, 'the-certfile')

    def test_keyfile_property(self):
        relation = mock.MagicMock()
        a = manila_ganesha.TlsCertificatesAdapter(relation)
        self.patch_object(a,
                          '_resolve_file_name',
                          name='mock_resolve_file_name')
        self.mock_resolve_file_name.return_value = None
        self.assertEqual(a.keyfile, None)
        self.mock_resolve_file_name.return_value = 'the-keyfile'
        self.assertEqual(a.certfile, 'the-keyfile')

    def test_cafile_property(self):
        relation = mock.MagicMock()
        a = manila_ganesha.TlsCertificatesAdapter(relation)
        self.patch_object(a,
                          '_resolve_file_name',
                          name='mock_resolve_file_name')
        self.mock_resolve_file_name.return_value = None
        self.assertEqual(a.cafile, None)
        self.mock_resolve_file_name.return_value = 'the-cafile'
        self.assertEqual(a.certfile, 'the-cafile')


class TestManilaGaneshaCharm(Helper):

    def test_request_ceph_permissions(self):
        c = manila_ganesha.ManilaGaneshaCharm()
        ceph = mock.MagicMock()
        ceph.get_current_request.return_value = None
        c.request_ceph_permissions(ceph)
        ceph.send_request_if_needed.assert_called_once()

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

    def test_get_client_cert_cn_sans(self):
        c = manila_ganesha.ManilaGaneshaCharm()
        self.patch_object(manila_ganesha, 'network_get')
        self.network_get.return_value = {
            'ingress-addresses': ['ip1', 'ip2', 'ip3'],
        }
        self.assertEqual(c.get_client_cert_cn_sans(), ('ip1', ['ip2', 'ip3']))
        self.network_get.assert_called_once_with('identity-service')

        def raises(*args, **kwargs):
            raise Exception('bang!')

        self.network_get.side_effect = raises
        self.patch_object(manila_ganesha, 'log')
        self.assertEqual(c.get_client_cert_cn_sans(), (None, None))
        self.log.assert_called_once()
        self.assertRegex(self.log.call_args.args[0],
                         r"^Getting ingress.*failed")

    def test_handle_changed_client_cert_files__none(self):
        # test that calling with None on all values ensures not files
        self.patch_object(manila_ganesha, 'mkdir', name='mock_mkdir')
        self.patch_object(manila_ganesha, 'path_hash', name='mock_path_hash')
        self.patch('os.path.exists', name='mock_os_path_exists')
        self.patch_object(manila_ganesha, 'log', name='mock_log')
        self.patch('os.remove', name='mock_os_remove')
        self.patch_object(manila_ganesha, 'write_file', name='mock_write_file')
        self.patch_object(manila_ganesha.relations, 'endpoint_from_flag',
                          name='mock_endpoint_from_flag')
        c = manila_ganesha.ManilaGaneshaCharm()
        self.patch_object(c,
                          'render_with_interfaces',
                          name='mock_render_with_interfaces')

        # Set up test conditions.
        self.mock_path_hash.return_value = None  # no file changes at all
        self.mock_os_path_exists.side_effect = [False, True, False]

        # call with all None.
        c.handle_changed_client_cert_files(None, None, None)

        # validate that things got called
        self.mock_os_remove.assert_called_once_with(
            manila_ganesha.MANILA_CLIENT_CERT_FILE)
        self.mock_write_file.assert_not_called()
        self.mock_endpoint_from_flag.assert_not_called()
        self.mock_render_with_interfaces.assert_not_called()

    def test_handle_changed_client_cert_files__none_os_remove_error(self):
        # test that calling with None on all values ensures not files
        self.patch_object(manila_ganesha, 'mkdir', name='mock_mkdir')
        self.patch_object(manila_ganesha, 'path_hash', name='mock_path_hash')
        self.patch('os.path.exists', name='mock_os_path_exists')
        self.patch_object(manila_ganesha, 'log', name='mock_log')
        self.patch('os.remove', name='mock_os_remove')
        self.patch_object(manila_ganesha, 'write_file', name='mock_write_file')
        self.patch_object(manila_ganesha.relations, 'endpoint_from_flag',
                          name='mock_endpoint_from_flag')
        c = manila_ganesha.ManilaGaneshaCharm()
        self.patch_object(c,
                          'render_with_interfaces',
                          name='mock_render_with_interfaces')

        # Set up test conditions.
        def raises(_path):
            if _path == manila_ganesha.MANILA_CLIENT_CERT_FILE:
                raise OSError('bang!')

        self.mock_path_hash.return_value = None  # no file changes at all
        self.mock_os_path_exists.side_effect = [True, True, False]
        self.mock_os_remove.side_effect = raises

        # call with all None.
        c.handle_changed_client_cert_files(None, None, None)

        # validate that things got called
        self.mock_os_remove.assert_has_calls([
            mock.call(manila_ganesha.MANILA_CLIENT_CA_FILE),
            mock.call(manila_ganesha.MANILA_CLIENT_CERT_FILE),
        ])
        self.assertRegex(self.mock_log.call_args.args[0],
                         r"^Path " + manila_ganesha.MANILA_CLIENT_CERT_FILE +
                         r".*deleted")
        self.mock_write_file.assert_not_called()
        self.mock_endpoint_from_flag.assert_not_called()
        self.mock_render_with_interfaces.assert_not_called()

    def test_handle_changed_client_cert_files__all(self):
        # test that calling with None on all values ensures not files
        self.patch_object(manila_ganesha, 'mkdir', name='mock_mkdir')
        self.patch_object(manila_ganesha, 'path_hash', name='mock_path_hash')
        self.patch('os.path.exists', name='mock_os_path_exists')
        self.patch_object(manila_ganesha, 'log', name='mock_log')
        self.patch('os.remove', name='mock_os_remove')
        self.patch_object(manila_ganesha, 'write_file', name='mock_write_file')
        self.patch_object(manila_ganesha.relations, 'endpoint_from_flag',
                          name='mock_endpoint_from_flag')
        c = manila_ganesha.ManilaGaneshaCharm()
        self.patch_object(c,
                          'render_with_interfaces',
                          name='mock_render_with_interfaces')

        # Set up test conditions.
        self.mock_path_hash.side_effect = [None, None, None, 'h1', 'h2', 'h3']
        self.mock_endpoint_from_flag.side_effect = [
            'e1', 'e2', 'e3', 'e4', 'e5', 'e6']

        # call with all None.
        c.handle_changed_client_cert_files('ca', 'cert', 'key')

        # validate that things got called
        self.mock_os_remove.assert_not_called()
        self.mock_write_file.assert_has_calls([
            mock.call(manila_ganesha.MANILA_CLIENT_CA_FILE, b"ca",
                      owner=c.user, group=c.group, perms=0o640),
            mock.call(manila_ganesha.MANILA_CLIENT_CERT_FILE, b"cert",
                      owner=c.user, group=c.group, perms=0o640),
            mock.call(manila_ganesha.MANILA_CLIENT_KEY_FILE, b"key",
                      owner=c.user, group=c.group, perms=0o640),
        ])
        self.mock_endpoint_from_flag.assert_has_calls([
            mock.call('ceph.available'),
            mock.call('amqp.available'),
            mock.call('manila-plugin.available'),
            mock.call('shared-db.available'),
            mock.call('identity-service.available'),
            mock.call('certificates.available'),
        ])
        self.mock_render_with_interfaces.assert_called_once_with(
            ['e1', 'e2', 'e3', 'e4', 'e5', 'e6'])

    def test_handle_changed_client_cert_files__all_not_all_endpoints(self):
        # test that calling with None on all values ensures not files
        self.patch_object(manila_ganesha, 'mkdir', name='mock_mkdir')
        self.patch_object(manila_ganesha, 'path_hash', name='mock_path_hash')
        self.patch('os.path.exists', name='mock_os_path_exists')
        self.patch_object(manila_ganesha, 'log', name='mock_log')
        self.patch('os.remove', name='mock_os_remove')
        self.patch_object(manila_ganesha, 'write_file', name='mock_write_file')
        self.patch_object(manila_ganesha.relations, 'endpoint_from_flag',
                          name='mock_endpoint_from_flag')
        c = manila_ganesha.ManilaGaneshaCharm()
        self.patch_object(c,
                          'render_with_interfaces',
                          name='mock_render_with_interfaces')

        # Set up test conditions.
        self.mock_path_hash.side_effect = [None, None, None, 'h1', 'h2', 'h3']
        self.mock_endpoint_from_flag.side_effect = [
            'e1', 'e2', 'e3', 'e4', None, 'e6']

        # call with all None.
        c.handle_changed_client_cert_files('ca', 'cert', 'key')

        # validate that things got called
        self.mock_os_remove.assert_not_called()
        self.mock_write_file.assert_has_calls([
            mock.call(manila_ganesha.MANILA_CLIENT_CA_FILE, b"ca",
                      owner=c.user, group=c.group, perms=0o640),
            mock.call(manila_ganesha.MANILA_CLIENT_CERT_FILE, b"cert",
                      owner=c.user, group=c.group, perms=0o640),
            mock.call(manila_ganesha.MANILA_CLIENT_KEY_FILE, b"key",
                      owner=c.user, group=c.group, perms=0o640),
        ])
        self.mock_endpoint_from_flag.assert_has_calls([
            mock.call('ceph.available'),
            mock.call('amqp.available'),
            mock.call('manila-plugin.available'),
            mock.call('shared-db.available'),
            mock.call('identity-service.available'),
        ])
        self.mock_render_with_interfaces.assert_not_called()
