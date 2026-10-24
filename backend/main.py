import asyncio
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, ConfigDict, field_validator, ValidationError
from .planner import DemoProvider, optimize, timeline, audit

load_dotenv()
app=FastAPI(title='EventPilot',version='1.0.0')
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','testserver'])
DB=os.getenv('EVENTPILOT_DB','eventpilot.sqlite')

@contextmanager
def db():
    c=sqlite3.connect(DB,timeout=10)
    try:
        c.execute('CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
        c.execute('BEGIN IMMEDIATE')
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally: c.close()

def get(c,id):
    row=c.execute('SELECT data FROM events WHERE id=?',(id,)).fetchone()
    if not row: raise HTTPException(404,'Event not found')
    return json.loads(row[0])

def save(c,e):
    e['revision']+=1
    c.execute('INSERT OR REPLACE INTO events VALUES (?,?)',(e['id'],json.dumps(e)))

def log(e,message):
    e['history'].append(dict(at=datetime.now(timezone.utc).isoformat(),message=message))

class Intake(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    name:str=Field(min_length=1,max_length=100)
    kind:Literal['birthday','wedding','corporate']
    location:str=Field(min_length=1,max_length=100)
    date:date
    start_time:str=Field(default='18:00',pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    duration_hours:int=Field(default=4,ge=3,le=12)
    guests:int=Field(ge=1,le=200)
    budget_cents:int=Field(ge=10000,le=100000000)
    indoor_only:bool=True
    preferences:str=Field(default='',max_length=2000)
    @field_validator('date')
    @classmethod
    def future(cls,v):
        if v<date.today(): raise ValueError('Choose today or a future date')
        return v

class Command(BaseModel):
    action:Literal['start','pause','resume','stop','step','approve','reject','select']
    revision:int
    selected:int=0

@app.middleware('http')
async def local_only(request:Request,call_next):
    # Prevent cross-site writes to a local, single-user service.
    origin=request.headers.get('origin')
    if request.method not in ['GET','HEAD','OPTIONS'] and origin and origin not in ['http://127.0.0.1:8000','http://localhost:8000','http://127.0.0.1:5173','http://localhost:5173']:
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail':'Origin not allowed'},status_code=403)
    return await call_next(request)

@app.get('/api/health')
def health(): return dict(ok=True,discovery='demo',ai_available=bool(os.getenv('OPENAI_API_KEY')))

@app.get('/api/events')
def events():
    with db() as c: return [json.loads(r[0]) for r in c.execute('SELECT data FROM events ORDER BY rowid DESC')]

@app.post('/api/events',status_code=201)
def create(body:Intake):
    e=body.model_dump(mode='json')
    e.update(id=str(uuid.uuid4()),revision=0,status='draft',stage=0,catalog=[],plans=[],selected=0,timeline=[],checks=[],history=[],approvals=[],ai_note=None)
    log(e,'Event created. Private preferences stay on this device.')
    with db() as c: save(c,e)
    return e

@app.get('/api/events/{id}')
def read(id:str):
    with db() as c: return get(c,id)

@app.put('/api/events/{id}')
def revise(id:str,body:Intake):
    with db() as c:
        e=get(c,id)
        if e['status']=='running': raise HTTPException(409,'Pause before changing requirements')
        e.update(body.model_dump(mode='json'))
        e.update(status='draft',stage=0,catalog=[],plans=[],selected=0,timeline=[],checks=[],ai_note=None,agent=None)
        log(e,'Requirements changed; previous approvals are historical and no longer apply.')
        save(c,e)
    return e

@app.delete('/api/events/{id}')
def delete(id:str):
    with db() as c:
        get(c,id)
        c.execute('DELETE FROM events WHERE id=?',(id,))
    return {'deleted':True}

@app.post('/api/events/{id}/command')
def command(id:str,body:Command):
    with db() as c:
        e=get(c,id)
        if body.revision!=e['revision']: raise HTTPException(409,'Event changed. Refresh and try again.')
        action=body.action
        if action=='pause' and e['status']=='running': e['status']='paused'
        elif action=='stop': e['status']='stopped'
        elif action=='resume' and e['status']=='paused': e['status']='running'
        elif action=='start' and e['status'] in ['draft','stopped','blocked','rejected']:
            e.update(status='running',stage=0,catalog=[],plans=[],checks=[],timeline=[],selected=0,ai_note=None,agent=None)
        elif action=='step' and e['status']=='running':
            if e.get('agent'): raise HTTPException(409,'Use the agent tool loop endpoint')
            try:
                if e['stage']==0:
                    e['catalog']=DemoProvider().discover(e)
                    log(e,f"Discovery found {len(e['catalog'])} fictional records; no live availability claim.")
                elif e['stage']==1:
                    e['plans']=optimize(e)
                    if not e['plans']:
                        e['status']='blocked'
                        log(e,'No feasible plan. Try Boston, fewer guests, a larger budget, or another date. No constraints were relaxed.')
                elif e['stage']==2: e['timeline']=timeline(e)
                elif e['stage']==3:
                    e['checks']=audit(e)
                    e['status']='review' if all(x['ok'] or x.get('warning') for x in e['checks']) else 'blocked'
                e['stage']+=1
            except Exception:
                e['status']='blocked'
                log(e,'Planning failed safely. Restart or revise requirements; no external action occurred.')
        elif action=='select' and e['status']=='review' and 0<=body.selected<len(e['plans']):
            e['selected']=body.selected
            e['checks']=audit(e)
        elif action in ['approve','reject'] and e['status']=='review':
            if not e['plans']: raise HTTPException(409,'Web research is a shortlist, not a priced selection. Verify quotes before approval.')
            e['status']='approved' if action=='approve' else 'rejected'
            e['approvals'].append(dict(decision=action,plan=e['plans'][e['selected']],at=datetime.now(timezone.utc).isoformat(),scope='Draft selection only. No bookings or commitments.'))
        else: raise HTTPException(409,'Action is not allowed in the current state')
        log(e,f'{action.capitalize()}: {e["status"]}')
        save(c,e)
    return e

class Consent(BaseModel):
    consent:bool
    revision:int

@app.post('/api/events/{id}/ai-summary')
async def ai_summary(id:str,body:Consent):
    if not body.consent: raise HTTPException(400,'Explicit sharing consent is required')
    with db() as c:
        e=get(c,id)
        if e['revision']!=body.revision or e['status'] not in ['review','approved']: raise HTTPException(409,'Review a completed plan first')
    if not os.getenv('OPENAI_API_KEY'): raise HTTPException(503,'No API key configured. Demo planning remains available.')
    # Purpose-limited allowlist; name, date, location and free-text memory are excluded.
    payload={'event_type':e['kind'],'guests':e['guests'],'budget_cents':e['budget_cents'],'estimated_total_cents':e['plans'][e['selected']]['total']}
    try:
        from openai import AsyncOpenAI
        async with AsyncOpenAI(timeout=20,max_retries=0) as client:
            result=await client.responses.create(model=os.getenv('OPENAI_MODEL','gpt-4.1-mini'),store=False,
                instructions='Write a short planning tip from these numeric facts. All estimates are fictional and unverified. Do not claim availability or make commitments. You have no tools.',input=json.dumps(payload),max_output_tokens=200)
        note=result.output_text
    except Exception:
        raise HTTPException(502,'AI service unavailable; your deterministic plan is preserved. Retry later.')
    with db() as c:
        current=get(c,id)
        if current['revision']!=body.revision or current['status'] not in ['review','approved']:
            raise HTTPException(409,'Plan changed or stopped; AI output discarded')
        current['ai_note']=note
        log(current,'Approved sharing of event type, guests, budget and estimate for an AI tip.')
        save(c,current)
    return current

class AgentStart(BaseModel):
    revision:int
    mode:Literal['live','rehearsal']
    consent:bool=False
    web_search:bool=False
    feedback:str=Field(default='',max_length=2000)

class AgentStep(BaseModel):
    revision:int

agent_locks={}

def agent_failure(exc, tool=None):
    """Report actionable errors without exposing keys, request bodies or notes."""
    from openai import AuthenticationError, RateLimitError, APITimeoutError, APIConnectionError, APIStatusError
    step=f' while executing {tool.replace("_", " ")}' if tool else ' while requesting the next AI decision'
    if isinstance(exc, ValidationError):
        fields=', '.join('.'.join(map(str,x['loc'])) for x in exc.errors(include_input=False,include_url=False))
        return f'The AI returned invalid tool fields{step}: {fields}. No external action occurred. Send a follow-up to retry.'
    if isinstance(exc, AuthenticationError): return 'The AI provider rejected the API key. Check OPENAI_API_KEY in .env and restart the server.'
    if isinstance(exc, RateLimitError): return 'The AI provider returned a rate or quota limit. Check API billing/usage or wait before retrying.'
    if isinstance(exc, (APITimeoutError, TimeoutError)): return 'The AI request timed out. Your event is saved. Send a follow-up to retry.'
    if isinstance(exc, APIConnectionError): return 'Could not connect to the AI provider. Check the internet connection and retry.'
    if isinstance(exc, APIStatusError): return f'The AI provider returned HTTP {exc.status_code}. Check model access and provider status before retrying.'
    if isinstance(exc, ValueError):
        # Only reveal known application validation messages, never arbitrary provider text.
        known=('Web research did not finish. Retry or narrow the request.',
               'No cited web results were returned. Try a more specific city and country.',
               'Timeline must be ordered, unique, include welcome at 0 and end at event duration',
               'Build options and timeline before critique','Interpretation, schedule and ready critic required',
               'Unknown option','Hard constraint check failed','Expected exactly one tool call',
               'Tool is not allowed for this role')
        detail=str(exc) if str(exc) in known else 'The returned tool arguments could not be read.'
        return f'Planning validation failed{step}: {detail}. Send a follow-up to retry; nothing was booked.'
    return f'An internal planning error occurred{step} ({type(exc).__name__}). Your event is saved; no external action occurred.'

@app.post('/api/events/{id}/agent/start')
def start_agent(id:str,body:AgentStart):
    if body.mode=='live':
        if not body.consent: raise HTTPException(400,'Approve sharing the event requirements, preferences, feedback and planning records with OpenAI')
        if not os.getenv('OPENAI_API_KEY'): raise HTTPException(503,'Set OPENAI_API_KEY to use live AI. Rehearsal is scripted, not AI.')
    with db() as c:
        e=get(c,id)
        if e['revision']!=body.revision or e['status']=='running': raise HTTPException(409,'Pause or refresh before starting a new run')
        old=e.get('agent')
        memory=(old.get('feedback','')+'\n' if old else '')+body.feedback
        archive=e.setdefault('agent_archive',[])
        if old: archive.append(old)
        e.update(status='running',stage=0,catalog=[],plans=[],checks=[],timeline=[],selected=0,ai_note=None)
        e['agent']=dict(mode=body.mode,web_search=body.web_search and body.mode=='live',role='planner',feedback=memory[-4000:],message=body.feedback,trace=[],turns=0,
                        consent=body.consent,critique=None,proposal=None,question=None)
        log(e,f'{body.mode.capitalize()} agent started. Prior draft approval no longer applies. Sharing consent: {body.consent}.')
        save(c,e)
    return e

@app.post('/api/events/{id}/agent/step')
async def agent_step(id:str,body:AgentStep):
    from . import agent
    # One model request per event/revision, while pause/stop remain independently available.
    lock=agent_locks.setdefault(id,asyncio.Lock())
    async with lock:
        with db() as c:
            e=get(c,id)
            if e['revision']!=body.revision or e['status']!='running' or not e.get('agent'):
                raise HTTPException(409,'Run changed or is not running')
        a=e['agent']
        if a['turns']>=16:
            e['status']='blocked';a['question']='Turn limit reached. Review the trace and refine your brief before restarting.'
        else:
            name=None
            try:
                web_run=a['mode']=='live' and a.get('web_search',False)
                if web_run:
                    from .research import research, apply_research
                    name='web_search'
                    report=await research(e)
                else:
                    name,args=await agent.model_decision(e) if a['mode']=='live' else agent.demo_decision(e)
                # No tool executes against a stopped or changed revision.
                with db() as c:
                    current=get(c,id)
                    if current['revision']!=body.revision or current['status']!='running':
                        raise HTTPException(409,'Run paused, stopped or changed; model output discarded')
                if web_run: apply_research(e,report)
                else: agent.execute(e,name,args)
            except HTTPException: raise
            except Exception as exc:
                e['status']='blocked'
                a['question']=agent_failure(exc,name)
                a['trace'].append(dict(role=a['role'],tool='safe_failure',summary='Run stopped safely.',result=a['question'],error_type=type(exc).__name__,failed_tool=name))
            a['turns']+=1
        with db() as c:
            current=get(c,id)
            if current['revision']!=body.revision or current['status']!='running':
                raise HTTPException(409,'Run changed; result discarded')
            log(e,f'Agent turn {a["turns"]}: {a["trace"][-1]["tool"] if a["trace"] else "turn limit"}')
            save(c,e)
        return e

dist=Path(__file__).resolve().parents[1]/'frontend'/'dist'
if dist.exists(): app.mount('/',StaticFiles(directory=dist,html=True),name='dashboard')
