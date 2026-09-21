import pytest
import asyncio
import getpass
import pathlib
import re
import time
from integrationtest.data_classes import *
from integrationtest.verbosity_helper import *
from datetime import datetime, timezone

import functools
print = functools.partial(print, flush=True)  # always flush print() output


async def read_stream(stream, process_name, app_exe_name, print_proc_name, run_dir,
                      shared_data: OutputMonitoringSharedData, verbosity_level):
    """Asynchronously reads lines from a stream and processes them immediately."""
    full_output = ""
    observed_command_prompt = ""

    # store the full output in a log file to be checked for problems and for later reference
    with open(f"{run_dir}/log_{getpass.getuser()}_{app_exe_name}_console_output.txt", "w", encoding="utf-8") as ff:
        while True:
            line = await stream.readline()
            if not line:
                break
            decoded_line = line.decode()
            async with shared_data.lock:
                shared_data.last_msg_time = time.time()

            # if we find a requested phrase in the output, set the relevant flag
            async with shared_data.lock:
                if shared_data.phrase_searching_in_progress and \
                   shared_data.search_phrase is not None:
                    clean_line = re.sub(r"\x1b\[[0-9;]*m", "", decoded_line)
                    if shared_data.search_phrase in clean_line:
                        shared_data.search_phrase_has_been_found = True

            # process the output of the "help" command, if requested
            async with shared_data.lock:
                if shared_data.parsing_of_help_output_in_progress:
                    trimmed_line = decoded_line.strip()
                    if len(trimmed_line) == 0:
                        continue
                    if "documented commands" in trimmed_line.lower():
                        continue
                    if "=====" in trimmed_line:
                        continue
                    if trimmed_line.endswith(r">"):
                        observed_command_prompt = trimmed_line
                        continue
                    if verbosity_level >= IntegtestVerbosityLevels.full_output:
                        now_string = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
                        print(f"[integtest_proc_mgmt {now_string}] Help command output: {decoded_line}")
                    the_cmds = trimmed_line.split()
                    tmp_list = shared_data.results_of_parsing_help_output + the_cmds
                    shared_data.results_of_parsing_help_output = sorted(set(tmp_list))
                    continue

            # print out each line of output, subject to the verbosity level that the user has
            # requested, as well as writing it to a log file and adding it to a string that
            # we pass back to the user
            should_be_printed = verbosity_level >= IntegtestVerbosityLevels.full_output

            # check for errors and warnings for all verbosity levels
            # (only if we have not already determined that the line should be printed out)
            if not should_be_printed:
                lc_line = decoded_line.lower()
                if ("error" in lc_line and (not "In error" in decoded_line and not "Endpoint" in decoded_line)) \
                   or "warning" in lc_line or "critical" in lc_line:
                    should_be_printed = True

            # check for basic transition messages, if that level of verbosity is requested
            # (only if we have not already determined that the line should be printed out)
            if not should_be_printed:
                if verbosity_level >= IntegtestVerbosityLevels.drunc_boot_terminate:
                    if "Booting session" in decoded_line or \
                       ("Current FSM status is " in decoded_line and ("initial" in decoded_line or "running" in decoded_line)):
                        should_be_printed = True

            # check for all transition messages, if that level of verbosity is requested
            # (only if we have not already determined that the line should be printed out)
            if not should_be_printed:
                if verbosity_level >= IntegtestVerbosityLevels.drunc_transitions:
                    if "Booting session" in decoded_line or "Running transition" in decoded_line \
                       or ("wait" in decoded_line and "running" in decoded_line) or "exit code" in decoded_line:
                        should_be_printed = True

            # remove the application command prompt from the front of the line, if needed
            if len(observed_command_prompt) > 0 and decoded_line.startswith(observed_command_prompt):
                tmp_line = decoded_line.removeprefix(observed_command_prompt)
                decoded_line = tmp_line.lstrip()

            # actually do the printout
            if should_be_printed:
                async with shared_data.lock:
                    if shared_data.number_of_lines_printed_to_the_console == 0:
                        print("++++++++++ DAQ Session BEGIN ++++++++++", flush=True)
                    if print_proc_name:
                        print(f"[{process_name}] {decoded_line}", end='', flush=True)
                    else:
                        print(decoded_line, end='', flush=True)
                    shared_data.number_of_lines_printed_to_the_console += 1

            clean_line = re.sub(r"\x1b\[[0-9;]*m", "", decoded_line)
            ff.write(f"{clean_line}")
            ff.flush()
            full_output += clean_line

    return full_output


# The purpose of this function is to wait until one of the requested conditions has been
# satified. The conditions are specified in "wait parameter" objects. The baseline wait
# parameter class provides time values that are used to watch for quiet times in the console
# output from the control process(es). Wait parameter classes that build on the
# ConsoleOutputWaitParameters class add conditions that allow the waiting to end earlier
# than the wait times specified in the base class.
# Return codes are 0 for console output timeout, 1 for finding a search phrase in the console
# output, and 2 for when the process has exited.
async def wait_for_requested_condition(start_time, wait_params: ConsoleOutputWaitParameters,
                                       shared_data: OutputMonitoringSharedData):
    retcode = 0

    if (isinstance(wait_params, EchoCommandWaitParameters) or \
        isinstance(wait_params, KeyPhraseWaitParameters)) and \
        wait_params.search_phrase is not None:
        async with shared_data.lock:
            shared_data.search_phrase_has_been_found = False
            shared_data.search_phrase = wait_params.search_phrase
            shared_data.phrase_searching_in_progress = True

    now = time.time()
    while True:
        async with shared_data.lock:
            if shared_data.last_msg_time <= start_time:
                if now - start_time > wait_params.timeout_waiting_for_first_msg:
                    break
            else:
                if now - shared_data.last_msg_time >= wait_params.wait_time_after_last_msg:
                    break
            if shared_data.search_phrase_has_been_found:
                retcode = 1
                break
        if isinstance(wait_params, ProcessExitWaitParameters) and \
           wait_params.process is not None:
            if wait_params.process.returncode is not None:
                retcode = 2
                break
        await asyncio.sleep(0.25)
        now = time.time()

    if (isinstance(wait_params, EchoCommandWaitParameters) or \
        isinstance(wait_params, KeyPhraseWaitParameters)) and \
        wait_params.search_phrase is not None:
        async with shared_data.lock:
            shared_data.phrase_searching_in_progress = False
            shared_data.search_phrase_has_been_found = False

    return retcode


async def send_commands(target_proc_info, proc_name, shared_data: OutputMonitoringSharedData,
                        cmd_list, wait_params, verbosity_level):
    # Check if the process is still running; return if not
    target_proc = target_proc_info.process
    if target_proc.returncode is not None:
        now_string = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
        print(f"[integtest_proc_mgmt {now_string}] Error: {proc_name} has already exited, unable to send \"{cmd_list}\".")
        return
    cmd_start_time = time.time()

    # for KeyPhrase wait conditions, start watching the console output *before* we send
    # the requested commands (to avoid a race condition)
    key_phrase_bg_task = None
    if wait_params is not None and isinstance(wait_params, KeyPhraseWaitParameters) and \
       wait_params.search_phrase is not None:
        key_phrase_bg_task = asyncio.create_task(wait_for_requested_condition(cmd_start_time, wait_params, shared_data))

    # send the requested commands
    for cmd in cmd_list:
        target_proc.stdin.write((cmd + "\n").encode())
        await target_proc.stdin.drain()
        if verbosity_level >= IntegtestVerbosityLevels.integtest_debug:
            now_string = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
            print(f"[integtest_proc_mgmt {now_string}] Sent command to {proc_name}: {cmd}")
        else:
            # in order to indicate to the user that the program is not stalled,
            # we print out dots if nothing else has been printed
            async with shared_data.lock:
                if shared_data.number_of_lines_printed_to_the_console == 0:
                    print(".", end="")

    # wait for the command(s) to finish, if requested
    if wait_params is None:
        return
    if isinstance(wait_params, ProcessExitWaitParameters):
        # The idea behind this wait style is that we want to wait until the process has
        # exited, and if it fails to exit, we want to time out after a reasonable time.
        # Of course, if the app doesn't support the "exit" command, there is no sense in
        # waiting for the process to respond to it.  But, we tell users that we skipped it.
        if "exit" in target_proc_info.supported_commands:
            wait_params.process = target_proc
            await wait_for_requested_condition(cmd_start_time, wait_params, shared_data)
            if target_proc.returncode is None:
                now_string = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
                print(f"[integtest_proc_mgmt {now_string}] WARNING: timeout waiting for {proc_name} to exit in response to {cmd_list}")
        else:
            if verbosity_level >= IntegtestVerbosityLevels.integtest_debug:
                now_string = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
                print(f"[integtest_proc_mgmt {now_string}] The {proc_name} process doesn't support the 'exit' command, so we won't wait for a response")
    elif isinstance(wait_params, EchoCommandWaitParameters):
        if "echo" in target_proc_info.supported_commands:
            # start a background task to watch for the echo command output
            bg_task = asyncio.create_task(wait_for_requested_condition(cmd_start_time, wait_params, shared_data))
            # send the echo command to the process
            target_proc.stdin.write((f"echo '{wait_params.search_phrase}'\n").encode())
            await target_proc.stdin.drain()
            if verbosity_level >= IntegtestVerbosityLevels.integtest_debug:
                now_string = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
                print(f"[integtest_proc_mgmt {now_string}] Sent command to {proc_name}: echo '{wait_params.search_phrase}'")
            # wait until the echo command output shows up in the console output
            retcode = await bg_task
            if retcode != 1:
                now_string = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
                print(f"[integtest_proc_mgmt {now_string}] WARNING: timeout waiting for {proc_name} to echo '{wait_params.search_phrase}' after executing {cmd_list}")
        else:
            now_string = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
            print(f"[integtest_proc_mgmt {now_string}] WARNING: The {proc_name} process doesn't support the 'echo' command, using time-based wait instead'")
            # we use a KeyPhrase wait parameter set here (without setting a search phrase)
            # because its default timeout values are longer than a couple of seconds but not too
            # long. In any case, this choice is a poor substitute for a test string to be echo-ed
            # by the application, and there is a non-trivial chance that the timeout values are
            # not well-matched to the console output that is produced by the process.
            wait_params = KeyPhraseWaitParameters()
            await wait_for_requested_condition(cmd_start_time, wait_params, shared_data)
    elif isinstance(wait_params, KeyPhraseWaitParameters) and key_phrase_bg_task is not None:
        retcode = await key_phrase_bg_task
        if retcode != 1:
            now_string = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
            print(f"[integtest_proc_mgmt {now_string}] WARNING: timeout waiting for {proc_name} to print out '{wait_params.search_phrase}' as part of executing {cmd_list}")
    else:
        await wait_for_requested_condition(cmd_start_time, wait_params, shared_data)

# add background task to avoid race condition?


async def intg_process_manager(daq_session_ingredients: DAQSessionIngredients, run_dir,
                               verbosity_level):
    processes = {}
    tasks = {}
    proc_results = {}
    shared_data: OutputMonitoringSharedData = OutputMonitoringSharedData()

    # 1. Start all subprocesses
    for session_app in daq_session_ingredients.applications:
        proc_name = session_app.alias
        if verbosity_level >= IntegtestVerbosityLevels.integtest_debug:
            now_string = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
            print()
            print(f"[integtest_proc_mgmt {now_string}] Starting \"{session_app.startup_strings}\" with process name \"{proc_name}\"...")
            #print()
        else:
            print(".", end="")
        proc = await asyncio.create_subprocess_exec(
            *session_app.startup_strings,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=run_dir
        )
        processes[proc_name] = RunningProcessInfo(proc)

        # 2. Schedule output reading tasks to run concurrently
        tasks[proc_name] = asyncio.create_task(read_stream(proc.stdout, proc_name, session_app.startup_strings[0],
                                                           (len(daq_session_ingredients.applications)>1),
                                                           run_dir, shared_data, verbosity_level
                                                           ))

        # Wait for the process to start up. If the user has not specified wait parameters,
        # default-construct ones that make use of the console output.
        wait_params = session_app.startup_wait_params
        if wait_params is None:
            wait_params = ConsoleOutputWaitParameters()
        await wait_for_requested_condition(time.time(), wait_params, shared_data)

    if verbosity_level >= IntegtestVerbosityLevels.integtest_debug:
        now_string = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
        print()
        print(f"[integtest_proc_mgmt {now_string}] Started {len(processes)} process(es).")
        print()
    else:
        async with shared_data.lock:
            if shared_data.number_of_lines_printed_to_the_console == 0:
                print(".", end="")

    # determine the supported commands for each app (using the 'help' command)
    help_cmd = ["help"]
    help_cmd_wait_params = ConsoleOutputWaitParameters(timeout_waiting_for_first_msg=2)
    #await wait_for_requested_condition(time.time(), help_cmd_wait_params, shared_data)
    for proc_name, proc_info in processes.items():
        async with shared_data.lock:
            shared_data.results_of_parsing_help_output = []
            shared_data.parsing_of_help_output_in_progress = True
        await send_commands(proc_info, proc_name, shared_data, help_cmd,
                            help_cmd_wait_params, verbosity_level)
        async with shared_data.lock:
            shared_data.parsing_of_help_output_in_progress = False
            proc_info.supported_commands = shared_data.results_of_parsing_help_output
            shared_data.results_of_parsing_help_output = []

    # 3. Send the commands to the running process(es)
    return_code = 0
    try:
        for cmd_set in daq_session_ingredients.commands:
            target = cmd_set.target
            if target in processes:
                proc_info = processes[target]

                # re-organize the DAQ commands to provide valid combinations, if needed
                working_cmd_list = []
                working_cmd = ""
                # we work backward thru the list so that we can add arguments to commands
                for daq_cmd in reversed(cmd_set.command_list):
                    daq_cmd = daq_cmd.strip()
                    # if the number of words is > 1, then we trust that the user specified the full command
                    if len(daq_cmd.split()) > 1:
                        working_cmd_list.append(daq_cmd)
                    else:
                        # check if the "cmd" is a number; if so, we expect it to be an argument
                        try:
                            int(daq_cmd)
                            working_cmd = " " + daq_cmd + working_cmd
                            continue
                        except:
                            pass
                        # check if the "cmd" starts with double-dash; if so, consider it an argument
                        if daq_cmd.startswith("--"):
                            working_cmd = " " + daq_cmd + working_cmd
                            continue
                        # check if the "cmd" is not one of the known supported commands
                        # if not, we consider it an argument to an application command
                        if len(proc_info.supported_commands) > 0:
                            if daq_cmd not in proc_info.supported_commands:
                                working_cmd = " " + daq_cmd + working_cmd
                                continue

                        # Here we assemble valid application commands.
                        # If there is a non-empty "working" cmd string, add it to the
                        # current command as its arguments.  Otherwise, the "cmd" stands
                        # alone and gets added to the list with no arguments.
                        if len(working_cmd) > 0:
                            working_cmd = daq_cmd + working_cmd
                            working_cmd_list.append(working_cmd)
                            working_cmd = ""
                        else:
                            working_cmd_list.append(daq_cmd)
                # restore the intended order of the commands to be sent to the process
                # (The "reversed" function returns an iterator that can only be used once.
                #  It seems safer to assign a fully-formed list to the this variable,
                #  so, we create a new list from the iterator.)
                reformatted_cmd_list = list(reversed(working_cmd_list))

                wait_params: ConsoleOutputWaitParameters = None
                if cmd_set.wait_for_command_completion:
                    wait_params = cmd_set.wait_params
                await send_commands(proc_info, target, shared_data, reformatted_cmd_list,
                                    wait_params, verbosity_level)

            else:
                now_string = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
                print(f"[integtest_proc_mgmt {now_string}] Error: Process '{target}' not found.")

    except asyncio.CancelledError:
        print(f"\n[integtest_proc_mgmt {now_string}] Received CancelledError...")
        pass
    finally:
        async with shared_data.lock:
            if shared_data.number_of_lines_printed_to_the_console > 0:
                print("---------- DAQ Session END ----------", flush=True)
                print("", flush=True)
            elif verbosity_level >= IntegtestVerbosityLevels.drunc_boot_terminate:
                # huh?
                print("", flush=True)

        # 4. Cleanup and terminate remaining processes
        if verbosity_level >= IntegtestVerbosityLevels.integtest_debug:
            now_string = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
            print(f"\n[integtest_proc_mgmt {now_string}] Shutting down processes...")
        for proc_name, proc_info in reversed(processes.items()):
            if proc_info.process.returncode is None:
                if verbosity_level >= IntegtestVerbosityLevels.integtest_debug:
                    now_string = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
                    print(f"\n[integtest_proc_mgmt {now_string}] Terminating the {proc_name} process...")
                proc_info.process.terminate()
                await proc_info.process.wait()
            proc_results[proc_name] = {"returncode": proc_info.process.returncode}

        # Cancel background reading tasks
        for proc_name, task in tasks.items():
            try:
                task.cancel()
                process_output = await task
                proc_results[proc_name]["stdout"] = process_output
            except asyncio.CancelledError:
                proc_results[proc_name]["stdout"] = "asyncio.CancelledError"
            except asyncio.InvalidStateError:
                proc_results[proc_name]["stdout"] = "asyncio.InvalidStateError"
            except asyncio.TimeoutError:
                proc_results[proc_name]["stdout"] = "asyncio.TimeoutError"

    return proc_results
