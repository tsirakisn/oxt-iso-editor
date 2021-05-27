oxt-iso-editor
=============

This repository contains scripts that allow you to modify an existing OpenXT iso and generate a new one.
Note: only master supported for now

### Getting started

#### Prerequisites

* python3
* xorriso
* openssl
* gunzip/gzip

#### Modifying an iso

0. Double check settings.py to tweak any settings to your liking. Most of the values can be safely left as is.
1. Copy your dev-ca{key,cert} pem files to `./extra/keys`
2. Run `sudo iso_edit.py -i /path/to/oxt.iso` to spawn an interactive menu
    - see `./iso_edit.py -h` for all options
3. You can also pass the `-u` flag  to generate an update.tar file with your changes.
4. When you're done making your changes, select the "finish" option to finalize them. The iso will be dev-signed at this point.
