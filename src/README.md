# Manila Ganesha

This charm provides Ganesha with CephFS as a storage backend for Manila,
OpenStack's shared filesystem service.

## Usage

Manila (charm 'manila') and this 'manila-ganesha' charm rely on services
provided by the following charms: 'percona-cluster' (MySQL), 'rabbitmq-server',
and 'keystone'. A charmed CephFS solution is also needed for the backend:
'ceph-fs' ('ceph-mon' is typically already included with OpenStack). High
availability is a separate topic.

## Spaces

This charm can optionally dedicate a provider's physical network to serving
Ganesha NFS shares. It does so through its support for Juju spaces. The charm
uses a space called 'tenant-storage'.

## Deployment

One way to deploy Manila Ganesha is to use a bundle overlay when deploying
OpenStack via a bundle:

    juju deploy ./base.yaml --overlay ./manila-ganesha-overlay.yaml

See appendix [Manila Ganesha: Ceph-backed Shared Filesystem
Service][cdg-appendix-q] in the OpenStack [Charms Deployment Guide][cdg] to see
what such an overlay may look like as well as for more general information on
using Manila Ganesha with charmed OpenStack.

## High Availability ##

This charm supports active/passive HA when deployed in a cluster with the
hacluster charm. This is done by co-locating manila-share and nfs-ganesha
systemd services on the same unit, and ensuring that those services are
running only on the master unit with the VIP. Once an HA deployment is
complete, pacemaker will ensure that only one unit is running the services.

If a second unit starts the services while the first is connected to CephFS,
the first will be evicted and its session state corrupted.

Any restarts of manila-ganesha services that aren't controlled by the
charm or pacemaker can result in evicted sessions.

## Bugs

Please report bugs on [Launchpad][lp-bugs-charm-manila-ganesha].

For general charm questions refer to the OpenStack [Charm Guide][cg].

<!-- LINKS -->

[cg]: https://docs.openstack.org/charm-guide
[cdg]: https://docs.openstack.org/project-deploy-guide/charm-deployment-guide
[cdg-appendix-q]: https://docs.openstack.org/project-deploy-guide/charm-deployment-guide/latest/app-manila-ganesha.html
[lp-bugs-charm-manila-ganesha]: https://bugs.launchpad.net/charm-manila-ganesha/+filebug
