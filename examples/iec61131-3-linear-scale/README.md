# PLC analogue input scaling — IEC 61131-3 Structured Text example

A small **vendor-neutral educational function block** for PLC programmers. It converts raw analogue input counts into engineering values and reports whether the result is inside the nominal calibrated range.

This is a public reference for an industrial automation problem. It is **not** a vendor-certified library, not a substitute for channel diagnostics and not qualified for safety-related logic.

## Why the raw endpoints are inputs

A 4–20 mA sensor may represent 0–10 bar, −50…+150 °C, 0–100% level or something else. The analogue module may output different raw counts at 4 and 20 mA depending on the manufacturer, model and configured mode. **Do not hard-code 0–27648 without reading the actual module manual.**

Configure the following values from verified hardware and calibration data:

| Input | Meaning | Illustrative value |
|---|---|---:|
| \`RawAtLowerRange\` | Raw counts at lower measured point | 100 |
| \`RawAtUpperRange\` | Raw counts at upper measured point | 200 |
| \`EUAtLowerRange\` | Engineering value at lower point | 0 bar |
| \`EUAtUpperRange\` | Engineering value at upper point | 10 bar |
| \`RawValue\` | Current raw count | 150 |

This hypothetical example gives 5 bar at raw 150. It is **not an actual Siemens/ОВЕН/Rockwell input scale**.

The calculation is:

\[
EU = EU_{low} + \frac{Raw - Raw_{low}}{Raw_{high} - Raw_{low}} \times (EU_{high} - EU_{low})
\]

The block deliberately reports *nominal range* separately from the computed value. If the sample is below/above the configured endpoints, \`EUValue\` is linearly extrapolated for diagnosis, while \`IsValid = FALSE\`.

## Outputs

| \`Status\` | Meaning | \`IsValid\` |
|---|---|---|
| 0 | Sample is inside nominal raw endpoints | TRUE |
| 1 | Block disabled | FALSE |
| 2 | Lower and upper raw endpoints are identical | FALSE |
| 3 | Sample below nominal range | FALSE |
| 4 | Sample above nominal range | FALSE |

Any actual wire-break or overflow indications **must also be handled using the input module's diagnostic/quality information**. Raw counts alone cannot reliably identify every fault. Never use the sample to bypass commissioning checks, output interlocks, E-stops, or Safety PLC functions.

## Reproducible example

- Source: [FB_LinearAnalogScale.st](FB_LinearAnalogScale.st)
- Independent Python maths tests: [reference_cases.py](reference_cases.py)
- Run \`python3 examples/iec61131-3-linear-scale/reference_cases.py\` to verify the example maths. **This does not compile or execute the Structured Text** — target IDE and hardware validation remain necessary.

For interactive conversion of **4–20 mA / 0–10 V**, reverse calculations, raw-code examples and a five-point CSV test table, use DLV's freely accessible [engineering calculator](https://dlvautomation.ru/blog/4-20ma-plk-kalkulyator/). The online calculator processes entered values locally in the browser. Its examples likewise do not replace official module documentation.

Published by [DLV Automation](https://dlvautomation.ru/) as a practical engineering reference; no service pricing, claims of certification or partner status are implied.
