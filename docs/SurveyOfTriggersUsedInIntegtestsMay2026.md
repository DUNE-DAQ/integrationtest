# Survey of trigger and readout window configurations that are used in existing integtests, May 2026

## Introduction

First, here a list of the trigger sources that we typically use in integration/regression tests (and emulated-data running generally):

* **RandomTriggerCandidateMaker**
    * This software module typically runs in the MLTApplication (along with the _MLTModule_ and the _DataHandlerModule_ that converts TriggerActivity objects into TriggerCandidate objects), and it receives TimeSync messages from the ReadoutApplications so that it knows what DTS (DUNE Timing System) timestamps are currently being processed by the emulated-data system.  It has the ability to produce periodic triggers at a configurable rate, and it uses the knowledge of "detector time" that it gains from the TimeSync messages to provide a useful timestamp in the TriggerCandidate objects that it creates.
* **FakeHSIEventGenerator**
* **TriggerActivity and TriggerCandidate objects derived from TriggerPrimitives**

Next, recall that it is the MLT (Module Level Trigger) that specifies the readout window size for each trigger (TriggerDecision).  It does this based on the configuration information that it was provided.

## Configured trigger types, trigger rates, readout window widths, etc.

The tables in this section list the configuration parameters that are set for each of the integration tests.  If an integtest uses more than one DUNE-DAQ configuration, the super-set of trigger types is listed.  If a given test does not use a particular trigger type, nothing is listed.

To help save space in the table cells, the following abbreviations are used:

* RWBT - readout window begin ticks - this value determines the beginning of the readout window.  It is added to the trigger time to determine the beginning of the readout window.  Obviously, if this value is less than zero, the result is a timestamp that is earlier than the trigger time.
* RWET - readout window end ticks - this value determines the end of the readout window.  It is added to the trigger time to determine the end of the readout window.
* RWW - readout window width, in either DTS clock ticks, wallclock time, or both.

ToDo:  add an explanation of how the emulated TP rate is determined.  e.g. 9x64x100 = 57,600 Hz of TPs; 57600/100/100 = 5.8 Hz of kPrescale triggers

### Integtests in the _daqsystemtest_ repo:

| Integtest name | RTCM | FakeHSI | Triggers from TPs |
| --- | :---: | :---: | :---: |
| 3ru_1df_multirun_test.py | 1 Hz trigger rate, RWBT=-2000, RWET=5, RWW=32.1 usec | - | number of WIBs=9, StreamEmu TP_rate param=1, TAMakerPrescale=100, TCMakerPrescale=100, effective 5.5 Hz, RWBT=0, RWET=32, RWW=512 nsec |
| 3ru_3df_multirun_test.py | 3 Hz trigger rate, RWBT=-2000, RWET=5, RWW=32.1 usec | - | number of WIBs=6, StreamEmu TP_rate param=1, TAMakerPrescale=100, TCMakerPrescale=100, effective 3.6 Hz, RWBT=0, RWET=32, RWW=512 nsec |
| disabled_tpg_test.py | 1 Hz trigger rate, RWBT=-2000, RWET=5, RWW=32.1 usec | 3 Hz trigger rate, RWBT=-3000, RWET=1001, RWW=64.02 usec | - |
| example_system_test.py | 1 Hz trigger rate, RWBT=-2000, RWET=5, RWW=32.1 usec | 3 Hz trigger rate, RWBT=-3000, RWET=1001, RWW=64.02 usec | number of WIBs=4 or 8, StreamEmu TP_rate param=1, TAMakerPrescale=1000, TCMakerPrescale=100, effective 0.25 or 0.5 Hz, RWBT=0, RWET=32, RWW=512 nsec |
| fake_data_producer_test.py | 1 Hz trigger rate, RWBT=-2000, RWET=2001, RWW=64.02 usec | - | - |
| long_window_readout_test.py | 0.05 Hz trigger rate, RWBT=-100000000, RWET=1000000, RWW=1.62 sec | - | - |
| minimal_system_quick_test.py | 1 Hz trigger rate, RWBT=-2000, RWET=5, RWW=32.1 usec | - | - |
| readout_type_scan_test.py | - | - | - |
| sample_ehn1_multihost_test.py | - | - | - |
| small_footprint_quick_test.py | - | 1 Hz trigger rate, RWBT=-3000, RWET=1001, RWW=64.02 usec  | - |
| tpg_state_collection_test.py | 1 Hz trigger rate, RWBT=-2000, RWET=5, RWW=32.1 usec | - | - |
| tpreplay_test.py | 0 Hz | - | - |
| tpstream_writing_test.py | - | - | - |
| trigger_bitwords_test.py | - | - | - |

### Integtests in the _dfmodules_ repo:

| Integtest name | RTCM | FakeHSI | Triggers from TPs |
| --- | :---: | :---: | :---: |
| disabled_output_test.py | - | - | - |
