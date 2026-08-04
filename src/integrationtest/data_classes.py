from dataclasses import dataclass, field
from enum import Enum

@dataclass
class DROMap_config:
    n_streams: int
    n_apps: int = 1
    det_id: int = 3
    app_host: str = "localhost"
    eth_protocol: str = "udp"
    flx_mode: str = "fix_rate"
    crate_id_offset: int = 1
    slot_id: int = 0


# 27-Aug-2025, KAB: added derived classes to handle various types of configuration
# substitutions.  The attribute_substitution class handles cases in which we
# just need to replace simple value(s) for attribute(s) in a config object.
# The relationship_substitution class handles cases in which the new referenced "value"
# is a configuration object. The list_element_substitution class handles cases in
# which the data item that we want to modify is an entry in a list within the specified
# configuration object. And, the list_element_addition class handles cases in which
# we want to add a data item to a list within the specified configuration object.
@dataclass
class config_substitution:
    obj_class: str
    obj_id: str = "*"

@dataclass
class attribute_substitution(config_substitution):
    updates: dict = field(default_factory=dict)

@dataclass
class relationship_substitution(config_substitution):
    rel_name: str = ""
    replacement_object_class: str = ""
    replacement_object_id: str = ""

@dataclass
class list_element_substitution(relationship_substitution):
    list_index: int = 0

@dataclass
class list_element_addition(config_substitution):
    rel_name: str = ""
    additional_object_class: str = ""
    additional_object_id: str = ""

class PosixSignal(Enum):
    SIGINT = 2
    SIGKILL = 9
    SIGUSR1 = 10
    SIGUSR2 = 12
    SIGTERM = 15
    SIGCONT = 18
    SIGSTOP = 19

@dataclass
class system_signal_config:
    application_label: str
    signal: PosixSignal
    delay_s: int
    application_name: str = "daq_application"

class ConnSvcControl(Enum):
    INTEGRATIONTEST = "integrationtest"
    RUNCONTROL = "runcontrol"
    NONE = "none"

@dataclass
class integtest_param_base_class:
    # daq_session_name can be specified; it is automatically populated if not specified
    daq_session_name: str = None

    # config substitutions can be made to both generated and predefined dunedaq configs
    config_substitutions: list[config_substitution] = field(default_factory=list)

    # the cleanup of leftover RunControl or ConnSvc processes is available to all types of integtests
    attempt_cleanup: bool = False

    # parameter(s) related to the startup of the Connectivity Service
    connsvc_port: int = 0
    connsvc_debug_level: int = None

    # whether the HDF5 files should be deleted at the end of the test
    remove_hdf5_files: bool = False

    # command-line arguments to be passed to run control
    dunerc_cmd_args: list[str] = field(default_factory=list)

    # Signals to send to applications during the test
    system_signal_configs: list[system_signal_config] = field(default_factory=list)

@dataclass
class integtest_params_for_generated_dunedaq_config(integtest_param_base_class):
    # *** Parameters that are needed for both generated and predefined configs,
    # *** and benefit from different default values
    # - for generated configs, these two params do not need to have specific values
    op_env: str = "integtest"
    config_session_name: str = "integtest"

    # *** Parameters that are only needed for generated dunedaq configurations
    # - databases that are needed to support config generation
    object_databases: list[str] = field(default_factory=list)
    # - parameters that control what the generators produce
    dro_map_config: DROMap_config = field(default_factory=lambda: DROMap_config(1))
    frame_file: str = "asset://?checksum=370df564205290d27cab47e44ae4ca47"  # wib_link_67.bin
    tpg_enabled: bool = False
    trmon_app_enabled: bool = False
    fake_hsi_enabled: bool = False
    use_fakedataprod: bool = False
    fake_data_fragment_type: str = ""
    n_df_apps: int = 1
    n_data_writers: int = 1
    # - control over how the Connectivity Service is started
    connsvc_control: ConnSvcControl = ConnSvcControl.INTEGRATIONTEST

@dataclass
class integtest_params_for_predefined_dunedaq_config(integtest_param_base_class):
    # *** Parameters that are needed for both generated and predefined configs,
    # *** and benefit from different default values
    # - for a predefined config, the following two parameters must contain values that
    #   match what is in that config; they are likely reassigned in integtest files
    op_env: str = "test"
    config_session_name: str = "local-1x1-config"

    # *** Parameters that are unique to predefined dunedaq configurations
    # - the predefined configuration that should be used
    predefined_config_db: str = ""


@dataclass
class CreateConfigResult:
    integtest_params: integtest_param_base_class
    dunedaq_config_dir: str
    dunedaq_config_file: str
    log_file: str
    data_dirs: list[str]
    tpstream_data_dirs: list[str]
    trmon_data_dirs: list[str]
