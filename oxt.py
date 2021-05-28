from settings import WORKDIR, IPK_STAGING_DIR
from utils import (
    shell, mount_ext3_rootfs, package_ext3_rootfs, update_xc_packages_file,
    print_mount_message_and_wait, check_ipks, install_ipks
)
import os
import shutil

############ dom0 ############

def modify_dom0():
    mount_ext3_rootfs('dom0')

    if check_ipks('dom0'):
        install_ipks('/mnt', '{}/dom0'.format(IPK_STAGING_DIR))

    print_mount_message_and_wait('dom0', mountpt='/mnt')
    package_ext3_rootfs('dom0')
    update_xc_packages_file('dom0')

############ installer ############

def extract_installerfs(tmpdir):
    print('extracting installer rootfs')
    shell('gunzip -c {}/isolinux/rootfs.gz | cpio --extract -D {}'.format(
        WORKDIR,
        tmpdir,
    ))

    # create a part2 directory so we can extract our control
    # tarball along with our installerfs.
    controlfs = '{}/install/part2'.format(tmpdir)
    if os.path.exists(controlfs):
        shutil.rmtree(controlfs)
    os.mkdir(controlfs)

    print('unpacking control.tar.bz2')
    shell('bunzip2 {}/packages.main/control.tar.bz2'.format(WORKDIR))

    print('extracting control.tar')
    shell('tar -xf {}/packages.main/control.tar'.format(WORKDIR), cwd=controlfs)

    print('\nnote: control tarball extracted to /install/part2 of installerfs')

def package_installerfs(tmpdir):
    controlfs = '{}/install/part2'.format(tmpdir)

    print('re-packaging control.tar.bz2')
    shell('tar -cf {}/packages.main/control.tar *'.format(WORKDIR), cwd=controlfs)
    shell('bzip2 {}/packages.main/control.tar'.format(WORKDIR))
    shutil.rmtree(controlfs)

    print('re-packaging installer rootfs')
    shell(
        'find . | cpio -o -H newc | gzip > "{}/isolinux/rootfs.gz"'.format(WORKDIR),
        cwd=tmpdir,
    )

def modify_installer():
    tmpdir = '{}/installerfs'.format(WORKDIR)
    if os.path.exists(tmpdir):
        shutil.rmtree(tmpdir)
    os.mkdir(tmpdir)

    extract_installerfs(tmpdir)
    print_mount_message_and_wait('installer', tmpdir)

    package_installerfs(tmpdir)
    shutil.rmtree(tmpdir)
    update_xc_packages_file('control')
