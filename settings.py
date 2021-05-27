import os

# temporary location that houses copied iso files.
# will be created if it doesn't exist. WARNING: this
# dir gets wiped after execution, so don't set it to
# anything important.
WORKDIR = '{}/work'.format(os.getcwd())

# dir that stores the dev key/cert used to sign the iso.
# will be created if it doesn't exist.
KEYDIR = '{}/extra/keys'.format(os.getcwd())

ISOHDPFX = '{}/extra/isohdpfx.bin'.format(os.getcwd())

# don't rm work dir after script completes, even if it succeeds.
DEBUG_WORKDIR = False
