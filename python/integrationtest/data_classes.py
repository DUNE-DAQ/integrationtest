from dataclasses import dataclass, field


@dataclass
class DROMap_config:
    n_streams: int
    n_apps: int = 1
    det_id: int = 3
    app_host: str = "localhost"
    eth_protocol: str = "udp"
    flx_mode: str = "fix_rate"


# 27-Aug-2025, KAB: added derived classes to handle various types of
# configuration substitutions.  The attribute_substitution handles cases in which we
# just need to replace simple value(s) for attribute(s) in a config object.
# The relationship_substitution handles cases in which the new referenced "value"
# is a configuration object. And, the list_element_substitution handles cases in
# which the data item that we want to modify is an entry in a list within the specified
# configuration object.
# --> Implementation Note:  the "updates" dictionary that is currently part of the
#     config_substitution class should really be part of the attribute_substitution class.
#     However, I've left it in config_substitution for backward-compatibility.  As we have
#     time, We should change existing integtests to use attribute_substitution.  Once
#     that is done, we should come back here and tighten up this code.
@dataclass
class config_substitution:
    obj_class: str
    obj_id: str = "*"
    updates: dict = field(default_factory=dict)

@dataclass
class attribute_substitution(config_substitution):
    pass

@dataclass
class relationship_substitution(config_substitution):
    rel_name: str = ""
    replacement_object_class: str = ""
    replacement_object_id: str = ""

@dataclass
class list_element_substitution(relationship_substitution):
    list_index: int = 0


@dataclass
class drunc_config:
    op_env: str = "integtest"
    session: str = "integtest"
    session_name: str = None
    dro_map_config: DROMap_config = field(default_factory=lambda: DROMap_config(1))
    frame_file: str = "asset://?checksum=e96fd6efd3f98a9a3bfaba32975b476e"
    tpg_enabled: bool = False
    fake_hsi_enabled: bool = False
    use_fakedataprod: bool = False
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
