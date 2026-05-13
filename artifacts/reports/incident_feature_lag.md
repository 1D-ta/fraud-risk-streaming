# Incident Report: Feature Lag

**Date**: 2026-05-13
**Severity**: MEDIUM
**Status**: INJECTED

## Summary

Newest transactions have zeroed velocity features

## Trigger

Feature pipeline delay left recent data stale

## Symptom

Newest transactions have zeroed velocity features

## Detection

Feature freshness monitoring shows old feature timestamps

**Detection Time**: Immediate (simulated failure)

## Impact

**Quantitative Impact**:
- Affected Transactions: 5026
- Lag Days: 3

**Business Impact**:
Recent fraud is under-scored and recall drops

**Timeline**:
- Detection: Immediate (simulated)
- Diagnosis: Immediate (known failure scenario)
- Mitigation: Pending manual intervention
- Resolution: Pending

## Root Cause

**Technical Root Cause**: Feature job lagged behind the event stream

**Contributing Factors**:
1. Simulated failure injection scenario
2. Testing system resilience and monitoring
3. Validating incident response procedures

## Mitigation

**Immediate Actions**:
Backfill the missing window and re-score affected transactions


**Short-term Actions**:
1. Monitor system metrics
2. Verify mitigation effectiveness
3. Document lessons learned

**Long-term Actions**:
1. Implement automated detection
2. Add preventive measures
3. Update runbooks

## Prevention

Alert on feature lag and automate backfills

**Monitoring**:
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

This incident demonstrates the importance of feature lag in production ML systems. Newest transactions have zeroed velocity features shows how Feature job lagged behind the event stream can impact model performance. The key lesson is that Alert on feature lag and automate backfills are essential for maintaining system reliability. This experience reinforced the need for comprehensive monitoring, automated detection, and well-documented incident response procedures.
