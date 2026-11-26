import json, os, urllib.request, urllib.error
from geodata.network import OUT, fingerprint

ORION=os.getenv('ORION_URL','http://localhost:1026')
IOTA=os.getenv('IOTA_URL','http://localhost:4041')
CRATE=os.getenv('CRATE_URL','http://localhost:4200')
TENANT='transito'
API_KEY='chave-trafego'
TRANSPORT='https://smart-data-models.github.io/dataModel.Transportation/context.jsonld'
DEVICE='https://raw.githubusercontent.com/smart-data-models/dataModel.Device/master/context.jsonld'
NS='https://github.com/andremedeiros03/fiware-mvp-cidades-inteligentes#'
CONTEXT=[TRANSPORT,DEVICE,{'osmEdge':NS+'osmEdge','referenceSpeed':NS+'referenceSpeed','corridorId':NS+'corridorId','signalState':NS+'signalState','simulated':NS+'simulated','osmTaggedSignal':NS+'osmTaggedSignal','refObservation':NS+'refObservation','refRoadSegment':'https://smartdatamodels.org/dataModel.Transportation/refRoadSegment'}]
IOTA_HEADERS={'fiware-service':TENANT,'fiware-servicepath':'/'}
LD_HEADERS={'NGSILD-Tenant':TENANT,'Content-Type':'application/ld+json'}

def load_inventory():
    result=json.loads((OUT/'road_segments.json').read_text(encoding='utf-8'))
    if result['graph_sha256']!=fingerprint(OUT/'natal.graphml'): raise RuntimeError('Inventário e grafo pertencem a snapshots diferentes.')
    if not result['segments']: raise RuntimeError('Inventário vazio.')
    return result

def request(method,url,body=None,headers=None,accept=(200,201,204)):
    h={'Content-Type':'application/json'}; h.update(headers or {})
    req=urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,headers=h,method=method)
    try:
        with urllib.request.urlopen(req,timeout=25) as r: status,raw=r.status,r.read().decode()
    except urllib.error.HTTPError as e: status,raw=e.code,e.read().decode()
    if status not in accept: raise RuntimeError(f'{method} {url}: HTTP {status}: {raw[:600]}')
    try: value=json.loads(raw) if raw else None
    except ValueError: value=raw
    return status,value

def prop(value,**kw): return {'type':'Property','value':value,**kw}
def rel(value): return {'type':'Relationship','object':value}
def geo(value): return {'type':'GeoProperty','value':value}
def road_id(s): return 'urn:ngsi-ld:RoadSegment:'+s['id']
def observation_id(s): return 'urn:ngsi-ld:TrafficFlowObserved:'+s['sensor_id']
def device_id(s): return 'urn:ngsi-ld:Device:'+s['id']
def upsert(entity):
    data={**entity,'@context':CONTEXT}
    url=f'{ORION}/ngsi-ld/v1/entities'
    status,_=request('POST',url,data,LD_HEADERS,accept=(201,409))
    if status==409:
        attrs={k:v for k,v in data.items() if k not in ('id','type')}
        # POST /attrs appends or overwrites attributes (no noOverwrite option).
        request('POST',f"{url}/{entity['id']}/attrs",attrs,LD_HEADERS,accept=(204,))
