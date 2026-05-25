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

### Integtests in the _daqsystemtest_ repo:

| Integtest name | RTCM | FakeHSI | Triggers from TPs |
| --- | :---: | :---: | :---: |
| 3ru_1df_multirun_test.py | 1 Hz trigger rate, RWBT=-2000, RWET=5, RWW=32.1 usec | - | number of data producers=3, StreamEmu TP_rate param=1, TAMakerPrescale=100, TCMakerPrescale=100, effective 5.5 Hz, RWBT=0, RWET=32, RWW=512 nsec |
| 3ru_3df_multirun_test.py | 3 Hz trigger rate, RWBT=-2000, RWET=5, RWW=32.1 usec | - | number of data produsers=2, StreamEmu TP_rate param=1, TAMakerPrescale=100, TCMakerPrescale=100, effective 3.6 Hz, RWBT=0, RWET=32, RWW=512 nsec |
| disabled_tpg_test.py | - | - | - |
| example_system_test.py | - | - | - |
| fake_data_producer_test.py | - | - | - |
| long_window_readout_test.py | - | - | - |
| minimal_system_quick_test.py | - | - | - |
| readout_type_scan_test.py | - | - | - |
| sample_ehn1_multihost_test.py | - | - | - |
| small_footprint_quick_test.py | - | - | - |
| tpg_state_collection_test.py | - | - | - |
| tpreplay_test.py | - | - | - |
| tpstream_writing_test.py | - | - | - |
| trigger_bitwords_test.py | - | - | - |

### Integtests in the _dfmodules_ repo:

| Integtest name | RTCM | FakeHSI | Triggers from TPs |
| --- | :---: | :---: | :---: |
| disabled_output_test.py | - | - | - |
