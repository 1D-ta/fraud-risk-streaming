# Incident Report: Distribution Shift

**Date**: 2026-05-13
**Severity**: HIGH
**Status**: INJECTED

## Summary

Review queue overflows with high-risk scores

## Trigger

Holiday shopping surge pushed amounts far above the training distribution

## Symptom

Review queue overflows with high-risk scores

## Detection

Drift monitoring shows PSI spikes on amount-sensitive features

**Detection Time**: Immediate (simulated failure)

## Impact

**Quantitative Impact**:
- Affected Transactions: 200
- Amount Multiplier: 10.0

**Business Impact**:
False positives increase and reviewers are overwhelmed

**Timeline**:
- Detection: Immediate (simulated)
- Diagnosis: Immediate (known failure scenario)
- Mitigation: Pending manual intervention
- Resolution: Pending

## Root Cause

**Technical Root Cause**: The model was trained on a narrower spending distribution

**Contributing Factors**:
1. Simulated failure injection scenario
2. Testing system resilience and monitoring
3. Validating incident response procedures

## Mitigation

**Immediate Actions**:
Raise thresholds temporarily and retrain on recent data


**Short-term Actions**:
1. Monitor system metrics
2. Verify mitigation effectiveness
3. Document lessons learned

**Long-term Actions**:
1. Implement automated detection
2. Add preventive measures
3. Update runbooks

## Prevention

Monitor feature distributions and seasonality

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

This incident demonstrates the importance of distribution shift in production ML systems. Review queue overflows with high-risk scores shows how The model was trained on a narrower spending distribution can impact model performance. The key lesson is that Monitor feature distributions and seasonality are essential for maintaining system reliability. This experience reinforced the need for comprehensive monitoring, automated detection, and well-documented incident response procedures.
