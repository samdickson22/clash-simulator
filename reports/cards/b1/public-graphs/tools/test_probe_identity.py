"""Stdlib-only controls for the probe's exported/shared-token identity check."""
import ast
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest

source = ast.parse(Path(__file__).with_name('real_games.py').read_text())
functions = [n for n in source.body if isinstance(n, ast.FunctionDef) and
             n.name in ('require', 'released_child_templates', 'check_child_payload')]
scope = {}
exec(compile(ast.Module(body=functions, type_ignores=[]), '<probe identity>', 'exec'), scope)
resolve, check = scope['released_child_templates'], scope['check_child_payload']


class IdentityControls(unittest.TestCase):
    def fixture(self):
        child = dict(class_='Troop', stats=dict(name='Skeleton'),
                     public_identity=[['troop_body', ['Missing', 'Skeleton']]])
        child['class'] = child.pop('class_')
        selected = {'class':'Troop', 'stats':dict(name='SkeletonArmy', max_hp=81., damage=81.,
                    range=.5, radius=.5, speed=90, interval=1000, load=1000)}
        builder = SimpleNamespace(token_id=lambda n, namespace: {'Skeleton':296}.get(n,1))
        return SimpleNamespace(builder=builder, config={'bomb_children':{'SkeletonBalloon':[child]}},
                               templates={(296,'Troop'):selected})

    def test_shared_token_selects_actual_template_not_exported_name(self):
        R = self.fixture()
        spec = resolve(R)[296,'Troop']
        self.assertEqual(spec['exported_names'], ['Skeleton'])
        self.assertEqual(spec['template']['stats']['name'], 'SkeletonArmy')
        check(copy.deepcopy(spec['template']), spec['template'])

    def test_missing_token_and_wrong_kind_are_rejected(self):
        for key in ((297,'Troop'), (296,'Projectile')):
            R = self.fixture(); R.templates[key] = R.templates.pop((296,'Troop'))
            with self.assertRaises(AssertionError): resolve(R)

    def test_wrong_payload_or_level_does_not_pass_by_identity(self):
        template = resolve(self.fixture())[296,'Troop']['template']
        for key, value in (('name','Skeleton'), ('max_hp',74.), ('damage',74.), ('speed',0), ('range',1.)):
            wrong = copy.deepcopy(template); wrong['stats'][key] = value
            with self.assertRaises(AssertionError): check(wrong, template)
        scaled = copy.deepcopy(template)
        scaled['stats'].update(max_hp=74., damage=74.)
        check(copy.deepcopy(scaled), scaled)
        with self.assertRaises(AssertionError): check(template, scaled)


if __name__ == '__main__': unittest.main()
