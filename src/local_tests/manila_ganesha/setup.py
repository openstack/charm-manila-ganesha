import logging
import zaza.openstack.utilities.openstack as openstack_utils

from manilaclient import client as manilaclient

def noop():
    """Run setup."""
    logging.info('OK')

def setup_ganesha_share_type(manila_client=None):
    if manila_client is None:
        keystone_session = openstack_utils.get_overcloud_keystone_session()
        manila_client = manilaclient.Client(
            session=keystone_session, client_version='2')

    manila_client.share_types.create(
        name="cephfsnfstype", spec_driver_handles_share_servers=False,
        extra_specs={
            'vendor_name': 'Ceph',
            'storage_protocol': 'NFS',
            'snapshot_support': False,
        })
