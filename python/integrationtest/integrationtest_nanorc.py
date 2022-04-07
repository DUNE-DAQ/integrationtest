import pytest
import shutil
import filecmp
import subprocess
import os.path
import os
import pathlib

def file_exists(s):
    p=pathlib.Path(s)
    return p.exists() and p.is_file()

def pytest_addoption(parser):
    parser.addoption(
        "--nanorc-path",
        action="store",
        type=pathlib.Path,
        default=None,
        help="Path to nanorc. Default is to search in $PATH",
        required=False
    )
    parser.addoption(
        "--frame-file",
        action="store",
        type=pathlib.Path,
        help="Path to frame file",
        required=True
    )
    parser.addoption(
        "--nanorc-option",
        action="append",
        nargs="+",
        help="Repeatable, nanorc arguments without leading dashes (e.g. kerberos)",
        required=False
    )

def pytest_configure(config):
    for opt in ("--nanorc-path", "--frame-file"):
        p=config.getoption(opt)
        if p is not None and not file_exists(p):
            pytest.exit(f"{opt} path {p} is not an existing file")

def parametrize_fixture_with_items(metafunc, fixture, itemsname):
    """Parametrize a fixture using the contents of variable `listname`
    from module scope. We want to distinguish between the cases where
    the list is a list of strings, and a list of lists of strings. We
    do this by checking whether the first item in the list is a
    string. Not perfect, but better than nothing

    """
    the_items=getattr(metafunc.module, itemsname)
    if isinstance(the_items, dict):
        metafunc.parametrize(fixture, the_items.values(), ids=the_items.keys(), indirect=True)
    elif isinstance(the_items, list) or isinstance(the_items, tuple):
        if type(the_items[0])==str:
            params=[the_items]
        else:
            params=the_items
        metafunc.parametrize(fixture, params, indirect=True)

def pytest_generate_tests(metafunc):
    # We want to be able to run multiple confgens and multiple nanorcs
    # from one pytest module, but the fixtures for running the
    # external commands are module-scoped, so we need to parametrize
    # the fixtures. This could be done by adding "params=..." to the
    # @pytest.fixture decorator at each fixture, but the user doesn't
    # have access to that point in the code. So instead we pull
    # variables from the module (which the user _does_ have access to)
    # and parametrize the fixtures here in pytest_generate_tests,
    # which is run at pytest startup
    parametrize_fixture_with_items(metafunc, "create_json_files", "confgen_arguments")
    parametrize_fixture_with_items(metafunc, "run_nanorc", "nanorc_command_list")

@pytest.fixture(scope="module")
def create_json_files(request, tmp_path_factory):
    """Run the confgen to produce the configuration json files

    The name of the module to use is taken (indirectly) from the
    `confgen_name` variable in the global scope of the test module,
    and the arguments for the confgen are taken from the
    `confgen_arguments` variable in the same place. These variables
    are converted into parameters for this fixture by the
    pytest_generate_tests function, to allow multiple confgens to be
    produced by one pytest module

    """
    script_name=getattr(request.module, "confgen_name")
    script_arguments=request.param

    class CreateJsonResult:
        pass

    json_dir=tmp_path_factory.getbasetemp() / f"json{request.param_index}"
    logfile = tmp_path_factory.getbasetemp() / f"stdouterr{request.param_index}.txt"

    if not os.path.isdir(json_dir):
        print("Creating json files")
        try:
            with open(logfile, "wb") as outerr:
                subprocess.run([script_name] + script_arguments + [str(json_dir)], check=True, stdout=outerr,stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as err:
            print(f"Generating json files failed with exit code {err.returncode}")
            pytest.fail()

    result=CreateJsonResult()
    result.confgen_name=script_name
    result.confgen_arguments=script_arguments
    result.json_dir=json_dir
    result.log_file=logfile

    yield result


@pytest.fixture(scope="module")
def create_minimal_json_files(request, tmp_path_factory):
    """Run the confgen to produce the configuration json files

    The name of the module to use is taken (indirectly) from the
    `confgen_name` variable in the global scope of the test module,
    and the arguments for the confgen are taken from the
    `confgen_arguments` variable in the same place. These variables
    are converted into parameters for this fixture by the
    pytest_generate_tests function, to allow multiple confgens to be
    produced by one pytest module

    """
    script_name=getattr(request.module, "confgen_name")
    script_arguments=['-o', '.']

    class CreateJsonResult:
        pass

    json_dir=tmp_path_factory.getbasetemp() / f"json_minimal_{request.param_index}"
    logfile = tmp_path_factory.getbasetemp() / f"stdouterr_minimal_{request.param_index}.txt"

    if not os.path.isdir(json_dir):
        print("Creating json files")
        try:
            with open(logfile, "wb") as outerr:
                subprocess.run([script_name] + script_arguments + [str(json_dir)], check=True, stdout=outerr,stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as err:
            print(f"Generating json files failed with exit code {err.returncode}")
            pytest.fail()

    result=CreateJsonResult()
    result.confgen_name=script_name
    result.confgen_arguments=script_arguments
    result.json_dir=json_dir
    result.log_file=logfile

    yield result

@pytest.fixture(scope="module")
def run_nanorc(request, create_json_files, tmp_path_factory):
    """Run nanorc with the json files created by `create_json_files`. The
    commands specified by the `nanorc_command_list` variable in the
    test module are executed. If `nanorc_command_list`'s items are
    themselves lists, then nanorc will be run multiple times, once for
    each set of arguments in the list

    """
    command_list=request.param

    nanorc=request.config.getoption("--nanorc-path")
    if nanorc is None:
        nanorc="nanorc"
    nanorc_options=request.config.getoption("--nanorc-option")
    nanorc_option_strings = []
    if nanorc_options is not None:
        for opt in nanorc_options:
            if len(opt) > 2:
                print("Nanorc options take either 0 or 1 arguments!")
                pytest.fail()
            if len(opt[0]) == 1:
                nanorc_option_strings.append("-" + ''.join(opt))
            else:
                nanorc_option_strings.append("--"+ opt[0])
                if(len(opt) == 2):
                    nanorc_option_strings.append(opt[1])

    class RunResult:
        pass

    run_dir=tmp_path_factory.mktemp("run")
    frame_path=request.config.getoption("--frame-file")
    os.symlink(frame_path, run_dir.joinpath("frames.bin"))

    result=RunResult()
    result.completed_process=subprocess.run([nanorc] + nanorc_option_strings + [str(create_json_files.json_dir)] + command_list, cwd=run_dir)
    result.confgen_name=create_json_files.confgen_name
    result.confgen_arguments=create_json_files.confgen_arguments
    result.nanorc_commands=command_list
    result.run_dir=run_dir
    result.json_dir=create_json_files.json_dir
    result.data_files=list(run_dir.glob("swtest_*.hdf5"))
    result.log_files=list(run_dir.glob("log_*.txt"))
    result.opmon_files=list(run_dir.glob("info_*.json"))
    yield result


@pytest.fixture(scope="module")
def diff_conf_files(create_minimal_json_files, create_json_files):
    class DiffResult:
        pass

    left  = create_minimal_json_files.json_dir
    right = create_json_files        .json_dir

    result = DiffResult()
    result.diff = filecmp.dircmp(left, right).diff_files + filecmp.dircmp(left/'data', right/'data').diff_files
    yield result
