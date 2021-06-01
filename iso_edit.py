#!/usr/bin/env python3

import os
import sys

if not os.getcwd().endswith('oxt-iso-editor'):
    # a lot of variables are dependent on the cwd so just
    # force the user to call from the top level dir
    print('error: script must be called from oxt-iso-editor dir')
    sys.exit(1)

from settings import WORKDIR, KEYDIR, DEBUG_WORKDIR, ISOHDPFX
from oxt import modify_dom0, modify_installer, modify_initramfs
from utils import (
    print_traceback, update_xc_repository_file, sign_files, generate_iso,
    prompt_user, normalize_path, chown_user, mount_iso_and_copy_files,
    generate_update_tarball
)
import argparse
import glob
import shutil

class SimpleMenu:
    def __init__(self):
        # list of 2-tuples
        self.options = []
        self.exit_option = None
        self.exit_callback = None

    def show(self):
        if not self.options:
            print('no menu to print.')
            return

        print('\nwhat would you like to do?')
        for i, opt in enumerate(self.options):
            print('{}. {}'.format(i + 1, opt[0]))
        print('{}. {}\n'.format(len(self.options) + 1, self.exit_option))

    def add_option(self, text, callback):
        self.options.append((text, callback))

    def add_exit_option(self, text, callback=None):
        self.exit_option = text
        self.exit_callback = callback

    def query_user(self):
        if not self.exit_option:
            print('error: menu has no exit option. add one with add_exit_option()')
            return

        self.show()

        while True:
            answer = input('selection: ')
            if self.validate_choice(answer):
                choice = int(answer)
                print()
                break

        if choice == len(self.options) + 1:
            if self.exit_callback:
                self.exit_callback()
            return False

        callback = self.options[choice - 1][1]
        if callback:
            callback()

        return True

    def validate_choice(self, choice):
        try:
            c = int(choice)
            if c < 1 or c > len(self.options) + 1: # options + exit option
                print('error: selection must be between 1 and {}'.format(len(self.options) + 1))
                return False
        except KeyboardInterrupt:
            raise
        except:
            print('error: selection must be an integer. try again.')
            return False

        return True

def init_args():
    parser = argparse.ArgumentParser(
        description='Interactive editing tool for OpenXT iso.'
    )

    parser.add_argument(
        '-i',
        dest='starting_iso',
        required=True,
        type=str,
        help='/path/to/oxt.iso'
    )

    parser.add_argument(
        '-o',
        dest='iso_outdir',
        type=str,
        default='{}/out'.format(os.getcwd()),
        help='where to store new iso (defaults to $cwd/out)'
    )

    parser.add_argument(
        '-u',
        '--update-tar',
        dest='update_tarball',
        action='store_true',
        help='generate an additional update.tar file'
    )

    parser.add_argument(
        '-U',
        '--update-only',
        dest='tarball_only',
        action='store_true',
        help='only generate an update.tar file (no iso)'
    )

    return parser.parse_args()

def run_interactive_menu():
    print('\n* note that you can edit the isolinux dir at any time - that dir')
    print('is extracted to {}/isolinux'.format(WORKDIR))

    menu = SimpleMenu()
    menu.add_option('edit dom0 rootfs', modify_dom0)
    menu.add_option('edit initramfs rootfs', modify_initramfs)
    menu.add_option('edit installer rootfs (parts 1 & 2)', modify_installer)
    menu.add_exit_option('finalize changes')

    while True:
        try:
            if not menu.query_user():
                break
        except KeyboardInterrupt:
            print('\nctrl+c caught; cleaning up')
            return False
        except Exception as exc:
            print()
            print('error: exception caught')
            print('exception: {}'.format(exc))
            print_traceback()
            return False

    return True

def verify_iso(iso):
    if not iso:
        print('error: iso must be specified')
        return False

    if not os.path.exists(iso):
        print('error: iso "{}" doesn\'t exist'.format(iso))
        return False

    return True

def verify_workdir():
    if WORKDIR == '/':
        print('error: your WORKDIR was set to /. surely you don\'t want this.')
        return False

    return True

def verify_keydir():
    files = glob.glob('{}/*.pem'.format(KEYDIR))

    if not os.path.exists(KEYDIR) or len(files) < 2:
        print('error: key/cert not found in key dir')
        print('copy dev-ca{{key,cert}}.pem to {}'.format(KEYDIR))
        return False

    return True

def verify_isohdpfx():
    if not ISOHDPFX or not os.path.exists(ISOHDPFX):
        print('error: path to isohdpfx doesn\'t exist')
        print('double check the ISOHDPFX value in settings.py')
        return False

    return True

def verify_outdir(outdir):
    if os.path.exists(outdir) and not os.path.isdir(outdir):
        print('error: {} is not a directory.'.format(outdir))
        print('please provide a proper outdir with the -o flag')
        return False

    return True

def check_mountpt():
    if os.path.ismount('/mnt'):
        print('error: something is already mounted on /mnt')
        print('unmount it before running this script')
        return False

    return True

def finalize_changes(outdir, make_iso=True, make_tarball=False):
    update_xc_repository_file()
    sign_files()

    if make_iso:
        iso = '{}/installer.iso'.format(outdir)
        generate_iso(iso)

    if make_tarball:
        update_tarball = '{}/update.tar'.format(outdir)
        generate_update_tarball(update_tarball)

def cleanup(error=False):
    rm_workdir = True

    if error:
        # offer to persist the workdir on error so the user can
        # potentially examine it
        if not DEBUG_WORKDIR:
            if not prompt_user('clean up workdir?'):
                rm_workdir = False

    if DEBUG_WORKDIR:
        print('preserving workdir as per DEBUG_WORKDIR setting')
    elif rm_workdir and os.path.exists(WORKDIR):
        shutil.rmtree(WORKDIR)

    if error:
        sys.exit(1)

def main():
    args = init_args()

    if os.geteuid() != 0:
        print('error: this script must be run with sudo privs (sorry)')
        return

    if os.path.exists(WORKDIR):
        shutil.rmtree(WORKDIR)

    os.makedirs(WORKDIR)

    if not verify_iso(args.starting_iso) or \
       not verify_outdir(args.iso_outdir) or \
       not verify_workdir() or \
       not verify_keydir() or \
       not verify_isohdpfx() or \
       not check_mountpt():
        sys.exit(1)

    iso_in = normalize_path(args.starting_iso)
    outdir = normalize_path(args.iso_outdir)
    make_iso = not args.tarball_only
    make_tarball = args.update_tarball or args.tarball_only

    if not os.path.exists(outdir):
        print('creating output dir')
        os.makedirs(outdir)
        chown_user(outdir)

    mount_iso_and_copy_files(iso_in)

    if not run_interactive_menu():
        cleanup(error=True)
        return

    try:
        finalize_changes(outdir, make_iso, make_tarball)
    except:
        cleanup(error=True)
        return

    cleanup()

if __name__ == '__main__':
    main()
