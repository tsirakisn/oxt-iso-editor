from settings import (
    WORKDIR, KEYDIR, ISOHDPFX, IPK_STAGING_DIR, IPK_FORCE_DEPENDS
)
from sys import exc_info
from traceback import extract_tb
import glob
import hashlib
import os
import re
import shutil
import subprocess

def print_traceback():
    tb_info = extract_tb(exc_info()[2])
    for tb in tb_info:
        filename, line, _, text = tb
        print('   {}:{}, {}'.format(filename, line, text))

def shell(command, **kwargs):
    # effectively "raise on error"
    # make it True by default
    if 'check' not in kwargs:
        kwargs['check'] = True

    if 'shell' not in kwargs:
        kwargs['shell'] = True

    if 'cwd' not in kwargs:
        kwargs['cwd'] = WORKDIR

    if 'quiet' in kwargs:
        kwargs['stdout'] = subprocess.DEVNULL
        kwargs['stderr'] = subprocess.DEVNULL
        del kwargs['quiet']

    try:
        proc = subprocess.run(command, **kwargs)
    except Exception:
        command_str = ' '.join(command.split())
        raise Exception('shell command "{}" failed'.format(command_str))

    return proc

def chown_user(f):
    os.chown(f, int(os.environ['SUDO_UID']), int(os.environ['SUDO_GID']))

def normalize_path(path):
    if path.startswith('~'):
        path = os.path.expanduser(path)

    if not path.startswith('/'):
        if path.startswith('./'):
            path = path[2:]
        elif path == '.':
            path = ''
        path = '{}/{}'.format(os.getcwd(), path)

    if path.endswith('/') and path != '/':
        path = path[:-1]

    return path

def sha256sum(filename):
    sha256_hash = hashlib.sha256()
    with open(filename, 'rb') as f:
        for byte_block in iter(lambda: f.read(4096), b''):
            sha256_hash.update(byte_block)

    return str(sha256_hash.hexdigest())

def copy_all(src, dest):
    for item in os.listdir(src):
        try: # directory
            shutil.copytree('{}/{}'.format(src, item), '{}/{}'.format(dest, item))
        except NotADirectoryError: # file
            shutil.copy('{}/{}'.format(src, item), '{}/{}'.format(dest, item))

def umount(mntpt):
    while True:
        try:
            shell('umount {}'.format(mntpt), quiet=True)
            break
        except:
            print('mountpoint {} still in use.'.format(mntpt))
            input('press [enter] to try again')

def mount_iso_and_copy_files(iso):
    print('mounting iso and copying files')
    shell('mount {} /mnt'.format(iso))

    copy_all('/mnt', WORKDIR)
    umount('/mnt')

def prompt_user(text, default='y'):
    default = default.lower()
    opts = '(Y/n)' if default == 'y' else '(N/y)'
    answer = input('{} {} '.format(text, opts))

    if default == 'y':
        return answer not in ('N', 'n')

    return answer not in ('y', 'Y')

def print_mount_message_and_wait(component, mountpt='/mnt'):
    print()
    print('======================================================')
    print('{} rootfs extracted to {}'.format(component, mountpt))
    print('make your changes in a new terminal and press [enter]')
    print('======================================================')
    input()

def mount_ext3_rootfs(name):
    print('extracting {} rootfs'.format(name))
    shell('gunzip {}-rootfs*.ext*'.format(name), cwd='{}/packages.main'.format(WORKDIR))

    print('mounting {} rootfs'.format(name))
    shell('mount {}-rootfs* /mnt'.format(name), cwd='{}/packages.main'.format(WORKDIR))

def package_ext3_rootfs(name):
    print('re-packaging {} rootfs'.format(name))
    umount('/mnt')
    shell('gzip {}-rootfs*'.format(name), cwd='{}/packages.main'.format(WORKDIR))

def get_xc_packages_line(component):
    with open('{}/packages.main/XC-PACKAGES'.format(WORKDIR)) as f:
        lines = f.readlines()

    for line in lines:
        if re.search('^{}'.format(component), line):
            return line

    return None

def sed(filename, mappings, match_line=''):
    with open(filename, 'r') as f:
        lines = f.readlines()

    with open(filename, 'w') as f:
        for line in lines:
            if re.match(match_line, line):
                for orig, new in mappings.items():
                    line = re.sub(orig, new, line)

            f.write(line)

def update_xc_packages_file(component):
    f = glob.glob('{}/packages.main/{}*'.format(WORKDIR, component))[0]
    new_length = str(os.path.getsize(f))
    new_shasum = sha256sum(f)

    info = get_xc_packages_line(component).split(' ')
    old_length = info[1]
    old_shasum = info[2]

    print('updating {} package info'.format(component))
    print('  old: {} {}'.format(old_length, old_shasum))
    print('  new: {} {}'.format(new_length, new_shasum))

    mappings = {
        old_length: new_length,
        old_shasum: new_shasum,
    }

    sed('{}/packages.main/XC-PACKAGES'.format(WORKDIR), mappings, match_line='^{}'.format(component))

def update_xc_repository_file():
    with open('{}/packages.main/XC-REPOSITORY'.format(WORKDIR)) as f:
        lines = f.readlines()

    for line in lines:
        if re.search('^packages:', line):
            old_shasum = line.split(':')[1].rstrip()

    new_shasum = sha256sum('{}/packages.main/XC-PACKAGES'.format(WORKDIR))

    print('updating xc-repository info')
    print('  old: {}'.format(old_shasum))
    print('  new: {}'.format(new_shasum))
    print()

    mappings = {old_shasum: new_shasum}
    sed('{}/packages.main/XC-REPOSITORY'.format(WORKDIR), mappings)

def sign_files():
    print('signing files with dev cert')
    shell('\
        openssl smime -sign \
            -aes256 \
            -binary \
            -in packages.main/XC-REPOSITORY \
            -out packages.main/XC-SIGNATURE \
            -outform PEM \
            -signer {0}/dev-cacert.pem \
            -inkey {0}/dev-cakey.pem \
        '.format(KEYDIR)
    )

def generate_iso(outiso):
    print('generating iso. output below:\n')

    try:
        shell('\
            xorriso -as mkisofs \
                -o {} \
                -isohybrid-mbr {} \
                -c isolinux/boot.cat \
                -b isolinux/isolinux.bin \
                -no-emul-boot \
                -boot-load-size 4 \
                -boot-info-table \
                -eltorito-alt-boot \
                -e "isolinux/efiboot.img" \
                -no-emul-boot \
                -isohybrid-gpt-basdat \
                -r -J -l \
                -V "OpenXT Custom" \
                -f . \
            '.format(outiso, ISOHDPFX),
        )
    except Exception as exc:
        print('failed to generate iso: {}'.format(exc))
    else:
        print('iso successfully generated to "{}"'.format(outiso))

    chown_user(outiso)

def generate_update_tarball(out_tarball):
    print('generating update.tar')
    shell('tar -cf {} packages.main/*'.format(out_tarball))
    print('tarball successfully generated to "{}"'.format(out_tarball))

    chown_user(out_tarball)

def check_ipks(component):
    ipkdir = '{}/{}'.format(IPK_STAGING_DIR, component)

    if not os.path.exists(ipkdir):
        return False

    ipks = glob.glob('{}/*.ipk'.format(ipkdir))
    if not ipks:
        return False

    show_ipks(ipks, component)
    return prompt_user('install?')

def show_ipks(ipks, component):
    print('\n{} ipks found in {} staging dir:'.format(len(ipks), component))
    for ipk in ipks:
        print('- {}'.format(os.path.basename(ipk)))
    print()

def install_ipks(chroot_dir, ipk_dir):
    print('staging ipks')
    os.mkdir('{}/tmp/ipks'.format(chroot_dir))
    ipks = glob.glob('{}/*.ipk'.format(ipk_dir))
    for ipk in ipks:
        shutil.copy(ipk, '{}/tmp/ipks'.format(chroot_dir))

    print('installing ipks')
    orig_cwd = os.getcwd()
    root = os.open('/', os.O_RDONLY)
    os.chroot(chroot_dir)

    args = '--force-downgrade --force-reinstall'
    if IPK_FORCE_DEPENDS:
        args += ' --force-depends'

    ipks = ' '.join(glob.glob('/tmp/ipks/*.ipk'))
    ipk_basenames = ' '.join([os.path.basename(ipk) for ipk in ipks.split()])
    try:
        print('installing: {}'.format(ipk_basenames))
        shell('opkg install {} {}'.format(args, ipks), cwd='/')
    except:
        print('warn: unable to install ipks')

    os.fchdir(root)
    os.chroot('.')
    os.close(root)
    os.chdir(orig_cwd)

    shutil.rmtree('{}/tmp/ipks'.format(chroot_dir))
