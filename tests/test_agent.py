import json
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from backend import main, agent

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(main,'DB',str(tmp_path/'agent.sqlite'))
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    return TestClient(main.app)

def event(client):
    return client.post('/api/events',json=dict(name='Private name',kind='birthday',location='Boston',date='2027-06-20',guests=40,budget_cents=500000,preferences='Prefer a relaxed dinner.')).json()

def start(client,e,**kwargs):
    return client.post(f'/api/events/{e["id"]}/agent/start',json=dict(revision=e['revision'],mode='rehearsal',**kwargs)).json()

def step(client,e):
    return client.post(f'/api/events/{e["id"]}/agent/step',json={'revision':e['revision']})

def finish(client,e):
    while e['status']=='running':
        r=step(client,e);assert r.status_code==200,r.text;e=r.json()
    return e

def test_rehearsal_end_to_end_and_feedback(client):
    e=finish(client,start(client,event(client)))
    assert e['status']=='review' and e['stage']==4
    assert e['agent']['mode']=='rehearsal'
    assert e['agent']['turns']==9
    assert e['agent']['critique']['verdict']=='ready'
    assert e['plans'][0]['total']<=e['budget_cents']
    assert e['approvals']==[]
    e=start(client,e,feedback='Please leave more money unallocated.')
    assert len(e['agent_archive'])==1 and e['status']=='running'
    assert 'more money' in e['agent']['feedback']

def test_live_consent_and_key(client):
    e=event(client);path=f'/api/events/{e["id"]}/agent/start'
    assert client.post(path,json=dict(revision=e['revision'],mode='live')).status_code==400
    assert client.post(path,json=dict(revision=e['revision'],mode='live',consent=True)).status_code==503

def test_model_chooses_tools_through_sdk(client,monkeypatch):
    import openai
    calls=[]
    class Fake:
        def __init__(self,**kw): self.responses=self
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def create(self,**kw):
            calls.append(kw)
            return SimpleNamespace(output=[SimpleNamespace(type='function_call',name='interpret_brief',arguments=json.dumps(dict(summary='Prioritize an intimate dinner.',interpretation='A relaxed indoor birthday with a dinner focus.',priorities=['Food','Conversation'])))])
    monkeypatch.setattr(openai,'AsyncOpenAI',Fake)
    monkeypatch.setenv('OPENAI_API_KEY','test-key')
    e=event(client)
    e=client.post(f'/api/events/{e["id"]}/agent/start',json=dict(revision=e['revision'],mode='live',consent=True)).json()
    r=step(client,e);assert r.status_code==200
    assert r.json()['agent']['priorities']==['Food','Conversation']
    assert calls[0]['tool_choice']=='required' and calls[0]['store'] is False
    assert 'Private name' not in calls[0]['input']
    assert 'Prefer a relaxed dinner.' in calls[0]['input']
    assert len(calls[0]['tools'])==7

def test_stop_during_model_call_discards_result(client,monkeypatch):
    e=start(client,event(client))
    with main.db() as c:
        e=main.get(c,e['id']);e['agent']['mode']='live';main.save(c,e)
    async def delayed(state):
        main.command(state['id'],main.Command(action='stop',revision=state['revision']))
        return agent.demo_decision(state)
    monkeypatch.setattr(agent,'model_decision',delayed)
    assert step(client,e).status_code==409
    saved=client.get(f'/api/events/{e["id"]}').json()
    assert saved['status']=='stopped' and saved['agent']['trace']==[]

def test_guardrails_cannot_be_skipped(client):
    e=start(client,event(client))
    with pytest.raises(ValueError): agent.execute(e,'submit_proposal',dict(summary='Skip checks',option=0))
    with pytest.raises(ValueError): agent.execute(e,'pay_vendor',{})
    with pytest.raises(ValueError): agent.execute(e,'record_critique',dict(summary='Bypass role',verdict='ready',concerns=['none']))
    with pytest.raises(ValueError): agent.execute(e,'design_timeline',dict(summary='Conflicting schedule',items=[dict(minute=m,task='x') for m in [0,60,60,240]]))
    assert client.post(f'/api/events/{e["id"]}/command',json=dict(action='step',revision=e['revision'])).status_code==409

def test_critic_revision_and_invalidation(client):
    e=start(client,event(client))
    while e['agent']['role']!='critic': e=step(client,e).json()
    agent.execute(e,'record_critique',dict(summary='Add dinner before the main program.',verdict='revise',concerns=['Food not emphasized enough']))
    with pytest.raises(ValueError): agent.execute(e,'submit_proposal',dict(summary='Ignore critic',option=0))
    agent.execute(e,'design_timeline',dict(summary='Revise dinner timing.',items=[dict(minute=m,task=t) for m,t in [(0,'Welcome'),(30,'Dinner'),(100,'Program'),(240,'Departure')]]))
    assert e['agent']['critique'] is None
    agent.execute(e,'request_critic',dict(summary='Review revision.'))
    agent.execute(e,'record_critique',dict(summary='Ready for draft review only.',verdict='ready',concerns=['Verify real availability']))
    agent.execute(e,'submit_proposal',dict(summary='Dinner now precedes the main program.',option=0))
    assert e['status']=='review'

def test_turn_limit(client):
    e=start(client,event(client))
    with main.db() as c:
        e=main.get(c,e['id']);e['agent']['turns']=16;main.save(c,e)
    e=step(client,e).json()
    assert e['status']=='blocked' and 'Turn limit' in e['agent']['question']

def test_infeasible_asks_user(client):
    e=event(client)
    with main.db() as c:
        e=main.get(c,e['id']);e['budget_cents']=10000;main.save(c,e)
    e=finish(client,start(client,e))
    assert e['status']=='blocked' and e['agent']['question']

def test_ai_failure_is_not_silent_demo_fallback(client,monkeypatch):
    e=start(client,event(client))
    with main.db() as c:
        e=main.get(c,e['id']);e['agent']['mode']='live';main.save(c,e)
    async def fail(state): raise TimeoutError()
    monkeypatch.setattr(agent,'model_decision',fail)
    e=step(client,e).json()
    assert e['status']=='blocked' and e['agent']['mode']=='live'
    assert e['agent']['trace'][0]['tool']=='safe_failure'
