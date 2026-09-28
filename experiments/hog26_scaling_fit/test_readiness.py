import json

import pytest
from readiness import sha, validate_memory_reports, validate_readiness


def reports(tmp_path):
    audit={'games':1536,'clusters':768,'diagnostic_fitting_games':0,
           'original':{'games':384},'extension':{'games':1152}}
    refs={}
    for phase in ('neural','tree'):
        details={'outcome_model_saved':False}
        if phase=='neural':
            details.update(batch=[2,750,128],full_backpropagation=True,finite_gradients=True,optimizer_steps=1)
        else:
            details.update(histogram_iterations=1,sklearn='1.7.2',largest_row_fold=0,matrix_bytes=100)
        report={'status':'passed','phase':phase,'implementation':{'fixture':'hash'},
                'collection_plan_sha256':'plan','runtime':{'fixture':'runtime'},'outcome_training':False,
                'peak_rss_bytes':100,'limit_bytes':1000,'data_audit':audit,'details':details}
        path=tmp_path/(phase+'.json');path.write_text(json.dumps(report))
        refs[phase]={'path':str(path),'sha256':sha(path)}
    return refs,audit


def verify(refs):
    return validate_memory_reports(refs,implementation={'fixture':'hash'},plan_sha256='plan',runtime={'fixture':'runtime'})


def test_matching_evidence_and_readiness(tmp_path):
    refs,audit=reports(tmp_path)
    assert verify(refs)==audit
    readiness={'status':'passed','implementation':{'fixture':'hash'},'collection_plan_sha256':'plan',
               'combined_games':1536,'memory_verified':True,'memory_reports':refs,'data_audit':audit}
    assert validate_readiness(readiness,implementation={'fixture':'hash'},plan_sha256='plan',runtime={'fixture':'runtime'})==audit
    readiness['data_audit']={'games':1536}
    with pytest.raises(ValueError,match='differs'):
        validate_readiness(readiness,implementation={'fixture':'hash'},plan_sha256='plan',runtime={'fixture':'runtime'})


def test_boolean_without_reports_is_insufficient(tmp_path):
    refs,_=reports(tmp_path)
    refs.pop('tree')
    with pytest.raises(ValueError,match='both'):
        verify(refs)


@pytest.mark.parametrize('field,value', [('peak_rss_bytes',1001),('implementation',{}),
    ('runtime',{}),('outcome_training',True),('data_audit',{'games':384}),('details',{})])
def test_mismatched_or_incomplete_evidence_rejected(tmp_path,field,value):
    refs,_=reports(tmp_path)
    path=tmp_path/'neural.json';report=json.loads(path.read_text());report[field]=value
    path.write_text(json.dumps(report));refs['neural']['sha256']=sha(path)
    with pytest.raises(ValueError):
        verify(refs)


def test_report_mutation_rejected(tmp_path):
    refs,_=reports(tmp_path)
    (tmp_path/'tree.json').write_text('{}')
    with pytest.raises(ValueError,match='digest'):
        verify(refs)
