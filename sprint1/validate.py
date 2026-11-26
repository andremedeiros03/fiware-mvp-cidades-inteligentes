"""Valida observações do intervalo de teste no Orion e CrateDB."""
import argparse, json
from datetime import datetime, timedelta, timezone
from sprint1.common import *

def main():
    p=argparse.ArgumentParser(); p.add_argument('--inicio',required=True); p.add_argument('--passos',type=int,required=True); args=p.parse_args()
    if args.passos<1: p.error('passos deve ser positivo')
    start=datetime.fromisoformat(args.inicio); start=start if start.tzinfo else start.replace(tzinfo=timezone(timedelta(hours=-3)))
    end=start+timedelta(minutes=5*args.passos); inv=load_inventory(); missing=[]; counts=[]
    for s in inv['segments']:
        eid=observation_id(s)
        status,_=request('GET',f'{ORION}/ngsi-ld/v1/entities/{eid}',headers={'NGSILD-Tenant':TENANT},accept=(200,404))
        if status!=200: missing.append(eid)
        for ent in [road_id(s),'urn:ngsi-ld:Device:'+s['sensor_id']]:
            status,_=request('GET',f'{ORION}/ngsi-ld/v1/entities/{ent}',headers={'NGSILD-Tenant':TENANT},accept=(200,404))
            if status!=200: missing.append(ent)
        _,result=request('POST',f'{CRATE}/_sql',{'stmt':'SELECT count(*), count(DISTINCT time_index) FROM mttransito.ettrafficflowobserved WHERE entity_id = ? AND time_index >= ? AND time_index < ?', 'args':[eid,int(start.timestamp()*1000),int(end.timestamp()*1000)]})
        total,unique=result['rows'][0]; counts.append({'sensor':eid,'total':total,'distinct_timestamps':unique,'expected':args.passos,'ok':total==unique==args.passos})
    for s in inv['signals']:
        status,_=request('GET',f'{ORION}/ngsi-ld/v1/entities/{device_id(s)}',headers={'NGSILD-Tenant':TENANT},accept=(200,404))
        if status!=200: missing.append(device_id(s))
    report={'missing_entities':missing,'history':counts,'ok':not missing and all(c['ok'] for c in counts)}
    print(json.dumps(report,indent=2)); raise SystemExit(0 if report['ok'] else 1)
if __name__=='__main__': main()
