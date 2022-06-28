# Copyright (C) 2022 Canonical
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

import os
import shutil
from pathlib import Path
from glob import glob

import charmhelpers.core.hookenv as hookenv
from charmhelpers.contrib.charmsupport import nrpe

# Relative path from the root directory
PLUGINS_DIR = "files/plugins"

CHECK_SCRIPTS = [
    {
        "shortname": "nfs_conn",
        "description": "NFS server listening check.",
        "check_cmd": "/usr/local/lib/nagios/plugins/check_nfs_conn",
    },
    {
        "shortname": "nfs_exports",
        "description": "NFS exports check.",
        "check_cmd": "/usr/local/lib/nagios/plugins/check_nfs_exports",
    },
    {
        "shortname": "nfs_services",
        "description": "NFS services check.",
        "check_cmd": "/usr/local/lib/nagios/plugins/check_nfs_services",
    },
]


class CustomNRPE(nrpe.NRPE):
    # Target installation paths
    NRPE_PLUGINS_DIR = Path("/usr/local/lib/nagios/plugins")
    CROND_DIR = Path("/etc/cron.d")

    # Values are pathlib.Path objects.
    installed_plugins = set()
    installed_cronjobs = {}

    def __init__(self, hostname=None, primary=True):
        super().__init__(hostname=hostname, primary=primary)

    def install_all_custom_plugins(self):
        search_dir = Path(hookenv.charm_dir(), PLUGINS_DIR)
        plugins = glob(str(search_dir / "*"))
        for src in plugins:
            self.install_custom_plugin(src)

    def remove_all_custom_plugins(self):
        plugins = map(Path, list(CustomNRPE.installed_plugins))
        for dst in plugins:
            self.remove_custom_plugin(dst)

    def install_custom_plugin(self, src):
        try:
            dst = shutil.copy(src, CustomNRPE.NRPE_PLUGINS_DIR)
            os.chmod(dst, 0o100755)
            os.chown(dst, 0, 0)
            hookenv.log(
                f"NRPE: Successfully installed {dst}.",
                hookenv.DEBUG
            )
            CustomNRPE.installed_plugins.add(Path(dst))
        except Exception as e:
            hookenv.log(
                f"NRPE: Failed to installed {src}.",
                hookenv.ERROR
            )
            raise e
        return Path(dst)

    def remove_custom_plugin(self, dst):
        try:
            dst.unlink()
            hookenv.log(
                f"NRPE: Successfully removed {dst}.",
                hookenv.DEBUG
            )
            CustomNRPE.installed_plugins.remove(Path(dst))
        except Exception as e:
            hookenv.log(
                f"NRPE: Failed to installed {dst}.",
                hookenv.ERROR
            )
            raise e
        return Path(dst)

    def install_custom_cronjob(self, command, name):
        if name in CustomNRPE.installed_cronjobs:
            hookenv.log(
                f"NRPE: Failed to installed {name}.",
                hookenv.ERROR
            )
            raise ValueError("cron job name must be unique.")

        cronpath = f"/etc/cron.d/nagios-check_{name}"
        output_path = f"{super().homedir}/check_{name}.txt"

        cron_file = f"*/5 * * * * root {command} > {output_path}\n"

        try:
            with open(cronpath, "w") as f:
                f.write(cron_file)
                hookenv.log(
                    f"cron.d: Successfully installed {cronpath}.",
                    hookenv.DEBUG
                )
                CustomNRPE.installed_cronjobs[name] = [
                    Path(cronpath),
                    Path(output_path),
                ]
        except Exception as e:
            hookenv.log(
                f"cron.d: Failed to installed {cronpath}.",
                hookenv.ERROR
            )
            raise e

    def remove_custom_cronjob(self, name):
        try:
            for f in CustomNRPE.installed_cronjobs[name]:
                if f.exists():
                    f.unlink()
                hookenv.log(
                    f"cron.d: Successfully removed {f}.",
                    hookenv.DEBUG
                )
            CustomNRPE.installed_cronjobs.pop(name)
        except Exception as e:
            hookenv.log(
                f"cron.d: Failed to remove {name}.",
                hookenv.ERROR
            )
            raise e

    def remove_all_custom_cronjobs(self):
        for name in CustomNRPE.installed_cronjobs.copy():
            self.remove_custom_cronjob(name)


def install_nrpe_checks(enable_cron=False):
    """Configure NRPE checks, i.e. adding custom check script or using standard
    nrpe check script."""
    custom_nrpe = CustomNRPE()
    for check in CHECK_SCRIPTS:
        custom_nrpe.add_check(
            shortname=check["shortname"],
            description=check["description"],
            check_cmd=check["check_cmd"]
        )
        if enable_cron:
            custom_nrpe.install_custom_cronjob(
                check["check_cmd"], check["shortname"]
            )
    custom_nrpe.write()
    return CustomNRPE.installed_cronjobs.copy()


def remove_nrpe_checks():
    """Remove existing NRPE checks."""
    custom_nrpe = CustomNRPE()
    for check in CHECK_SCRIPTS:
        custom_nrpe.remove_check(
            shortname=check["shortname"],
        )
    custom_nrpe.remove_all_custom_cronjobs()
    custom_nrpe.write()


def install_nrpe_plugins():
    """Install all available local nagios nrpe plugins defined in PLUGINS_DIR.
    """
    custom_nrpe = CustomNRPE()
    custom_nrpe.install_all_custom_plugins()
    return CustomNRPE.installed_plugins.copy()


def remove_nrpe_plugins():
    """Remove all available local nagios nrpe plugins defined in PLUGINS_DIR.
    """
    custom_nrpe = CustomNRPE()
    custom_nrpe.remove_all_custom_plugins()
