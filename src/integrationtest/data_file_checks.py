import datetime
import h5py
import os.path
import re
from hdf5libs import HDF5RawDataFile
from integrationtest.data_file_check_utilities import (
    get_TC_types,
    get_trigger_type_string,
    get_record_ordinal_strings,
    get_fragment_count_limits,
    get_fragment_size_limits,
    get_fragment_error_bitmask,
    get_set_error_bit_names,
    sid_key,
    get_TR_trigger_types,
    unpack_TR_trigger_types,
    convert_TR_strings_to_types,
    convert_TR_type_to_TC_bit,
    check_multi_TR_type,
    record_ordinal_string_all_tests,
    trigger_functions_checks
    )

# 21-May-2025, KAB: tweak the print() statement default behavior so that it always flushes the output.
import functools
print = functools.partial(print, flush=True)

class DataFile:
    def __init__(self, filename):
        self.h5file=h5py.File(filename, 'r')
        self.events=self.h5file.keys()
        self.name=str(filename)

def sanity_check(datafile):
    "Very basic sanity checks on file"
    passed=True
    base_filename = os.path.basename(datafile.h5file.filename)
    print("") # Clear potential dot from pytest

    # execute unit tests for local function(s)
    # (this is probably not the best place for these...)
    record_ordinal_string_all_tests()

    # Check that every event has a TriggerRecordHeader
    for event in datafile.events:
        triggerrecordheader_count = 0
        for key in datafile.h5file[event]["RawData"].keys():
            if "TriggerRecordHeader" in key:
                triggerrecordheader_count += 1
        if triggerrecordheader_count == 0:
            print(f"\N{POLICE CARS REVOLVING LIGHT} No TriggerRecordHeader in record {event} \N{POLICE CARS REVOLVING LIGHT}")
            passed=False
        if triggerrecordheader_count > 1:
            print(f"\N{POLICE CARS REVOLVING LIGHT} More than one TriggerRecordHeader in record {event} \N{POLICE CARS REVOLVING LIGHT}")
            passed=False

    # check that the trigger_type in the TriggerRecordHeader matches one of the
    # TriggerCandidates in the TC fragment
    h5_file = HDF5RawDataFile(datafile.name)
    records = h5_file.get_all_record_ids()
    for rec in records:
        trigger_type_string = get_trigger_type_string(h5_file, rec)
        TC_type_list = get_TC_types(h5_file, rec)
        # 20-Nov-2025, KAB: added the condition that the trigger record sequence number is zero to the following test.
        # The reason for this is that when triggers with long readout windows are split into a sequence of
        # trigger records, typically only the first TR in the sequence has a non-empty TriggerCandidate fragment.
        # We don't want to complain about an invalid trigger type for the remaining TRs in the sequence when those
        # TRs are expected to have an empty TC fragment.  Of course, it would be really great if all TRs in the
        # sequence would have a non-empty TC fragment, but that is a problem for another day.
        if trigger_type_string not in TC_type_list and rec[1] == 0:
            print(f"\N{POLICE CARS REVOLVING LIGHT} The trigger_type in the TriggerRecordHeader ({trigger_type_string}) does not match any of the TriggerCandidate types ({TC_type_list}) in record {rec} \N{POLICE CARS REVOLVING LIGHT}")
            passed=False

    if passed:
        print(f"\N{WHITE HEAVY CHECK MARK} Sanity-check passed for file {base_filename}")
    else:
        print(f"\N{POLICE CARS REVOLVING LIGHT} One or more sanity-checks failed for file {base_filename} \N{POLICE CARS REVOLVING LIGHT}")
    return passed

# 17-Nov-2025, KAB: added the 'was_test_run' function argument to allow us
# to validate the run_was_for_test_purposes Attribute value.  Valid values
# are the strings "true" and "false", which is easiest given that the values
# in the HDF5 Attribute are lower-case strings.
def check_file_attributes(datafile, was_test_run="true"):
    "Checking that the expected Attributes exist within the data file"
    passed=True
    base_filename = os.path.basename(datafile.h5file.filename)
    if "tp" in base_filename:
        print("") # Clear potential dot from pytest
    expected_attribute_names = ["application_name", "closing_timestamp", "creation_timestamp", "file_index", "filelayout_params", "filelayout_version", "offline_data_stream", "operational_environment", "record_type", "recorded_size", "run_number", "run_was_for_test_purposes", "source_id_geo_id_map"]
    for expected_attr_name in expected_attribute_names:
        if expected_attr_name not in datafile.h5file.attrs.keys():
            passed=False
            print(f"\N{POLICE CARS REVOLVING LIGHT} Attribute '{expected_attr_name}' not found in file {base_filename} \N{POLICE CARS REVOLVING LIGHT}")
        elif expected_attr_name == "run_number":
            # value from the Attribute
            attr_value = datafile.h5file.attrs.get(expected_attr_name)
            # value from the filename
            pattern = r"_run\d+_"
            match_obj = re.search(pattern, base_filename)
            if match_obj:
                filename_value = int(re.sub('run','',re.sub('_','',match_obj.group(0))))
                if attr_value != filename_value:
                    passed=False
                    print(f"\N{POLICE CARS REVOLVING LIGHT} The value in HDF5 File Attribute '{expected_attr_name}' ({attr_value}) does not match the value in the filename ({base_filename}) \N{POLICE CARS REVOLVING LIGHT}")
        elif expected_attr_name == "file_index":
            # value from the Attribute
            attr_value = datafile.h5file.attrs.get(expected_attr_name)
            # value from the filename
            pattern = r"_\d+_"
            match_obj = re.search(pattern, base_filename)
            if match_obj:
                filename_value = int(re.sub('_','',match_obj.group(0)))
                if attr_value != filename_value:
                    passed=False
                    print(f"\N{POLICE CARS REVOLVING LIGHT} The value in HDF5 File Attribute '{expected_attr_name}' ({attr_value}) does not match the value in the filename ({base_filename}) \N{POLICE CARS REVOLVING LIGHT}")
        elif expected_attr_name == "creation_timestamp":
            # value from the Attribute (with a little bit of variation allowed)
            attr_value = datafile.h5file.attrs.get(expected_attr_name)
            date_obj = datetime.datetime.fromtimestamp((int(attr_value)/1000)-1, datetime.timezone.utc)
            date_string = date_obj.strftime("%Y%m%dT%H%M%S")
            pattern_low = f".*{date_string}.*"
            date_obj = datetime.datetime.fromtimestamp((int(attr_value)/1000)+1, datetime.timezone.utc)
            date_string = date_obj.strftime("%Y%m%dT%H%M%S")
            pattern_high = f".*{date_string}.*"
            date_obj = datetime.datetime.fromtimestamp((int(attr_value)/1000)+0, datetime.timezone.utc)
            date_string = date_obj.strftime("%Y%m%dT%H%M%S")
            pattern_exact = f".*{date_string}.*"
            # 05-Feb-2026, KAB: added code to check if the unique substring based on the current date/time
            # exists in the filename exists before we do any checking.
            # value from the filename
            pattern = r"_\d+T\d+"
            match_obj = re.search(pattern, base_filename)
            if match_obj:
                filename_value = re.sub('_','',match_obj.group(0))
                if not re.match(pattern_exact, filename_value) and not re.match(pattern_low, filename_value) and not re.match(pattern_high, filename_value):
                    passed=False
                    print(f"\N{POLICE CARS REVOLVING LIGHT} The value in HDF5 File Attribute '{expected_attr_name}' ({date_string}) does not match the value in the filename ({base_filename}) \N{POLICE CARS REVOLVING LIGHT}")
                    print(f"\N{POLICE CARS REVOLVING LIGHT} Debug information: pattern_low={pattern_low} pattern_high={pattern_high} pattern_exact={pattern_exact} filename_value={filename_value} \N{POLICE CARS REVOLVING LIGHT}")
        elif expected_attr_name == "run_was_for_test_purposes":
            # value from the Attribute
            attr_value = datafile.h5file.attrs.get(expected_attr_name)
            if attr_value != was_test_run:
                passed=False
                print(f"\N{POLICE CARS REVOLVING LIGHT} The value in HDF5 File Attribute '{expected_attr_name}' ({attr_value}) does not match the expected value ({was_test_run}) \N{POLICE CARS REVOLVING LIGHT}")
    if passed:
        print(f"\N{WHITE HEAVY CHECK MARK} All Attribute tests passed")
    return passed

def check_event_count(datafile, expected_value, tolerance):
    "Checking that the number of records in the file is within tolerance of the expected_value"
    passed=True
    event_count=len(datafile.events)
    min_event_count=expected_value-tolerance
    max_event_count=expected_value+tolerance
    if event_count<min_event_count or event_count>max_event_count:
        passed=False
        print(f"\N{POLICE CARS REVOLVING LIGHT} Record count {event_count} is outside the tolerance of {tolerance} from an expected value of {expected_value} \N{POLICE CARS REVOLVING LIGHT}")
    if passed:
        print(f"\N{WHITE HEAVY CHECK MARK} Record count {event_count} is within a tolerance of {tolerance} from an expected value of {expected_value}")
    return passed

# 18-Aug-2021, KAB: General-purposed test for fragment count.  The idea behind this test
# is that each type of fragment can be tested individually, by calling this routine for
# each type.  The test is driven by a set of parameters that describe both the fragments
# to be tested (e.g. the Fragment type) and the characteristics that they should have
# (e.g. the number of fragments that should be present).
#
# The parameters that are required by this routine are the following:
# * fragment_type_description - descriptive text for the fragment type, e.g. "WIB" or "PDS" or "Raw TP"
# * fragment_type - Type of the Fragment, e.g. "ProtoWIB" or "Trigger_Primitive"
# * expected_fragment_count - the expected number of fragments of this type
def check_fragment_count(datafile, params):
    debug_mask = 0
    if 'debug_mask' in params:
        debug_mask = params['debug_mask']
    min_count_list = []
    max_count_list = []
    subdet_string = ""
    if 'subdetector' in params:
        subdet_string = params['subdetector']

    "Checking that there are {params['expected_fragment_count']} {params['fragment_type_description']} fragments in each record in the file"
    passed=True
    h5_file = HDF5RawDataFile(datafile.name)
    records = h5_file.get_all_record_ids()
    for rec in records:
        trigger_type_string = get_trigger_type_string(h5_file, rec)
        rno_strings = get_record_ordinal_strings(rec, records)
        fragment_count_limits = get_fragment_count_limits(params, trigger_type_string, rno_strings)
        if (debug_mask & 0x1) != 0:
            print(f'DataFileChecks Debug: the fragment count limits are {fragment_count_limits} for TC type {trigger_type_string} and record ordinal strings {rno_strings}')
        if fragment_count_limits[0] not in min_count_list:
            min_count_list.append(fragment_count_limits[0])
        if fragment_count_limits[1] not in max_count_list:
            max_count_list.append(fragment_count_limits[1])
        if subdet_string == "":
            src_ids = h5_file.get_source_ids_for_fragment_type(rec, params['fragment_type'])
        else:
            src_ids = h5_file.get_source_ids_for_fragtype_and_subdetector(rec, params['fragment_type'], subdet_string)
        fragment_count=len(src_ids)
        if (debug_mask & 0x2) != 0:
            print(f'  DataFileChecks Debug: fragment count is {fragment_count}')
        if fragment_count<fragment_count_limits[0] or fragment_count>fragment_count_limits[1]:
            passed=False
            print(f"\N{POLICE CARS REVOLVING LIGHT} Record {rec} has an unexpected number of {params['fragment_type_description']} fragments: {fragment_count} (outside range {fragment_count_limits}) \N{POLICE CARS REVOLVING LIGHT}")
    if passed:
        min_count_list.sort()
        max_count_list.sort()
        if len(min_count_list) > 1 or len(max_count_list) > 1 or min_count_list[0] != max_count_list[0]:
            print(f"\N{WHITE HEAVY CHECK MARK} {params['fragment_type_description']} fragment count in range {min_count_list} to {max_count_list} confirmed in all {len(records)} records")
        else:
            print(f"\N{WHITE HEAVY CHECK MARK} {params['fragment_type_description']} fragment count of {min_count_list[0]} confirmed in all {len(records)} records")
    return passed

# 18-Aug-2021, KAB: general-purposed test for fragment sizes.  The idea behind this test
# is that each type of fragment can be tested individually, by calling this routine for
# each type.  The test is driven by a set of parameters that describe both the fragments
# to be tested (e.g. the Fragment type) and the characteristics that they should have
# (e.g. the minimum and maximum fragment size).
#
# The parameters that are required by this routine are the following:
# * fragment_type_description - descriptive text for the fragment type, e.g. "WIB" or "PDS" or "Raw TP"
# * fragment_type - Type of the Fragment, e.g. "ProtoWIB" or "Trigger_Primitive"
# * min_size_bytes - the minimum size of fragments of this type
# * max_size_bytes - the maximum size of fragments of this type
def check_fragment_sizes(datafile, params):
    if params['expected_fragment_count'] == 0:
        return True
    debug_mask = 0
    if 'debug_mask' in params:
        debug_mask = params['debug_mask']
    min_size_list = []
    max_size_list = []
    subdet_string = ""
    if 'subdetector' in params:
        subdet_string = params['subdetector']

    "Checking that every {params['fragment_type_description']} fragment size is within its allowed range"
    passed=True
    h5_file = HDF5RawDataFile(datafile.name)
    records = h5_file.get_all_record_ids()
    for rec in records:
        trigger_type_string = get_trigger_type_string(h5_file, rec)
        rno_strings = get_record_ordinal_strings(rec, records)
        size_limits = get_fragment_size_limits(params, trigger_type_string, rno_strings)
        if (debug_mask & 0x4) != 0:
            print(f'DataFileChecks Debug: the fragment size limits are {size_limits} for TC type {trigger_type_string} and record ordinal strings {rno_strings}')
        if size_limits[0] not in min_size_list:
            min_size_list.append(size_limits[0])
        if size_limits[1] not in max_size_list:
            max_size_list.append(size_limits[1])
        if subdet_string == "":
            src_ids = h5_file.get_source_ids_for_fragment_type(rec, params['fragment_type'])
        else:
            src_ids = h5_file.get_source_ids_for_fragtype_and_subdetector(rec, params['fragment_type'], subdet_string)
        for src_id in src_ids:
            frag=h5_file.get_frag(rec,src_id);
            size=frag.get_size()
            if (debug_mask & 0x8) != 0:
                print(f'  DataFileChecks Debug: fragment size for SourceID {src_id} is {size}')
            if size<size_limits[0] or size>size_limits[1]:
                passed=False
                print(f" \N{POLICE CARS REVOLVING LIGHT} {params['fragment_type_description']} fragment for SrcID {src_id.to_string()} in record {rec} has size {size} (outside range {size_limits}) \N{POLICE CARS REVOLVING LIGHT}")
    if passed:
        min_size_list.sort()
        max_size_list.sort()
        print(f"\N{WHITE HEAVY CHECK MARK} All {params['fragment_type_description']} fragments in {len(records)} records have sizes between {min_size_list[0] if len(min_size_list) == 1 else min_size_list} and {max_size_list[0] if len(max_size_list) == 1 else max_size_list}")
    return passed

# 07-Jan-2025, ELF: test for fragment error flags.  The idea behind this test
# is that each type of fragment can be tested individually, by calling this routine for
# each type.  The test is driven by a set of parameters that describe both the fragments
# to be tested (e.g. the Fragment type) and the characteristics that they should have
# (e.g. any allowed error bits).
#
# The parameters that are required by this routine are the following:
# * fragment_type_description - descriptive text for the fragment type, e.g. "WIB" or "PDS" or "Raw TP"
# * fragment_type - Type of the Fragment, e.g. "ProtoWIB" or "Trigger_Primitive"
# * error_bitmask - A mask to be applied to the error bits of the Fragment (default: 0xFFFFFFFF)
def check_fragment_error_flags(datafile, params):
    if params['expected_fragment_count'] == 0:
        return True
    debug_mask = 0
    if 'debug_mask' in params:
        debug_mask = params['debug_mask']
    error_mask_list = []
    subdet_string = ""
    if 'subdetector' in params:
        subdet_string = params['subdetector']

    "Checking that every {params['fragment_type_description']} fragment size is within its allowed range"
    passed=True
    h5_file = HDF5RawDataFile(datafile.name)
    records = h5_file.get_all_record_ids()
    for rec in records:
        trigger_type_string = get_trigger_type_string(h5_file, rec)
        rno_strings = get_record_ordinal_strings(rec, records)
        error_bitmask = get_fragment_error_bitmask(params, trigger_type_string, rno_strings)
        if (debug_mask & 0x4) != 0:
            print(f'DataFileChecks Debug: the fragment error bitmask is {hex(error_bitmask)} for TC type {trigger_type_string} and record ordinal strings {rno_strings}')
        if error_bitmask not in error_mask_list:
            error_mask_list.append(error_bitmask)
        if subdet_string == "":
            src_ids = h5_file.get_source_ids_for_fragment_type(rec, params['fragment_type'])
        else:
            src_ids = h5_file.get_source_ids_for_fragtype_and_subdetector(rec, params['fragment_type'], subdet_string)
        for src_id in src_ids:
            frag=h5_file.get_frag(rec,src_id);
            error_bits=frag.get_error_bits()
            if (debug_mask & 0x8) != 0:
                print(f'  DataFileChecks Debug: fragment error bits for SourceID {src_id} are {hex(error_bits)}')
            if error_bits & error_bitmask != 0:
                passed=False
                print(f" \N{POLICE CARS REVOLVING LIGHT} {params['fragment_type_description']} fragment for SrcID {src_id.to_string()} in record {rec} has the following unmasked error flags set: {get_set_error_bit_names(error_bits & error_bitmask)} \N{POLICE CARS REVOLVING LIGHT}")
    if passed:
        error_mask_list.sort()
        print(f"\N{WHITE HEAVY CHECK MARK} All {params['fragment_type_description']} fragments in {len(records)} records have no error flags set (after applying bitmasks)")
    return passed

def check_n_unique_sids(datafile, expected_sids_tp, expected_sids_ta, expected_sids_tc):
    """
    Checks that the number of unique Source IDs in the HDF5 data file matches expectations
    for each trigger object type: Trigger Primitive, Trigger Activity, and Trigger Candidate.

    Parameters:
        datafile: A pathlib.Path or similar object pointing to the raw HDF5 file.
        expected_sids_tp (int): Expected number of unique Source IDs for Trigger Primitives.
        expected_sids_ta (int): Expected number of unique Source IDs for Trigger Activities.
        expected_sids_tc (int): Expected number of unique Source IDs for Trigger Candidates.

    Returns:
        bool: True if all expected Source ID counts match, False otherwise.
    """
    passed=True
    h5_file = HDF5RawDataFile(datafile.name)
    records = h5_file.get_all_record_ids()
    all_sids_tps = set()
    all_sids_tas = set()
    all_sids_tcs = set()
    for rec in records:
        sids_tps = h5_file.get_source_ids_for_fragment_type(rec, 'Trigger_Primitive')
        all_sids_tps.update( sid_key(sid) for sid in sids_tps )
        sids_tas = h5_file.get_source_ids_for_fragment_type(rec, 'Trigger_Activity')
        all_sids_tas.update( sid_key(sid) for sid in sids_tas )
        sids_tcs = h5_file.get_source_ids_for_fragment_type(rec, 'Trigger_Candidate')
        all_sids_tcs.update( sid_key(sid) for sid in sids_tcs )
    try:
        assert len(all_sids_tps) == expected_sids_tp
        assert len(all_sids_tas) == expected_sids_ta
        assert len(all_sids_tcs) == expected_sids_tc
        return True
    except AssertionError:
        return False

def check_tr_trigger_types(datafile, expected_tr_types_list):
    """
    Test that the datafile contains the expected TC types (and only those).
    Expected Behavior:
        Confirms whether the expected TC types (provided) are identical to
        those extracted from the data file.
    Parameters:
        datafile: name of the raw HDF5 datafile
        expected_tr_types_list: list of strings representing trgdataformats TC types
    Returns:
        bool: True if TC types match, False otherwise
    """
    h5_file = HDF5RawDataFile(datafile.name)
    expected_tc_bits = convert_TR_strings_to_types(expected_tr_types_list)
    extracted_tr_types = get_TR_trigger_types(h5_file)
    unpacked_tr_types = unpack_TR_trigger_types(extracted_tr_types)
    unpacked_tc_bits = convert_TR_type_to_TC_bit(unpacked_tr_types)
    #print("TR TYPES CHECK!")
    #print("expected types as string:", expected_tr_types_list)
    #print("expected types as bits:", expected_tc_bits)
    #print("extracted tr types:", extracted_tr_types)
    #print("unpacked tr types:", unpacked_tr_types)
    #print("unpacked tc bits:", unpacked_tc_bits)

    if expected_tc_bits != unpacked_tc_bits:
        print(f"Trigger bits do not match: expected {expected_tc_bits} != extracted {unpacked_tc_bits}")
        return False

    return True

def check_tr_type_multiplicity(datafile, multi_required):
    """
    Test whether the datafile contains a TR trigger with multiplicity (i.e., merged TC types).
    Parameters:
        datafile: name of the raw HDF5 datafile
        multi_required: boolean indicating whether multiplicity is expected
    Returns:
        bool: True if multiplicity matches expectation, False otherwise
    """
    h5_file = HDF5RawDataFile(datafile.name)
    extracted_tr_types = get_TR_trigger_types(h5_file)
    is_multi = check_multi_TR_type(extracted_tr_types)
    #print("TR TYPES MULTI CHECK!")
    #print("is multi expected:", multi_required)
    #print("is multi extracted:", is_multi)

    if multi_required != is_multi:
        print(f"Trigger types multiplicity mismatch: expected {multi_required}, got {is_multi}")
        return False

    return True

def trigger_sanity_checks():
    all_ok = trigger_functions_checks()
    if all_ok:
        print(f"\n\N{WHITE HEAVY CHECK MARK} All trigger sanity checks passed successfully.")
    else:
        print(f"\n\N{POLICE CARS REVOLVING LIGHT} Some trigger sanity checks FAILED. Please review the errors above.")

