"""Local phrase extraction and address derivation. Private keys never leave this process."""
import csv,hashlib,hmac,json,re,time,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

class Cancelled(Exception): pass
def check_stop(stop):
 if stop is not None and getattr(stop,'is_set',lambda:False)(): raise Cancelled

# #region agent log
def _dbg(hypothesisId,location,message,data=None):
 try:
  p=Path(__file__).parent/'debug-f25f2a.log'
  with p.open('a',encoding='utf-8') as f:f.write(json.dumps({'sessionId':'f25f2a','hypothesisId':hypothesisId,'location':location,'message':message,'data':data or {},'timestamp':int(time.time()*1000),'runId':'post-fix'})+'\n')
 except Exception:pass
# #endregion

WORDS=Path(__file__).with_name('bip39_english.txt').read_text(encoding='utf-8').split()
WIX={w:i for i,w in enumerate(WORDS)}
P=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
Gx=0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
Gy=0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8
B58='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
B32='qpzry9x8gf2tvdw0s3jn54khce6mua7l'

def _inv(a,n):return pow(a,n-2,n)
def _ptadd(p1,p2):
 if p1 is None:return p2
 if p2 is None:return p1
 x1,y1=p1;x2,y2=p2
 if x1==x2:
  if (y1+y2)%P==0:return None
  m=(3*x1*x1* _inv(2*y1,P))%P
 else:m=((y2-y1)*_inv(x2-x1,P))%P
 x3=(m*m-x1-x2)%P;y3=(m*(x1-x3)-y1)%P;return x3,y3
def _ptmul(k,pt=(Gx,Gy)):
 r=None;p=pt
 while k:
  if k&1:r=_ptadd(r,p)
  p=_ptadd(p,p);k>>=1
 return r
def _pub(priv,comp=True):
 x,y=_ptmul(int.from_bytes(priv,'big'))
 if comp:return bytes([2+(y&1)])+x.to_bytes(32,'big')
 return b'\x04'+x.to_bytes(32,'big')+y.to_bytes(32,'big')

_RC= [1,32898,0x800000000000808a,0x8000000080008000,32907,0x80000001,0x8000000080008081,0x8000000000008009,138,136,0x80008009,0x8000000a,0x8000808b,0x800000000000008b,0x8000000000008089,0x8000000000008003,0x8000000000008002,0x8000000000000080,32778,0x800000008000000a,0x8000000080008081,0x8000000000008080,0x80000001,0x8000000080008008]
def keccak256(data):
 st=[0]*25;rate=136;buf=bytearray(data);buf.append(0x01)
 while len(buf)%rate:buf.append(0)
 buf[-1]|=0x80
 def rol(x,n):return ((x<<n)|(x>>(64-n)))&((1<<64)-1)
 for off in range(0,len(buf),rate):
  block=buf[off:off+rate]
  for i in range(rate//8):st[i]^=int.from_bytes(block[i*8:i*8+8],'little')
  for rnd in range(24):
   c=[st[i]^st[i+5]^st[i+10]^st[i+15]^st[i+20] for i in range(5)]
   d=[c[(i-1)%5]^rol(c[(i+1)%5],1) for i in range(5)]
   st=[st[i]^d[i%5] for i in range(25)]
   t=st[1];rot=0
   x,y=1,0
   for i in range(24):
    x,y=y,(2*x+3*y)%5;rot+=i+1;st[x+5*y],t=rol(t,rot%64),st[x+5*y]
   for y in range(0,25,5):
    row=st[y:y+5];st[y:y+5]=[row[i]^((~row[(i+1)%5])&row[(i+2)%5]) for i in range(5)]
   st[0]^=_RC[rnd]
 return b''.join(st[i].to_bytes(8,'little') for i in range(4))

def _ripemd160(data):
 try:return hashlib.new('ripemd160',data).digest()
 except Exception:
  raise RuntimeError('RIPEMD160 is required for Bitcoin addresses')
def hash160(data):return _ripemd160(hashlib.sha256(data).digest())
def b58encode(data):
 n=int.from_bytes(data,'big');s=''
 while n:n,r=divmod(n,58);s=B58[r]+s
 return B58[0]* (len(data)-len(data.lstrip(b'\x00'))) + (s or B58[0][0:0] or '')
def b58check(payload):
 chk=hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
 n=int.from_bytes(payload+chk,'big');s=''
 while n:n,r=divmod(n,58);s=B58[r]+s
 pad=0
 for b in payload+chk:
  if b==0:pad+=1
  else:break
 return B58[0]*pad+s
def _bech32_polymod(values):
 gen=[0x3b6a57b2,0x26508e6d,0x1ea119fa,0x3d4233dd,0x2e1462b3];chk=1
 for v in values:
  b=chk>>25;chk=((chk&0x1ffffff)<<5)^v
  for i in range(5):
   if (b>>i)&1:chk^=gen[i]
 return chk
def _bech32_hrp_expand(hrp):return [ord(x)>>5 for x in hrp]+[0]+[ord(x)&31 for x in hrp]
def _convertbits(data,frombits,tobits,pad=True):
 acc=0;bits=0;ret=[];maxv=(1<<tobits)-1
 for value in data:
  acc=(acc<<frombits)|value;bits+=frombits
  while bits>=tobits:bits-=tobits;ret.append((acc>>bits)&maxv)
 if pad and bits:ret.append((acc<<(tobits-bits))&maxv)
 return ret
def bech32_encode(hrp,witver,witprog):
 data=[witver]+_convertbits(list(witprog),8,5)
 spec=_bech32_polymod(_bech32_hrp_expand(hrp)+data+[0,0,0,0,0,0])^1
 chk=[(spec>>5*(5-i))&31 for i in range(6)]
 return hrp+'1'+''.join(B32[d] for d in data+chk)

def mnemonic_ok(words):
 if len(words) not in (12,15,18,21,24) or any(w not in WIX for w in words):return False
 concat=0
 for w in words:concat=(concat<<11)|WIX[w]
 ms=len(words)*11;cs=ms//33;ent=concat>>cs;chk=concat&((1<<cs)-1)
 raw=ent.to_bytes((ms-cs)//8,'big')
 return (hashlib.sha256(raw).digest()[0]>>(8-cs))==chk
def seed_from(phrase,passphrase=''):
 return hashlib.pbkdf2_hmac('sha512',phrase.encode(),('mnemonic'+passphrase).encode(),2048)
def ckd(k,c,i):
 data=(b'\x00'+k if i>=2**31 else _pub(k,True))+i.to_bytes(4,'big')
 I=hmac.new(c,data,hashlib.sha512).digest()
 ki=(int.from_bytes(I[:32],'big')+int.from_bytes(k,'big'))%N
 return ki.to_bytes(32,'big'),I[32:]
def derive_path(seed,path):
 I=hmac.new(b'Bitcoin seed',seed,hashlib.sha512).digest();k,c=I[:32],I[32:]
 for part in path.lstrip('m/').split('/'):
  if not part:continue
  hard=part.endswith("'");idx=int(part[:-1] if hard else part)+(2**31 if hard else 0)
  k,c=ckd(k,c,idx)
 return k
def eth_addr(priv):
 pub=_pub(priv,False)[1:];raw=keccak256(pub)[-20:]
 hexaddr=raw.hex();chk=keccak256(hexaddr.encode()).hex()
 out='0x'+''.join(c.upper() if int(chk[i],16)>=8 else c for i,c in enumerate(hexaddr))
 return out
def btc_p2pkh(priv):return b58check(b'\x00'+hash160(_pub(priv,True)))
def btc_p2sh_p2wpkh(priv):
 h=hash160(_pub(priv,True));redeem=bytes([0x00,0x14])+h;return b58check(b'\x05'+hash160(redeem))
def btc_p2wpkh(priv):return bech32_encode('bc',0,hash160(_pub(priv,True)))

def _read_xlsx(path):
 ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
 with zipfile.ZipFile(path) as z:
  shared=[]
  if 'xl/sharedStrings.xml' in z.namelist():
   root=ET.fromstring(z.read('xl/sharedStrings.xml'))
   for si in root.findall(f'{ns}si'):shared.append(''.join(t.text or '' for t in si.iter(f'{ns}t')))
  texts=[]
  for name in z.namelist():
   if not name.startswith('xl/worksheets/') or not name.endswith('.xml'):continue
   root=ET.fromstring(z.read(name))
   for c in root.iter(f'{ns}c'):
    v=c.find(f'{ns}v')
    if v is None or v.text is None:continue
    if c.attrib.get('t')=='s':
     try:texts.append(shared[int(v.text)])
     except Exception:texts.append(v.text)
    else:texts.append(v.text)
  return '\n'.join(texts)
def _file_text(path):
 p=Path(path);suf=p.suffix.lower()
 if suf=='.xlsx':
  try:return _read_xlsx(p)
  except Exception:return p.read_text(encoding='utf-8',errors='ignore')
 raw=p.read_bytes()
 if suf=='.xls':
  return ' '.join(re.findall(rb'[A-Za-z]{3,}',raw)).decode('ascii','ignore')
 try:return raw.decode('utf-8')
 except Exception:return raw.decode('latin-1','ignore')

_EVM=re.compile(r'0x[0-9a-fA-F]{40}(?![0-9a-fA-F])')
_EVM_LOOSE=re.compile(r'0x[0-9a-fA-F]{40}')
_BTC=re.compile(r'\b(?:[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[qpzry9x8gf2tvdw0s3jn54khce6mua7l]{8,87})\b')
def extract(files,text,stop=None,log=lambda s:None):
 check_stop(stop);chunks=[]
 for f in files or []:
  check_stop(stop);log('Reading '+str(f));chunks.append(_file_text(f))
 chunks.append(text or '');blob='\n'.join(chunks)
 tokens=re.findall(r"[A-Za-z]+",blob.lower());phrases=[];seen=set();used=[False]*len(tokens)
 for n in (24,21,18,15,12):
  for i in range(0,max(0,len(tokens)-n+1)):
   if any(used[i:i+n]):continue
   cand=tokens[i:i+n]
   if mnemonic_ok(cand):
    phrase=' '.join(cand)
    if phrase not in seen:seen.add(phrase);phrases.append(phrase)
    for j in range(i,i+n):used[j]=True
 addresses=[];aseen=set()
 for m in _EVM.findall(blob):
  a=m.lower()
  if a not in aseen:aseen.add(a);addresses.append(m)
 log(f'Extracted {len(phrases)} phrases and {len(addresses)} listed addresses')
 # #region agent log
 _dbg('G','wallet_core.py:extract','extract complete',{'phrases':len(phrases),'phrase_words':[len(x.split()) for x in phrases],'addresses':len(addresses),'evm40_strict':len(_EVM.findall(blob)),'evm40_loose':len(_EVM_LOOSE.findall(blob)),'evm64':len(re.findall(r'0x[0-9a-fA-F]{64}',blob)),'files':len(files or [])})
 # #endregion
 return phrases,addresses

def derive(phrases,addresses,evm_count,btc_count=0,_extra=False,stop=None,log=lambda s:None):
 rows=[];evm_count=max(0,int(evm_count))
 for n,phrase in enumerate(phrases or [],1):
  check_stop(stop);log(f'Deriving seed {n}/{len(phrases)}');seed=seed_from(phrase);sid=f'seed_{n}'
  for i in range(evm_count):
   path=f"m/44'/60'/0'/0/{i}";priv=derive_path(seed,path)
   rows.append(dict(seed_id=sid,phrase=phrase,address=eth_addr(priv),kind='EVM',path=path))
 for a in addresses or []:
  check_stop(stop)
  if not (a.lower().startswith('0x') and len(a)==42):continue
  hexaddr=a[2:].lower();chk=keccak256(hexaddr.encode()).hex()
  addr='0x'+''.join(c.upper() if int(chk[i],16)>=8 else c for i,c in enumerate(hexaddr))
  rows.append(dict(seed_id='',phrase='',address=addr,kind='EVM',path='listed'))
 # #region agent log
 _dbg('A','wallet_core.py:derive','derive complete',{'rows':len(rows),'evm_count':evm_count,'btc_count':btc_count,'phrase_n':len(phrases or [])})
 # #endregion
 return rows

def write_csv(path,rows,fields):
 path=Path(path)
 with path.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader()
  for r in rows:w.writerow({k:r.get(k,'') for k in fields})

def export_extraction(folder,phrases,addresses,mapping,private):
 folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
 uniq=[];seen=set()
 for r in mapping or []:
  a=r.get('address') or '';k=a.lower()
  if a and k not in seen:seen.add(k);uniq.append(a)
 (folder/'public_addresses.txt').write_text('\n'.join(uniq)+('\n' if uniq else ''),encoding='utf-8')
 # Keep phrase text in a single private file. The public mapping is one row per address.
 fields=['seed_id','address','kind','path']
 write_csv(folder/'address_mapping.csv',mapping or [],fields)
 if private:
  phrase_rows=[{'seed_id':f'seed_{i}','phrase':p} for i,p in enumerate(phrases or [],1)]
  write_csv(folder/'seed_phrases_PRIVATE.csv',phrase_rows,['seed_id','phrase'])
  (folder/'seed_phrases_PRIVATE.txt').write_text('\n'.join(phrases or [])+('\n' if phrases else ''),encoding='utf-8')
 # #region agent log
 _dbg('F','wallet_core.py:export','export files written',{'folder':str(folder),'private':bool(private),'public_n':len(uniq),'phrase_n':len(phrases or []),'map_n':len(mapping or [])})
 # #endregion

# #region agent log
_dbg('A','wallet_core.py:import','wallet_core module loaded',{'words':len(WORDS),'has_extract':True})
# #endregion

