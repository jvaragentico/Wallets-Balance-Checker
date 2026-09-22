import sys,threading,queue,traceback,json,time
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
sys.path.insert(0,str(Path(__file__).parent))
# #region agent log
def _dbg(hypothesisId,location,message,data=None):
 try:
  p=Path(__file__).parent/'debug-f25f2a.log'
  with p.open('a',encoding='utf-8') as f:f.write(json.dumps({'sessionId':'f25f2a','hypothesisId':hypothesisId,'location':location,'message':message,'data':data or {},'timestamp':int(time.time()*1000)})+'\n')
 except Exception:pass
_app=Path(__file__).resolve().parent
_dbg('A','wallet_audit.py:startup','startup paths',{'file':str(Path(__file__).resolve()),'app':str(_app),'cwd':str(Path.cwd()),'sys_path0':sys.path[0],'py_files':sorted(x.name for x in _app.glob('*.py')),'wallet_core_exists':(_app/'wallet_core.py').exists(),'networks_json_exists':(_app/'networks.json').exists(),'vendor_dirs':[x.name for x in _app.iterdir() if x.is_dir()]})
# #endregion
try:
 from wallet_core import extract,derive,export_extraction,write_csv,Cancelled
 # #region agent log
 _dbg('B','wallet_audit.py:import','wallet_core import ok',{'module':'wallet_core'})
 # #endregion
except Exception as _imp_exc:
 # #region agent log
 _dbg('B','wallet_audit.py:import','wallet_core import failed',{'type':type(_imp_exc).__name__,'msg':str(_imp_exc)})
 # #endregion
 raise
from balance_engine import run,summarize,summarize_seeds,balances_found

class App(tk.Tk):
 def __init__(self):
  super().__init__();self.title('Wallet Audit â€” local phrase and address organizer');self.geometry('900x680');self.stop=threading.Event();self.events=queue.Queue();self.files=[];self.mapping=[];self.phrases=[];self.addresses=[]
  box=ttk.Frame(self,padding=14);box.pack(fill='both',expand=True)
  ttk.Label(box,text='Wallet Audit',font=('',16,'bold')).pack(anchor='w');ttk.Label(box,text='Seed phrases stay on this computer. Only public addresses are sent during a balance check.').pack(anchor='w',pady=(0,8))
  top=ttk.Frame(box);top.pack(fill='x');ttk.Button(top,text='Add TXT / CSV / XLS / XLSX',command=self.add_files).pack(side='left');ttk.Button(top,text='Clear files',command=lambda:self.files.clear()).pack(side='left',padx=6)
  self.file_label=tk.StringVar(value='No files selected');ttk.Label(top,textvariable=self.file_label).pack(side='left',padx=10)
  ttk.Label(box,text='Or paste mixed text, addresses, and phrases:').pack(anchor='w',pady=(10,2));self.text=tk.Text(box,height=10,wrap='word');self.text.pack(fill='both',expand=True)
  form=ttk.Frame(box);form.pack(fill='x',pady=8);self.evm_count=tk.StringVar(value='10');self.private=tk.BooleanVar(value=True)
  ttk.Label(form,text='MetaMask accounts per phrase:').pack(side='left');ttk.Spinbox(form,from_=0,to=1000,textvariable=self.evm_count,width=6).pack(side='left',padx=(3,12))
  ttk.Checkbutton(form,text='Include phrases in private export',variable=self.private).pack(side='left')
  buttons=ttk.Frame(box);buttons.pack(fill='x');self.scan=ttk.Button(buttons,text='1. Extract and derive',command=self.start_extract);self.scan.pack(side='left');self.check=ttk.Button(buttons,text='2. Check balances',command=self.start_balance,state='disabled');self.check.pack(side='left',padx=7);self.export=ttk.Button(buttons,text='3. Export results',command=self.save,state='disabled');self.export.pack(side='left');ttk.Button(buttons,text='Stop',command=self.stop.set).pack(side='right')
  self.status=tk.StringVar(value='Choose files or paste input.');ttk.Label(box,textvariable=self.status).pack(anchor='w',pady=(8,2));self.log=tk.Text(box,height=10,state='disabled');self.log.pack(fill='both',expand=True);self.after(100,self.poll)
 def add_files(self):
  self.files+=list(filedialog.askopenfilenames(filetypes=[('Supported','*.txt *.csv *.tsv *.xls *.xlsx'),('All','*.*')]))
  self.files=list(dict.fromkeys(self.files));self.file_label.set(f'{len(self.files)} file(s) selected')
 def note(self,message):self.events.put(('note',message))
 def start(self,target):
  self.stop.clear();self.scan.configure(state='disabled');self.check.configure(state='disabled');threading.Thread(target=target,daemon=True).start()
 def start_extract(self):
  def task():
   try:
    self.phrases,self.addresses=extract(self.files,self.text.get('1.0','end'),self.stop,self.note);self.mapping=derive(self.phrases,self.addresses,int(self.evm_count.get()),0,False,self.stop,self.note);self.events.put(('done_extract',f'Found {len(self.phrases)} valid phrases, {len(self.addresses)} listed addresses, and derived {len(self.mapping)} address records.'))
   except Exception as exc:self.events.put(('error',self.err(exc)))
  self.start(task)
 def start_balance(self):
  def task():
   try:
    # #region agent log
    _dbg('I','wallet_audit.py:start_balance','balance start',{'map_n':len(self.mapping)})
    # #endregion
    self.balances=run(self.mapping,self.stop,self.note);self.summary=summarize(self.mapping,self.balances);self.seed_summary=summarize_seeds(self.mapping,self.balances);self.found_summary=balances_found(self.seed_summary,self.summary);self.events.put(('done_balance',f'Balance check completed: {len(self.balances)} asset records; {len(self.found_summary)} record(s) meet the 0.001 threshold.'))
    # #region agent log
    _dbg('I','wallet_audit.py:start_balance','balance done',{'bal_n':len(getattr(self,'balances',[])),'sum_n':len(getattr(self,'summary',[]))})
    # #endregion
   except Exception as exc:
    # #region agent log
    _dbg('I','wallet_audit.py:start_balance','balance error',{'type':type(exc).__name__,'msg':str(exc)[:200]})
    # #endregion
    self.events.put(('error',self.err(exc)))
  self.start(task)
 def save(self):
  folder=filedialog.askdirectory(title='Choose an empty or dedicated export folder')
  if not folder:return
  try:
   export_extraction(folder,self.phrases,self.addresses,self.mapping,self.private.get())
   write_csv(Path(folder)/'balances.csv',self.balances,['address','chain','chain_id','asset','asset_type','contract','amount','usd','status','checked_utc','source'])
   address_fields=['seed_id','address','kind','path','portfolio_usd','ETH','WETH','BNB','POL','coverage']
   write_csv(Path(folder)/'address_portfolio.csv',self.summary,address_fields)
   seed_fields=['seed_id','metamask_address_0','evm_addresses_checked','portfolio_usd','ETH','WETH','BNB','POL']
   if self.private.get():
    seed_fields.insert(1,'phrase');write_csv(Path(folder)/'seed_portfolio_PRIVATE.csv',self.seed_summary,seed_fields)
   else:write_csv(Path(folder)/'seed_portfolio.csv',self.seed_summary,seed_fields)
   found_fields=['record_type','seed_id','metamask_address_0','wallet_address','portfolio_usd','ETH','WETH','BNB','POL']
   found_name='balances_found_PRIVATE.csv' if self.private.get() else 'balances_found.csv'
   if self.private.get():found_fields.insert(2,'phrase')
   write_csv(Path(folder)/found_name,self.found_summary,found_fields)
   Path(folder,'README.txt').write_text('Files are organized by purpose. balances_found_PRIVATE.csv contains only seed phrases or listed wallets where at least one checked asset is 0.001 or greater; each seed phrase appears once with totals across its derived addresses. seed_portfolio_PRIVATE.csv has one row per seed phrase with combined totals across all addresses derived for that seed. address_portfolio.csv has one row per address and never repeats phrases. address_mapping.csv connects seed IDs to addresses and paths without exposing phrases. Checked assets only: ETH, WETH, BNB, POL. Empty amount/status is an error, not zero. Coverage is not exhaustive all-chain or all-token coverage. PRIVATE files contain recovery phrases; store them offline.\n',encoding='utf-8')
   # #region agent log
   _dbg('F','wallet_audit.py:save','export complete',{'private':bool(self.private.get()),'files':sorted(p.name for p in Path(folder).iterdir() if p.is_file())})
   # #endregion
   self.status.set('Exported results to '+folder)
  except Exception as exc:messagebox.showerror('Export failed',self.err(exc))
 def err(self,exc):return 'Stopped.' if isinstance(exc,Cancelled) else f'{type(exc).__name__}: {exc}'
 def poll(self):
  try:
   while True:
    kind,msg=self.events.get_nowait();self.status.set(msg)
    if kind=='note':self.log.configure(state='normal');self.log.insert('end',msg+'\n');self.log.see('end');self.log.configure(state='disabled')
    elif kind=='done_extract':self.check.configure(state='normal');self.scan.configure(state='normal')
    elif kind=='done_balance':self.export.configure(state='normal');self.scan.configure(state='normal');self.check.configure(state='normal')
    elif kind=='error':self.scan.configure(state='normal');messagebox.showerror('Task stopped',msg)
  except queue.Empty:pass
  self.after(100,self.poll)
if __name__=='__main__':App().mainloop()

