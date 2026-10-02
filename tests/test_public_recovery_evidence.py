"""Public recovery projection: real ZIP verification, synthetic local evidence."""
from pathlib import Path
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import source_bundle
import build_public_recovery_evidence as public


class PublicRecoveryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mygpt-public-recovery-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.evidence = self.base/"evidence";self.evidence.mkdir()
        self.recovered = self.base/"recovered";self.recovered.mkdir()
        self.commit = "a"*40
        self.archive = self.evidence/"mygpt-source.zip"
        self.repeat = self.base/"repeat.zip"
        raw = b"Synthetic source fixture only.\n"
        entry = {"path":"README.md","bytes":len(raw),"sha256":public.hashlib.sha256(raw).hexdigest(),
                 "git_blob":source_bundle.git_blob(raw),"mode":"100644"}
        manifest = {"schema":"mygpt.source-bundle.v2","repository":"Jvust1/mygpt","source_commit":self.commit,
                    "scope":"TRACKED_PROJECT_SOURCE_WITH_EXTERNAL_SUBMODULE_REFERENCES","includes_dependencies":False,
                    "external_submodules":[],"build_bootstraps":[],"files":[entry]}
        with zipfile.ZipFile(self.archive,"w") as z:
            source_bundle.write_entry(z,"README.md",raw)
            source_bundle.write_entry(z,"SOURCE_MANIFEST.json",json.dumps(manifest).encode())
        shutil.copyfile(self.archive,self.repeat)
        with zipfile.ZipFile(self.archive) as z:z.extractall(self.recovered)
        sha = source_bundle.sha256_file(self.archive)
        self.write("build.json",{**source_bundle.verify(self.archive,sha),"sha256":sha,"archive_bytes":self.archive.stat().st_size})
        shutil.copyfile(self.evidence/"build.json",self.evidence/"repeat.json")
        (self.evidence/"source-commit.txt").write_text(self.commit+"\n")
        self.write("doctor.json",{"schema":"mygpt.launcher-doctor.v1","status":"READY","python":"3.13.15",
                   "missing_files":[],"dependencies":[{"package":"httpx","expected":"0.28.1","installed":"0.28.1","matches":True}],
                   "issue":None,"opens_listener":False,"installs_packages":False,"live_model_enabled":False,"note":"synthetic","instructions":"START_HERE.md"})
        versions={k:"1.0.0" for k in ("pydantic","httpx","pydantic-ai-slim","mcp","pytest","pytest-asyncio")}
        self.write("recovered-brain/acceptance.json",{"evidence_kind":"SIMULATED_SDK_ACCEPTANCE","python":"3.13.15",
                   "expected_versions":versions,"installed_versions":versions,"accepted":True,"status":"PASS",
                   "exit_code":0,"tests":4,"failed":0,"errors":0,"skipped":0,"missing_required_cases":[]})
        (self.evidence/"recovered-brain/tests.xml").write_text('<testsuites><testsuite>'+''.join(f'<testcase name="{n}"/>' for n in public.REQUIRED_CASES)+'</testsuite></testsuites>')
        (self.evidence/"recovered-root.txt").write_text('Ran 10 tests in 0.01s\n\nOK\n')
        (self.evidence/"recovered-node.txt").write_text('\n'.join('# '+k+' '+str(v) for k,v in {"tests":70,"pass":70,"fail":0,"cancelled":0,"skipped":0,"todo":0}.items()))
        (self.evidence/"recovered-java.txt").write_text('PASS: Android companion boundary smoke\n'+'\n'.join(n+' PASS' for n in public.JAVA_SMOKES)+'\n')
        self.write("launcher-http.json",{"status":"PASS","scope":"ACTUAL_POSIX_LAUNCHER_AND_LOOPBACK","checks":sorted(public.LAUNCHER_CHECKS),"checks_passed":12,"paid_model_calls":0,"source_text_received":False,"windows_device_acceptance":False})
        self.write("recovered-http.json",{"result":"PASS","scope":"LOOPBACK_HTTP_SYNTHETIC_INPUT_INJECTED_RESPONDER","checks":sorted(public.SELECTION_CHECKS),"checks_passed":32,"paid_model_calls":0,"external_requests":0})

    def write(self,name,value):
        path=self.evidence/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))

    def build(self):
        return public.build_summary(self.evidence,self.repeat,self.recovered,self.commit)

    def test_public_output_has_exact_closed_fields_and_no_archive_or_log(self):
        summary=self.build()
        self.assertEqual(set(summary),public.OUTPUT_KEYS)
        self.assertEqual(summary['source_files'],1)
        self.assertFalse(summary['contains_source_archive'])
        self.assertFalse(summary['contains_raw_logs'])
        self.assertNotIn('Synthetic source fixture',json.dumps(summary))
        self.assertNotIn(str(self.base),json.dumps(summary))
        self.assertEqual(summary['java_entrypoints'],22)

    def test_commit_hash_failed_skipped_missing_and_private_extra_fields_fail(self):
        cases=[('build.json','source_commit','b'*40),('build.json','sha256','0'*64),
               ('repeat.json','archive_bytes',1),('build.json','private_identifier','SYNTHETIC_ONLY'),
               ('repeat.json','path','/synthetic/private/input'),
               ('recovered-brain/acceptance.json','raw_log','SYNTHETIC_PRIVATE_LOG'),
               ('recovered-brain/acceptance.json','failed',1),('recovered-brain/acceptance.json','skipped',1),
               ('recovered-brain/acceptance.json','accepted',False),('recovered-brain/acceptance.json','tests',False),
               ('doctor.json','status','BLOCKED'),('launcher-http.json','paid_model_calls',1),
               ('recovered-http.json','checks',['/synthetic/private/input']*32)]
        for name,key,value in cases:
            with self.subTest(name=name,key=key):
                path=self.evidence/name;before=path.read_bytes();obj=json.loads(before);obj[key]=value;self.write(name,obj)
                with self.assertRaises((ValueError,TypeError)):self.build()
                path.write_bytes(before)

    def test_missing_recovery_evidence_cannot_emit_success(self):
        for name in ('recovered-root.txt','recovered-node.txt','recovered-java.txt','recovered-brain/tests.xml'):
            with self.subTest(name=name):
                path=self.evidence/name;before=path.read_bytes();path.unlink()
                with self.assertRaises(OSError):self.build()
                path.write_bytes(before)

    def test_changed_recovered_bytes_and_repeat_archive_are_rejected(self):
        path=self.recovered/'README.md';before=path.read_bytes();path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'recovered_source_mismatch'):self.build()
        path.write_bytes(before);self.repeat.write_bytes(b'not the second archive')
        with self.assertRaises(ValueError):self.build()

    def test_root_javascript_java_and_junit_failure_or_skip_are_rejected(self):
        cases=[('recovered-root.txt','Ran 10 tests in 0.01s\n\nOK (skipped=1)\n'),
               ('recovered-node.txt','# tests 1\n# pass 0\n# fail 0\n# cancelled 0\n# skipped 1\n# todo 0\n'),
               ('recovered-java.txt','PASS: Android companion boundary smoke\n'),
               ('recovered-brain/tests.xml','<testsuites><testcase name="x"><skipped/></testcase></testsuites>')]
        for name,value in cases:
            with self.subTest(name=name):
                path=self.evidence/name;before=path.read_bytes();path.write_text(value)
                with self.assertRaises(ValueError):self.build()
                path.write_bytes(before)

    def test_public_schema_rejects_extra_fields_paths_strings_and_boolean_counts(self):
        base=self.build()
        for key,value in [('private_identifier','SYNTHETIC_ONLY'),('path','/synthetic/private'),('raw_log','text'),
                          ('source_commit','/synthetic/private'),('inner_archive_sha256','SYNTHETIC_ONLY'),
                          ('strict_tests',True),('contains_source_archive',True),('failed',1)]:
            with self.subTest(key=key):
                changed={**base,key:value}
                with self.assertRaises(ValueError):public.validate_public_summary(changed)

    def test_cli_failure_redacts_raw_exception_and_leaves_no_success_file(self):
        sentinel='SYNTHETIC_PRIVATE_VALUE'
        (self.evidence/'build.json').write_text('{'+sentinel)
        output=self.base/'public.json'
        result=subprocess.run([sys.executable,str(ROOT/'scripts/build_public_recovery_evidence.py'),
                               '--evidence-dir',str(self.evidence),'--repeat-archive',str(self.repeat),
                               '--recovered-root',str(self.recovered),'--source-commit',self.commit,'--output',str(output)],
                              text=True,capture_output=True)
        self.assertEqual(result.returncode,1);self.assertFalse(output.exists())
        self.assertNotIn(sentinel,result.stdout+result.stderr);self.assertNotIn(str(self.base),result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout),{'status':'FAIL','error':'PUBLIC_RECOVERY_EVIDENCE_REJECTED'})

    def test_workflow_uploads_only_summary_after_all_existing_recovery_gates(self):
        text=(ROOT/'.github/workflows/source-delivery.yml').read_text()
        self.assertEqual(text.count('uses: actions/upload-artifact@'),1)
        self.assertIn('path: ${{ runner.temp }}/public-recovery-summary.json',text)
        self.assertIn('name: source-recovery-evidence-${{ github.sha }}-${{ github.run_attempt }}',text)
        self.assertIn('if-no-files-found: error',text)
        self.assertNotIn('if: always()',text)
        upload=text.split('uses: actions/upload-artifact@',1)[1]
        self.assertNotIn('source-evidence/',upload);self.assertNotIn('.zip',upload)
        self.assertEqual(text.count('scripts/source_bundle.py build --commit "$GITHUB_SHA"'),2)
        for required in ('cmp "$OUT/mygpt-source.zip" "$RUNNER_TEMP/source-repeat.zip"',
                         "verified = verify(out / 'mygpt-source.zip', report['sha256'])",'archive.extractall(dest)',
                         "python -m unittest discover -s tests -p 'test_*.py' -q",'node --test tests/*.test.mjs',
                         'python scripts/verify_integrations.py','smoke_selection_intake.py','run_boundary_smoke.sh'):
            self.assertIn(required,text)
        self.assertLess(text.index('run_boundary_smoke.sh'),text.index('scripts/build_public_recovery_evidence.py'))
        self.assertLess(text.index('scripts/build_public_recovery_evidence.py'),text.index('uses: actions/upload-artifact@'))


if __name__=='__main__':unittest.main()
