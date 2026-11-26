"""Provisionamento complementar: não substitui o setup original."""
import argparse
from sprint1.common import *

def road_entity(s):
    return {'id':road_id(s),'type':'RoadSegment','name':prop(s['name']),
        'location':geo(s['geometry']),'startPoint':geo({'type':'Point','coordinates':s['geometry']['coordinates'][0]}),
        'endPoint':geo({'type':'Point','coordinates':s['geometry']['coordinates'][-1]}),
        'length':prop(s['length_m']/1000,unitCode='KMT'),'referenceSpeed':prop(s['reference_speed_kph'],unitCode='KMH'),
        'osmEdge':prop(s['edge']),'corridorId':prop(s['corridor'])}

def sensor_entity(s):
    return {'id':'urn:ngsi-ld:Device:'+s['sensor_id'],'type':'Device','name':prop(s['sensor_id']),
        'location':geo({'type':'Point','coordinates':s['sensor_location']}),'controlledProperty':prop(['trafficFlow','speed','occupancy']),
        'refRoadSegment':rel(road_id(s)),'refObservation':rel(observation_id(s)),'corridorId':prop(s['corridor']),'simulated':prop(True)}

def signal_entity(s):
    return {'id':device_id(s),'type':'Device','name':prop(s['id']),'location':geo({'type':'Point','coordinates':s['location']}),
        'refRoadSegment':rel('urn:ngsi-ld:RoadSegment:'+s['road_segment_id']),'corridorId':prop(s['corridor']),
        'signalState':prop('unknown'),'simulated':prop(True),'osmTaggedSignal':prop(s['osm_tagged_signal'])}

def iota_device(s):
    return {'device_id':s['sensor_id'],'entity_name':observation_id(s),'entity_type':'TrafficFlowObserved','apikey':API_KEY,'transport':'MQTT',
        'attributes':[{'object_id':'v','name':'averageVehicleSpeed','type':'Number'}, {'object_id':'q','name':'intensity','type':'Number'}, {'object_id':'o','name':'occupancy','type':'Number'}, {'name':'congested','type':'Boolean','expression':'o > 0.25'}, {'name':'dateObserved','type':'DateTime','expression':'TimeInstant'}],
        'static_attributes':[{'name':'refRoadSegment','type':'Relationship','value':road_id(s)}, {'name':'laneId','type':'Number','value':1}, {'name':'laneDirection','type':'Text','value':'forward'}, {'name':'location','type':'geo:json','value':{'type':'Point','coordinates':s['sensor_location']}}, {'name':'dataProvider','type':'Text','value':'simulador-sprint1'}]}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--dry-run',action='store_true'); args=p.parse_args(); inv=load_inventory()
    entities=[road_entity(s) for s in inv['segments']]+[sensor_entity(s) for s in inv['segments']]+[signal_entity(s) for s in inv['signals']]
    if args.dry_run:
        print(json.dumps({'entities':entities,'iot_devices':[iota_device(s) for s in inv['segments']]},ensure_ascii=False,indent=2)); return
    _,groups=request('GET',f'{IOTA}/iot/services',headers=IOTA_HEADERS)
    if not any(g['apikey']==API_KEY for g in groups['services']): raise SystemExit('Execute o provisionamento original antes da expansão.')
    for ent in entities: upsert(ent); print('Orion:',ent['id'])
    for s in inv['segments']:
        status,_=request('GET',f"{IOTA}/iot/devices/{s['sensor_id']}",headers=IOTA_HEADERS,accept=(200,404))
        if status==404: request('POST',f'{IOTA}/iot/devices',{'devices':[iota_device(s)]},IOTA_HEADERS)
        print('IoT Agent:',s['sensor_id'], 'registrado' if status==404 else 'já existe (mantido)')
    print('Concluído. Execute o simulador Sprint 1.')
if __name__=='__main__': main()
