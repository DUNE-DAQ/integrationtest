from dataclasses import dataclass, field


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

@dataclass
class drunc_config:
    op_env: str = "integtest"
    session: str = "integtest"
    session_name: str = None
    dro_map_config: DROMap_config = field(default_factory=lambda: DROMap_config(1))
    frame_file: str = "asset://?checksum=370df564205290d27cab47e44ae4ca47"
    tpg_enabled: bool = False
    trmon_app_enabled: bool = False
    fake_hsi_enabled: bool = False
    use_fakedataprod: bool = False
    fake_data_fragment_type: str = ""
    config_db: str = ""
    n_df_apps: int = 1
    n_data_writers: int = 1
    object_databases: list[str] = field(default_factory=list)
    config_substitutions: list[config_substitution] = field(default_factory=list)
    attempt_cleanup: bool = False
    drunc_connsvc: bool = False
    connsvc_port: int = 0
    connsvc_debug_level: int = 0


@dataclass
class CreateConfigResult:
    config: drunc_config
    config_dir: str
    config_file: str
    log_file: str
    data_dirs: list[str]
    tpstream_data_dirs: list[str]
    trmon_data_dirs: list[str]

@dataclass
class IntegtestVerbosityLevels:
    just_errors_and_warnings: int = 1  # shows just errors and warnings
    drunc_boot_terminate: int = 2  # shows validation check successes as well as failures
    drunc_transitions: int = 3  # shows drunc transitions plus test results
    integtest_debug: int = 4  # shows ResourceValidation debug info plus test results, drunc transitions
    full_output: int = 5  # shows everything
    drunc_debug: int = 6  # includes drunc debug messages
