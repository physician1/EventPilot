from backend import agent
from backend import main
from backend.planner import DemoProvider, blockers
from test_agent import client, event, start, step, finish


def test_compare_defers_missing_category(client):
    e=start(client,event(client))
    for cat in ['venue','catering']:
        agent.execute(e,'search_catalog',dict(category=cat,summary='Rooftop suppliers cost $500,000'))
    agent.execute(e,'compare_options',dict(objective='value',summary='Compare'))
    assert e['status']=='running'
    assert 'entertainment' in e['agent']['trace'][-1]['result']
    assert e['plans']==[]
    assert 'Rooftop suppliers' not in e['agent']['trace'][0]['summary']


def test_capacity_blocker_not_budget(client):
    e=start(client,event(client))
    e.update(kind='wedding',guests=100,budget_cents=5000000)
    for cat in ['venue','catering','photography']:
        agent.execute(e,'search_catalog',dict(category=cat,summary='Search'))
    agent.execute(e,'compare_options',dict(objective='value',summary='Compare'))
    agent.execute(e,'ask_user',dict(summary='Too expensive',question='Increase budget to $500,000?'))
    assert 'maximum catalog capacity is 80' in e['agent']['question']
    assert 'Increasing the budget cannot fix capacity' in e['agent']['question']
    assert 'catering' not in e['agent']['question']


def test_verified_money_and_context(client):
    e=start(client,event(client))
    agent.execute(e,'interpret_brief',dict(summary='Budget $500,000',interpretation='Outdoor wedding $500,000',priorities=['Budget $500,000']))
    assert '$5,000.00' in e['agent']['interpretation']
    assert 'Indoor only' in e['agent']['interpretation']
    assert '$500,000' not in str(e['agent']['trace'])
    assert agent.context(e)['budget_usd']=='5000.00'


def test_followup_preserves_message_and_archive(client):
    e=finish(client,start(client,event(client),feedback='First message'))
    e=start(client,e,feedback='Second message')
    assert e['agent']['message']=='Second message'
    assert e['agent_archive'][0]['message']=='First message'
    assert 'First message' in e['agent']['feedback']


def test_budget_diagnostic_only_after_other_constraints_pass(client):
    e=event(client)
    e.update(guests=2,budget_cents=50000,kind='corporate')
    e['catalog']=DemoProvider().discover(e)
    assert 'exceed the saved $500.00 budget' in blockers(e)[0]

def test_error_diagnostics_do_not_expose_arbitrary_messages():
    assert 'timed out' in main.agent_failure(TimeoutError('secret'))
    assert 'secret' not in main.agent_failure(ValueError('secret'))
    message=main.agent_failure(ValueError('Timeline must be ordered, unique, include welcome at 0 and end at event duration'),'design_timeline')
    assert 'design timeline' in message and 'end at event duration' in message

def test_failed_tool_is_recorded(client,monkeypatch):
    e=start(client,event(client))
    monkeypatch.setattr(agent,'demo_decision',lambda state: ('design_timeline',dict(summary='Invalid end',items=[dict(minute=m,task='test') for m in [0,30,60,999]])))
    e=step(client,e).json()
    assert e['status']=='blocked'
    assert e['agent']['trace'][-1]['failed_tool']=='design_timeline'
    assert 'items.3.minute' in e['agent']['question']
