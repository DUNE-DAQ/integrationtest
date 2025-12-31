# 30-Dec-2025, KAB: this function determines the root of the current pytest output
# directory (i.e. the current pytest "tmpdir"). It does this by checking the relevant
# environmental variables to see if any of them have been set.
#
# The order in which the env vars are checked is based on the precedence that the
# pytest framework uses.
#
# A useful reference is here:
# https://docs.pytest.org/en/stable/how-to/tmp_path.html#temporary-directory-location-and-retention
#
# If none of the relevent env vars have been set, this functions returns "/tmp"
# which is the current default for the pytest output root directory.
#
# This function will initially be used in our integtest (python) files and in
# our integtest bundle script(s).
#
import os
def get_pytest_tmpdir():
    tmpdir = os.environ.get("PYTEST_DEBUG_TEMPROOT")
    if tmpdir:
        return tmpdir
    tmpdir = os.environ.get("TMPDIR")
    if tmpdir:
        return tmpdir
    tmpdir = os.environ.get("TEMP")
    if tmpdir:
        return tmpdir
    tmpdir = os.environ.get("TMP")
    if tmpdir:
        return tmpdir
    return "/tmp"
