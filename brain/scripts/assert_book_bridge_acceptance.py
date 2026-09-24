"""Fail if the new receiver tests disappear, skip, or fail in a JUnit report."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

REQUIRED = {
    'test_book_receiver_default_uses_actual_testmodel',
    'test_new_live_contract_does_not_widen_legacy_simulated_protocol',
    'test_receiver_rechecks_authority_and_deduplicates_without_rerunning',
    'test_cancel_before_explain_is_a_tombstone',
    'test_cancel_after_reply_blocks_cached_delivery',
    'test_wrong_reply_reference_fails_and_is_not_retried',
    'test_alias_roundtrip_revalidates_instances_but_rejects_internal_wire_names',
}

def inspect(path):
    cases = [case for case in ET.parse(path).getroot().iter('testcase')
             if case.get('classname', '').endswith('test_book_bridge')]
    missing = sorted(REQUIRED - {case.get('name') for case in cases})
    bad = [case.get('name') for case in cases if any(case.find(x) is not None for x in ('failure','error','skipped'))]
    return {'receiver_cases':len(cases), 'missing_required':missing, 'nonpassing_cases':bad,
            'accepted':len(cases)>=20 and not missing and not bad,
            'scope':'synthetic capability tests including actual SDK TestModel; not a real Book feed'}

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('junit',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=inspect(args.junit)
    with args.output.open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps(report));raise SystemExit(0 if report['accepted'] else 1)
