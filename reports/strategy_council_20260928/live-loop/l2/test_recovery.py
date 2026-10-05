"""Exercise the actual nested recovery function without emulator or model I/O."""
import ast,json,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
H=Path(__file__).resolve().parent
source=ast.parse((H/'offline_loop.py').read_text())
main=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='main')
node=next(n for n in main.body if isinstance(n,ast.FunctionDef) and n.name=='call')
code=compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(H/'offline_loop.py'),'exec')
class Recovery(unittest.TestCase):
 def make(self,fail,mapping=''):
  req=Mock(side_effect=[fail,{'ok':True}]);run=Mock(return_value=SimpleNamespace(stdout=mapping))
  env=dict(request=req,owner=dict(serial='emulator-5580',probe_port=26789),json=json,
    append=Mock(),HERE=H,ADB=Path('/owned/adb'),time=SimpleNamespace(time=lambda:0,sleep=Mock()),
    subprocess=SimpleNamespace(run=run,DEVNULL=-3,PIPE=-1))
  exec(code,env);return env['call'],req,run
 def test_read_reconnects_only_missing_owned_mapping(self):
  call,req,run=self.make(ConnectionRefusedError())
  self.assertEqual(call('status'),{'ok':True});self.assertEqual(req.call_count,2)
  self.assertIn('--no-rebind',run.call_args_list[1].args[0]);self.assertFalse(run.call_args_list[1].kwargs['close_fds'])
 def test_lost_mutation_response_is_not_repeated(self):
  call,req,run=self.make(json.JSONDecodeError('empty','',0))
  with self.assertRaises(json.JSONDecodeError):call('replay-schedule-card 0 1 2 3 4')
  self.assertEqual(req.call_count,1);run.assert_not_called()
 def test_other_forward_owner_is_preserved(self):
  call,req,run=self.make(ConnectionRefusedError(),'emulator-5590 tcp:26789 tcp:26789\n')
  with self.assertRaisesRegex(RuntimeError,'ownership changed'):call('observe')
  self.assertEqual(run.call_count,1);self.assertEqual(req.call_count,1)
 def test_existing_owned_forward_is_not_rebound(self):
  call,req,run=self.make(ConnectionResetError(),'emulator-5580 tcp:26789 tcp:26789\n')
  self.assertEqual(call('observe'),{'ok':True});self.assertEqual(run.call_count,1)
 def test_preserved_intro_cannot_end_an_unstarted_match(self):
  cue=next(n.test for n in ast.walk(main) if isinstance(n,ast.If) and 'player.started' in ast.unparse(n.test) and 'elixir_feature' in ast.unparse(n.test))
  expr=compile(ast.Expression(cue),'<actual lifecycle condition>','eval')
  env=dict(player=SimpleNamespace(started=False),public=SimpleNamespace(visible_clock_seconds=None),
    capture=SimpleNamespace(pixels=None),elixir_feature=lambda _:0.)
  self.assertFalse(eval(expr,env));env['player'].started=True;self.assertTrue(eval(expr,env))
if __name__=='__main__':unittest.main()
