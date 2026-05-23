# Survey of triggers that are used in existing integtests as of May 2026

## Introduction

First, here a list of the typical trigger sources that we use in integration/regression tests (and emulated-data running generally):

* **RandomTriggerCandidateMaker**
    * This software module typically runs in the MLTApplication (along with the _MLTModule_ and the _DataHandlerModule_ that converts TriggerActivity objects into TriggerCandidate objects), and it receives TimeSync messages from the ReadoutApplications so that it knows what DTS (DUNE Timing System) timestamps are currently being processed by the emulated-data system.  It has the ability to produce periodic triggers at a configurable rate, and it uses the knowledge of "detector time" that it gains from the TimeSync messages to provide a useful timestamp in the TriggerCandidate objects that it creates.
* **FakeHSIEventGenerator**
* **TriggerActivity and TriggerCandidate objects derived from TriggerPrimitives**

Next, recall that it is the MLT (Module Level Trigger) that specifies the readout window size for each trigger (TriggerDecision).  It does this based on the configuration that it was provided.

## Summary information, by repository

| Integtest name | RTCM | FakeHSI | Triggers from TPs |
| --- | --- | --- | --- |
| 3ru_1df_multirun_test.py | | | |
| 3ru_3df_multirun_test.py | 3Hz | - | - |

### 3ru_1df_multirun_test.py

### 3ru_3df_multirun_test.py

- 3 Hz periodic triggers from RTCM

### disabled_tpg_test.py

### example_system_test.py

- 

### fake_data_producer_test.py

### long_window_readout_test.py

### minimal_system_quick_test.py

### readout_type_scan_test.py

### sample_ehn1_multihost_test.py

### small_footprint_quick_test.py

### tpg_state_collection_test.py

### tpreplay_test.py

### tpstream_writing_test.py

### trigger_bitwords_test.py

## dfmodules package

