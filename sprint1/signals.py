"""Estados demonstrativos somente no Orion-LD, não controla dispositivos físicos."""
import argparse
from sprint1.common import *

def main():
    p=argparse.ArgumentParser(); p.add_argument('--tick',type=int,default=0); args=p.parse_args(); inv=load_inventory()
    for j,s in enumerate(inv['signals']):
        cycle=(args.tick+j*3)%12
        state='green' if cycle<5 else 'yellow' if cycle==5 else 'red'
        request('POST',f'{ORION}/ngsi-ld/v1/entities/{device_id(s)}/attrs',{'signalState':prop(state),'@context':CONTEXT},LD_HEADERS,accept=(204,))
        print(s['corridor'],s['id'],state)
    print('Estados ilustrativos independentes, não representam plano de fases seguro.')
if __name__=='__main__': main()
