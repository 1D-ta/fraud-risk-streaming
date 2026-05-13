# Incident Report: Leakage Bug

**Date**: 2026-05-13
**Severity**: MEDIUM
**Status**: INJECTED

## Summary

Validation metrics look suspiciously perfect

## Trigger

A feature accidentally used future labels from the same user

## Symptom

Validation metrics look suspiciously perfect

## Detection

Leakage checks and production monitoring disagree

**Detection Time**: Immediate (simulated failure)

## Impact

**Quantitative Impact**:
- Affected Transactions: 50000
- Max Future Fraud Count: 87

**Business Impact**:
The model looks great offline and fails in production

**Timeline**:
- Detection: Immediate (simulated)
- Diagnosis: Immediate (known failure scenario)
- Mitigation: Pending manual intervention
- Resolution: Pending

## Root Cause

**Technical Root Cause**: A hidden feature stores future fraud counts

**Contributing Factors**:
1. Simulated failure injection scenario
2. Testing system resilience and monitoring
3. Validating incident response procedures

## Mitigation

**Immediate Actions**:
Remove the leaky feature and retrain the model


**Short-term Actions**:
1. Monitor system metrics
2. Verify mitigation effectiveness
3. Document lessons learned

**Long-term Actions**:
1. Implement automated detection
2. Add preventive measures
3. Update runbooks

## Prevention

Automated leakage checks and temporal validation

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

This incident demonstrates the importance of leakage bug in production ML systems. Validation metrics look suspiciously perfect shows how A hidden feature stores future fraud counts can impact model performance. The key lesson is that Automated leakage checks and temporal validation are essential for maintaining system reliability. This experience reinforced the need for comprehensive monitoring, automated detection, and well-documented incident response procedures.
