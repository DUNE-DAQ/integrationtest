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
# resval.cpu_count_needs(32, 64)
# resval.free_memory_needs(28)
# # set other minimum values, if desired
# resval_debug_string = resval.get_debug_string()
# print(f"{resval_debug_string}")
# # then, in one of the pytest "tests"
# if not resval.required_resources_are_present
#     resval_full_report = resval.get_required_resources_report()
#     print(f"{resval_full_report}")
#     resval_summary_report = resval.get_required_resources_summary()
#     pytest.skip(f"{resval_summary_report}")
# if not resval.recommended_resources_are_present
#     resval_full_report = resval.get_recommended_resources_report()
#     print(f"{resval_full_report}")

import os
import psutil
import shutil

class ResourceValidator:
    def __init__(self):
        # initialization of constants
        hostname = os.uname().nodename
        self.required_resource_report_header = f"This computer ({hostname}) does not have enough resources to run this test."
        self.recommended_resource_report_header = f"This computer ({hostname}) does not have the recommended amount of resources to run this test."
        self.report_indentation = " *"

        # set the initial state of the status variables to indicate sufficient resources
        # users check these directly to confirm if resources are available
        self.this_computer_has_sufficient_resources = True
        self.required_resources_are_present = True
        self.recommended_resources_are_present = True

        # debug and report strings start out empty and are filled in, as needed
        self.debug_string = ""
        self.required_resource_report_string = ""
        self.recommended_resource_report_string = ""

        # this is provided to users for whatever extra disk-space-checking they may want to do
        self.free_disk_space_gb = -1

    # deprecated method, will be removed someday, simply calls newer method
    def require_cpu_count(self, minimum_cpu_count):
        self.cpu_count_needs(required_count=minimum_cpu_count)

    # method to specify the needs for number of CPUs
    def cpu_count_needs(self, required_count=-1, recommended_count=-1):
        cpu_count = os.cpu_count()
        self.debug_string += f"\nDEBUG: CPU count is {cpu_count}"
        if required_count >= 0:
            self.debug_string += f", required number is {required_count}"
        if recommended_count >= 0:
            self.debug_string += f", recommended number is {recommended_count}"
        if cpu_count < required_count:
            self.this_computer_has_sufficient_resources = False
            self.required_resources_are_present = False
            if len(self.required_resource_report_string) == 0:
                self.required_resource_report_string = self.required_resource_report_header
            self.required_resource_report_string += f"\n{self.report_indentation} CPU count is {cpu_count}, required CPU count is {required_count}."
        if cpu_count < recommended_count:
            self.recommended_resources_are_present = False
            if len(self.recommended_resource_report_string) == 0:
                self.recommended_resource_report_string = self.recommended_resource_report_header
            self.recommended_resource_report_string += f"\n{self.report_indentation} CPU count is {cpu_count}, recommended CPU count is {recommended_count}."

    # deprecated method, will be removed someday, simply calls newer method
    def require_free_memory_gb(self, minimum_free_memory):
        self.free_memory_needs(required_free_memory=minimum_free_memory)

    # method to specify the needs for free memory, in units of GB
    def free_memory_needs(self, required_free_memory=-1, recommended_free_memory=-1):
        mem_obj = psutil.virtual_memory()
        free_mem = round((mem_obj.available / (1024 * 1024 * 1024)), 2)
        self.debug_string += f"\nDEBUG: Free memory is {free_mem} GB"
        if required_free_memory >= 0:
            self.debug_string += f", required amount is {required_free_memory}."
        if recommended_free_memory >= 0:
            self.debug_string += f", recommended amount is {recommended_free_memory}."
        if free_mem < required_free_memory:
            self.this_computer_has_sufficient_resources = False
            self.required_resources_are_present = False
            if len(self.required_resource_report_string) == 0:
                self.required_resource_report_string = self.required_resource_report_header
            self.required_resource_report_string += f"\n{self.report_indentation} Free memory is {free_mem} GB, required amount is {required_free_memory}."
        if free_mem < recommended_free_memory:
            self.recommended_resources_are_present = False
            if len(self.recommended_resource_report_string) == 0:
                self.recommended_resource_report_string = self.recommended_resource_report_header
            self.recommended_resource_report_string += f"\n{self.report_indentation} Free memory is {free_mem} GB, recommended amount is {recommended_free_memory}."

    # deprecated method, will be removed someday, simply calls newer method
    def require_total_memory_gb(self, minimum_total_memory):
        self.total_memory_needs(required_total_memory=minimum_total_memory)

    # method to specify the needs for total memory, in units of GB
    def total_memory_needs(self, required_total_memory=-1, recommended_total_memory=-1):
        mem_obj = psutil.virtual_memory()
        total_mem = round((mem_obj.available / (1024 * 1024 * 1024)), 2)
        self.debug_string += f"\nDEBUG: Total memory is {total_mem} GB"
        if required_total_memory >= 0:
            self.debug_string += f", required amount is {required_total_memory}."
        if recommended_total_memory >= 0:
            self.debug_string += f", recommended amount is {recommended_total_memory}."
        if total_mem < required_total_memory:
            self.this_computer_has_sufficient_resources = False
            self.required_resources_are_present = False
            if len(self.required_resource_report_string) == 0:
                self.required_resource_report_string = self.required_resource_report_header
            self.required_resource_report_string += f"\n{self.report_indentation} Total memory is {total_mem} GB, required amount is {required_total_memory}."
        if total_mem < recommended_total_memory:
            self.recommended_resources_are_present = False
            if len(self.recommended_resource_report_string) == 0:
                self.recommended_resource_report_string = self.recommended_resource_report_header
            self.recommended_resource_report_string += f"\n{self.report_indentation} Total memory is {total_mem} GB, recommended amount is {recommended_total_memory}."

    # deprecated method, will be removed someday, simply calls newer method
    def require_free_disk_space_gb(self, path_of_interest, minimum_free_disk_space):
        self.free_disk_space_needs(path_of_interest, required_free_disk_space=minimum_free_disk_space)

    # method to specify the needs for free disk space, in units of GB
    def free_disk_space_needs(self, path_of_interest, required_free_disk_space=-1, recommended_free_disk_space=-1):
        disk_space = shutil.disk_usage(path_of_interest)
        self.free_disk_space_gb = disk_space.free / (1024 * 1024 * 1024)
        self.debug_string += f"\nDEBUG: Free disk space on \"{path_of_interest}\" is {self.free_disk_space_gb} GB"
        if required_free_disk_space >= 0:
            self.debug_string += f", required amount is {required_free_disk_space}."
        if recommended_free_disk_space >= 0:
            self.debug_string += f", recommended amount is {recommended_free_disk_space}."
        if self.free_disk_space_gb < required_free_disk_space:
            self.this_computer_has_sufficient_resources = False
            self.required_resources_are_present = False
            if len(self.required_resource_report_string) == 0:
                self.required_resource_report_string = self.required_resource_report_header
            self.required_resource_report_string += f"\n{self.report_indentation} Free disk space on \"{path_of_interest}\" is {self.free_disk_space_gb} GB, required amount is {required_free_disk_space}."
        if self.free_disk_space_gb < recommended_free_disk_space:
            self.recommended_resources_are_present = False
            if len(self.recommended_resource_report_string) == 0:
                self.recommended_resource_report_string = self.recommended_resource_report_header
            self.recommended_resource_report_string += f"\n{self.report_indentation} Free disk space on \"{path_of_interest}\" is {self.free_disk_space_gb} GB, recommended amount is {recommended_free_disk_space}."

    # deprecated method, will be removed someday, simply calls newer method
    def require_total_disk_space_gb(self, path_of_interest, minimum_total_disk_space):
        self.total_disk_space_needs(path_of_interest, required_total_disk_space=minimum_total_disk_space)

    # method to specify the needs for total disk space, in units of GB
    def total_disk_space_needs(self, path_of_interest, required_total_disk_space=-1, recommended_total_disk_space=-1):
        disk_space = shutil.disk_usage(path_of_interest)
        self.total_disk_space_gb = disk_space.total / (1024 * 1024 * 1024)
        self.debug_string += f"\nDEBUG: Total disk space on \"{path_of_interest}\" is {self.total_disk_space_gb} GB"
        if required_total_disk_space >= 0:
            self.debug_string += f", required amount is {required_total_disk_space}."
        if recommended_total_disk_space >= 0:
            self.debug_string += f", recommended amount is {recommended_total_disk_space}."
        if self.total_disk_space_gb < required_total_disk_space:
            self.this_computer_has_sufficient_resources = False
            self.required_resources_are_present = False
            if len(self.required_resource_report_string) == 0:
                self.required_resource_report_string = self.required_resource_report_header
            self.required_resource_report_string += f"\n{self.report_indentation} Total disk space on \"{path_of_interest}\" is {self.total_disk_space_gb} GB, required amount is {required_total_disk_space}."
        if self.total_disk_space_gb < recommended_total_disk_space:
            self.recommended_resources_are_present = False
            if len(self.recommended_resource_report_string) == 0:
                self.recommended_resource_report_string = self.recommended_resource_report_header
            self.recommended_resource_report_string += f"\n{self.report_indentation} Total disk space on \"{path_of_interest}\" is {self.total_disk_space_gb} GB, recommended amount is {recommended_total_disk_space}."

    def get_debug_string(self):
        return self.debug_string

    def get_insufficient_resources_report(self):
        return self.required_resource_report_string

    def get_insufficient_resources_summary(self):
        return self.required_resource_report_header

    def get_required_resources_report(self):
        return self.required_resource_report_string

    def get_required_resources_summary(self):
        return self.required_resource_report_header

    def get_recommended_resources_report(self):
        return self.recommended_resource_report_string

    def get_recommended_resources_summary(self):
        return self.recommended_resource_report_header
