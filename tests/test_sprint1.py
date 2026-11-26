from datetime import datetime, timezone
import networkx as nx
from geodata.network import route, select_segments, select_signals
from sprint1.provision import road_entity, sensor_entity, iota_device, signal_entity
from sprint1.simulate import scenario

def graph():
    g=nx.MultiDiGraph()
    for n,(x,y) in enumerate([(0,0),(.001,0),(.002,0),(.001,.001)],1): g.add_node(n,x=x,y=y)
    for u,v,k,length in [(1,2,0,100),(1,2,1,130),(2,3,0,100),(1,4,0,150),(4,3,0,150)]:
        g.add_edge(u,v,key=k,length=length,speed_kph=30.,travel_time=length*.12,name='Avenida Salgado Filho')
    return g

def config(): return {'corridors':[{'id':'salgado','aliases':['salgado filho']}],'minimum_segment_m':30,'segments_per_corridor':3,'signals_per_corridor':2}

def test_directed_route_parallel_edges():
    r=route(graph(),1,3); assert r['distance_m']==200; assert r['edges']['features'][0]['properties']['edge_id']=='osm-1-2-0'
    import pytest
    with pytest.raises(nx.NetworkXNoPath): route(graph(),3,1)

def test_segments_and_relationships():
    g=graph(); segments,coverage=select_segments(g,config()); assert len(segments)==3 and coverage[0]['selected']==3
    assert len({s['id'] for s in segments})==3
    for s in segments:
        r=road_entity(s); d=sensor_entity(s); i=iota_device(s)
        assert r['id']==d['refRoadSegment']['object']==i['static_attributes'][0]['value']
        assert d['refObservation']['object']==i['entity_name']
        assert r['length']['value']==s['length_m']/1000
    sig=select_signals(g,segments,config()); assert len(sig)==2
    assert all(signal_entity(s)['simulated']['value'] for s in sig)

def test_simulation_reproducible_and_bounded():
    segments,_=select_segments(graph(),config()); t=datetime(2026,1,1,tzinfo=timezone.utc)
    a=list(scenario(segments,t,30,42)); b=list(scenario(segments,t,30,42)); assert a==b
    assert len(a)==30 and all(len(r)==3 for _,r in a)
    for _,readings in a:
        for s,p in readings:
            assert 0<=p['o']<=.55 and p['v']>=5 and p['q']>=0 and p['TimeInstant'].endswith('Z')

def test_upsert_create_and_existing(monkeypatch):
    import sprint1.common as common
    calls=[]
    def mock(method,url,body=None,headers=None,accept=()):
        calls.append((method,url,body,headers,accept))
        return (409,None) if len(calls)==1 else (204,None)
    monkeypatch.setattr(common,'request',mock)
    segments,_=select_segments(graph(),config()); entity=road_entity(segments[0]); common.upsert(entity)
    assert calls[0][2]['id']==entity['id']
    assert calls[1][1].endswith('/attrs') and 'id' not in calls[1][2] and '@context' in calls[1][2]

def test_scenario_weekday_variation():
    segments,_=select_segments(graph(),config()); start=datetime(2026,1,5,tzinfo=timezone.utc)
    days=list(scenario(segments,start,7*288,42))
    weekday_peak=[p['o'] for _,r in days[7*12:8*12] for _,p in r]
    weekend_peak=[p['o'] for _,r in days[5*288+7*12:5*288+8*12] for _,p in r]
    assert sum(weekday_peak)/len(weekday_peak)>sum(weekend_peak)/len(weekend_peak)
