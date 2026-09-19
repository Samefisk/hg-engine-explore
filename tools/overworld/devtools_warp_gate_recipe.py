"""One fixed real-door route; setup travel is not part of the warp claim."""
from .devtools_warp_gate_measurement import KIND

def stage(name):
    return dict(kind='measurement-stage',measurement=KIND,stage=name,when='final')

def setup():
    return [('teleport',dict(map=67,x=555,z=392,facing=0)),
            ('party',dict(slot=0,species=155,level=10,hp=1,status=0)),
            ('spawn',dict(species=155,form=0,role='mounted',slot=0,level=5)),
            ('step',dict(frames=16,keys=[])),('bind',dict(subject='cyndaquil'))]

def route():
    actions=[]
    for index,keys in enumerate((['DOWN'],['UP'])):
        actions.extend([('mount-teleport.configure',dict(subject='cyndaquil',locomotion=9,teleportTime=7,teleportPause=0)),
                        *(([('step',dict(frames=1,keys=['UP']))]) if index==0 else []),
                        ('step',dict(frames=8,keys=keys,until=stage('case-started'))),
                        ('wait',dict(predicate=stage('case-complete')))])
    return actions+[('mount-teleport.restore',dict(subject='cyndaquil')),
                    ('step',dict(frames=32,keys=['UP'],until=stage('walk-started'))),
                    ('wait',dict(predicate=stage('arrived')))]

def validate_recipe(value,measurement):
    if measurement!=dict(kind=KIND,subject='cyndaquil') or value['mode']!='prepared' or value['subjects']!=[dict(id='cyndaquil',species=155,role='MOUNTED',acquire='existing')]:
        raise ValueError('warp requires one prepared Mounted Cyndaquil')
    if value['budgets']['maxFrames']>800:
        raise ValueError('warp route exceeds frame bound')
    for phase,expected in (('setup',setup()),('actions',route())):
        if [(row['op'],row['args']) for row in value[phase]]!=expected:
            raise ValueError('warp fixed '+phase+' route differs')
    if value['assertions']!=[dict(kind='measurement-complete',measurement=KIND,when='final')]:
        raise ValueError('warp requires complete measurement')
