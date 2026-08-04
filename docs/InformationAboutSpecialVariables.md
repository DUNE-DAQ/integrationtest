# Special variables that are used by the integrationtest infrastructure

## Introduction

In the Pytest files that we write (our integtests), there are several special variables that are used to communication information about the desired conditions of the testing to the integrationtest infrastructure.  This information includes things such as configuration parameters and run control commands.

This document describes the special variables that are currently available and how they can and should be used.

### Computer resource validation parameters

This is communicated by the "resource_validator" special variable.  It should point to an instance of the ResourceValidator class.

(More details coming soon.)

### Integrationtest and DAQ system configuration parameters

This is communicated by the "confgen_arguments" special variable.

(More details coming soon.)

### Run control process manager type(s)

This is communicated by the "process_manager_choices" special variable.

(More details coming soon.)

### Run control commands or full DAQ session ingredients

This is communicated either by the "dunerc_command_list" or the "daq_session_ingredients" special variable.  Only one of these two variables should be specified in a single integtest file, but if both of them happen to be specified in the same integtest, the "daq_session_ingredients" takes precedence.

The purposes of these two variables are similar - both provide commands that should be run by one or more run control applications - but the "daq_session_ingredients" variable is more powerful in that it allows users to specify one or more applications that should be run, instead of simply using the `drunc-unified-shell`.

Information about `dunerc_command_list`:

* this is the variable that has been used historically, and many of our existing integtests use it.
* it is expected to contain a Python list of the commands (strings) that are passed to run control in "batch" mode
    * some examples:
* it can contain a single list of commands, or it can contain a dictionary of one or more lists that should be run.  In this way, multiple DAQ sessions with different sets of commands can be run from an single integtest.
    * for example:

Information about `daq_session_ingredients`:
* this variable was recently introduced so that developers of integtests can specify multiple control applications to be run in a given (integtest) DAQ session
* at the moment, this variable needs to contain a dictionary with one or more entries, and each entry should contain a string key (with a word or phrase that describes the DAQ session) and an instance of the DAQSessionIngredients Python class as the value.

(More details coming soon.)
