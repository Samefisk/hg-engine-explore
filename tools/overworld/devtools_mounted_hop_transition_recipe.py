"""Finite proposed route; runtime terrain and transition remain mandatory proof."""
from tools.overworld.devtools_mounted_hop_transition_measurement import KIND, REQUIREMENT, require


def stage(name):
    return dict(kind='measurement-stage', measurement=KIND, stage=name, when='final')


def actions():
    def step(name, frames, keys, until=None):
        args=dict(frames=frames,keys=keys)
        if until is not None:args['until']=until
        return dict(id=name,op='step',args=args,budget=dict(maxSeconds=30,maxFrames=frames,noProgressFrames=frames))
    idle=dict(kind='actor-field',subject='mankey',path='motionPhase',operator='eq',value='IDLE',when='final')
    result=[step('cross-boundary',120,['RIGHT'],stage('context-changed')),
            step('finish-crossing-hop',120,[],stage('transition-motion-complete')),
            step('recovery-hop',20,['RIGHT']),step('finish-recovery-hop',120,[],idle)]
    for index in range(250):
        result.extend([step('soak-input-'+str(index),20,['LEFT' if index%2==0 else 'RIGHT']),
                       step('soak-settle-'+str(index),120,[],idle)])
    result.append(step('final-recovery',120,[],stage('recovered')))
    return result


def validate_recipe_contract(value, measurement):
    require(measurement==dict(kind=KIND,subject='mankey'), 'measurement shape differs')
    require(value['mode']=='prepared' and value['requirements']==[REQUIREMENT]
            and value['subjects']==[dict(id='mankey',species=56,role='MOUNTED',acquire='existing')]
            and value['fixture']==dict(rom='test.nds',save='test.sav'), 'fixture identity differs')
    require(value['budgets']['maxFrames']==40000 and value['budgets']['minObservedFrames']==5000
            and value['budgets']['maxSeconds']<=3600, 'finite soak bounds differ')
    setup=value['setup']
    require([a['op'] for a in setup]==['teleport','party','spawn','step','bind'], 'setup operations differ')
    require([a['args'] for a in setup]==[
        dict(map=33,x=671,z=402,facing=3),dict(slot=0,species=56,level=10,hp=1,status=0),
        dict(species=56,form=0,role='mounted',slot=0,level=10),dict(frames=16,keys=[]),dict(subject='mankey')],
        'prepared setup differs')
    require(value['actions']==actions(), 'bounded input/settle route differs')
    require(value['assertions']==[dict(kind='measurement-complete',measurement=KIND,when='final')], 'final contract differs')
