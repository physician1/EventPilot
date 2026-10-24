"""Deterministic, inspectable planning. Catalog records are data, never instructions."""
from itertools import product
from datetime import datetime, timedelta
from typing import Protocol

class DiscoveryProvider(Protocol):
    def discover(self, event: dict) -> list[dict]: ...

class DemoProvider:
    def discover(self, event):
        rows = []
        specs = {
            'venue': [('Harbor House', 1200, 80, False), ('The Glass Garden', 2100, 150, True), ('Foundry Studio', 750, 45, False)],
            'catering': [('Gather & Graze', 24, 200, False), ('Table & Thyme', 38, 150, False)],
            'entertainment': [('Sunday Sound', 450, 200, False), ('Velvet Sessions', 800, 200, False)],
            'photography': [('Little Moments', 600, 200, False), ('Golden Hour Studio', 950, 200, False)],
            'av': [('Clear Signal AV', 350, 200, False), ('Stagecraft', 650, 200, False)]}
        if event['location'].strip().lower() != 'boston':
            return []
        for category, options in specs.items():
            for i, (name, price, capacity, outdoor) in enumerate(options):
                rows.append(dict(id=f'{category}-{i}', name=name, category=category,
                    cost_cents=price*100*(event['guests'] if category=='catering' else 1),
                    capacity=capacity, outdoor=outdoor, location='Boston', date=event['date'],
                    available=event['date'] not in ['2027-12-31'], verified=False,
                    source='Fictional demo catalog', quality=80+i*10))
        return rows

def required_categories(e):
    return ['venue','catering', {'birthday':'entertainment','wedding':'photography','corporate':'av'}[e['kind']]]

def blockers(e):
    reasons=[]
    for cat in required_categories(e):
        rows=[r for r in e['catalog'] if r['category']==cat]
        if not rows:
            reasons.append(f'No {cat} records found. Search this category; the demo only covers Boston.')
            continue
        rows=[r for r in rows if r['available'] and r['date']==e['date'] and r['location'].lower()==e['location'].strip().lower()]
        if not rows:
            reasons.append(f'No {cat} matches the location and simulated availability on this date.')
            continue
        if e['indoor_only']: rows=[r for r in rows if not r['outdoor']]
        if not rows:
            reasons.append(f'No indoor {cat} is available in the demo catalog.')
        elif max(r['capacity'] for r in rows)<e['guests']:
            reasons.append(f"No {'indoor ' if e['indoor_only'] else ''}{cat} accommodates {e['guests']} guests; maximum catalog capacity is {max(r['capacity'] for r in rows)}. Increasing the budget cannot fix capacity.")
    if not reasons and not optimize(e):
        reasons.append(f"Complete supplier combinations exceed the saved ${e['budget_cents']/100:,.2f} budget including 15% fees and 10% contingency.")
    return reasons

def optimize(e, objective='quality'):
    categories = required_categories(e)
    groups = [[r for r in e['catalog'] if r['category']==cat and r['capacity']>=e['guests']
               and r['available'] and r['date']==e['date'] and r['location'].lower()==e['location'].strip().lower()
               and not (e['indoor_only'] and r['outdoor'])] for cat in categories]
    plans=[]
    for items in product(*groups):
        subtotal=sum(r['cost_cents'] for r in items)
        # Explicit allowances, not verified tax rates or quotes.
        fees=(subtotal*15+99)//100
        reserve=(e['budget_cents']*10+99)//100
        total=subtotal+fees+reserve
        if total<=e['budget_cents']:
            plans.append(dict(items=list(items), subtotal=subtotal, fees=fees, reserve=reserve, total=total,
                              score=sum(r['quality'] for r in items)))
    return sorted(plans,key=(lambda p:(p['total'],-p['score'])) if objective=='value' else (lambda p:(-p['score'],p['total'])))[:3]

def timeline(e):
    start=datetime.fromisoformat(e['date']+'T'+e['start_time'])
    moments=[(-60,'Vendor arrival & setup'),(0,'Welcome guests'),(30,{'birthday':'Toast & celebration','wedding':'Ceremony','corporate':'Opening session'}[e['kind']]),(60,'Food & refreshments'),(120,'Main program'),(e['duration_hours']*60,'Guest departure & teardown')]
    return [dict(at=(start+timedelta(minutes=m)).isoformat(timespec='minutes'),task=t) for m,t in moments]

def audit(e):
    p=e['plans'][e.get('selected',0)]
    return [dict(label='Budget includes 15% fee allowance and 10% contingency', ok=p['total']<=e['budget_cents']),
            dict(label='All suppliers cover the guest count',ok=all(r['capacity']>=e['guests'] for r in p['items'])),
            dict(label='Location, requested date and indoor requirement match demo records',ok=all(r['location'].lower()==e['location'].strip().lower() and r['date']==e['date'] and r['available'] and not(e['indoor_only'] and r['outdoor']) for r in p['items'])),
            dict(label='Real prices, availability and policies require verification',ok=False,warning=True),
            dict(label='Bookings, payments and vendor messages are disabled',ok=True)]
