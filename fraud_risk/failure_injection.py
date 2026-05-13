"""Shared helpers for failure injection scenarios."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


REPORT_DIR = Path("artifacts/reports")


def ensure_report_dir() -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    return REPORT_DIR


def write_report(filename: str, payload: Dict[str, Any]) -> Path:
    report_path = ensure_report_dir() / filename
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return report_path


def write_incident_report(scenario_name: str, report_data: Dict[str, Any]) -> Path:
    """Generate a markdown incident report from failure injection data."""
    
    # Map scenario names to severity levels
    severity_map = {
        "label_delay_spike": "HIGH",
        "feature_lag": "MEDIUM",
        "distribution_shift": "HIGH",
        "leakage": "CRITICAL",
    }
    
    # Get current date
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Build the markdown content
    markdown_content = f"""# Incident Report: {report_data.get('failure_type', scenario_name).replace('_', ' ').title()}

**Date**: {current_date}
**Severity**: {severity_map.get(report_data.get('failure_type', scenario_name), 'MEDIUM')}
**Status**: {report_data.get('status', 'INJECTED').upper()}

## Summary

{report_data.get('symptom', 'Failure scenario injected for testing purposes.')}

## Trigger

{report_data.get('trigger', 'Simulated failure injection for testing.')}

## Symptom

{report_data.get('symptom', 'Observable symptoms of the failure.')}

## Detection

{report_data.get('detection', 'How the failure was detected.')}

**Detection Time**: Immediate (simulated failure)

## Impact

**Quantitative Impact**:
"""
    
    # Add quantitative metrics
    metrics_added = False
    for key, value in report_data.items():
        if key not in ['failure_type', 'trigger', 'symptom', 'detection', 'impact',
                       'root_cause', 'mitigation', 'prevention', 'status']:
            if isinstance(value, (int, float)):
                markdown_content += f"- {key.replace('_', ' ').title()}: {value}\n"
                metrics_added = True
    
    if not metrics_added:
        markdown_content += "- See JSON report for detailed metrics\n"
    
    markdown_content += f"""
**Business Impact**:
{report_data.get('impact', 'Impact on system performance and reliability.')}

**Timeline**:
- Detection: Immediate (simulated)
- Diagnosis: Immediate (known failure scenario)
- Mitigation: Pending manual intervention
- Resolution: Pending

## Root Cause

**Technical Root Cause**: {report_data.get('root_cause', 'Simulated failure for testing purposes.')}

**Contributing Factors**:
1. Simulated failure injection scenario
2. Testing system resilience and monitoring
3. Validating incident response procedures

## Mitigation

**Immediate Actions**:
"""
    
    # Add mitigation section
    mitigation_text = report_data.get('mitigation', '1. Identify the failure\n2. Assess impact\n3. Apply corrective measures')
    markdown_content += mitigation_text + "\n"
    
    markdown_content += """

**Short-term Actions**:
1. Monitor system metrics
2. Verify mitigation effectiveness
3. Document lessons learned

**Long-term Actions**:
1. Implement automated detection
2. Add preventive measures
3. Update runbooks

## Prevention

"""
    
    # Add prevention section
    prevention_text = report_data.get('prevention', 'Preventive measures to avoid similar failures in the future.')
    markdown_content += prevention_text + "\n\n"
    
    markdown_content += """**Monitoring**:
- Automated alerts for similar patterns
- Regular health checks
- Performance metric tracking

**Process Changes**:
- Enhanced testing procedures
- Improved monitoring coverage
- Regular failure injection drills

**Technical Changes**:
- System hardening
- Redundancy improvements
- Better error handling

## Lessons Learned

1. System behavior under failure conditions validated
2. Monitoring and alerting effectiveness confirmed
3. Incident response procedures tested

## Interview Talking Point

"""
    
    # Build interview talking point
    failure_type = report_data.get('failure_type', 'system resilience').replace('_', ' ')
    symptom = report_data.get('symptom', 'The failure scenario')
    root_cause = report_data.get('root_cause', 'system issues')
    prevention = report_data.get('prevention', 'proper monitoring and preventive measures')
    
    interview_point = f"This incident demonstrates the importance of {failure_type} in production ML systems. {symptom} shows how {root_cause} can impact model performance. The key lesson is that {prevention} are essential for maintaining system reliability. This experience reinforced the need for comprehensive monitoring, automated detection, and well-documented incident response procedures."
    
    markdown_content += interview_point + "\n"
    
    # Write the markdown file
    report_filename = f"incident_{scenario_name}.md"
    report_path = ensure_report_dir() / report_filename
    report_path.write_text(markdown_content, encoding="utf-8")
    
    return report_path