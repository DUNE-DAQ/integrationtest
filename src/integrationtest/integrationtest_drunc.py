import pytest
import subprocess
import pathlib
import getpass
import os
import conffwk
from integrationtest.integrationtest_commandline import file_exists
from integrationtest.resource_validation import ResourceValidator
from integrationtest.data_classes import (
    CreateConfigResult,
    config_substitution,
    attribute_substitution,
    relationship_substitution,
    list_element_substitution,
    list_element_addition,
)
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
import time
import random
import json


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

    # 27-Feb-2026, KAB: support for the nanorc --> dunerc transition
    # We will be able to remove the following two lines once all integtests
    # have been converted to use dunerc instead of nanorc.
    if not hasattr(metafunc.module, "dunerc_command_list") and hasattr(metafunc.module, "nanorc_command_list"):
        metafunc.module.dunerc_command_list = metafunc.module.nanorc_command_list

    parametrize_fixture_with_items(metafunc, "create_config_files", "confgen_arguments")
    parametrize_fixture_with_items(metafunc, "process_manager_type", "process_manager_choices")

    # 27-Feb-2026, KAB: support for the nanorc --> dunerc transition
    # We will be able to just use "run_dunerc" once all integtests
    # have been converted to use dunerc instead of nanorc.
    if "run_nanorc" in metafunc.fixturenames:
        parametrize_fixture_with_items(metafunc, "run_nanorc", "dunerc_command_list")
    if "run_dunerc" in metafunc.fixturenames:
        parametrize_fixture_with_items(metafunc, "run_dunerc", "dunerc_command_list")


# 29-Dec-2025, KAB: added fixture to handle different process manager choices
@pytest.fixture(scope="module")
def process_manager_type(request, tmp_path_factory):
    yield request.param

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

    resval = getattr(request.module, "resource_validator", ResourceValidator())
    if not resval.required_resources_are_present:
        resval_report_string = resval.get_required_resources_report()
        print(f"\n\N{LARGE YELLOW CIRCLE} {resval_report_string}")
        if not skip_resource_checks:
            # 16-Feb-2026, KAB: discard all of the test items except the
            # first one so that we only get one "skip" output message.
            del request.session.items[1:]
            pytest.skip(f"\n\N{LARGE YELLOW CIRCLE} {resval_report_string}")
    if not resval.recommended_resources_are_present:
        resval_report_string = resval.get_recommended_resources_report()
        print(f"\n*** Note: {resval_report_string}")

    yield True

    # 16-Feb-2026, KAB: added a printout for recommended resources after the "yield"
    # statement so that it gets printed out at the end of the output that the user sees.
    if not resval.recommended_resources_are_present:
        resval_report_string = resval.get_recommended_resources_report()
        print(f"\n*** Note: {resval_report_string}")

@pytest.fixture(scope="module")
def create_config_files(request, tmp_path_factory, check_system_resources):
    """Run the confgen to produce the configuration json files

    The name of the module to use is taken (indirectly) from the
    `base_oks_config` variable in the global scope of the test module,
    and the arguments for the confgen are taken from the
    `confgen_arguments` variable in the same place. These variables
    are converted into parameters for this fixture by the
    pytest_generate_tests function, to allow multiple confgens to be
    produced by one pytest module

    """
    dummy_resource_check = check_system_resources
    drunc_config = request.param

    disable_connectivity_service = request.config.getoption(
        "--disable-connectivity-service"
    )
    skip_resource_checks = request.config.getoption(
        "--skip-resource-checks"
    )

    config_dir = tmp_path_factory.mktemp("config")
    boot_file = config_dir / "boot.json"
    configfile = config_dir / "config.json"
    dro_map_file = config_dir / "ReadoutMap.data.xml"
    readout_db = config_dir / "readout-segment.data.xml"
    dataflow_db = config_dir / "df-segment.data.xml"
    trigger_db = config_dir / "trg-segment.data.xml"
    hsi_db = config_dir / "hsi-segment.data.xml"
    config_db = config_dir / "integtest-session-resolved.data.xml"
    temp_config_db = config_dir / "integtest-session.data.xml"
    logfile = tmp_path_factory.getbasetemp() / f"stdouterr{request.param_index}.txt"

    integtest_conf = drunc_config.config_db

    object_databases = getattr(request.module, "object_databases", [])
    local_object_databases = copy_configuration(config_dir, object_databases)

    print()  # Blank line
    if file_exists(integtest_conf):
        print(f"Integtest preconfigured config file: {integtest_conf}")
        consolidate_files(str(temp_config_db), integtest_conf, *local_object_databases)
    else:
        if not drunc_config.use_fakedataprod:
            if not file_exists(dro_map_file):
                dro_map_config = drunc_config.dro_map_config
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
                    emulated_file_name=drunc_config.frame_file,
                    tpg_enabled=drunc_config.tpg_enabled,
                )
        elif not file_exists(readout_db):
            generate_fakedata(
                oksfile=str(readout_db),
                include=local_object_databases,
                generate_segment=True,
                n_streams=drunc_config.dro_map_config.n_streams,
                n_apps=drunc_config.dro_map_config.n_apps,
                det_id=drunc_config.dro_map_config.det_id,
                fragment_type=drunc_config.fake_data_fragment_type,
            )

        generate_trigger(
            oksfile=str(trigger_db),
            include=local_object_databases,
            generate_segment=True,
            tpg_enabled=drunc_config.tpg_enabled,
            hsi_enabled=drunc_config.fake_hsi_enabled,
        )
        if drunc_config.fake_hsi_enabled:
            generate_hsi(
                oksfile=str(hsi_db),
                include=local_object_databases,
                generate_segment=True,
            )
        generate_dataflow(
            oksfile=str(dataflow_db),
            include=local_object_databases,
            n_dfapps=drunc_config.n_df_apps,
            tpwriting_enabled=drunc_config.tpg_enabled,
            generate_segment=True,
            n_data_writers=drunc_config.n_data_writers,
            trmon_app=drunc_config.trmon_app_enabled,
        )

        generate_session(
            oksfile=str(temp_config_db),
            include=local_object_databases
            + [str(readout_db), str(trigger_db), str(dataflow_db)]
            + ([str(hsi_db)] if drunc_config.fake_hsi_enabled else []),
            session_name=drunc_config.session,
            op_env=drunc_config.op_env,
            connectivity_service_is_infrastructure_app=drunc_config.drunc_connsvc,
            disable_connectivity_service=disable_connectivity_service,
        )

    consolidate_db(str(temp_config_db), str(config_db))
    if drunc_config.connsvc_port is not None:
        drunc_config.connsvc_port = set_connectivity_service_port(
            oksfile=str(config_db),
            session_name=drunc_config.session,
            connsvc_port=drunc_config.connsvc_port, # Default is 0, which causes random port to be selected
        )
    # 05-Nov-2025, KAB, MiR: added the setting of a random RC port
    set_rc_controller_port(oksfile=str(config_db), session_name=drunc_config.session, rc_port=0)

    # 03-Jul-2025, KAB: added the setting of the TRACE_FILE env var in the OKS Session,
    # if it is set in the user's environment, and if it is not already set in the configuration.
    try:
        trace_file_env_var = os.environ["TRACE_FILE"]
        set_session_env_var(str(config_db), drunc_config.session, "TRACE_FILE", trace_file_env_var, overwrite=False)
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

    for substitution in drunc_config.config_substitutions:
        if substitution.obj_id != "*":
            obj = db.get_dal(class_name=substitution.obj_class, uid=substitution.obj_id)
            apply_update(obj, substitution)
        else:
            objs = db.get_dals(class_name=substitution.obj_class)
            for obj in objs:
                apply_update(obj, substitution)

    db.commit()

    # For preconfigured tests, disable starting the ConnSvc if the ConnectionService is an ifapp or unused
    sessionobj = db.get_dal(class_name="Session", uid=drunc_config.session)
    if sessionobj.connectivity_service is None:
        drunc_config.drunc_connsvc = True
    for if_app in sessionobj.infrastructure_applications:
        if if_app.className() == "ConnectionService":
            drunc_config.drunc_connsvc = True

    # 30-Dec-2024, KAB: build up the list of directories used for writing raw and TPStream data
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
        config=drunc_config,
        config_dir=config_dir,
        config_file=config_db,
        log_file=logfile,
        data_dirs=rawdata_dirs,
        tpstream_data_dirs=tpstream_dirs,
        trmon_data_dirs=trmon_dirs
    )

    yield result


# 27-Feb-2026, KAB: support for the nanorc --> dunerc transition
# Temporary fixture until all integtests have been changed to use "dunerc".
@pytest.fixture(scope="module")
def run_nanorc(run_dunerc):
    yield run_dunerc

@pytest.fixture(scope="module")
def run_dunerc(request, create_config_files, process_manager_type, tmp_path_factory):
    """Run drunc with the OKS DB files created by `create_config_files`. The
    commands specified by the `dunerc_command_list` variable in the
    test module are executed. If `dunerc_command_list`'s items are
    themselves lists, then drunc will be run multiple times, once for
    each set of arguments in the list

    """
    command_list = request.param

    disable_connectivity_service = request.config.getoption(
        "--disable-connectivity-service"
    )

    run_dir = tmp_path_factory.mktemp("run")

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

    connsvc_obj = None
    if (
        not disable_connectivity_service
        and not create_config_files.config.drunc_connsvc
        and create_config_files.config.connsvc_port is not None
    ):
        # start connsvc
        print(
            f"Starting Connectivity Service on port {create_config_files.config.connsvc_port}"
        )

        connsvc_env = os.environ.copy()
        connsvc_env["CONNECTION_FLASK_DEBUG"] = str(
            create_config_files.config.connsvc_debug_level
        )

        connsvc_log = open(
            run_dir
            / f"log_{getpass.getuser()}_{create_config_files.config.session}_connectivity-service.txt",
            "w",
        )
        connsvc_obj = subprocess.Popen(
            f"gunicorn -b 0.0.0.0:{create_config_files.config.connsvc_port} --workers=1 --worker-class=gthread --threads=2 --timeout 5000000000 --log-level=info connectivityserver.connectionflask:app".split(),
            stdout=connsvc_log,
            stderr=connsvc_log,
            env=connsvc_env,
        )

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

    for path in rawdata_paths:
        rawdata_dir = pathlib.Path(path)
        if rawdata_dir not in rawdata_dirs:
            rawdata_dirs.append(rawdata_dir)
        # deal with any pre-existing data files
        temp_suffix = ".temp_saved"
        now = time.time()
        for file_obj in rawdata_dir.glob(
            f"{create_config_files.config.op_env}_raw*.hdf5"
        ):
            print(f"Renaming raw data file from earlier test: {str(file_obj)}")
            new_name = str(file_obj) + temp_suffix
            file_obj.rename(new_name)
        for file_obj in rawdata_dir.glob(
            f"{create_config_files.config.op_env}_raw*.hdf5{temp_suffix}"
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
            f"{create_config_files.config.op_env}_tp*.hdf5"
        ):
            print(f"Renaming TP data file from earlier test: {str(file_obj)}")
            new_name = str(file_obj) + temp_suffix
            file_obj.rename(new_name)
        for file_obj in tpset_dir.glob(
            f"{create_config_files.config.op_env}_tp*.hdf5{temp_suffix}"
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
            f"{create_config_files.config.op_env}_trmon*.hdf5"
        ):
            print(f"Renaming TRMon data file from earlier test: {str(file_obj)}")
            new_name = str(file_obj) + temp_suffix
            file_obj.rename(new_name)
        for file_obj in trmon_dir.glob(
            f"{create_config_files.config.op_env}_trmon*.hdf5{temp_suffix}"
        ):
            modified_time = file_obj.stat().st_mtime
            if (now - modified_time) > 3600:
                print(f"Deleting TRMon data file from earlier test: {str(file_obj)}")
                file_obj.unlink(True)  # missing is OK

    print(
        "++++++++++ DRUNC Run BEGIN ++++++++++", flush=True
    )  # Apparently need to flush before subprocess.run
    result = RunResult()
    time_before = time.time()
    # 25-Mar-2026, KAB: use subprocess.Popen to manage the run control session so that we can
    # capture the console output and pass it back to the user for inspection and validation.
    rc_process = subprocess.Popen(
        [dunerc]
        + dunerc_option_strings
        + [process_manager_type]
        + [str(create_config_files.config_file)]
        + [str(create_config_files.config.session)]
        + [str(create_config_files.config.session_name if create_config_files.config.session_name else create_config_files.config.session)]
        + command_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=run_dir
    )

    # print out each line of captured output, as well as add it to the string that we
    # pass back to the user
    full_output = ""
    for line in rc_process.stdout:
        print(line, end='', flush=True)
        full_output += line

    rc_process.communicate()
    proc_returncode = rc_process.returncode

    # construct a CompletedProcess instance to be passed back to the user. In this way,
    # user code does not need to change in response to the change in this code from
    # using subprocess.run() to subprocess.Popen().
    result.completed_process = subprocess.CompletedProcess(
        [dunerc]
        + dunerc_option_strings
        + [process_manager_type]
        + [str(create_config_files.config_file)]
        + [str(create_config_files.config.session)]
        + [str(create_config_files.config.session_name if create_config_files.config.session_name else create_config_files.config.session)]
        + command_list,
        returncode=proc_returncode,
        stdout=full_output
    )
    time_after = time.time()

    if connsvc_obj is not None:
        time.sleep(1)
        connsvc_obj.send_signal(2)
        try:
            connsvc_obj.wait(0.5)
        except:
            pass
        connsvc_obj.kill()

    if create_config_files.config.attempt_cleanup:
        print(
            "Checking for remaining gunicorn and drunc-controller processes", flush=True
        )
        subprocess.run(["killall", "gunicorn", "drunc-controller"])

    result.confgen_config = create_config_files.config
    result.session = create_config_files.config.session
    result.session_name = create_config_files.config.session_name
    # 27-Feb-2026, KAB: the nanorc_commands return value can be removed once
    # all integtests have been changed to use "dunerc".
    result.nanorc_commands = command_list
    result.dunerc_commands = command_list
    result.run_dir = run_dir
    result.config_dir = create_config_files.config_dir
    result.data_files = []
    for rawdata_dir in rawdata_dirs:
        result.data_files += list(
            rawdata_dir.glob(f"{create_config_files.config.op_env}_raw_*.hdf5")
        )
    result.tpset_files = []
    for tpset_dir in tpset_dirs:
        result.tpset_files += list(
            tpset_dir.glob(f"{create_config_files.config.op_env}_tp_*.hdf5")
        )
    result.trmon_files = []
    for trmon_dir in trmon_dirs:
        result.trmon_files += list(
            trmon_dir.glob(f"{create_config_files.config.op_env}_trmon_*.hdf5")
        )
    result.log_files = list(run_dir.glob("log_*.txt")) + list(run_dir.glob("log_*.log"))
    result.opmon_files = list(run_dir.glob(f"info*{result.session_name if result.session_name else result.session}*.json"))
    # 10-Dec-2025, KAB: added the DAQ session overall time so that we can use this
    # information in fine-tuning the allowed ranges in time-based checking of test results.
    result.daq_session_overall_time = time_after - time_before
    print("---------- DRUNC Run END ----------", flush=True)
    yield result
