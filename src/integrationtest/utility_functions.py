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
