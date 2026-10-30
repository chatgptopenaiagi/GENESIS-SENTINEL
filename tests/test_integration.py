"""Opt-in guidance ownership, unchanged wrapper rollback, and fresh-process handoff."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from genesis_sentinel import core,integration
from genesis_sentinel.cli import main

class IntegrationTests(unittest.TestCase):
    def test_guidance_install_rollback_preserves_unrelated_text(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'state';path=Path(t)/'project/AGENTS.md';path.parent.mkdir();path.write_text('Existing project instructions.\n')
            integration.install(root,path)
            self.assertIn(str(root/'SESSION-BRIEF.md'),path.read_text());self.assertTrue((root/'runtime/integration.json').exists())
            path.write_text(path.read_text()+'Later unrelated instruction.\n')
            result=integration.uninstall(root)
            self.assertEqual(path.read_text(),'Existing project instructions.\nLater unrelated instruction.\n')
            self.assertIn('owned block removed',result['guidance'])

    def test_existing_unowned_blocks_and_launchers_are_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'state';path=Path(t)/'AGENTS.md';path.write_text(integration.BEGIN+'\nUnowned\n'+integration.END+'\n')
            with self.assertRaises(ValueError):integration.install(root,path)
            path.write_text('Original\n');wrapper=Path(t)/'program';wrapper.write_text('Unowned executable')
            with self.assertRaises(ValueError):integration.install(root,path,wrapper,sys.executable)
            self.assertEqual(wrapper.read_text(),'Unowned executable');self.assertEqual(path.read_text(),'Original\n')

    def test_modified_managed_block_and_wrapper_are_retained(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'state';path=Path(t)/'AGENTS.md';wrapper=Path(t)/'program'
            integration.install(root,path,wrapper,sys.executable)
            path.write_text(path.read_text().replace('Keep environments separate.','Operator changed this block.'))
            wrapper.write_text('#!/bin/sh\n# operator modification\n')
            result=integration.uninstall(root)
            self.assertTrue(path.exists());self.assertTrue(wrapper.exists());self.assertTrue(result['guidance'].startswith('preserved:'));self.assertTrue(result['launcher'].startswith('preserved:'))
            self.assertEqual(core.load(root/'runtime/integration.json')['status'],'review required')

    def test_wrapper_exec_preserves_arguments_output_and_exit(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'state';path=Path(t)/'AGENTS.md';wrapper=Path(t)/'program'
            cfg=core.default_config();cfg.update(interpreters=[],conda_roots=[],conda_registry_files=[],tool_names=[],collect_arch_packages=False)
            core.atomic(root/'config.json',cfg);integration.install(root,path,wrapper,sys.executable)
            p=subprocess.run([str(wrapper),'-c','import json,sys;print(json.dumps(sys.argv[1:]));raise SystemExit(17)','space argument','$(literal)','--literal'],capture_output=True,text=True,timeout=30)
            self.assertEqual(p.returncode,17,p.stderr);self.assertEqual(json.loads(p.stdout),['space argument','$(literal)','--literal'])
            self.assertTrue((root/'SESSION-BRIEF.md').exists());integration.uninstall(root)
            self.assertFalse(wrapper.exists());self.assertFalse(path.exists())

    def test_fresh_process_discovers_brief_via_guidance(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'state';path=Path(t)/'AGENTS.md'
            cfg=core.default_config();cfg.update(interpreters=[sys.executable],conda_roots=[],conda_registry_files=[],tool_names=[],collect_arch_packages=False)
            core.atomic(root/'config.json',cfg)
            with contextlib.redirect_stdout(io.StringIO()):snapshot=core.refresh(root)
            integration.install(root,path)
            code="import json,sys;from pathlib import Path;g=Path(sys.argv[1]).read_text();p=Path(sys.argv[2]);assert str(p) in g;text=p.read_text();graph=json.loads((p.parent/'CAPABILITY-GRAPH.json').read_text());print(json.dumps({'generation':graph['generation'],'environment_count':len({c['environment_id'] for c in graph['capabilities']}),'guidance_found':True,'fresh_process':True}))"
            p=subprocess.run([sys.executable,'-I','-c',code,str(path),str(root/'SESSION-BRIEF.md')],capture_output=True,text=True,timeout=10)
            self.assertEqual(p.returncode,0,p.stderr);result=json.loads(p.stdout);self.assertEqual(result['generation'],snapshot['generation']);self.assertTrue(result['guidance_found'])

    def test_cli_explicit_state_init_register_and_unintegrate(self):
        with tempfile.TemporaryDirectory() as t,contextlib.redirect_stdout(io.StringIO()):
            root=Path(t)/'state';guidance=Path(t)/'project/AGENTS.md'
            self.assertEqual(main(['--state-dir',str(root),'init']),0)
            self.assertEqual(main(['--state-dir',str(root),'register-python',sys.executable]),0)
            self.assertEqual(main(['--state-dir',str(root),'integrate','--guidance',str(guidance)]),0)
            self.assertEqual(main(['--state-dir',str(root),'unintegrate']),0)
            self.assertFalse(guidance.exists())

if __name__=='__main__':unittest.main(verbosity=2)
