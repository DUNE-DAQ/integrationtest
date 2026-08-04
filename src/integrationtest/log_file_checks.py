from glob import glob
import re
import copy
from integrationtest.verbosity_helper import (
    IntegtestVerbosityLevels,
    VerbosityHelper
)

# 21-May-2025, KAB: tweak the print() statement default behavior so that it always flushes the output.
import functools
print = functools.partial(print, flush=True)

def log_has_no_errors(log_file_name, print_logfilename_for_problems=True, excluded_substring_list=[],
                      required_substring_list=[], print_required_message_report=False,
                      verbosity_helper: VerbosityHelper = VerbosityHelper(99)):
    ok=True
    ignored_problem_count=0
    required_counts={ss:0 for ss in required_substring_list}
    with open(log_file_name, errors='ignore') as file_handle:
        for line in file_handle.readlines():

            # First check if the line appears to be in the standard format of messages produced with our logging package
            # For lines produced with our logging package, the first two words in the line are the date and time, then the severity

            bad_line=False
            match_logline_prefix = re.search(r"^20[0-9][0-9]-[A-Z][a-z][a-z]-[0-9]+\s+[0-9:,]+\s+([A-Z]+)", line)
            if match_logline_prefix:
                severity=match_logline_prefix.group(1)
                if severity in ("WARNING", "ERROR", "FATAL"):
                    bad_line=True
            else: # This line's not produced with our logging package, so let's just look for bad words
                if "WARN" in line or "Warn" in line or "warn" in line or \
                   "ERROR" in line or "Error" in line or "error" in line or \
                   "FATAL" in line or "Fatal" in line or "fatal" in line or \
                   "egmentation fault" in line:
                    bad_line=True

            if bad_line:
                ignore_this_problem=False
                for excluded_substring in excluded_substring_list:
                    match_obj = re.search(excluded_substring, line)
                    if match_obj:
                        ignore_this_problem=True
                        break
                if ignore_this_problem:
                    bad_line=False
                    ignored_problem_count+=1
            if bad_line:
                for substr in required_substring_list:
                    match_obj = re.search(substr, line)
                    if match_obj:
                        bad_line=False
                        break
            if bad_line:
                if ok and print_logfilename_for_problems:
                    print("----------")
                    print(f"\N{POLICE CARS REVOLVING LIGHT} Problem(s) found in logfile {log_file_name}:")
                print(line)
                ok=False

            for substr in required_substring_list:
                match_obj = re.search(substr, line)
                if match_obj:
                    required_counts[substr] += 1

    if ignored_problem_count > 0:
        if verbosity_helper.compare_level(IntegtestVerbosityLevels.integtest_debug):
            print(f"\N{CONSTRUCTION SIGN} Note: problems found in {ignored_problem_count} lines in {log_file_name} were ignored based on {len(excluded_substring_list)} phrase(s). \N{CONSTRUCTION SIGN}")
    overall_required_message_count = 0
    found_message_count = 0
    for (substr,count) in required_counts.items():
        if count == 0:
            print(f"\N{POLICE CARS REVOLVING LIGHT} Failure: Required log message \"{substr}\" was not found in {log_file_name} \N{POLICE CARS REVOLVING LIGHT}")
            ok=False
        elif print_required_message_report:
            if verbosity_helper.compare_level(IntegtestVerbosityLevels.drunc_transitions):
                print(f"\N{WHITE HEAVY CHECK MARK} Required log message \"{substr}\" occurred {count} times in {log_file_name}")
        overall_required_message_count += count
        if count > 0:
            found_message_count += 1
    if overall_required_message_count > 0:
        if verbosity_helper.compare_level(IntegtestVerbosityLevels.drunc_transitions):
            print(f"\N{WHITE HEAVY CHECK MARK} Note: required log messages were found in {overall_required_message_count} lines in {log_file_name} based on {found_message_count} required messages (of a total of {len(required_substring_list)} required messages).")
    return ok

# 23-Nov-2021, KAB: added the ability for users to specify sets of excluded substrings, to
# enable checking of all log files, and to print out the logfile name when there are problems.
#
# This function accepts the following arguments:
# * the list of logfiles to be checked (array of PythonPath objects)
# * a flag to control whether all logfiles are checked for problems or whether checking
#   stops as soon as one file with problems is found (default is to check them all)
# * a flag to control whether the logfile name is printed to the console when an a problem
#   is first found in that logfile (default is printout)
# * the sets of excluded substrings.  The goal of this argument is to allow certain
#   select messages to be ignored so that overall checking of logfiles can remain enabled
#   without being distracted by 'expected' problems.  This argument is expected to be a
#   dictionary keyed by strings that might appear in the logfile name and having values
#   that are lists of excluded phrases.  Both the logfile name key and the excluded phrases
#   support regular expressions.  Use r"<regex_pattern>" to handle any special patterns.
#   For example:
#   ex_sub_map = {"ruemu": ["expected problem phrase 1", "expected problem  phrase 2"]}
#   ex_sub_map = {"ruemu": [r"expected problem phrase \d+"]}
def logs_are_error_free(log_file_names, show_all_problems=True, print_logfilename_for_problems=True,
                        excluded_substring_map={}, required_substring_map={}, print_required_message_report=False,
                        verbosity_helper: VerbosityHelper = VerbosityHelper(99)):

    # since we modify the excluded_substring_map in this code, we'll make a local copy so that
    # we don't leak changes back into the calling code
    local_excl_string_map = copy.deepcopy(excluded_substring_map)

    # 06-Apr-2026, KAB: if the verbosity level is set to enable DRUNC debug messages, add
    # some strings to the excluded substring map so we don't trigger on those debug messages
    if verbosity_helper.compare_level(IntegtestVerbosityLevels.drunc_debug):
        local_excl_string_map.setdefault("SSH_SHELL_process_manager", []).extend(
            ["LogLevel=error", r'key:\s+"DUNEDAQ_ERS_',
             r"drunc.utils.ConnectivityServiceClient\s+404 Client Error: NOT FOUND for url:"]
        )
        local_excl_string_map.setdefault("drunc-unified_shell", []).extend(
            ["LogLevel=error", r'key:\s+"DUNEDAQ_ERS_', r"DUNEDAQ_ERS_.*erstrace", "export DUNEDAQ_ERS_",
             r"NewConnectionError.* Failed to establish a new connection: \[Errno 111\] Connection refused",
             r"drunc.utils.ConnectivityServiceClient\s+404 Client Error: NOT FOUND for url:"]
        )
        excluded_substring_map.setdefault("drunc-process-manager", []).extend(
            ["LogLevel=error", "key:\s\"DUNEDAQ_ERS_", "DUNEDAQ_ERS_.*erstrace", "export DUNEDAQ_ERS_"]
        )

    # 21-Jul-2026, KAB: phrases that we always want to exclude
    local_excl_string_map.setdefault("drunc-unified-shell", []).extend(["Substate.*In error.*Endpoint"])

    all_ok=True
    #print("") # Clear potential dot from pytest
    for log in log_file_names:
        exclusions=[]
        requireds=[]
        for exclusion_key in local_excl_string_map.keys():
            #print(f"Checking for match for {exclusion_key} in {log.name}")
            match_obj = re.search(exclusion_key, log.name)
            if match_obj:
                exclusions += local_excl_string_map[exclusion_key]
        for required_key in required_substring_map.keys():
            match_obj = re.search(required_key, log.name)
            if match_obj:
                requireds += required_substring_map[required_key]

        single_ok=log_has_no_errors(log, print_logfilename_for_problems, exclusions, requireds,
                                    print_required_message_report, verbosity_helper)

        if not single_ok:
            all_ok=False
            if not show_all_problems:
                break
    return all_ok
