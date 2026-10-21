"""Bounded read/login release checks. Prints no credentials, tokens or sensor payloads."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
import httpx

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('--credentials',type=Path,default=ROOT/'gateway/backend-login.local.json')
    parser.add_argument('--vercel-curl',action='store_true')
    args = parser.parse_args()
    if not args.url.startswith('https://') or not args.url.endswith('.vercel.app'):
        raise SystemExit('Use the verified HTTPS Vercel deployment origin')
    credentials = json.loads(args.credentials.read_text())
    checks = {}
    with tempfile.TemporaryDirectory(prefix='cloud-check-',dir=ROOT/'.codex-tools') as folder, httpx.Client(timeout=65) as client:
        scratch = Path(folder)
        def request(method,path,payload=None,token=None):
            start=time.monotonic()
            if args.vercel_curl:
                headers=scratch/'headers.local.txt'
                headers.write_text('Content-Type: application/json\n'+ ('Authorization: Bearer '+token+'\n' if token else ''))
                command=['node',str(ROOT/'.codex-tools/vercel-cli/node_modules/vercel/dist/index.js'),'curl',args.url+path,
                         '--scope','team_ywvVSVA26lWSbH1XkoAgHdCE','--','--silent','--show-error',
                         '--request',method,'--header','@'+str(headers),'--write-out','\n%{http_code}']
                if payload is not None:
                    body=scratch/'body.local.json';body.write_text(json.dumps(payload))
                    command+=['--data-binary','@'+str(body)]
                result=subprocess.run(command,cwd=ROOT/'Tamper_admin/backend',capture_output=True,text=True)
                if result.returncode:
                    raise RuntimeError('Protected deployment request failed; sensitive output withheld')
                raw,code=result.stdout.rsplit('\n',1)
                status=int(code.strip());data=json.loads(raw)
            else:
                response=client.request(method,args.url+path,json=payload,headers={'Authorization':'Bearer '+token} if token else {})
                status=response.status_code
                try:data=response.json()
                except ValueError:data={}
            checks[method+' '+path]={'status':status,'seconds':round(time.monotonic()-start,2)}
            if status!=200:
                reason = data.get('detail')
                classification = reason if reason in ('Invalid credentials','Invalid or expired token','Shipment not found') else 'response withheld'
                print(json.dumps({'url':args.url,'completed_checks':checks,'error':classification}),flush=True)
                raise RuntimeError(f'{method} {path} returned HTTP {status}; {classification}')
            return data
        admin=request('POST','/api/auth/login',{'username':credentials['admin_username'],'password':credentials['admin_password']})['access_token']
        request('GET','/api/admin/dashboard',token=admin)
        devices=request('GET','/api/devices',token=admin)
        detail=request('GET','/api/shipments/PRCL-2024-05-21-001',token=admin)
        live=request('GET','/api/shipments/PRCL-2024-05-21-001/live',token=admin)
        proof=request('GET','/api/shipments/PRCL-2024-05-21-001/evidence?limit=1',token=admin)
        user=request('POST','/api/auth/login',{'username':credentials['user_username'],'password':credentials['user_password']})['access_token']
        request('GET','/api/shipments/PRCL-2024-05-21-001/live',token=user)
        if len(detail.get('events',[]))!=30 or not live.get('latest_telemetry') or not proof.get('records'):
            raise RuntimeError('Expected real restored events/live/evidence are missing')
        print(json.dumps({'url':args.url,'checks':checks,'ledger_count':len(detail['events']),'devices':len(devices),
                          'real_existing_event_visible':True,'source_upload':'NOT TESTED (no synthetic production telemetry)'}))

if __name__=='__main__':
    main()
