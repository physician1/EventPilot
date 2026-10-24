import json
from types import SimpleNamespace
import pytest
from backend import research, main
from test_agent import client, event, step

def response(url='https://example.com/venue'):
    return SimpleNamespace(model_dump=lambda:dict(status='completed',output=[
        dict(type='web_search_call',status='completed'),
        dict(type='message',content=[dict(type='output_text',text='Accra venue [1]. Quote unknown.',annotations=[dict(type='url_citation',start_index=12,end_index=15,url=url,title='Venue source')])])]))

def test_citations_are_retained_and_unsafe_urls_rejected():
    report=research.extract_report(response())
    assert report['parts'][0][1]['url']=='https://example.com/venue'
    with pytest.raises(ValueError): research.extract_report(response('javascript:alert(1)'))

@pytest.mark.parametrize('city',['Accra, Ghana','Tokyo, Japan','Lagos, Nigeria','Boston, USA'])
def test_live_search_any_city_and_unknown_costs(client,monkeypatch,city):
    import openai
    calls=[]
    class Fake:
        def __init__(self,**kwargs): self.responses=self
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def create(self,**kwargs): calls.append(kwargs);return response()
    monkeypatch.setattr(openai,'AsyncOpenAI',Fake)
    monkeypatch.setenv('OPENAI_API_KEY','test')
    e=event(client)
    with main.db() as c:
        e=main.get(c,e['id']);e['location']=city;main.save(c,e)
    e=client.post(f'/api/events/{e["id"]}/agent/start',json=dict(revision=e['revision'],mode='live',web_search=True,consent=True,feedback='Find real venues')).json()
    r=step(client,e);assert r.status_code==200
    e=r.json()
    assert e['status']=='review' and e['plans']==[] and e['catalog']==[]
    assert e['agent']['research']['parts']
    payload=json.loads(calls[0]['input'])
    assert payload['saved_requirements']['location']==city
    assert 'Private name' not in calls[0]['input']
    assert calls[0]['tools']==[{'type':'web_search'}]
    assert calls[0]['tool_choice']=='required'
    assert client.post(f'/api/events/{e["id"]}/command',json=dict(action='approve',revision=e['revision'])).status_code==409

def test_stop_discards_web_research(client,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test')
    e=event(client)
    e=client.post(f'/api/events/{e["id"]}/agent/start',json=dict(revision=e['revision'],mode='live',web_search=True,consent=True)).json()
    async def interrupted(state):
        main.command(state['id'],main.Command(action='stop',revision=state['revision']))
        return research.extract_report(response())
    monkeypatch.setattr(research,'research',interrupted)
    assert step(client,e).status_code==409
    stored=client.get(f'/api/events/{e["id"]}').json()
    assert stored['status']=='stopped' and 'research' not in stored['agent']
