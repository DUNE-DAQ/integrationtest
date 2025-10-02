# 01-Oct-2025, KAB:  This code is intended to provide a utility class that takes care
# of checking whether the current computer has sufficient resources (memory, CPU,
# disk space) for running a given integrationtest.
#
# The intention is that users would create an instance of the ResourceValidator in their
# integtest code, set whichever minimum sizes they want to enforce, and call the
# appropriate methods in the ResourceValidator instance to see where sufficient resources
# are available.  Only the resources that have been explicitly set in the
# ResourceValidator instance are considered when determining if sufficient resources are
# available.
#
# The current implementation is not bullet-proof.  A given resource limit value should only
# be set once.
#
# Here is pseudo-code for using this utility:
#
# import integrationtest.resource_validation as resource_validation
# resval = resource_validation.ResourceValidator()
# resval.require_cpu_count(64)
# resval.require_free_memory_gb(28)
# # set other minimum values, if desired
# resval_debug_string = resval.get_debug_string()
# print(f"{resval_debug_string}")
# # then, in one of the pytest "tests"
# if not resval.this_computer_has_sufficient_resources:
#     resval_full_report = resval.get_insufficient_resources_report()
#     print(f"{resval_full_report}")
#     resval_summary_report = resval.get_insufficient_resources_summary()
#     pytest.skip(f"{resval_summary_report}")

import os
import psutil
import shutil

class ResourceValidator:
    def __init__(self):
        self.this_computer_has_sufficient_resources = True

        hostname = os.uname().nodename
        self.report_header = f"This computer ({hostname}) does not have enough resources to run this test."
        self.report_indentation = " *"

        self.debug_string = ""
        self.report_string = ""

        self.free_disk_space_gb = -1

    def require_cpu_count(self, minimum_cpu_count):
        cpu_count = os.cpu_count()
        self.debug_string += f"\nDEBUG: CPU count is {cpu_count}, minimum required number is {minimum_cpu_count}."
        if cpu_count < minimum_cpu_count:
            self.this_computer_has_sufficient_resources = False
            if len(self.report_string) == 0:
                self.report_string = self.report_header
            self.report_string += f"\n{self.report_indentation} CPU count is {cpu_count}, minimum CPU count is {minimum_cpu_count}."

    def require_free_memory_gb(self, minimum_free_memory):
        mem_obj = psutil.virtual_memory()
        free_mem = round((mem_obj.available / (1024 * 1024 * 1024)), 2)
        self.debug_string += f"\nDEBUG: Free memory is {free_mem} GB, minimum required amount is {minimum_free_memory}."
        if free_mem < minimum_free_memory:
            self.this_computer_has_sufficient_resources = False
            if len(self.report_string) == 0:
                self.report_string = self.report_header
            self.report_string += f"\n{self.report_indentation} Free memory is {free_mem} GB, minimum amount is {minimum_free_memory}."

    def require_total_memory_gb(self, minimum_total_memory):
        mem_obj = psutil.virtual_memory()
        total_mem = round((mem_obj.total / (1024 * 1024 * 1024)), 2)
        self.debug_string += f"\nDEBUG: Total memory is {total_mem} GB, minimum required amount is {minimum_total_memory}."
        if total_mem < minimum_total_memory:
            self.this_computer_has_sufficient_resources = False
            if len(self.report_string) == 0:
                self.report_string = self.report_header
            self.report_string += f"\n{self.report_indentation} Total memory is {total_mem} GB, minimum amount is {minimum_total_memory}."

    def require_free_disk_space_gb(self, path_of_interest, minimum_free_disk_space):
        disk_space = shutil.disk_usage(path_of_interest)
        self.free_disk_space_gb = disk_space.free / (1024 * 1024 * 1024)
        self.debug_string += f"\nDEBUG: Free disk space on \"{path_of_interest}\" is {self.free_disk_space_gb} GB, minimum required amount is {minimum_free_disk_space}."
        if self.free_disk_space_gb < minimum_free_disk_space:
            self.this_computer_has_sufficient_resources = False
            if len(self.report_string) == 0:
                self.report_string = self.report_header
            self.report_string += f"\n{self.report_indentation} Free disk space on \"{path_of_interest}\" is {self.free_disk_space_gb} GB, minimum amount is {minimum_free_disk_space}."

    def require_total_disk_space_gb(self, path_of_interest, minimum_total_disk_space):
        disk_space = shutil.disk_usage(path_of_interest)
        total_disk_space = disk_space.total / (1024 * 1024 * 1024)
        self.debug_string += f"\nDEBUG: Total disk space on \"{path_of_interest}\" is {total_disk_space} GB, minimum required amount is {minimum_total_disk_space}."
        if total_disk_space < minimum_total_disk_space:
            self.this_computer_has_sufficient_resources = False
            if len(self.report_string) == 0:
                self.report_string = self.report_header
            self.report_string += f"\n{self.report_indentation} Total disk space on \"{path_of_interest}\" is {total_disk_space} GB, minimum amount is {minimum_total_disk_space}."

    def get_debug_string(self):
        return self.debug_string

    def get_insufficient_resources_report(self):
        return self.report_string

    def get_insufficient_resources_summary(self):
        return self.report_header
