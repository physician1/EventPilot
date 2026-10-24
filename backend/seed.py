"""Idempotent local demo seed: python -m backend.seed."""
from .main import create, events, Intake, command, Command

if not events():
    for name,kind,guests,budget in [('A birthday to remember','birthday',40,500000),('Together, always','wedding',80,1200000),('The next chapter · Team offsite','corporate',30,600000)]:
        e=create(Intake(name=name,kind=kind,location='Boston',date='2027-06-20',guests=guests,budget_cents=budget,preferences='Warm lighting, thoughtful details, and room to connect.'))
        e=command(e['id'],Command(action='start',revision=e['revision']))
        while e['status']=='running': e=command(e['id'],Command(action='step',revision=e['revision']))
    print('Created three fictional demo events awaiting draft approval.')
else:
    print('Existing events found; seed skipped.')
