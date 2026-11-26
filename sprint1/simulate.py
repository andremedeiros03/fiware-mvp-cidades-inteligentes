"""Sensores sintéticos, com demanda semanal e incidentes correlacionados."""
import argparse, math, os, random, time
from datetime import datetime,timedelta,timezone
from sprint1.common import *

STEP=timedelta(minutes=5)

def bell(h, center, width): return math.exp(-((h-center)**2)/(2*width**2))

def scenario(segments,start,steps,seed):
    rng=random.Random(seed); state={s['id']:0.0 for s in segments}; incidents={}; daily={}
    for i in range(steps):
        t=start+i*STEP; h=t.hour+t.minute/60; weekday=t.weekday()<5
        if t.date() not in daily: daily[t.date()]=rng.uniform(.82,1.18)
        for corridor in sorted({s['corridor'] for s in segments}):
            if incidents.get(corridor,0)<=i and rng.random()<.008: incidents[corridor]=i+rng.randint(3,12)
        readings=[]
        for j,s in enumerate(segments):
            f=.85+(j%5)*.10
            demand=(.045+.07*bell(h,13,5)+(.22*bell(h,7.5,1.1)+.25*bell(h,18,1.3))*(1 if weekday else .45))*f*daily[t.date()]
            state[s['id']]=.75*state[s['id']]+rng.gauss(0,.015)
            occ=max(.01,min(.55,demand+state[s['id']]+(.19 if incidents.get(s['corridor'],0)>i else 0)))
            speed=max(5.,s['reference_speed_kph']*(1-occ/.6))
            flow=round(200*occ*speed/12)
            readings.append((s,{'v':round(speed,1),'q':flow,'o':round(occ,3),'TimeInstant':t.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}))
        yield t,readings

def main():
    p=argparse.ArgumentParser(); p.add_argument('--inicio',required=True,help='ISO 8601; use período inédito, fuso local -03:00'); p.add_argument('--dias',type=int,default=1); p.add_argument('--passos',type=int,help='Número de passos para smoke test'); p.add_argument('--semente',type=int,default=42); p.add_argument('--spacing',type=float,default=.5,help='Segundos entre publicações'); p.add_argument('--dry-run',action='store_true'); args=p.parse_args()
    if args.dias<1 or (args.passos is not None and args.passos<1) or args.spacing<0: p.error('Parâmetros inválidos.')
    start=datetime.fromisoformat(args.inicio); start=start if start.tzinfo else start.replace(tzinfo=timezone(timedelta(hours=-3)))
    start=start.astimezone(timezone(timedelta(hours=-3)))
    if start.minute%5 or start.second or start.microsecond: p.error('Início deve estar alinhado ao passo de cinco minutos.')
    inv=load_inventory(); steps=args.passos if args.passos is not None else args.dias*288
    if not args.dry_run:
        import paho.mqtt.client as mqtt
        client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2); client.connect(os.getenv('MQTT_HOST','localhost'),int(os.getenv('MQTT_PORT','1883'))); client.loop_start()
    count=0
    try:
        for i,(t,readings) in enumerate(scenario(inv['segments'],start,steps,args.semente)):
            for s,payload in readings:
                if args.dry_run: print(s['sensor_id'],json.dumps(payload))
                else:
                    result=client.publish(f"/json/{API_KEY}/{s['sensor_id']}/attrs",json.dumps(payload),qos=1); result.wait_for_publish(timeout=20)
                    if not result.is_published(): raise RuntimeError('MQTT não confirmou publicação.')
                    time.sleep(args.spacing)
                count+=1
            if not args.dry_run and (i==0 or i==steps-1 or (i+1)%12==0): print(t.isoformat(),count,'publicações MQTT confirmadas',flush=True)
    finally:
        if not args.dry_run: client.disconnect(); client.loop_stop()
    print(f'{count} publicações. Confirmação MQTT não comprova persistência; execute validate.')
if __name__=='__main__': main()
