#!/usr/bin/env python3
"""Deterministic biological clock verification layer (stdlib only).

BioClock recombines three concerns:
  - DriftDossier: clinical evidence drift tracking
  - Qvidence: bio data pipeline health
  - LazarettoStage: biological quarantine staging

No wall-clock state is used; every computation is a pure function of its inputs.
"""

SEVERITY = {"none": 0, "moderate": 1, "severe": 2}
DEFAULT_MAX_FRESHNESS_DAYS = 30


def _require_fields(name, obj, fields):
    if not isinstance(obj, dict):
        raise TypeError(f"{name} must be a dict")
    missing = [field for field in fields if field not in obj]
    if missing:
        raise ValueError(f"{name} missing fields: " + ", ".join(missing))


def _require_non_negative_number(name, value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{name} must be a number")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


def _validate_protocol(protocol):
    _require_fields("protocol", protocol, ("endpoint", "target_effect_size", "required_samples"))
    _require_non_negative_number("target_effect_size", protocol["target_effect_size"])
    _require_non_negative_number("required_samples", protocol["required_samples"])


def _validate_evidence(evidence):
    _require_fields(
        "evidence",
        evidence,
        ("observed_effect_size", "actual_samples", "data_freshness_days"),
    )
    _require_non_negative_number("observed_effect_size", evidence["observed_effect_size"])
    _require_non_negative_number("actual_samples", evidence["actual_samples"])
    _require_non_negative_number("data_freshness_days", evidence["data_freshness_days"])


def _validate_quarantine(quarantine_schedule):
    _require_fields("quarantine_schedule", quarantine_schedule, ("organism_id", "stages"))
    stages = quarantine_schedule["stages"]
    if not isinstance(stages, list):
        raise TypeError("quarantine_schedule.stages must be a list")
    for i, stage in enumerate(stages):
        _require_fields(f"quarantine_schedule.stages[{i}]", stage, ("name", "duration_days", "observation_passed"))
        _require_non_negative_number(f"quarantine_schedule.stages[{i}].duration_days", stage["duration_days"])
        if not isinstance(stage["observation_passed"], bool):
            raise TypeError(f"quarantine_schedule.stages[{i}].observation_passed must be a bool")


def _severity_for(drift_magnitude):
    if drift_magnitude < 0.1:
        return "none"
    if drift_magnitude < 0.3:
        return "moderate"
    return "severe"


def track_drift(protocol, evidence, max_freshness_days=DEFAULT_MAX_FRESHNESS_DAYS):
    """Measure clinical evidence drift against a trial protocol.

    protocol: {endpoint, target_effect_size, required_samples}
    evidence: {observed_effect_size, actual_samples, data_freshness_days}

    Returns a deterministic drift report dict.
    """
    _validate_protocol(protocol)
    _validate_evidence(evidence)
    _require_non_negative_number("max_freshness_days", max_freshness_days)

    target = protocol["target_effect_size"]
    observed = evidence["observed_effect_size"]
    required = protocol["required_samples"]
    actual = evidence["actual_samples"]
    data_freshness_days = evidence["data_freshness_days"]

    drift_magnitude = abs(target - observed)
    sample_gap = max(0, required - actual)
    drift_severity = _severity_for(drift_magnitude)
    freshness_expired = data_freshness_days > max_freshness_days
    protocol_compliant = (
        drift_severity == "none"
        and sample_gap == 0
        and not freshness_expired
    )

    return {
        "endpoint": protocol["endpoint"],
        "drift_magnitude": drift_magnitude,
        "sample_gap": sample_gap,
        "data_freshness_days": data_freshness_days,
        "max_freshness_days": max_freshness_days,
        "freshness_expired": freshness_expired,
        "drift_severity": drift_severity,
        "protocol_compliant": protocol_compliant,
    }


def certify_bio_clock(drift_report, quarantine_schedule):
    """Certify a biological clock from a drift report and quarantine stages.

    drift_report: output of track_drift (must carry drift_severity)
    quarantine_schedule: {organism_id, stages: [{name, duration_days, observation_passed}]}

    Returns a deterministic certification verdict dict.
    """
    _require_fields("drift_report", drift_report, ("drift_severity", "sample_gap", "freshness_expired"))
    _validate_quarantine(quarantine_schedule)

    drift_severity = drift_report["drift_severity"]
    stages = quarantine_schedule["stages"]
    all_stages_passed = bool(stages) and all(s["observation_passed"] for s in stages)

    if not all_stages_passed:
        certification = "blocked"
    elif drift_report.get("freshness_expired"):
        certification = "expired"
    elif drift_severity == "severe":
        certification = "revoked"
    elif drift_severity == "moderate" or drift_report.get("sample_gap", 0) > 0:
        certification = "conditional"
    else:
        certification = "certified"

    return {
        "organism_id": quarantine_schedule["organism_id"],
        "certification": certification,
        "drift_severity": drift_severity,
        "freshness_expired": drift_report.get("freshness_expired", False),
        "sample_gap": drift_report.get("sample_gap", 0),
        "quarantine_complete": all_stages_passed,
        "bio_clock_valid": certification == "certified",
    }


def render_report(result):
    """Render a drift report and/or a certification verdict as Markdown."""
    lines = ["# BioClock Report", ""]

    if "drift_magnitude" in result:
        endpoint = result.get("endpoint", "")
        lines.append(f"## Drift Dossier — {endpoint}")
        lines.append("")
        lines.append(f"- drift_magnitude: {result['drift_magnitude']}")
        lines.append(f"- drift_severity: **{result['drift_severity']}**")
        lines.append(f"- sample_gap: {result['sample_gap']}")
        lines.append(f"- data_freshness_days: {result['data_freshness_days']}")
        lines.append(f"- max_freshness_days: {result['max_freshness_days']}")
        lines.append(f"- freshness_expired: {result['freshness_expired']}")
        lines.append(f"- protocol_compliant: {result['protocol_compliant']}")
        lines.append("")

    if "certification" in result:
        organism_id = result.get("organism_id", "")
        lines.append(f"## Bio Clock Certification — {organism_id}")
        lines.append("")
        lines.append(f"- certification: **{result['certification']}**")
        lines.append(f"- drift_severity: {result['drift_severity']}")
        lines.append(f"- freshness_expired: {result['freshness_expired']}")
        lines.append(f"- sample_gap: {result['sample_gap']}")
        lines.append(f"- quarantine_complete: {result['quarantine_complete']}")
        lines.append(f"- bio_clock_valid: {result['bio_clock_valid']}")
        lines.append("")

    return "\n".join(lines)
