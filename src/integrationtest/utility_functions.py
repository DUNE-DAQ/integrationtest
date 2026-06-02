import pytest
import os
import re
from integrationtest.verbosity_helper import IntegtestVerbosityLevels

import functools
print = functools.partial(print, flush=True)  # always flush print() output

def basic_checks(run_dunerc, caplog, print_test_name: bool = True):

    # print out the name of the current test, if requested
    if print_test_name and run_dunerc.verbosity_helper.compare_level(IntegtestVerbosityLevels.drunc_transitions):
        # print the name of the current test
        current_test = os.environ.get("PYTEST_CURRENT_TEST")
        match_obj = re.search(r".*\[(.+)-run_.*rc.*\d].*", current_test)
        if match_obj:
            current_test = match_obj.group(1)
        banner_line = re.sub(".", "=", current_test)
        print(banner_line)
        print(current_test)
        print(banner_line)

    # Check that dunerc completed correctly
    if run_dunerc.completed_process.returncode != 0:
        fail_msg = f"The run control session returned a non-zero status code ({run_dunerc.completed_process.returncode})."
        pytest.fail(fail_msg, pytrace=False)

    # Check that there weren't any warnings or errors during setup
    setup_logs = caplog.get_records("setup")
    if len(setup_logs) > 0:
        fail_msg = f"One or more problems were encountered during the setup of the pytest: {setup_logs}"
        pytest.fail(fail_msg, pytrace=False)


def remove_hdf5_files_if_requested(run_dunerc, this_test_requests_hdf5_file_removal: bool = False):

    # if the user requested that the files should be kept, we can simply exit early
    if (run_dunerc.user_requests_hdf5_file_removal is not None and
        ("false" in run_dunerc.user_requests_hdf5_file_removal.lower() or
         "never" in run_dunerc.user_requests_hdf5_file_removal.lower())):
        return

    # if either of the integtest writer or the user running the test requested that the HDF5 files
    # be deleted at the end of the test, do that.
    if ((run_dunerc.user_requests_hdf5_file_removal is not None and
         ("true" in run_dunerc.user_requests_hdf5_file_removal.lower() or
          "always" in run_dunerc.user_requests_hdf5_file_removal.lower())) or
        this_test_requests_hdf5_file_removal):
        pathlist_string = ""
        filelist_string = ""
        for data_file in run_dunerc.data_files:
            filelist_string += " " + str(data_file)
            if str(data_file.parent) not in pathlist_string:
                pathlist_string += " " + str(data_file.parent)
        for data_file in run_dunerc.tpset_files:
            filelist_string += " " + str(data_file)
            if str(data_file.parent) not in pathlist_string:
                pathlist_string += " " + str(data_file.parent)
        for data_file in run_dunerc.trmon_files:
            filelist_string += " " + str(data_file)
            if str(data_file.parent) not in pathlist_string:
                pathlist_string += " " + str(data_file.parent)

        if pathlist_string and filelist_string:
            if run_dunerc.verbosity_helper.compare_level(IntegtestVerbosityLevels.integtest_debug):
                print("============================================")
                print("Listing the hdf5 files before deleting them:")
                print("============================================")

                os.system(f"df -h {pathlist_string}")
                print("--------------------")
                os.system(f"ls -alF {filelist_string}")

            for data_file in run_dunerc.data_files:
                data_file.unlink()
            for data_file in run_dunerc.tpset_files:
                data_file.unlink()
            for data_file in run_dunerc.trmon_files:
                data_file.unlink()

            if run_dunerc.verbosity_helper.compare_level(IntegtestVerbosityLevels.integtest_debug):
                print("--------------------")
                os.system(f"df -h {pathlist_string}")
                print("============================================")
