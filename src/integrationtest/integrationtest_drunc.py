import pytest
import subprocess
import pathlib
import getpass
import os
import re
import sys
import time
import asyncio
import random
import json
import copy
from io import StringIO
import conffwk
from integrationtest.integrationtest_commandline import file_exists
from integrationtest.resource_validation import ResourceValidator
from integrationtest.verbosity_helper import *
from integrationtest.data_classes import *
from integrationtest.async_proc_mgmt import *
from integrationtest.utility_functions import delete_file
from daqconf.generate_hwmap import generate_hwmap
from daqconf.generate import (
    generate_readout,
    generate_fakedata,
    generate_trigger,
    generate_hsi,
    generate_dataflow,
    generate_session,
)
from daqconf.consolidate import consolidate_files, consolidate_db, copy_configuration
from daqconf.set_connectivity_service_port import (
    set_connectivity_service_port,
)
from daqconf.set_rc_controller_port import (
    set_rc_controller_port,
)
from daqconf.set_session_env_var import (
    set_session_env_var,
)
from daqconf.get_session_apps import get_segment_apps


# keep track of the number of parametrizations (for various display uses)
total_paramtrization_combinations = 0
parametrization_counter = 0


def parametrize_fixture_with_items(metafunc, fixture, itemsname):
    """Parametrize a fixture using the contents of variable `listname`
    from module scope. We want to distinguish between the cases where
    the list is a list of strings, and a list of lists of strings. We
    do this by checking whether the first item in the list is a
    string. Not perfect, but better than nothing

    """
    the_items = getattr(metafunc.module, itemsname)
    if isinstance(the_items, dict):
        metafunc.parametrize(
            fixture, the_items.values(), ids=the_items.keys(), indirect=True
        )
    elif isinstance(the_items, list) or isinstance(the_items, tuple):
        if type(the_items[0]) == str:
            params = [the_items]
        else:
            params = the_items
        metafunc.parametrize(fixture, params, indirect=True)


def pytest_generate_tests(metafunc):
    # We want to be able to run multiple confgens and multiple DAQ
    # sessions from one pytest module, but the fixtures for running the
    # external commands are module-scoped, so we need to parametrize
    # the fixtures. This could be done by adding "params=..." to the
    # @pytest.fixture decorator at each fixture, but the user doesn't
    # have access to that point in the code. So instead we pull
    # variables from the module (which the user _does_ have access to)
    # and parametrize the fixtures here in pytest_generate_tests,
    # which is run at pytest startup


    # Feb 2026, KAB, Handle run control process manager types...
    # Choices provided on the command-line, via the --process-manager-type
    #    option, have the highest priority. The possible values that can be
    #    specified for this option include a pipe-delimited list of PM types.
    # If no choices were provided on the command-line, then we check for
    #    choice(s) specified in the pytest module file (aka one of our
    #    'integtest' files). For this, we check for a variable named
    #    'process_manager_choices'.
    # If neither of those two ways of specifying the PM type were used in
    #    the current testing, then we default to the SSH standalone PM type.
    # In all cases, we want to create a dictionary that has a descriptive name
    #    and the PM type for each entry
    cmdline_pmtype = metafunc.config.getoption("--process-manager-type")
    if cmdline_pmtype:  # a PM type was specified on the command line
        # translate the one or more PM types into a dictionary
        pmtype_dict = {}
        type_list = cmdline_pmtype.split('|')
        for pm_type in type_list:
            type_name = pm_type.upper()+"_PM"
            type_name = type_name.replace("-", "_")
            addl_dict_entry = {type_name : pm_type}
            pmtype_dict.update(addl_dict_entry)
        # assign this new dictionary to the metafunc.module parameter used later
        metafunc.module.process_manager_choices = pmtype_dict
    elif not hasattr(metafunc.module, "process_manager_choices"):
        # create an entry for the default choice of ssh-standalone
        metafunc.module.process_manager_choices = { "StandAloneSSH_PM" : "ssh-standalone" }

    parametrize_fixture_with_items(metafunc, "create_config_files", "confgen_arguments")
    parametrize_fixture_with_items(metafunc, "process_manager_type", "process_manager_choices")
    if hasattr(metafunc.module, "daq_session_ingredients"):
        parametrize_fixture_with_items(metafunc, "run_dunerc", "daq_session_ingredients")
    else:
        parametrize_fixture_with_items(metafunc, "run_dunerc", "dunerc_command_list")

    # determine the number of different parametrizations
    # (recall that this fixture is called once per pytest function in each integtest)
    # (we only need to calculate this value once, so we check the initial value of zero)
    global total_paramtrization_combinations
    if total_paramtrization_combinations == 0:
        total_paramtrization_combinations = len(metafunc.module.confgen_arguments) * len(metafunc.module.process_manager_choices)
        if hasattr(metafunc.module, "dunerc_command_list"):
            if type(metafunc.module.dunerc_command_list) is dict:
                total_paramtrization_combinations *= len(metafunc.module.dunerc_command_list)


@pytest.fixture(scope="module")
def process_manager_type(request):
    """Simply return the process manager type that was requested
    """
    yield request.param


@pytest.fixture(scope="module")
def create_config_files(request, tmp_path_factory, check_system_resources):
    """Run the confgen to produce the configuration json files

    The parameters for the DUNE-DAQ configuration are taken from the
    `confgen_arguments` variable in the global scope of the test module.
    This variable is converted into parameters for this fixture by the
    pytest_generate_tests function, to allow multiple confgens to be
    produced by one pytest module

    """
    dummy_resource_check = check_system_resources
    integtest_params = request.param

    #if isinstance(integtest_params, integtest_params_for_generated_dunedaq_config):
    #    print("*** integtest_params is of type integtest_params_for_generated_dunedaq_config")
    #if isinstance(integtest_params, integtest_params_for_predefined_dunedaq_config):
    #    print("*** integtest_params is of type integtest_params_for_predefined_dunedaq_config")
    if not isinstance(integtest_params, integtest_params_for_generated_dunedaq_config) \
       and not isinstance(integtest_params, integtest_params_for_predefined_dunedaq_config):
        fail_msg = f"The integtest configuration object has an invalid type: {type(integtest_params)}"
        pytest.fail(fail_msg, pytrace=False)

    no_integtest_connsvc = request.config.getoption("--no-integtest-connsvc")
    skip_resource_checks = request.config.getoption("--skip-resource-checks")

    if no_integtest_connsvc and \
       isinstance(integtest_params, integtest_params_for_generated_dunedaq_config):
        integtest_params.connsvc_control = ConnSvcControl.NONE

    # 06-Mar-2026, KAB: if the DAQ session name has not explicitly been set by the
    # user, set it here so that we can make use of it from this point onward.
    if not integtest_params.daq_session_name:
        integtest_params.daq_session_name = integtest_params.config_session_name

    # 26-Mar-2026, KAB: suppress output messages, if requested
    verbosity_level = int(request.config.getoption("--integtest-verbosity"))
    if verbosity_level >= IntegtestVerbosityLevels.integtest_debug:
        print("", flush=True)
    original_stdout = sys.stdout
    if verbosity_level < IntegtestVerbosityLevels.full_output:
        if verbosity_level >= IntegtestVerbosityLevels.integtest_debug:
            print("----------------------------------------", flush=True)
            print("*** Messages related to configuration generation have been suppressed ***", flush=True)
            print("----------------------------------------", flush=True)
            print("", flush=True)
        sys.stdout = catcher = StringIO()

    config_dir = tmp_path_factory.mktemp("config")
    config_db = config_dir / "integtest-session-resolved.data.xml"
    temp_config_db = config_dir / "integtest-session.data.xml"
    logfile = tmp_path_factory.getbasetemp() / f"stdouterr{request.param_index}.txt"

    if isinstance(integtest_params, integtest_params_for_predefined_dunedaq_config):
        integtest_conf = integtest_params.predefined_config_db
        # 10-Jun-2026, KAB: added support for finding the specified config_db file
        # in one of the directories listed in the DUNEDAQ_DB_PATH env var
        found_file = file_exists(integtest_conf)
        if not found_file:
            try:
                # the name of a file somewhere in the DB path shouldn't have a leading slash,
                # so we'll provide that little bit of helpfulness here
                integtest_conf = integtest_conf.lstrip("/")
                path_string = os.environ["DUNEDAQ_DB_PATH"]
                directories = path_string.split(":")
                found_file = any((pathlib.Path(dd) / integtest_conf).is_file() for dd in directories if dd)
            except KeyError:
                pass
        if found_file:
            print(f"Integtest preconfigured config file: {integtest_conf}")
            consolidate_files(str(temp_config_db), integtest_conf)
        else:
            fail_msg = f"The file containing the predefined dunedaq configuration \"{integtest_conf}\" could not be found either from its absolute location or in any of the paths in DUNEDAQ_DB_PATH."
            pytest.fail(fail_msg, pytrace=False)
    else:
        dro_map_file = config_dir / "ReadoutMap.data.xml"
        readout_db = config_dir / "readout-segment.data.xml"
        dataflow_db = config_dir / "df-segment.data.xml"
        trigger_db = config_dir / "trg-segment.data.xml"
        hsi_db = config_dir / "hsi-segment.data.xml"

        local_object_databases = copy_configuration(config_dir, integtest_params.object_databases)

        if not integtest_params.use_fakedataprod:
            if not file_exists(dro_map_file):
                dro_map_config = integtest_params.dro_map_config
                if dro_map_config != None:
                    generate_hwmap(
                        str(dro_map_file),
                        dro_map_config.n_streams,
                        dro_map_config.n_apps,
                        dro_map_config.det_id,
                        dro_map_config.app_host,
                        dro_map_config.eth_protocol,
                        dro_map_config.flx_mode,
                        dro_map_config.crate_id_offset,
                        dro_map_config.slot_id,
                    )

            if not file_exists(readout_db):
                generate_readout(
                    readoutmap=str(dro_map_file),
                    oksfile=str(readout_db),
                    include=local_object_databases,
                    generate_segment=True,
                    emulated_file_name=integtest_params.frame_file,
                    tpg_enabled=integtest_params.tpg_enabled,
                )
        elif not file_exists(readout_db):
            generate_fakedata(
                oksfile=str(readout_db),
                include=local_object_databases,
                generate_segment=True,
                n_streams=integtest_params.dro_map_config.n_streams,
                n_apps=integtest_params.dro_map_config.n_apps,
                det_id=integtest_params.dro_map_config.det_id,
                fragment_type=integtest_params.fake_data_fragment_type,
            )

        generate_trigger(
            oksfile=str(trigger_db),
            include=local_object_databases,
            generate_segment=True,
            tpg_enabled=integtest_params.tpg_enabled,
            hsi_enabled=integtest_params.fake_hsi_enabled,
        )
        if integtest_params.fake_hsi_enabled:
            generate_hsi(
                oksfile=str(hsi_db),
                include=local_object_databases,
                generate_segment=True,
            )
        generate_dataflow(
            oksfile=str(dataflow_db),
            include=local_object_databases,
            n_dfapps=integtest_params.n_df_apps,
            tpwriting_enabled=integtest_params.tpg_enabled,
            generate_segment=True,
            n_data_writers=integtest_params.n_data_writers,
            trmon_app=integtest_params.trmon_app_enabled,
        )

        runcontrol_starts_connsvc = integtest_params.connsvc_control == ConnSvcControl.RUNCONTROL
        generate_session(
            oksfile=str(temp_config_db),
            include=local_object_databases
            + [str(readout_db), str(trigger_db), str(dataflow_db)]
            + ([str(hsi_db)] if integtest_params.fake_hsi_enabled else []),
            session_name=integtest_params.config_session_name,
            op_env=integtest_params.op_env,
            connectivity_service_is_infrastructure_app=runcontrol_starts_connsvc,
            disable_connectivity_service=no_integtest_connsvc,
        )

    consolidate_db(str(temp_config_db), str(config_db))
    if integtest_params.connsvc_port is not None:
        integtest_params.connsvc_port = set_connectivity_service_port(
            oksfile=str(config_db),
            session_name=integtest_params.config_session_name,
            connsvc_port=integtest_params.connsvc_port, # Default is 0, which causes random port to be selected
        )
    # 05-Nov-2025, KAB, MiR: added the setting of a random RC port
    set_rc_controller_port(oksfile=str(config_db), session_name=integtest_params.config_session_name, rc_port=0)

    # 03-Jul-2025, KAB: added the setting of the TRACE_FILE env var in the OKS Session,
    # if it is set in the user's environment, and if it is not already set in the configuration.
    try:
        trace_file_env_var = os.environ["TRACE_FILE"]
        set_session_env_var(str(config_db), integtest_params.config_session_name, "TRACE_FILE", trace_file_env_var, overwrite=False)
    except KeyError:
        pass

    dal = conffwk.dal.module("generated", "schema/appmodel/fdmodules.schema.xml")
    db = conffwk.Configuration("oksconflibs:" + str(config_db))

    def apply_update(obj, substitution):
        # 27-Aug-2025, KAB: modified this code to support different types of substitutions
        if isinstance(substitution, list_element_addition):
            additional_obj = db.get_dal(substitution.additional_object_class, substitution.additional_object_id)
            the_list = getattr(obj, substitution.rel_name)
            the_list.append(additional_obj)
            setattr(obj, substitution.rel_name, the_list)
        elif isinstance(substitution, list_element_substitution):
            replacement_obj = db.get_dal(substitution.replacement_object_class, substitution.replacement_object_id)
            the_list = getattr(obj, substitution.rel_name)
            the_list[substitution.list_index] = replacement_obj
            setattr(obj, substitution.rel_name, the_list)
        elif isinstance(substitution, relationship_substitution):
            replacement_obj = db.get_dal(substitution.replacement_object_class, substitution.replacement_object_id)
            setattr(obj, substitution.rel_name, replacement_obj)
        elif isinstance(substitution, attribute_substitution):
            for name, value in substitution.updates.items():
                setattr(obj, name, value)
        else:
            print(f"*** ERROR: Unexpected configuration substitution type *** (\"{substitution}\")")

        db.update_dal(obj)

    for substitution in integtest_params.config_substitutions:
        if substitution.obj_id != "*":
            obj = db.get_dal(class_name=substitution.obj_class, uid=substitution.obj_id)
            apply_update(obj, substitution)
        else:
            objs = db.get_dals(class_name=substitution.obj_class)
            for obj in objs:
                apply_update(obj, substitution)

    db.commit()

    # 30-Dec-2024, KAB: build up the list of directories used for writing raw and TPStream data
    sessionobj = db.get_dal(class_name="Session", uid=integtest_params.config_session_name)
    rawdata_dirs = []
    tpstream_dirs = []
    trmon_dirs = []
    segment = sessionobj.segment
    app_list = get_segment_apps(segment)
    for app in app_list:
        try:
            dfapp = db.get_dal(class_name="DFApplication", uid=app)
            for dw in dfapp.data_writers:
                outdir = dw.data_store_params.directory_path
                if outdir not in rawdata_dirs:
                    rawdata_dirs.append(outdir)
        except:
            # not a DFApplication, so simply continue to the next app
            pass
        try:
            tpswapp = db.get_dal(class_name="TPStreamWriterApplication", uid=app)
            outdir = tpswapp.tp_writer.data_store_params.directory_path
            if outdir not in tpstream_dirs:
                tpstream_dirs.append(outdir)
        except:
            # not a TPStreamWriterApplication, so simply continue to the next app
            pass
        try:
            trmonapp = db.get_dal(class_name="TRMonReqApplication", uid=app)
            outdir = trmonapp.data_store_params.directory_path
            if outdir not in trmon_dirs:
                trmon_dirs.append(outdir)
        except:
            # not a TPStreamWriterApplication, so simply continue to the next app
            pass

    result = CreateConfigResult(
        integtest_params=integtest_params,
        dunedaq_config_dir=config_dir,
        dunedaq_config_file=config_db,
        log_file=logfile,
        data_dirs=rawdata_dirs,
        tpstream_data_dirs=tpstream_dirs,
        trmon_data_dirs=trmon_dirs
    )

    # restore the usual stdout behavior, if needed
    if verbosity_level < IntegtestVerbosityLevels.full_output:
        sys.stdout = original_stdout
    else:
        print("", flush=True)
    yield result


@pytest.fixture(scope="module")
def run_dunerc(request, create_config_files, process_manager_type, cleanup_hdf5_files, tmp_path_factory):
    """Run drunc with the OKS DB files created by `create_config_files`. The
    commands specified by the `dunerc_command_list` variable in the
    test module are executed. If `dunerc_command_list`'s items are
    themselves lists, then drunc will be run multiple times, once for
    each set of arguments in the list

    """
    run_control_commands = request.param

    # determine which type of request this is, either a list of commands for dunerc or a more
    # sophisticated list of applications to be started and the commands to be sent to them
    user_supplied_apps = False
    if type(run_control_commands) is DAQSessionIngredients:
        user_supplied_apps = True

    no_integtest_connsvc = request.config.getoption("--no-integtest-connsvc")
    verbosity_level = int(request.config.getoption("--integtest-verbosity"))

    if no_integtest_connsvc and \
       isinstance(create_config_files.integtest_params, integtest_params_for_generated_dunedaq_config):
        create_config_files.integtest_params.connsvc_control = ConnSvcControl.NONE

    run_dir = tmp_path_factory.mktemp("run")

    global total_paramtrization_combinations
    if total_paramtrization_combinations > 1:
        global parametrization_counter
        parametrization_counter += 1
        if parametrization_counter > 1:
            if verbosity_level > IntegtestVerbosityLevels.just_errors_and_warnings and \
               verbosity_level < IntegtestVerbosityLevels.integtest_debug:
                print("", flush=True)
                print("", flush=True)

        if verbosity_level > IntegtestVerbosityLevels.just_errors_and_warnings:
            current_test = os.environ.get("PYTEST_CURRENT_TEST")
            match_obj = re.search(r".*\[(.+)-run_.*rc.*\d\].*", current_test)
            if match_obj:
                current_test = match_obj.group(1)
            else:
                match_obj = re.search(r".*\[(.+)\].*", current_test)
                if match_obj:
                    current_test = match_obj.group(1)
            print(f"-> {current_test} <-")


    # 15-Dec-2025, KAB: if one of our integtest bundle scripts has provided information
    # about itself in the execution environment of the currently running test, use that
    # information to create a file in the 'run' directory of the test. This is used by the
    # bundle script to locate which pytest directory on disk matches the running of which test.
    try:
        bundle_script_info = os.environ["DUNEDAQ_INTEGTEST_BUNDLE_INFO"]
        info_list = bundle_script_info.split(';')
        if (len(info_list) == 3):
            bundle_info_data = {
                "description": "This file was automatically generated by the DUNE DAQ integrationtest infrastructure. It contains information about the 'bundle' script that ran this test.",
                "bundle_script_start_time": info_list[0],
                "bundle_script_process_id": info_list[1],
                "individual_test_start_time": info_list[2]
                }
            bundle_file_name = f"{run_dir}/bundle_script_info.json"
            try:
                with open(f"{bundle_file_name}", "w") as info_file:
                    json.dump(bundle_info_data, info_file, indent=2)
            except FileNotFoundError:
                print(f"\n*** Warning: unable to write bundle info data to file {bundle_file_name}")
        else:
            print("\n*** Warning: the DUNEDAQ_INTEGTEST_BUNDLE_INFO env var is set, but it doesn't seem")
            print(  "    to contain the expected 3 values that are used to help bundle scripts match")
            print(  "    pytest directories to individual tests that are run.")
            print( f"    Contents of the env var: '{bundle_script_info}'")
    except KeyError:
        # if the expected env var is not set, we simply don't create the bundle info file
        pass

    # start the Connectivity Service, if requested (only supported for generated dune-daq configs, for now)
    connsvc_obj = None
    if (
        isinstance(create_config_files.integtest_params, integtest_params_for_generated_dunedaq_config)
        and create_config_files.integtest_params.connsvc_control == ConnSvcControl.INTEGRATIONTEST
    ):
        # start connsvc
        if verbosity_level >= IntegtestVerbosityLevels.full_output:
            print(
                f"Starting Connectivity Service on port {create_config_files.integtest_params.connsvc_port}"
            )

        connsvc_env = os.environ.copy()
        if create_config_files.integtest_params.connsvc_debug_level is not None:
            connsvc_env["CONNECTION_FLASK_DEBUG"] = str(
                create_config_files.integtest_params.connsvc_debug_level
            )

        connsvc_log = open(
            run_dir
            / f"log_{getpass.getuser()}_{create_config_files.integtest_params.daq_session_name}_connectivity-service.txt",
            "w",
        )
        connsvc_obj = subprocess.Popen(
            f"gunicorn -b 0.0.0.0:{create_config_files.integtest_params.connsvc_port} --workers=1 --worker-class=gthread --threads=2 --timeout 5000000000 --log-level=info connectivityserver.connectionflask:app".split(),
            stdout=connsvc_log,
            stderr=connsvc_log,
            env=connsvc_env,
        )

    elif create_config_files.integtest_params.connsvc_debug_level is not None:
        set_session_env_var(str(create_config_files.dunedaq_config_file), create_config_files.integtest_params.config_session_name,
                            "CONNECTION_FLASK_DEBUG", create_config_files.integtest_params.connsvc_debug_level, overwrite=True)

    dunerc = request.config.getoption("--dunerc-path")
    if dunerc is None:
        dunerc = "drunc-unified-shell"
    dunerc_options = request.config.getoption("--dunerc-option")
    dunerc_option_strings = []
    if dunerc_options is not None:
        for opt in dunerc_options:
            if len(opt) > 2:
                print("dunerc options take either 0 or 1 arguments!")
                pytest.fail()
            if len(opt[0]) == 1:
                dunerc_option_strings.append("-" + "".join(opt))
            else:
                dunerc_option_strings.append("--" + opt[0])
                if len(opt) == 2:
                    dunerc_option_strings.append(opt[1])

    class RunResult:
        pass

    # 28-Jun-2022, KAB: added the ability to handle a non-standard output directory
    rawdata_dirs = [run_dir]
    rawdata_paths = create_config_files.data_dirs
    tpset_dirs = [run_dir]
    tpset_paths = create_config_files.tpstream_data_dirs
    trmon_dirs = [run_dir]
    trmon_paths = create_config_files.trmon_data_dirs

    # suppress output, if requested
    original_stdout = sys.stdout
    if verbosity_level < IntegtestVerbosityLevels.full_output:
        sys.stdout = catcher = StringIO()

    for path in rawdata_paths:
        rawdata_dir = pathlib.Path(path)
        if rawdata_dir not in rawdata_dirs:
            rawdata_dirs.append(rawdata_dir)
        # deal with any pre-existing data files
        temp_suffix = ".temp_saved"
        now = time.time()
        for file_obj in rawdata_dir.glob(
            f"{create_config_files.integtest_params.op_env}_raw*.hdf5"
        ):
            print(f"Renaming raw data file from earlier test: {str(file_obj)}")
            new_name = str(file_obj) + temp_suffix
            file_obj.rename(new_name)
        for file_obj in rawdata_dir.glob(
            f"{create_config_files.integtest_params.op_env}_raw*.hdf5{temp_suffix}"
        ):
            modified_time = file_obj.stat().st_mtime
            if (now - modified_time) > 3600:
                print(f"Deleting raw data file from earlier test: {str(file_obj)}")
                file_obj.unlink(True)  # missing is OK
    for tpset_path in tpset_paths:
        tpset_dir = pathlib.Path(tpset_path)
        if tpset_dir not in tpset_dirs:
            tpset_dirs.append(tpset_dir)
        # deal with any pre-existing data files
        temp_suffix = ".temp_saved"
        now = time.time()
        for file_obj in tpset_dir.glob(
            f"{create_config_files.integtest_params.op_env}_tp*.hdf5"
        ):
            print(f"Renaming TP data file from earlier test: {str(file_obj)}")
            new_name = str(file_obj) + temp_suffix
            file_obj.rename(new_name)
        for file_obj in tpset_dir.glob(
            f"{create_config_files.integtest_params.op_env}_tp*.hdf5{temp_suffix}"
        ):
            modified_time = file_obj.stat().st_mtime
            if (now - modified_time) > 3600:
                print(f"Deleting TP data file from earlier test: {str(file_obj)}")
                file_obj.unlink(True)  # missing is OK
    for trmon_path in trmon_paths:
        trmon_dir = pathlib.Path(trmon_path)
        if trmon_dir not in trmon_dirs:
            trmon_dirs.append(trmon_dir)
        # deal with any pre-existing data files
        temp_suffix = ".temp_saved"
        now = time.time()
        for file_obj in trmon_dir.glob(
            f"{create_config_files.integtest_params.op_env}_trmon*.hdf5"
        ):
            print(f"Renaming TRMon data file from earlier test: {str(file_obj)}")
            new_name = str(file_obj) + temp_suffix
            file_obj.rename(new_name)
        for file_obj in trmon_dir.glob(
            f"{create_config_files.integtest_params.op_env}_trmon*.hdf5{temp_suffix}"
        ):
            modified_time = file_obj.stat().st_mtime
            if (now - modified_time) > 3600:
                print(f"Deleting TRMon data file from earlier test: {str(file_obj)}")
                file_obj.unlink(True)  # missing is OK

    # restore the usual stdout behavior, if needed
    if verbosity_level < IntegtestVerbosityLevels.full_output:
        sys.stdout = original_stdout

    exit_cmd = DAQCommandSet("drunc", [ "exit" ], CommandWaitParameters(style=CommandWaitStyle.TIME))
    if user_supplied_apps:
        dsi = run_control_commands
        for app in dsi.applications:
            tmp_exit_cmd = copy.deepcopy(exit_cmd)
            tmp_exit_cmd.target = app.alias
            dsi.commands.append(tmp_exit_cmd)

            for idx in range(len(app.startup_strings)):
                if app.startup_strings[idx] == "<proc_mgr_choice>":
                    app.startup_strings[idx] = str(process_manager_type)
                    continue
                if app.startup_strings[idx] == "<config_data_file>":
                    app.startup_strings[idx] = str(create_config_files.dunedaq_config_file)
                    continue
                if app.startup_strings[idx] == "<config_session_name>":
                    app.startup_strings[idx] = str(create_config_files.integtest_params.config_session_name)
                    continue
                if app.startup_strings[idx] == "<daq_session_name>":
                    app.startup_strings[idx] = str(create_config_files.integtest_params.daq_session_name)
                    continue

            if len(dunerc_option_strings) > 0 and app.alias == "drunc":
                app.startup_strings[1:1] = dunerc_option_strings
    else:
        popen_command_list = [dunerc] + create_config_files.integtest_params.dunerc_cmd_args \
            + dunerc_option_strings + [process_manager_type] + [str(create_config_files.dunedaq_config_file)] \
            + [str(create_config_files.integtest_params.config_session_name)] \
            + [str(create_config_files.integtest_params.daq_session_name)]

        dsapp = DAQSessionApp("drunc", popen_command_list)

        requested_cmds = DAQCommandSet("drunc", run_control_commands, CommandWaitParameters(style=CommandWaitStyle.ECHO))

        app_list = [ dsapp ]
        cmd_set_list = [ requested_cmds, exit_cmd ]
        dsi = DAQSessionIngredients(app_list, cmd_set_list)

    result = RunResult()
    time_before = time.time()

    proc_results = asyncio.run(intg_process_manager(dsi, run_dir, verbosity_level))

    time_after = time.time()

    # construct a CompletedProcess instance for each application that was run.
    result.completed_processes = {}
    for app in dsi.applications:
        result.completed_processes[app.alias] = subprocess.CompletedProcess(
            app.startup_strings,
            returncode=proc_results[app.alias]["returncode"],
            stdout=proc_results[app.alias]["stdout"]
        )

    if connsvc_obj is not None:
        time.sleep(1)
        connsvc_obj.send_signal(2)
        try:
            connsvc_obj.wait(0.5)
        except:
            pass
        connsvc_obj.kill()

    if create_config_files.integtest_params.attempt_cleanup:
        print(
            "Checking for remaining gunicorn and drunc-controller processes", flush=True
        )
        subprocess.run(["killall", "gunicorn", "drunc-controller"])

    result.confgen_config = create_config_files.integtest_params
    result.config_session_name = create_config_files.integtest_params.config_session_name
    result.daq_session_name = create_config_files.integtest_params.daq_session_name
    result.dunerc_commands = run_control_commands
    result.run_dir = run_dir
    result.dunedaq_config_dir = create_config_files.dunedaq_config_dir
    result.data_files = []
    for rawdata_dir in rawdata_dirs:
        result.data_files += list(
            rawdata_dir.glob(f"{create_config_files.integtest_params.op_env}_raw_*.hdf5")
        )
    result.tpset_files = []
    for tpset_dir in tpset_dirs:
        result.tpset_files += list(
            tpset_dir.glob(f"{create_config_files.integtest_params.op_env}_tp_*.hdf5")
        )
    result.trmon_files = []
    for trmon_dir in trmon_dirs:
        result.trmon_files += list(
            trmon_dir.glob(f"{create_config_files.integtest_params.op_env}_trmon_*.hdf5")
        )
    result.log_files = list(run_dir.glob("log_*.txt")) + list(run_dir.glob("log_*.log"))
    result.opmon_files = list(run_dir.glob(f"info*{result.daq_session_name}*.json"))
    # 10-Dec-2025, KAB: added the DAQ session overall time so that we can use this
    # information in fine-tuning the allowed ranges in time-based checking of test results.
    result.daq_session_overall_time = time_after - time_before
    result.verbosity_helper = VerbosityHelper(verbosity_level)

    # pass the names of the HDF5 files to the 'cleanup' fixture
    cleanup_hdf5_files["raw"] = result.data_files
    cleanup_hdf5_files["tpset"] = result.tpset_files
    cleanup_hdf5_files["trmon"] = result.trmon_files

    yield result


import functools
print = functools.partial(print, flush=True)  # always flush print() output

@pytest.fixture(scope="module")
def check_system_resources(request):
    """Check that the system resources (CPU, Memory) are sufficient for the test
    The required and recommended resources are taken from the
    `resource_validator` variable in the global scope of the test
    module, which should be an instance of ResourceValidator. If the
    required resources are not present, then the test is skipped. If
    the recommended resources are not present, then a warning is printed
    """
    skip_resource_checks = request.config.getoption("--skip-resource-checks")
    verbosity_level = int(request.config.getoption("--integtest-verbosity"))

    # print out a couple of blank lines to help with formatting
    if verbosity_level > IntegtestVerbosityLevels.just_errors_and_warnings:
        print("", flush=True)
        print("", flush=True)

    resval = getattr(request.module, "resource_validator", ResourceValidator())

    if verbosity_level >= IntegtestVerbosityLevels.integtest_debug:
        resval_debug_string = resval.get_debug_string()
        print(resval_debug_string)

    if not resval.required_resources_are_present:
        resval_report_string = resval.get_required_resources_report()
        print(f"\n\N{LARGE YELLOW CIRCLE} {resval_report_string}")
        if not skip_resource_checks:
            # 16-Feb-2026, KAB: discard all of the test items except the
            # first one so that we only get one "skip" output message.
            del request.session.items[1:]
            pytest.skip(f"\n\N{LARGE YELLOW CIRCLE} {resval_report_string}")
    if not resval.recommended_resources_are_present:
        if verbosity_level >= IntegtestVerbosityLevels.integtest_debug:
            resval_report_string = resval.get_recommended_resources_report()
            print(f"\n*** Note: {resval_report_string}")

    yield True

    # 16-Feb-2026, KAB: added a printout for recommended resources after the "yield"
    # statement so that it gets printed out at the end of the output that the user sees.
    if not resval.recommended_resources_are_present:
        if verbosity_level >= IntegtestVerbosityLevels.integtest_debug:
            resval_report_string = resval.get_recommended_resources_report()
            print(f"\n*** Note: {resval_report_string}")


@pytest.fixture(scope="module")
def cleanup_hdf5_files(request, create_config_files):
    """Delete the HDF5 files that are produced by the test, if requested
    """

    # nothing to be done during setup; all of the work happens during teardown
    # so, we simply return here
    # we return a dictionary that run_dunerc can fill with the names of the files
    file_lists = {}
    yield file_lists

    # here is where the work gets done...
    verbosity_level = int(request.config.getoption("--integtest-verbosity"))
    user_requests_hdf5_file_removal = request.config.getoption("--remove-hdf5-files")
    the_test_requests_hdf5_file_removal = create_config_files.integtest_params.remove_hdf5_files

    # if the user requested that the files should be kept, we can exit early
    if (user_requests_hdf5_file_removal is not None and
        ("false" in user_requests_hdf5_file_removal.lower() or
         "never" in user_requests_hdf5_file_removal.lower())):
        return

    # if either of the integtest writer or the user running the test requested that the HDF5 files
    # be deleted at the end of the test, do that.
    if ((user_requests_hdf5_file_removal is not None and
         ("true" in user_requests_hdf5_file_removal.lower() or
          "always" in user_requests_hdf5_file_removal.lower())) or
        the_test_requests_hdf5_file_removal):
        pathlist_string = ""
        filelist_string = ""
        for data_file in file_lists["raw"]:
            filelist_string += " " + str(data_file)
            if str(data_file.parent) not in pathlist_string:
                pathlist_string += " " + str(data_file.parent)
        for data_file in file_lists["tpset"]:
            filelist_string += " " + str(data_file)
            if str(data_file.parent) not in pathlist_string:
                pathlist_string += " " + str(data_file.parent)
        for data_file in file_lists["trmon"]:
            filelist_string += " " + str(data_file)
            if str(data_file.parent) not in pathlist_string:
                pathlist_string += " " + str(data_file.parent)

        if pathlist_string and filelist_string:
            if verbosity_level >= IntegtestVerbosityLevels.integtest_debug:
                print("============================================")
                print("Listing the hdf5 files before deleting them:")
                print("============================================")

                os.system(f"df -h {pathlist_string}")
                print("--------------------")
                os.system(f"ls -alF {filelist_string}")

            for data_file in file_lists["raw"]:
                delete_file(data_file)
            for data_file in file_lists["tpset"]:
                delete_file(data_file)
            for data_file in file_lists["trmon"]:
                delete_file(data_file)

            if verbosity_level >= IntegtestVerbosityLevels.integtest_debug:
                print("--------------------")
                os.system(f"df -h {pathlist_string}")
                print("============================================")
