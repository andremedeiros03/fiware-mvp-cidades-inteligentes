"""Execute na raiz: python -m geodata.extract_network"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import osmnx as ox
from shapely.geometry import box
from geodata.network import *

def main():
    parser=argparse.ArgumentParser(description='Extrai e congela a malha viária da região piloto.')
    parser.add_argument('--graph',type=Path,help='Reutiliza um GraphML OSMnx existente, sem baixar novamente.')
    args=parser.parse_args(); cfg=load_config(); OUT.mkdir(exist_ok=True)
    ox.settings.use_cache=True
    ox.settings.cache_folder=str(ROOT/'cache')
    if args.graph:
        g=ox.io.load_graphml(args.graph)
    else:
        g=ox.graph.graph_from_polygon(box(*cfg['bbox_wsen']), network_type='drive', simplify=True, retain_all=False)
    if not len(g) or not g.is_directed(): raise SystemExit('Grafo vazio ou não direcionado.')
    g=ox.routing.add_edge_speeds(g,fallback=cfg['fallback_speed_kph'])
    g=ox.routing.add_edge_travel_times(g)
    ox.io.save_graphml(g, filepath=OUT/'natal.graphml')
    segs, coverage=select_segments(g,cfg); signals=select_signals(g,segs,cfg)
    write_json(OUT/'roads.geojson',collection([feature(mapping(edge_geometry(g,u,v,d)),{'edge_id':edge_id(u,v,k),'name':' / '.join(names(d)), 'length_m':float(d['length']),'reference_speed_kph':float(d['speed_kph'])}) for u,v,k,d in g.edges(keys=True,data=True)]))
    write_json(OUT/'intersections.geojson',collection([feature({'type':'Point','coordinates':[float(d['x']),float(d['y'])]},{'node_id':str(n)}) for n,d in g.nodes(data=True)]))
    write_json(OUT/'monitored_roads.geojson',collection([feature(s['geometry'],{'segment_id':s['id'],'corridor':s['corridor'],'name':s['name']}) for s in segs]))
    write_json(OUT/'signals.geojson',collection([feature({'type':'Point','coordinates':s['location']},{k:v for k,v in s.items() if k!='location'}) for s in signals]))
    write_json(OUT/'road_segments.json',{'generated_at':datetime.now(timezone.utc).isoformat(),'graph_sha256':fingerprint(OUT/'natal.graphml'),'source':'OpenStreetMap contributors','bbox_wsen':cfg['bbox_wsen'],'segments':segs,'signals':signals,'coverage':coverage})
    print(f'Nós: {len(g)} | arestas direcionadas: {g.number_of_edges()} | sensores: {len(segs)} | semáforos: {len(signals)}')
    for r in coverage: print(r)
    if any(r['selected']<r['requested'] for r in coverage): print('AVISO: cobertura parcial; revise aliases e bbox antes de provisionar.')
    if not segs: raise SystemExit('Nenhum segmento selecionado.')

if __name__=='__main__': main()
