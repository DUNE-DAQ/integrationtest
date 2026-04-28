from dataclasses import dataclass
#import pytest

@dataclass
class IntegtestVerbosityLevels:
    just_errors_and_warnings: int = 1  # shows just errors and warnings
    drunc_boot_terminate: int = 2  # adds a small subset of drunc transitions
    drunc_transitions: int = 3  # adds all drunc transitions plus validation check results
    integtest_debug: int = 4  # adds ResourceValidation debug info and any other integtest debug
    full_output: int = 5  # shows everything
    drunc_debug: int = 6  # enables drunc debug messages

class VerbosityHelper:
    #def __init__(self, request):
    #    self.requested_verbosity = int(request.config.getoption("--integtest-verbosity"))

    def __init__(self, verbosity_level):
        self.requested_verbosity = int(verbosity_level)

    def get_requested_verbosity_level(self) -> int:
        return self.requested_verbosity

    def compare_level(self, comparison_level) -> bool:
        return self.requested_verbosity >= int(comparison_level)

    def lvl_print(self, comparison_level: int, text: str):
        if self.requested_verbosity >= comparison_level:
            print(text, flush=True)
