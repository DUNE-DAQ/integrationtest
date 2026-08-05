# Special variables that are used by the integrationtest infrastructure

05-Aug-2026, Kurt Biery

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
* the [basic_multiapp_test.py](https://github.com/DUNE-DAQ/drunc/blob/kbiery/multi_ctrl_proc_support/src/drunc/integtest/basic_multi_app_test.py) regression test in the `drunc` repo has an example of specifying three applications to be run in the DAQ session and specifying commands that are sent to two of those applications.
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
