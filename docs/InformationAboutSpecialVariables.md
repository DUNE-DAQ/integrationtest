# Special variables that are used by the integrationtest infrastructure

18-Aug-2026, Kurt Biery

## Introduction

In the Pytest files that we write (our integtests), there are several special variables that are used to communication information about the desired conditions of the testing to the `integrationtest` infrastructure.  This information includes things such as configuration parameters and run control commands.

This document describes the special variables that are currently available and how they can, and should, be used.

### Computer resource validation parameters

This is communicated by the `resource_validator` special variable.  It should point to an instance of the `ResourceValidator` class.  This class is defined in [integrationtest/src/integrationtest/resource_validation.py](https://github.com/DUNE-DAQ/integrationtest/blob/develop/src/integrationtest/resource_validation.py).

(More details coming soon.)

### Integrationtest and DAQ system configuration parameters

This is communicated by the `confgen_arguments` special variable.

(More details coming soon.)

### Run control process manager type(s)

This is communicated by the `process_manager_choices` special variable.

(More details coming soon.)

### Run control commands or full DAQ session ingredients

These are communicated either by the `dunerc_command_list` or the `daq_session_ingredients` special variable.  Only one of these two variables should be specified in a single integtest file, but if both of them happen to be specified in the same integtest, the `daq_session_ingredients` takes precedence.

The purposes of these two variables are similar - both provide commands that should be run by one or more run control applications - but the `daq_session_ingredients` variable is more powerful in that it allows users to specify one or more applications that should be run, instead of simply using the `drunc-unified-shell`.

Information about `dunerc_command_list`:

* this is the variable that has been used historically, and many of our existing integtests use it.
* it is expected to contain a Python list of the commands (strings) that are passed to run control in "batch" mode
    * some examples:
        * `dunerc_command_list = ("boot conf start --run-number 101 wait 1 enable-triggers wait ".split() + [str(run_duration)] + "disable-triggers wait 2 drain-dataflow wait 2 stop-trigger-sources stop scrap terminate".split())`
        * `dunerc_command_list = ["boot", "conf", "start", "--run-number", "101", "wait", str(1), "enable-triggers", "wait", str(20), "disable-triggers", "stop-run", "shutdown"]`
* in addition to containing a single list of commands (as shown above), this variable can contain a dictionary of one or more lists of commands.  With this functionality, multiple DAQ sessions with different sets of commands can be run from an single integtest.
    * here is an example of this type declaration:
        * `dunerc_command_list = {"DAQ_Session_1": ["boot", "conf", "start", "--run-number", "101", "wait", str(1), "enable-triggers", "wait", str(20), "disable-triggers", "stop-run", "shutdown"], "DAQ Session 2": ["boot", "conf", "start", "--run-number", "101", "wait", str(3), "enable-triggers", "wait", str(20), "disable-triggers", "stop-run", "scrap", "terminate"]}`

Information about `daq_session_ingredients`:
* this variable was recently introduced so that developers of integtests can specify multiple control applications to be run in a given (integtest) DAQ session
* at the moment, this variable needs to contain a dictionary with one or more elements, and each element should contain a string key (with a word or phrase that describes the DAQ session) and an instance of the `DAQSessionIngredients` class as the value.  The `DAQSessionIngredients` class is defined in [integrationtest/src/integrationtest/data_classes.py](https://github.com/DUNE-DAQ/integrationtest/blob/0fe60d9b1c1aa697ec9524c4aaf1507aaa3c6b2a/src/integrationtest/data_classes.py#L139).
* the `DAQSessionIngredients` class has data members that allow developers to specify the applications that should be run and the commands that should be sent to the applications.  In this class, applications are represented by instances of the `DAQSessionApp` class and commands are listed in instances of the `DAQCommandSet` class.  The `DAQCommandSet` has a field that specifies the application that we want to send the commands to.
    * reference information:

```
@dataclass
class DAQSessionIngredients:
    applications: list[DAQSessionApp]
    commands: list[DAQCommandSet]

@dataclass
class DAQSessionApp:
    alias: str  # a short-hand name for the process that is started
    startup_strings: list[str]  # the elements of the command string that should be used to start the application
    wait_time_after_start: int = 2  # seconds to sleep after spawning the process

@dataclass
class DAQCommandSet:
    target: str  # the name of the process that should receive the commands
    command_list: list[str]  $ the list of commands, e.g. ["boot", "conf"]
    wait_params: CommandWaitParameters = field(default_factory=lambda: CommandWaitParameters())

@dataclass
class CommandWaitParameters:  # please see the comments below for information about this class, etc.
    wait_for_command_completion: bool = True
    style: CommandWaitStyle = CommandWaitStyle.TIME
    timeout_waiting_for_first_msg: int = 2  # seconds
    wait_time_after_last_msg: int = 2  # seconds
    timeout_waiting_for_exit: int = 5  # seconds

class CommandWaitStyle(Enum):
    ECHO = "echo"
    TIME = "time"
    TIME_PLUS_EXIT = "time_plus_exit"
    NONE = "none"
```

* Here is some additional information about `CommandWaitParameters`:
    * the commands that are specified in a `DAQCommandSet` are sent individually to the target process without any delay between them.  So, we typically send all of the commands in the set in a fraction of a second, while the target process could take tens of seconds to execute all of them.
    * when there is only one control process in an integtest, this rapid-fire approach may be all that we need, because a single process handles the throttling of the commands, running them one after another.  However, when there are multiple control processes in an integtest, we may want to send a set of commands to Process1, wait for those to finish, and only then send a set of commands to Process2.  This demonstrates a need to allow the user to specify whether they want the integrationtest infrastructure to wait for each command set to finish before moving on to the next set of commands, and if so, what style of waiting they would like be used.  This is the motivation for the `CommandWaitParameters` class.
        * of course, there are also situations in which we want to wait for all of the requested commands to finish running even when there is only one control process in the integtest.  For example, we will likely want to allow a single process to finish executing all of the requested commands before the `integrationtest` infrastructure starts shutting down that process.
    * the currently-supported wait styles are ECHO, TIME, and TIME_PLUS_EXIT.
    * the ECHO wait style makes use of the `echo` command that is available in some of our control applications to clearly identify when a set of commands has finished.  So, if a user specifies a command set that contains commands `['boot', 'conf']` and has a wait style of ECHO, the `integrationtest` infrastructure appends an `echo` command with a special string to the set, i.e. `['boot', 'conf', 'echo "<special string>"']`.  When the `integrationtest` infrastructure sees the special string in the output of the target process, it knows that the command set has finished.
    * the TIME wait style simply waits for configured amounts of time for console output to start and then stop.  The idea here is to use the console output as an indicator of activity, and when the console output stops, presume that activity related to the requested command(s) has stopped.  
    * the TIME_PLUS_EXIT wait style is intended to be used with "exit" commands.  The idea here is to wait for console output to stop and then wait for the process to exit (within a configurable timeout).
* the [basic_multiapp_test.py](https://github.com/DUNE-DAQ/drunc/blob/kbiery/multi_ctrl_proc_support/src/drunc/integtest/basic_multiapp_test.py) regression test in the `drunc` repo has an example of specifying three applications to be run in the DAQ session and specifying commands that are sent to two of those applications.
    * For reference, the relevant lines from `basic_multiapp_test.py` are copied below.
* There are several strings that are dynamically determined by the `integrationtest` infrastructure that we may want to include in the `startup_strings` field in our `DAQSessionApp` declarations.  To take this into account, placeholder strings have been defined.  These placeholder strings can be used in `DAQSessionApp` declarations and the `integrationtest` infrastructure will substitute the appropriate value at runtime.  The placeholders that are currently available are the following:
    * `<proc_mgr_choice>` - the process manager type that should be used in the DAQ session
        * recall that the `integrationtest` infrastructure has support for user-specified (dynamic) process manager types.  If we don't want to make use of that functionality, we can hard-code the process manager type in our `DAQSessionApp.startup_strings`.  Of course, that reduces flexibility, but there may be cases where it would make sense.
    * `<config_data_file>` - the configuration data file that the infrastructure has created for the integtest
        * this placeholder string should always be used since the `integrationtest` infrastructure creates a new, temporary config data file for each running of an integtest
    * `<config_session_name>` - the name of the configuration session that should be used for the DAQ session
        * this could be hard-coded, but it is safer to let it get filled in dynamically
    * `<daq_session_name>` - the name that should be used to identify the DAQ session
        * this placeholder can be used, or the name of the DAQ session could be hard-coded in the `startup_strings`
* when an integration test is run with verbosity level of 4 or greater, the command lines that are used to start the applications are printed on the console, and this output can be used to check if the desired substitutions were made

Here is a snippet of code from the `basic_multapp_test.py` that shows how the `DAQSessionIngredients` are constructed in that integtest:

```
# The commands to run in dunerc and the process manager shell
dunerc_commands_1 = (
    "boot conf start --run-number 101 wait 1 enable-triggers wait ".split()
    + [str(run_duration)] + ["disable-triggers"]
)
dunerc_commands_2 = (
    "drain-dataflow stop-trigger-sources stop wait 2 scrap terminate".split()
)
pmshell_command = ["ps"]

# Find a free network port to use for the process manager
pm_port = find_free_port(50020, 52000)

# The command lines that should be used to start the applications
procmsg_startup_commands = ["drunc-process-manager", "<proc_mgr_choice>", str(pm_port)]
pmapp = DAQSessionApp("pm", procmsg_startup_commands)

pmshell_startup_commands = ["drunc-process-manager-shell", f"grpc://localhost:{pm_port}"]
pmshellapp = DAQSessionApp("pmshell", pmshell_startup_commands)

drunc_startup_commands = ["drunc-unified-shell", f"grpc://localhost:{pm_port}", "<config_data_file>", "<config_session_name>", "<daq_session_name>"]
druncapp = DAQSessionApp("drunc", drunc_startup_commands)

# Packaging up the commands into DAQCommandSets
cmd_set_1 = DAQCommandSet("drunc", dunerc_commands_1, CommandWaitParameters(style=CommandWaitStyle.ECHO))
cmd_set_2 = DAQCommandSet("pmshell", pmshell_command, CommandWaitParameters(style=CommandWaitStyle.TIME))
cmd_set_3 = DAQCommandSet("drunc", dunerc_commands_2, CommandWaitParameters(style=CommandWaitStyle.ECHO))

# Putting everything together into a DAQSessionIngredients object
app_list = [ pmapp, pmshellapp, druncapp ]
cmd_set_list = [ cmd_set_1, cmd_set_2, cmd_set_3 ]
dsi = DAQSessionIngredients(app_list, cmd_set_list)

# Declare the special variable that tells the integrationtest infrastructure what we want to run
daq_session_ingredients = {"MultiRCAppSession": dsi}
```
