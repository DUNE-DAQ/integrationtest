import pytest
import asyncio
import getpass
import pathlib
import re
import time
from integrationtest.data_classes import *
from integrationtest.verbosity_helper import *
from datetime import datetime, timezone
from typing import Final

import functools
print = functools.partial(print, flush=True)  # always flush print() output

PROCESS_ECHO_STRING: Final[str] = "*** COMMAND HAS COMPLETED ***"


async def read_stream(stream, process_name, app_exe_name, print_proc_name, run_dir,
                      shared_data: CommandProcessingSharedData, verbosity_level):
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

            # if the special end-of-command string has been echo-ed by the process,
            # send the relevant signal to any waiting task by setting the completion event
            if PROCESS_ECHO_STRING in decoded_line:
                #print("=== Setting the completion event ===", flush=True)
                shared_data.cmd_cmplt_evt.set()
                continue

            # process the output of the "help" command, if requested
            async with shared_data.lock:
                if shared_data.parsing_of_help_output_in_progress:
                    trimmed_line = decoded_line.strip()
                    if len(trimmed_line) == 0:
                        continue
                    if "ocumented" in trimmed_line:
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
            if should_be_printed == False:
                lc_line = decoded_line.lower()
                if ("error" in lc_line and (not "In error" in decoded_line and not "Endpoint" in decoded_line)) \
                   or "warning" in lc_line or "critical" in lc_line:
                    should_be_printed = True

            # check for basic transition messages, if that level of verbosity is requested
            if should_be_printed == False:
                if verbosity_level >= IntegtestVerbosityLevels.drunc_boot_terminate:
                    if "Booting session" in decoded_line or \
                       ("Current FSM status is " in decoded_line and ("initial" in decoded_line or "running" in decoded_line)):
                        should_be_printed = True

            # check for all transition messages, if that level of verbosity is requested
            if should_be_printed == False:
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


async def wait_for_console_output_lull(start_time, wait_params: CommandWaitParameters,
                                       shared_data: CommandProcessingSharedData):
    now = time.time()
    while True:
        async with shared_data.lock:
            if shared_data.last_msg_time <= start_time:
                if now - start_time > wait_params.timeout_waiting_for_first_msg:
                    break
            else:
                if now - shared_data.last_msg_time >= wait_params.wait_time_after_last_msg:
                    break
        await asyncio.sleep(0.25)
        now = time.time()


async def send_commands(target_proc_info, proc_name, shared_data: CommandProcessingSharedData,
                        cmd_list, wait_params, verbosity_level):
    target_proc = target_proc_info.process
    if target_proc.returncode is not None:  # Check if process is still running
        now_string = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
        print(f"[integtest_proc_mgmt {now_string}] Error: {proc_name} has already exited, unable to send \"{cmd_list}\".")
        return

    # send the requested commands
    cmd_start_time = time.time()
    for cmd in cmd_list:
        target_proc.stdin.write((cmd + "\n").encode())
        await target_proc.stdin.drain()
        if verbosity_level >= IntegtestVerbosityLevels.integtest_debug:
            now_string = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
            print(f"[integtest_proc_mgmt {now_string}] Sent command to {proc_name}: {cmd}")
        else:
            async with shared_data.lock:
                if shared_data.number_of_lines_printed_to_the_console == 0:
                    print(".", end="")

    # wait for the command(s) to finish, if requested
    if not wait_params.wait_for_command_completion:
        return
    if wait_params.style == CommandWaitStyle.TIME_PLUS_EXIT:
        # The idea behind this command style is that we want to wait until the process has
        # exited and we want to support 'exit' timeout values that are not long and arbitrary.
        # In order to do that, we wait for a lull in the console output before waiting
        # for the process exit.  So, the exit timeout can hopefully be relative to the
        # finishing of the console output.
        # Of course, if the app doesn't support the "exit" command, there is no sense in
        # waiting for the process to respond to it.  But, we tell users that we skipped it.
        await wait_for_console_output_lull(cmd_start_time, wait_params, shared_data)
        if "exit" in target_proc_info.supported_commands:
            sleep_interval: float = wait_params.timeout_waiting_for_exit / 10
            for idx in range(10):
                if target_proc.returncode is not None:
                    break
                await asyncio.sleep(sleep_interval)
            if target_proc.returncode is None:
                now_string = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
                print(f"[integtest_proc_mgmt {now_string}] WARNING: timeout waiting for {proc_name} to exit in response to {cmd_list}")
        else:
            if verbosity_level >= IntegtestVerbosityLevels.integtest_debug:
                now_string = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
                print(f"[integtest_proc_mgmt {now_string}] The {proc_name} process doesn't support the 'exit' command, so waiting for exit was skipped")
    elif wait_params.style == CommandWaitStyle.ECHO:
        if "echo" in target_proc_info.supported_commands:
            shared_data.cmd_cmplt_evt.clear()
            target_proc.stdin.write((f"echo '{PROCESS_ECHO_STRING}'\n").encode())
            await target_proc.stdin.drain()
            if verbosity_level >= IntegtestVerbosityLevels.integtest_debug:
                now_string = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
                print(f"[integtest_proc_mgmt {now_string}] Sent command to {proc_name}: echo '{PROCESS_ECHO_STRING}'")
            await shared_data.cmd_cmplt_evt.wait()
            shared_data.cmd_cmplt_evt.clear()
        else:
            now_string = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
            print(f"[integtest_proc_mgmt {now_string}] The {proc_name} process doesn't support the 'echo' command, using TIME wait instead'")
            await wait_for_console_output_lull(cmd_start_time, wait_params, shared_data)
    else:  # treat everything else as wait_params.style == CommandWaitStyle.TIME:
        await wait_for_console_output_lull(cmd_start_time, wait_params, shared_data)


async def intg_process_manager(daq_session_ingredients: DAQSessionIngredients, run_dir,
                               verbosity_level):
    processes = {}
    tasks = {}
    command_completion_event = asyncio.Event()
    proc_results = {}
    shared_data: CommandProcessingSharedData = CommandProcessingSharedData()

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

        time.sleep(session_app.wait_time_after_start)

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
    help_cmd_wait_params = CommandWaitParameters(timeout_waiting_for_first_msg=2)
    await wait_for_console_output_lull(time.time(), help_cmd_wait_params, shared_data)
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

                await send_commands(proc_info, target, shared_data, reformatted_cmd_list,
                                    cmd_set.wait_params, verbosity_level)

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
