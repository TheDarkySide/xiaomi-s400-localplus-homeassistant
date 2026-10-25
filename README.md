# Xiaomi S400 Local Plus for Home Assistant

[![GitHub Release](https://img.shields.io/github/v/release/TheDarkySide/xiaomi-s400-localplus-homeassistant.svg?style=flat-square)](https://github.com/TheDarkySide/xiaomi-s400-localplus-homeassistant/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom_Repository-orange.svg?style=flat-square)](https://hacs.xyz)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg?style=flat-square)](LICENSE)

A high-performance, 100% local Home Assistant integration for the **Xiaomi Body Composition Scale S400** (`MJTZC01YM` / `yunmai.scales.ms103/ms104/ms107`).

Forked and enhanced from [kbpk/xiaomi-s400-homeassistant](https://github.com/kbpk/xiaomi-s400-homeassistant).

---

## Features & Highlights

* **100% Local Operation:** Data decryption and state processing take place entirely on your Home Assistant machine via Bluetooth. No cloud traffic, no external server dependency.
* **Dual Operation Modes:**
  * **Passive BLE Mode (Bindkey only):** Decodes encrypted MiBeacon v4/v5 advertisement broadcasts. Extremely fast, lightweight, and zero battery impact.
  * **Active GATT Mode (Bindkey + Token):** Automatically connects to the scale when awake, authenticates via standard Xiaomi Auth v2, and streams real-time weight and final CMTP packets.
* **Complete Metric & Sensor Suite:**
  * **Weight:** Real-time and stabilized reading (`kg`).
  * **Heart Rate:** Decoded directly from both passive frames and active CMTP stream (`bpm`).
  * **Dual-Frequency Impedance:** Bioelectrical impedance at **50 kHz** (High / $Z_{lf}$) and **250 kHz** (Low / $Z_{hf}$) in $\Omega$.
  * **Profile ID:** Decoded physical user slot assigned by the scale hardware.
  * **Measurement Timestamp:** Diagnostic sensor showing when the measurement stabilized on the device.
  * **Diagnostic Sensors:** Bluetooth RSSI, Stabilized binary sensor, and GATT Connected state.
* **Clean Connection Lifecycle:** Enhanced GATT teardown logic automatically disconnects immediately after stabilized impedance and heart rate are received, preventing Bluetooth bus saturation and scale lockout.
* **Reconfiguration Support:** Update your bindkey or token at any time via **Settings → Devices & Services → Configure** without losing entity history.

---

## Entities Provided

| Entity | Type | Description |
| :--- | :--- | :--- |
| `sensor.xiaomi_s400_<mac>_weight` | Sensor | Current/stabilized weight in kg |
| `sensor.xiaomi_s400_<mac>_heart_rate` | Sensor | Heart rate measurement in bpm |
| `sensor.xiaomi_s400_<mac>_impedance_low` | Sensor | High-frequency impedance (250 kHz, $Z_{hf}$) in $\Omega$ |
| `sensor.xiaomi_s400_<mac>_impedance_high` | Sensor | Low-frequency impedance (50 kHz, $Z_{lf}$) in $\Omega$ |
| `sensor.xiaomi_s400_<mac>_profile_id` | Sensor | Physical scale user profile index |
| `sensor.xiaomi_s400_<mac>_measurement_time` | Diagnostic | Hardware measurement timestamp |
| `sensor.xiaomi_s400_<mac>_signal_strength` | Diagnostic | Bluetooth RSSI in dBm |
| `binary_sensor.xiaomi_s400_<mac>_stabilized` | Binary Sensor | `on` when measurement has stabilized |
| `binary_sensor.xiaomi_s400_<mac>_gatt_connected` | Binary Sensor | `on` when active GATT session is open |

---

## Installation via HACS

1. Open **HACS** in your Home Assistant UI.
2. Click the three dots in the top-right corner and select **Custom repositories**.
3. Add the repository:
   - **Repository:** `https://github.com/TheDarkySide/xiaomi-s400-localplus-homeassistant`
   - **Category:** `Integration`
4. Click **Add**, locate **Xiaomi S400 Local Plus**, and click **Download**.
5. Restart Home Assistant.

---

## Configuration

1. In Home Assistant, navigate to **Settings** → **Devices & Services** → **Add Integration**.
2. Search for **Xiaomi S400 Local Plus**.
3. Enter your scale credentials:
   - **Bluetooth MAC Address:** e.g. `CC:F9:57:A4:A1:XX`
   - **Bindkey (32 hex characters):** e.g. `c0326e129119c8d0cbbadfe4eb8ef025`
   - **Token (24 hex characters, optional):** Required only if you wish to use active GATT streaming. If left blank, the integration operates in passive BLE advertisement mode.
4. Click **Submit**.

> **Tip:** You can obtain your scale's MAC address and bindkey easily using the [Xiaomi Cloud Tokens Extractor](https://github.com/PiotrMachowski/Xiaomi-Cloud-Tokens-Extractor) after binding the scale once to the official Mi Home / Mi Fitness app.

---

## Integration with Bodymiscale

To compute advanced body composition metrics (Body Fat %, Muscle Mass, Water %, Bone Mass, Protein, BMR, and Body Score), pair this integration with **[TheDarkySide/bodymiscale-s400](https://github.com/TheDarkySide/bodymiscale-s400)**:

* Weight Sensor: `sensor.xiaomi_s400_<mac>_weight`
* Impedance Mode: **Dual Frequency**
* Impedance Low (250 kHz): `sensor.xiaomi_s400_<mac>_impedance_low`
* Impedance High (50 kHz): `sensor.xiaomi_s400_<mac>_impedance_high`
* User Identification: **Profile ID** (`sensor.xiaomi_s400_<mac>_profile_id`)

---

## License

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for details.
