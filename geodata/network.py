from __future__ import annotations
import hashlib
import json
import math
import unicodedata
from pathlib import Path
from shapely.geometry import LineString, mapping
import networkx as nx

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output'

def load_config():
    return json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

def normalized(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(s).lower()) if not unicodedata.combining(c))

def names(data):
    val = data.get('name', '')
    return [str(v) for v in val] if isinstance(val, (list, tuple)) else [str(val)]

def edge_id(u, v, k):
    return f'osm-{u}-{v}-{k}'

def edge_geometry(g, u, v, data):
    a = (float(g.nodes[u]['x']), float(g.nodes[u]['y']))
    b = (float(g.nodes[v]['x']), float(g.nodes[v]['y']))
    geom = data.get('geometry')
    coords = list(geom.coords) if geom is not None else [a, b]
    if math.dist(coords[-1][:2], a) < math.dist(coords[0][:2], a):
        coords.reverse()
    return LineString([c[:2] for c in coords])

def point_on_edge(g, u, v, data):
    return list(edge_geometry(g, u, v, data).interpolate(.5, normalized=True).coords[0])

def haversine(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(h)))

def feature(geometry, props):
    return {'type':'Feature','geometry':geometry,'properties':props}

def collection(features):
    return {'type':'FeatureCollection','features':features}

def select_segments(g, config):
    segments, report, used = [], [], set()
    for corridor in config['corridors']:
        aliases = [normalized(a) for a in corridor['aliases']]
        candidates = [(u,v,k,d) for u,v,k,d in g.edges(keys=True,data=True)
                      if d.get('length',0) >= config['minimum_segment_m']
                      and any(a in normalized(n) for a in aliases for n in names(d))
                      and (u,v,k) not in used]
        # Avoid concentrating all sensors in a single intersection: choose first by length,
        # then maximize distance to previously selected midpoints.
        chosen = []
        while candidates and len(chosen) < config['segments_per_corridor']:
            def score(e):
                u,v,k,d=e
                p=point_on_edge(g,u,v,d)
                return (min(haversine(p, q[4]) for q in chosen) if chosen else float(d['length']), float(d['length']), str((u,v,k)))
            best=max(candidates,key=score)
            candidates.remove(best)
            u,v,k,d=best; p=point_on_edge(g,u,v,d)
            chosen.append((u,v,k,d,p)); used.add((u,v,k))
            sid=edge_id(u,v,k)
            segments.append({'id':sid,'corridor':corridor['id'],'name':' / '.join(names(d)) or sid,
                'edge':[int(u),int(v),int(k)],'length_m':round(float(d['length']),3),
                'reference_speed_kph':round(float(d['speed_kph']),2),
                'geometry':mapping(edge_geometry(g,u,v,d)),'sensor_location':p,
                'sensor_id':f's1-sensor-{sid}'})
        report.append({'corridor':corridor['id'],'selected':len(chosen),'requested':config['segments_per_corridor']})
    return segments, report

def select_signals(g, segments, config):
    signals, used = [], set()
    for corridor in config['corridors']:
        chosen = 0
        for s in sorted((s for s in segments if s['corridor']==corridor['id']), key=lambda s:-s['length_m']):
            u,v,k=s['edge']
            # Prefer an OSM-tagged signal if available; otherwise mark the site as hypothetical.
            endpoints=[v,u]
            node=next((n for n in endpoints if n not in used and g.nodes[n].get('highway')=='traffic_signals'), None)
            if node is None:
                node=next((n for n in endpoints if n not in used),None)
            if node is None: continue
            used.add(node)
            signals.append({'id':f's1-semaforo-{node}','node':int(node),'corridor':s['corridor'],
                'road_segment_id':s['id'],'location':[float(g.nodes[node]['x']),float(g.nodes[node]['y'])],
                'osm_tagged_signal':g.nodes[node].get('highway')=='traffic_signals'})
            chosen+=1
            if chosen>=config['signals_per_corridor']: break
    return signals

def route(g, start, end, weight='length'):
    nodes=nx.shortest_path(g,start,end,weight=weight,method='dijkstra')
    edges=[]
    for u,v in zip(nodes,nodes[1:]):
        k,d=min(g[u][v].items(), key=lambda kv:(float(kv[1][weight]),str(kv[0])))
        edges.append((u,v,k,d))
    return {'nodes':[int(n) for n in nodes],'distance_m':round(sum(float(d['length']) for _,_,_,d in edges),2),
        'reference_time_s':round(sum(float(d['travel_time']) for _,_,_,d in edges),2),
        'edges':collection([feature(mapping(edge_geometry(g,u,v,d)),{'edge_id':edge_id(u,v,k),'name':' / '.join(names(d)),'length_m':float(d['length'])}) for u,v,k,d in edges])}

def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
