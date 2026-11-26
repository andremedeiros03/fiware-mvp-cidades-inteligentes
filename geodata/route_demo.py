import argparse
import osmnx as ox
from geodata.network import OUT, load_config, route, write_json, haversine

def main():
    p=argparse.ArgumentParser(description='Primeiro cálculo de rota, por distância ou tempo de referência.')
    p.add_argument('--origem',nargs=2,type=float,metavar=('LAT','LON'),required=True)
    p.add_argument('--destino',nargs=2,type=float,metavar=('LAT','LON'),required=True)
    p.add_argument('--criterio',choices=['length','travel_time'],default='length')
    args=p.parse_args(); g=ox.io.load_graphml(OUT/'natal.graphml'); cfg=load_config()
    def snap(point):
        lat,lon=point; west,south,east,north=cfg['bbox_wsen']
        if not (west<=lon<=east and south<=lat<=north): raise SystemExit('Ponto fora da região piloto.')
        n=ox.distance.nearest_nodes(g,X=lon,Y=lat)
        d=haversine((lon,lat),(float(g.nodes[n]['x']),float(g.nodes[n]['y'])))
        if d>cfg['max_snap_m']: raise SystemExit(f'Ponto distante {d:.0f} m da malha; selecione outro.')
        return n,round(d,1)
    a,da=snap(args.origem); b,db=snap(args.destino)
    try: result=route(g,a,b,args.criterio)
    except Exception as exc:
        import networkx as nx
        if isinstance(exc,nx.NetworkXNoPath): raise SystemExit('Sem caminho direcionado entre os pontos.') from exc
        raise
    result.update({'criterion':args.criterio,'origin_snap_m':da,'destination_snap_m':db,'source':'OpenStreetMap contributors'})
    write_json(OUT/'route.json',result); write_json(OUT/'route.geojson',result['edges'])
    print(f"Distância: {result['distance_m']:.0f} m | tempo de referência: {result['reference_time_s']/60:.1f} min | ajuste origem/destino: {da}/{db} m")
    print('Arquivos: geodata/output/route.json e route.geojson. Não é uma rota de trânsito em tempo real.')
if __name__=='__main__': main()
