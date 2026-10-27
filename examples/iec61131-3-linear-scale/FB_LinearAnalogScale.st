(*
 Educational IEC 61131-3 Structured Text example, not a safety function.
 Analog input raw counts -> engineering units. No vendor-specific raw assumptions.

 Source: DLV Automation industrial automation reference.
 Real deployments require module-specific fault diagnostics, I/O tests
 and approved commissioning procedures.
*)
FUNCTION_BLOCK FB_LinearAnalogScale
VAR_INPUT
    Enable          : BOOL;
    RawValue        : LREAL;
    RawAtLowerRange : LREAL; // Actual raw code for lower physical point
    RawAtUpperRange : LREAL; // Actual raw code for upper physical point
    EUAtLowerRange  : LREAL; // e.g. pressure at 4 mA
    EUAtUpperRange  : LREAL; // e.g. pressure at 20 mA
END_VAR
VAR_OUTPUT
    EUValue   : LREAL; // Diagnostic value; only use when IsValid = TRUE
    Fraction  : LREAL; // 0.0 to 1.0 in nominal range
    IsValid   : BOOL;  // Does NOT replace channel-quality diagnostics
    Status    : UINT;  // 0=OK, 1=Disabled, 2=Bad config, 3=Below, 4=Above
END_VAR
VAR
    RawSpan : LREAL;
END_VAR

EUValue := 0.0;
Fraction := 0.0;
IsValid := FALSE;
Status := UINT#1;

IF Enable THEN
    RawSpan := RawAtUpperRange - RawAtLowerRange;

    IF ABS(RawSpan) < 0.000000001 THEN
        Status := UINT#2;
    ELSE
        Fraction := (RawValue - RawAtLowerRange) / RawSpan;
        EUValue := EUAtLowerRange
                   + Fraction * (EUAtUpperRange - EUAtLowerRange);

        IF Fraction < 0.0 THEN
            Status := UINT#3; // Outside nominal range; value extrapolated
        ELSIF Fraction > 1.0 THEN
            Status := UINT#4; // Outside nominal range; value extrapolated
        ELSE
            Status := UINT#0;
            IsValid := TRUE;
        END_IF;
    END_IF;
END_IF;
END_FUNCTION_BLOCK
