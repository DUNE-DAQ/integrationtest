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

* RWTB - readout window ticks before - this value determines the start of the readout window. This number of DTS clock ticks is subtracted from the trigger time to determine the start of the readout window.
* RWTA - readout window ticks after - this value determines the end of the readout window. This number of DTS clock ticks is added to the trigger time to determine the end of the readout window.
* RWW - readout window width, in either DTS clock ticks, wallclock seconds, or both

### Integtests in the _daqsystemtest_ repo:

| Integtest name | RTCM | FakeHSI | Triggers from TPs |
| --- | :---: | :---: | :---: |
| 3ru_1df_multirun_test.py | | | |
| 3ru_3df_multirun_test.py | 3Hz trigger rate, RWTB=abc,<br/>RWTB=def, RWW: pdq sec | - | - |
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
