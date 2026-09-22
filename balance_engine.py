"""Public-address balance queries. Phrases/private keys are never sent over the network."""
import json,urllib.request,urllib.parse
from decimal import Decimal
from datetime import datetime,timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from wallet_core import check_stop

APP=Path(__file__).parent;CHAINS=json.loads((APP/'networks.json').read_text())
REPORT_ASSETS=('ETH','WETH','BNB','POL','BTC')
BALANCE_FOUND_MINIMUM=Decimal('0.001')
def http(url,body=None,headers=None):
 req=urllib.request.Request(url,data=None if body is None else json.dumps(body).encode(),headers={'User-Agent':'WalletAudit/1.0','Content-Type':'application/json',**(headers or {})})
 with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
def price(ids,stop):
 check_stop(stop)
 try:
  data=http('https://api.coingecko.com/api/v3/simple/price?'+urllib.parse.urlencode({'ids':','.join(sorted(set(x for x in ids if x))),'vs_currencies':'usd'}));return {k:Decimal(str(v.get('usd',0))) for k,v in data.items()}
 except Exception:return {}
def batch(chain,method,params,stop):
 values={}
 for offset in range(0,len(params),75):
  check_stop(stop);part=params[offset:offset+75];request=[{'jsonrpc':'2.0','id':i,'method':method,'params':p} for i,p in enumerate(part)]
  try:
   got={x.get('id'):x for x in http(chain['rpc'],request)}
   for i,p in enumerate(part):values[p[0] if method=='eth_getBalance' else p[0]['data'][-40:]]=(got.get(i,{}).get('result'),got.get(i,{}).get('error'))
  except Exception as exc:
   for p in part:values[p[0] if method=='eth_getBalance' else p[0]['data'][-40:]]=(None,str(exc))
 return values
def check_evm(addresses,stop=None,log=lambda s:None):
 prices=price([c.get('price_id') for c in CHAINS]+[t.get('price_id') for c in CHAINS for t in c['tokens']],stop);output=[]
 def scan(chain):
  check_stop(stop);log('Checking '+chain['name']);stamp=datetime.now(timezone.utc).isoformat();out=[]
  try:
   if int(http(chain['rpc'],{'jsonrpc':'2.0','id':1,'method':'eth_chainId','params':[]})['result'],16)!=chain['id']:raise ValueError('unexpected chain ID')
  except Exception as exc:return [dict(address=a,chain=chain['name'],chain_id=chain['id'],asset=chain['symbol'],asset_type='native',amount='',usd='',status=str(exc),checked_utc=stamp,source=chain['rpc']) for a in addresses]
  native=batch(chain,'eth_getBalance',[(a,'latest') for a in addresses],stop)
  # Only the five requested assets are queried and exported.
  items=[]
  if chain['symbol'] in {'ETH','BNB','POL'}:items.append((chain['symbol'],'native','',18,chain.get('price_id')))
  items += [(t['symbol'],'token',t['address'],t['decimals'],t.get('price_id')) for t in chain['tokens'] if t['symbol']=='WETH']
  for symbol,kind,contract,decimals,price_id in items:
   got=native if kind=='native' else batch(chain,'eth_call',[({'to':contract,'data':'0x70a08231'+a[2:].zfill(64)},'latest') for a in addresses],stop)
   for a in addresses:
    raw,error=got.get(a if kind=='native' else a[2:],(None,'no response'));amount=Decimal(int(raw,16))/Decimal(10**decimals) if raw not in (None,'0x') else (Decimal(0) if raw=='0x' else None)
    out.append(dict(address=a,chain=chain['name'],chain_id=chain['id'],asset=symbol,asset_type=kind,contract=contract,amount=str(amount) if amount is not None else '',usd=str(amount*prices.get(price_id,0)) if amount is not None else '',status='ok' if amount is not None else str(error),checked_utc=stamp,source=chain['rpc']))
  return out
 with ThreadPoolExecutor(max_workers=5) as pool:
  for f in as_completed([pool.submit(scan,c) for c in CHAINS]):output.extend(f.result())
 return output,prices
def check_btc(addresses,stop=None,log=lambda s:None):
 out=[]
 for n,address in enumerate(addresses,1):
  check_stop(stop)
  if n%25==0:log(f'Checking Bitcoin {n}/{len(addresses)}')
  stamp=datetime.now(timezone.utc).isoformat();url='https://blockstream.info/api/address/'+address
  try:
   data=http(url);sats=sum(Decimal(x['funded_txo_sum']-x['spent_txo_sum']) for x in (data['chain_stats'],data['mempool_stats']))
   out.append(dict(address=address,chain='Bitcoin',chain_id='bitcoin',asset='BTC',asset_type='native',contract='',amount=str(sats/Decimal(100000000)),usd='',status='ok',checked_utc=stamp,source=url))
  except Exception as exc:out.append(dict(address=address,chain='Bitcoin',chain_id='bitcoin',asset='BTC',asset_type='native',contract='',amount='',usd='',status=str(exc),checked_utc=stamp,source=url))
 return out
def run(address_rows,stop=None,log=lambda s:None):
 evm=sorted({r['address'].lower() for r in address_rows if r['kind']=='EVM'});btc=sorted({r['address'] for r in address_rows if r['kind']=='BTC'})
 # #region agent log
 try:
  from pathlib import Path as _P; import json as _j,time as _t
  with (_P(__file__).parent/'debug-f25f2a.log').open('a',encoding='utf-8') as _f:_f.write(_j.dumps({'sessionId':'f25f2a','hypothesisId':'I','location':'balance_engine.py:run','message':'run start','data':{'evm':len(evm),'btc':len(btc),'rows':len(address_rows or [])},'timestamp':int(_t.time()*1000),'runId':'post-fix'})+'\n')
 except Exception:pass
 # #endregion
 rows,prices=check_evm(evm,stop,log) if evm else ([],{}) ;btc_rows=check_btc(btc,stop,log) if btc else [];btc_usd=prices.get('bitcoin') or price(['bitcoin'],stop).get('bitcoin',Decimal(0))
 for r in btc_rows:
  if r['status']=='ok':r['usd']=str(Decimal(r['amount'])*btc_usd)
 return rows+btc_rows
def summarize(address_rows,balance_rows):
 result=[]
 for source in address_rows:
  entries=[r for r in balance_rows if r['address'].lower()==source['address'].lower() and r['status']=='ok'];assets={k:sum((Decimal(r['amount']) for r in entries if r['asset']==k),Decimal(0)) for k in REPORT_ASSETS}
  result.append(dict(seed_id=source.get('seed_id',''),address=source['address'],kind=source['kind'],path=source.get('path',''),portfolio_usd=str(sum((Decimal(r.get('usd') or 0) for r in entries),Decimal(0))),**{k:str(v) for k,v in assets.items()},coverage='; '.join(sorted({r['chain'] for r in entries}))))
 return result

def summarize_seeds(address_rows,balance_rows):
 """One output row per phrase; address-level detail remains in address_portfolio.csv."""
 result=[]
 for seed_id in sorted({r.get('seed_id','') for r in address_rows if r.get('seed_id','')}):
  members=[r for r in address_rows if r.get('seed_id')==seed_id]
  entries=[r for r in balance_rows if any(r['address'].lower()==m['address'].lower() for m in members) and r['status']=='ok']
  assets={k:sum((Decimal(r['amount']) for r in entries if r['asset']==k),Decimal(0)) for k in REPORT_ASSETS}
  primary=next((m['address'] for m in members if m['kind']=='EVM' and m['path'].endswith('/0')),'')
  result.append(dict(seed_id=seed_id,phrase=members[0].get('phrase',''),metamask_address_0=primary,evm_addresses_checked=sum(m['kind']=='EVM' for m in members),bitcoin_addresses_checked=sum(m['kind']=='BTC' for m in members),portfolio_usd=str(sum((Decimal(r.get('usd') or 0) for r in entries),Decimal(0))),**{k:str(v) for k,v in assets.items()}))
 return result

def balances_found(seed_rows,address_rows,minimum=BALANCE_FOUND_MINIMUM):
 """Return one row per qualifying seed and one row per qualifying listed wallet.

 A record qualifies when any of the five checked assets is at least ``minimum``.
 Derived addresses are represented by their combined seed row, so a phrase never
 appears more than once in this short report.
 """
 def qualifies(row):
  return any(Decimal(row.get(asset) or 0)>=minimum for asset in REPORT_ASSETS)
 found=[]
 for row in seed_rows:
  if qualifies(row):
   found.append(dict(record_type='seed',seed_id=row['seed_id'],phrase=row.get('phrase',''),metamask_address_0=row.get('metamask_address_0',''),wallet_address='',portfolio_usd=row.get('portfolio_usd','0'),**{asset:row.get(asset,'0') for asset in REPORT_ASSETS}))
 for row in address_rows:
  if not row.get('seed_id') and qualifies(row):
   found.append(dict(record_type='wallet',seed_id='',phrase='',metamask_address_0='',wallet_address=row.get('address',''),portfolio_usd=row.get('portfolio_usd','0'),**{asset:row.get(asset,'0') for asset in REPORT_ASSETS}))
 return found

