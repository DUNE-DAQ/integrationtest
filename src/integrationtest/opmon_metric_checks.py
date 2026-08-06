import re
from opmonlib.info_file_collator import collate_info_files
from integrationtest.verbosity_helper import (
    IntegtestVerbosityLevels,
    VerbosityHelper
)

# modify the print() statement default behavior so that it always flushes the output.
import functools
print = functools.partial(print, flush=True)


# simple wrapper for the function in opmonlib that collates metric files
def collate_opmon_data_from_files(json_files: list) -> dict:
    return collate_info_files(json_files)


# Function to check whether the number of samples reported in the specified collection
# of opmon data for the specified metric name is within the specified range.
# The metric name is specified as a list of dictionary keys.  For example:
#   [session_name, "df-01", "df-01-trb", "dfmodules.TRBInfo", "generated_trigger_records"]
# The default upper bound on the number of samples is -1, which is a special value that means "unbounded."
# The default lower bound on the number of samples is 1.
# So, the default behavior of this function is to check that there is at least one sample.
# Returns False if a problem is encountered (e.g. parsing the collated JSON metric data)
# or the sample count is out of the requested range.  True otherwise.
def check_metric_sample_count(collated_opmon_data: dict, dict_key_list: list, min_count=1, max_count=-1,
                              verbosity_helper: VerbosityHelper = VerbosityHelper(99)):
    full_key_path = dict_key_list[0]
    for key_name in dict_key_list[1:]:
        full_key_path += "/" + str(key_name)
    "Checking that the number of {full_key_path} metric samples is within its allowed range"

    # sanity check - make sure that we really have a dictionary
    working_dict = collated_opmon_data
    if not isinstance(working_dict, dict):
        print(f"\N{POLICE CARS REVOLVING LIGHT} The data type of the collated opmon data ({type(working_dict)}) is not 'dictionary', as it needs to be. \N{POLICE CARS REVOLVING LIGHT}")
        return False

    # work our way down the nested dictionaries until we get to the requested metric values
    for key_name in dict_key_list:
        # if the user specified a key name of "*", we just use the first available key
        if key_name == "*":
            key_list = list(working_dict.keys())
            first_key = key_list[0]
            working_dict = working_dict[first_key]
        # otherwise, we fetch the requested key, if it's available
        elif key_name in working_dict.keys():
            working_dict = working_dict[key_name]
        # otherwise, we bail out
        else:
            print(f"\N{POLICE CARS REVOLVING LIGHT} Unable to find the data for key \"{key_name}\" when looking up metric \"{full_key_path}\" in collated opmon data. \N{POLICE CARS REVOLVING LIGHT}")
            return False

        # sanity check - make sure that we really have a dictionary at the next level in the tree
        if not isinstance(working_dict, dict):
            print(f"\N{POLICE CARS REVOLVING LIGHT} The data type of the opmon data associated with the '{key_name}' key ({type(working_dict)}) is not 'dictionary', as it needs to be. \N{POLICE CARS REVOLVING LIGHT}")
            return False

    number_of_samples = len(working_dict)
    if max_count == -1:
        if number_of_samples < min_count:
            print(f"\N{POLICE CARS REVOLVING LIGHT} The number of metric samples for key \"{full_key_path}\" ({number_of_samples}) is outside the expected range ({min_count}..unbounded). \N{POLICE CARS REVOLVING LIGHT}")
            return False
        else:
            verbosity_helper.lvl_print(IntegtestVerbosityLevels.drunc_transitions,
                                       f"\N{WHITE HEAVY CHECK MARK} The number of metric samples for key \"{full_key_path}\" ({number_of_samples}) is within the expected range ({min_count}..unbounded).")
            return True
    else:
        if number_of_samples < min_count or number_of_samples > max_count:
            print(f"\N{POLICE CARS REVOLVING LIGHT} The number of metric samples for key \"{full_key_path}\" ({number_of_samples}) is outside the expected range ({min_count}..{max_count}). \N{POLICE CARS REVOLVING LIGHT}")
            return False
        else:
            verbosity_helper.lvl_print(IntegtestVerbosityLevels.drunc_transitions,
                                       f"\N{WHITE HEAVY CHECK MARK} The number of metric samples for key \"{full_key_path}\" ({number_of_samples}) is within the expected range ({min_count}..{max_count}).")
            return True


# Function to check whether the values reported in the specified collection of opmon data for
# the specified metric name sum up to a total that is within the specified range.
# The metric name is specified as a list of dictionary keys.  For example:
#   [session_name, "df-01", "df-01-trb", "dfmodules.TRBInfo", "generated_trigger_records"]
# The default upper bound on the sum of the values is -1, which is a special value that means "unbounded."
# The default lower bound on the sum of the values is 1.
# So, the default behavior of this function is to check that there is at least one non-zero metric value.
# Returns False if a problem is encountered (e.g. parsing the collated JSON metric data)
# or the value sum is out of the requested range.  True otherwise.
def check_metric_value_sum(collated_opmon_data: dict, dict_key_list: list, min_value_sum=1, max_value_sum=-1,
                           verbosity_helper: VerbosityHelper = VerbosityHelper(99)):
    full_key_path = dict_key_list[0]
    for key_name in dict_key_list[1:]:
        full_key_path += "/" + str(key_name)
    "Checking that the sum of {full_key_path} metric values is within its allowed range"

    # sanity check - make sure that we really have a dictionary
    working_dict = collated_opmon_data
    if not isinstance(working_dict, dict):
        print(f"\N{POLICE CARS REVOLVING LIGHT} The data type of the collated opmon data ({type(working_dict)}) is not 'dictionary', as it needs to be. \N{POLICE CARS REVOLVING LIGHT}")
        return False

    # work our way down the nested dictionaries until we get to the requested metric values
    for key_name in dict_key_list:
        # if the user specified a key name of "*", we just use the first available key
        if key_name == "*":
            key_list = list(working_dict.keys())
            first_key = key_list[0]
            working_dict = working_dict[first_key]
        # otherwise, we fetch the requested key, if it's available
        elif key_name in working_dict.keys():
            working_dict = working_dict[key_name]
        # otherwise, we bail out
        else:
            print(f"\N{POLICE CARS REVOLVING LIGHT} Unable to find the data for key \"{key_name}\" when looking up metric \"{full_key_path}\" in collated opmon data. \N{POLICE CARS REVOLVING LIGHT}")
            return False

        # sanity check - make sure that we really have a dictionary at the next level in the tree
        if not isinstance(working_dict, dict):
            print(f"\N{POLICE CARS REVOLVING LIGHT} The data type of the opmon data associated with the '{key_name}' key ({type(working_dict)}) is not 'dictionary', as it needs to be. \N{POLICE CARS REVOLVING LIGHT}")
            return False

    value_sum = 0;
    for timestamp_string, value_string in working_dict.items():
        value_sum += int(value_string)
    if max_value_sum == -1:
        if value_sum < min_value_sum:
            print(f"\N{POLICE CARS REVOLVING LIGHT} The sum of metric values for key \"{full_key_path}\" ({value_sum}) is outside the expected range ({min_value_sum}..unbounded). \N{POLICE CARS REVOLVING LIGHT}")
            return False
        else:
            verbosity_helper.lvl_print(IntegtestVerbosityLevels.drunc_transitions,
                                       f"\N{WHITE HEAVY CHECK MARK} The sum of metric values for key \"{full_key_path}\" ({value_sum}) is within the expected range ({min_value_sum}..unbounded).")
            return True
    else:
        if value_sum < min_value_sum or value_sum > max_value_sum:
            print(f"\N{POLICE CARS REVOLVING LIGHT} The sum of metric values for key \"{full_key_path}\" ({value_sum}) is outside the expected range ({min_value_sum}..{max_value_sum}). \N{POLICE CARS REVOLVING LIGHT}")
            return False
        else:
            verbosity_helper.lvl_print(IntegtestVerbosityLevels.drunc_transitions,
                                       f"\N{WHITE HEAVY CHECK MARK} The sum of metric values for key \"{full_key_path}\" ({value_sum}) is within the expected range ({min_value_sum}..{max_value_sum}).")
            return True


# Function to check whether the strings reported in the specified collection of opmon data
# for the specified metric name match the specified regular expression.
# The metric name is specified as a list of dictionary keys.  For example:
#   [daq_session_name, "df-01", "appfwk.AppInfo", "state"]
# Returns False if a problem is encountered (e.g. parsing the collated JSON metric data)
# or the metric (string) values do not match the specified regex.  True otherwise.
def check_metric_value_string(collated_opmon_data: dict, dict_key_list: list, pattern_string: str,
                              verbosity_helper: VerbosityHelper = VerbosityHelper(99)):
    full_key_path = dict_key_list[0]
    for key_name in dict_key_list[1:]:
        full_key_path += "/" + str(key_name)
    "Checking that the sum of {full_key_path} metric values is within its allowed range"

    # sanity check - make sure that we really have a dictionary
    working_dict = collated_opmon_data
    if not isinstance(working_dict, dict):
        print(f"\N{POLICE CARS REVOLVING LIGHT} The data type of the collated opmon data ({type(working_dict)}) is not 'dictionary', as it needs to be. \N{POLICE CARS REVOLVING LIGHT}")
        return False

    # work our way down the nested dictionaries until we get to the requested metric values
    for key_name in dict_key_list:
        # if the user specified a key name of "*", we just use the first available key
        if key_name == "*":
            key_list = list(working_dict.keys())
            first_key = key_list[0]
            working_dict = working_dict[first_key]
        # otherwise, we fetch the requested key, if it's available
        elif key_name in working_dict.keys():
            working_dict = working_dict[key_name]
        # otherwise, we bail out
        else:
            print(f"\N{POLICE CARS REVOLVING LIGHT} Unable to find the data for key \"{key_name}\" when looking up metric \"{full_key_path}\" in collated opmon data. \N{POLICE CARS REVOLVING LIGHT}")
            return False

        # sanity check - make sure that we really have a dictionary at the next level in the tree
        if not isinstance(working_dict, dict):
            print(f"\N{POLICE CARS REVOLVING LIGHT} The data type of the opmon data associated with the '{key_name}' key ({type(working_dict)}) is not 'dictionary', as it needs to be. \N{POLICE CARS REVOLVING LIGHT}")
            return False

    for timestamp_string, value_string in working_dict.items():
        if not re.search(pattern_string, value_string):
            print(f"\N{POLICE CARS REVOLVING LIGHT} One of the metric values for key \"{full_key_path}\" ({repr(value_string)}) does not match the expected pattern ({pattern_string}). \N{POLICE CARS REVOLVING LIGHT}")
            return False

    verbosity_helper.lvl_print(IntegtestVerbosityLevels.drunc_transitions,
                               f"\N{WHITE HEAVY CHECK MARK} All of the metric values for key \"{full_key_path}\" match the expected pattern ({pattern_string}).")
    return True
