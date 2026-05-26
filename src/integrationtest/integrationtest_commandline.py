import pytest
import pathlib

def file_exists(s):
    p=pathlib.Path(s)
    return p.exists() and p.is_file()

def pytest_addoption(parser):
    parser.addoption(
        "--dunerc-path",
        action="store",
        type=pathlib.Path,
        default=None,
        help="Path to DUNE run control. Default is to search in $PATH",
        required=False
    )
    parser.addoption(
        "--dunerc-option",
        action="append",
        nargs="+",
        help="Repeatable, DUNE run control arguments without leading dashes (e.g. kerberos)",
        required=False
    )
    parser.addoption(
        "--no-integtest-connsvc",
        action="store_true",
        default=False,
        help="Whether to disable the Connectivity Service for this test",
        required=False
    )
    parser.addoption(
        "--skip-resource-checks",
        action="store_true",
        default=False,
        help="Whether to skip the node resource (CPU/Memory) checks for this test",
        required=False
    )
    parser.addoption(
        "--process-manager-type",
        action="store",
        default="",
        help="The run control process manager type to use for this test, e.g. ssh-standalone",
        required=False
    )
    parser.addoption(
        "--integtest-verbosity",
        action="store",
        default=3,
        help="The volume of messages that are printed out by the integration test infrastructure",
        required=False
    )
    parser.addoption(
        "--dunerc-fullprint-watch-string",
        action="store",
        default="",
        help="A phrase that, if found in run control messages, will trigger the printout of all RC messages",
        required=False
    )
    parser.addoption(
        "--remove-hdf5-files",
        action="store",
        default=None,
        help="Whether to remove HDF5 (data) files when the testing has finished (over-rides value in integtest)",
        required=False
    )

def pytest_configure(config):
    for opt in ("--dunerc-path",):
        p=config.getoption(opt)
        if p is not None and not file_exists(p):
            pytest.exit(f"{opt} path {p} is not an existing file")
