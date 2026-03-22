import { useState, useEffect, useRef, useCallback } from "react";

// ═══════════════════════════════════════════════════
// GBM DATA GENERATOR (runs in browser)
// ═══════════════════════════════════════════════════
function generateData(n) {
  const BASE = 150, DV = 0.015, DT = 1/390;
  const EXCHS = [
    { name:'Alpha', noise:0.00025, dRate:0.006, dMag:0.004 },
    { name:'Beta',  noise:0.00030, dRate:0.008, dMag:0.005 },
    { name:'Gamma', noise:0.00020, dRate:0.005, dMag:0.003 },
  ];
  const rn = () => { let u=0,v=0; while(!u) u=Math.random(); while(!v) v=Math.random(); return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v); };
  const ri = (a,b) => Math.floor(Math.random()*(b-a))+a;

  const ret = Array.from({length:n}, ()=> rn()*DV*Math.sqrt(DT));
  const tp = new Float64Array(n);
  tp[0] = BASE;
  for(let i=1;i<n;i++) tp[i] = tp[i-1]*Math.exp(ret[i]);

  const data = {Alpha:new Float64Array(n), Beta:new Float64Array(n), Gamma:new Float64Array(n)};
  for(const ex of EXCHS) {
    const arr = data[ex.name];
    const disloc = new Float64Array(n);
    const nd = Math.floor(n*ex.dRate);
    const idxs = new Set();
    while(idxs.size<nd) idxs.add(ri(10,n-20));
    for(const ix of idxs) {
      const mg = rn()*ex.dMag;
      const dl = ri(4,18);
      const mr = 0.08+Math.random()*0.12;
      for(let j=0;j<dl&&ix+j<n;j++) disloc[ix+j] += mg*Math.exp(-j*mr)*tp[ix];
    }
    for(let i=0;i<n;i++) arr[i] = tp[i] + rn()*ex.noise*tp[i] + disloc[i];
  }
  return data;
}

// ═══════════════════════════════════════════════════
// GRID SEARCH OPTIMIZER
// ═══════════════════════════════════════════════════
const FEES = {Alpha:2,Beta:3,Gamma:1.5}, SLIP=1;

function runBacktest(data, n, start, sT, pT, zT, vA) {
  const sBuf=[], vBuf=[], zL=120, vL=30;
  let pc=0,inT=false,eTick=0,eBP=0,eSP=0,eSpread=0,tBuy='',tSell='',lastTP=0;
  const trades=[];
  const A=data.Alpha, B=data.Beta, G=data.Gamma;
  for(let t=start;t<start+n;t++) {
    const a=A[t],b=B[t],g=G[t];
    const mx=Math.max(a,b,g),mn=Math.min(a,b,g),mid=(mx+mn)/2;
    const s=(mx-mn)/mid*10000;
    sBuf.push(s); if(sBuf.length>zL) sBuf.shift();
    const tp2=(a+b+g)/3;
    if(lastTP>0) {vBuf.push(Math.log(tp2/lastTP)*10000); if(vBuf.length>vL) vBuf.shift();}
    lastTP=tp2;
    const ps={Alpha:a,Beta:b,Gamma:g};
    const buyE=a<=b&&a<=g?'Alpha':b<=g?'Beta':'Gamma';
    const sellE=a>=b&&a>=g?'Alpha':b>=g?'Beta':'Gamma';
    if(inT) {
      const cbp=ps[tBuy],csp=ps[tSell],cmid=(cbp+csp)/2;
      const cs=cmid>0?(csp-cbp)/cmid*10000:0;
      const hold=t-eTick; let ex=false,reason='';
      if(sBuf.length>=30){const mu=sBuf.reduce((a,b)=>a+b,0)/sBuf.length;const st=Math.sqrt(sBuf.map(x=>(x-mu)**2).reduce((a,b)=>a+b,0)/sBuf.length);if(st>0.01&&Math.abs((s-mu)/st)<0.5){ex=true;reason='z_revert';}}
      if(!ex&&cs>eSpread+15){ex=true;reason='stop_loss';}
      if(!ex&&hold>=20){ex=true;reason='max_hold';}
      if(ex){const qty=100000/eBP;const gr=qty*(cbp-eBP)+qty*(eSP-csp);const cost=100000*(FEES[tBuy]+FEES[tSell])*2/10000+100000*SLIP*4/10000;trades.push({net:gr-cost,reason});inT=false;pc=0;}
      continue;
    }
    if(s<=sT){pc=0;continue;}
    if(s-(FEES[buyE]+FEES[sellE]+2*SLIP)<=0){pc=0;continue;}
    pc++;if(pc<pT)continue;
    if(sBuf.length<30)continue;
    const mu=sBuf.reduce((a,b)=>a+b,0)/sBuf.length;const st=Math.sqrt(sBuf.map(x=>(x-mu)**2).reduce((a,b)=>a+b,0)/sBuf.length);
    if(st<0.01)continue;const z=(s-mu)/st;if(Math.abs(z)<=zT)continue;
    if(vBuf.length<vL)continue;const vm=vBuf.reduce((a,b)=>a+b,0)/vBuf.length;const vs=Math.sqrt(vBuf.map(x=>(x-vm)**2).reduce((a,b)=>a+b,0)/vBuf.length);
    if(vs<0.1||s/vs<=vA)continue;
    inT=true;eTick=t;tBuy=buyE;tSell=sellE;eBP=ps[buyE];eSP=ps[sellE];eSpread=s;pc=0;
  }
  if(!trades.length) return{sharpe:-999,pnl:0,n:0,wr:0,pf:0};
  const pnls=trades.map(x=>x.net),w=pnls.filter(x=>x>0),l=pnls.filter(x=>x<=0);
  const tot=pnls.reduce((a,b)=>a+b,0),mu2=tot/pnls.length;
  const st2=Math.sqrt(pnls.map(x=>(x-mu2)**2).reduce((a,b)=>a+b,0)/pnls.length);
  const sh=st2>0?(mu2/st2)*Math.sqrt(252):0;
  const gp=w.reduce((a,b)=>a+b,0),gl=Math.abs(l.reduce((a,b)=>a+b,0))||1;
  return{sharpe:Math.round(sh*1000)/1000,pnl:Math.round(tot*100)/100,n:pnls.length,wr:Math.round(w.length/pnls.length*1000)/10,pf:Math.round(gp/gl*100)/100};
}

function gridSearch(data, n, start) {
  const sTs=[3,5,7,10],pTs=[2,3,4,5],zTs=[1.5,2,2.5,3],vAs=[1,1.5,2,2.5];
  let best=null, bestSh=-999, all=[];
  for(const sT of sTs) for(const pT of pTs) for(const zT of zTs) for(const vA of vAs) {
    const r=runBacktest(data,n,start,sT,pT,zT,vA);
    all.push({sT,pT,zT,vA,...r});
    if(r.n>=10&&r.sharpe>bestSh){bestSh=r.sharpe;best={sT,pT,zT,vA,...r};}
  }
  if(!best) best=all.sort((a,b)=>b.sharpe-a.sharpe)[0];
  return {best, all:all.sort((a,b)=>b.sharpe-a.sharpe).slice(0,10)};
}

// ═══════════════════════════════════════════════════
// LIVE TRADING ENGINE
// ═══════════════════════════════════════════════════
class LiveEngine {
  constructor(p){this.p={...p};this.cap=1000000;this.trades=[];this.sBuf=[];this.vBuf=[];this.pc=0;this.inT=false;this.eTick=0;this.eBP=0;this.eSP=0;this.eSpread=0;this.tBuy='';this.tSell='';this.tc=0;this.pk=1000000;this.lastTP=0;}
  tick(a,b,g){
    this.tc++;const mx=Math.max(a,b,g),mn=Math.min(a,b,g),mid=(mx+mn)/2;
    const s=(mx-mn)/mid*10000;this.sBuf.push(s);if(this.sBuf.length>120)this.sBuf.shift();
    const tp=(a+b+g)/3;if(this.lastTP>0){this.vBuf.push(Math.log(tp/this.lastTP)*10000);if(this.vBuf.length>30)this.vBuf.shift();}this.lastTP=tp;
    const ps={Alpha:a,Beta:b,Gamma:g};
    const buyE=a<=b&&a<=g?'Alpha':b<=g?'Beta':'Gamma';
    const sellE=a>=b&&a>=g?'Alpha':b>=g?'Beta':'Gamma';
    let sig=null;
    if(this.inT){
      const cbp=ps[this.tBuy],csp=ps[this.tSell],cmid=(cbp+csp)/2;
      const cs=cmid>0?(csp-cbp)/cmid*10000:0;const hold=this.tc-this.eTick;let ex=false,reason='';
      if(this.sBuf.length>=30){const mu=this.sBuf.reduce((a,b)=>a+b,0)/this.sBuf.length;const st=Math.sqrt(this.sBuf.map(x=>(x-mu)**2).reduce((a,b)=>a+b,0)/this.sBuf.length);if(st>0.01&&Math.abs((s-mu)/st)<0.5){ex=true;reason='z_revert';}}
      if(!ex&&cs>this.eSpread+15){ex=true;reason='stop_loss';}
      if(!ex&&hold>=20){ex=true;reason='max_hold';}
      if(ex){const qty=100000/this.eBP;const gr=qty*(cbp-this.eBP)+qty*(this.eSP-csp);const cost=100000*(FEES[this.tBuy]+FEES[this.tSell])*2/10000+100000*SLIP*4/10000;const net=gr-cost;this.cap+=net;this.pk=Math.max(this.pk,this.cap);
        const trade={entry:this.eTick,exit:this.tc,hold,be:this.tBuy,se:this.tSell,es:+this.eSpread.toFixed(1),net:Math.round(net*100)/100,reason,cap:Math.round(this.cap*100)/100};this.trades.push(trade);sig={type:'exit',trade};this.inT=false;this.pc=0;}
      return{s:s.toFixed(1),sig,f:{f1:0,f2:0,f3:0,f4:0,f5:0,inT:1},z:'—',va:'—'};}
    const f1=s>this.p.sT;if(!f1){this.pc=0;return{s:s.toFixed(1),sig,f:{f1:0,f2:0,f3:0,f4:0,f5:0},z:'—',va:'—'};}
    const cost=FEES[buyE]+FEES[sellE]+2*SLIP;const f2=(s-cost)>0;if(!f2){this.pc=0;return{s:s.toFixed(1),sig,f:{f1:1,f2:0,f3:0,f4:0,f5:0},z:'—',va:'—'};}
    this.pc++;const f3=this.pc>=this.p.pT;if(!f3)return{s:s.toFixed(1),sig,f:{f1:1,f2:1,f3:0,f4:0,f5:0},z:'—',va:'—'};
    let f4=0,z=0;if(this.sBuf.length>=30){const mu=this.sBuf.reduce((a,b)=>a+b,0)/this.sBuf.length;const st=Math.sqrt(this.sBuf.map(x=>(x-mu)**2).reduce((a,b)=>a+b,0)/this.sBuf.length);if(st>0.01){z=(s-mu)/st;f4=Math.abs(z)>this.p.zT?1:0;}}
    if(!f4)return{s:s.toFixed(1),sig,f:{f1:1,f2:1,f3:1,f4:0,f5:0},z:z.toFixed(2),va:'—'};
    let f5=0,va=0;if(this.vBuf.length>=30){const vm=this.vBuf.reduce((a,b)=>a+b,0)/this.vBuf.length;const vs=Math.sqrt(this.vBuf.map(x=>(x-vm)**2).reduce((a,b)=>a+b,0)/this.vBuf.length);if(vs>0.1){va=s/vs;f5=va>this.p.vA?1:0;}}
    if(!f5)return{s:s.toFixed(1),sig,f:{f1:1,f2:1,f3:1,f4:1,f5:0},z:z.toFixed(2),va:va.toFixed(2)};
    this.inT=true;this.eTick=this.tc;this.tBuy=buyE;this.tSell=sellE;this.eBP=ps[buyE];this.eSP=ps[sellE];this.eSpread=s;this.pc=0;
    sig={type:'entry',buy:buyE,sell:sellE,s:s.toFixed(1),z:z.toFixed(2)};
    return{s:s.toFixed(1),sig,f:{f1:1,f2:1,f3:1,f4:1,f5:1},z:z.toFixed(2),va:va.toFixed(2)};}
  metrics(){const t=this.trades;if(!t.length)return{pnl:0,sh:0,pf:0,wr:0,n:0,dd:0,ap:0,sl:0,mh:0,zr:0};
    const ps=t.map(x=>x.net),w=ps.filter(x=>x>0),l=ps.filter(x=>x<=0),tot=ps.reduce((a,b)=>a+b,0),mu=tot/ps.length;
    const st=ps.length>1?Math.sqrt(ps.map(x=>(x-mu)**2).reduce((a,b)=>a+b,0)/ps.length):1;
    const sh=st>0?(mu/st)*Math.sqrt(252):0;const gp=w.reduce((a,b)=>a+b,0),gl=Math.abs(l.reduce((a,b)=>a+b,0))||1;
    return{pnl:Math.round(tot*100)/100,sh:Math.round(sh*100)/100,pf:Math.round(gp/gl*100)/100,wr:w.length?Math.round(w.length/ps.length*10000)/100:0,n:ps.length,dd:Math.round((this.pk-this.cap)/this.pk*10000)/100,ap:Math.round(mu*100)/100,sl:t.filter(x=>x.reason==='stop_loss').length,mh:t.filter(x=>x.reason==='max_hold').length,zr:t.filter(x=>x.reason==='z_revert').length};}
}

// ═══════════════════════════════════════════════════
// REACT DASHBOARD
// ═══════════════════════════════════════════════════
const TOTAL=100000, TRAIN=50000, LIVE=50000;

export default function App(){
  const[phase,setPhase]=useState('init'); // init | optimizing | ready | trading | done
  const[progress,setProgress]=useState(0);
  const[optResult,setOptResult]=useState(null);
  const[topResults,setTopResults]=useState([]);
  const[params,setParams]=useState(null);
  const[tick,setTick]=useState(0);
  const[prices,setPrices]=useState({a:0,b:0,g:0});
  const[spread,setSpread]=useState('0');
  const[filters,setFilters]=useState({});
  const[cap,setCap]=useState(1000000);
  const[m,setM]=useState({pnl:0,sh:0,pf:0,wr:0,n:0,dd:0,ap:0,sl:0,mh:0,zr:0});
  const[trades,setTrades]=useState([]);
  const[sig,setSig]=useState(null);
  const[zs,setZs]=useState('—');
  const[va,setVa]=useState('—');
  const[speed,setSpeed]=useState(30);
  const[reopt,setReopt]=useState(0);
  const[paramLog,setParamLog]=useState([]);
  const dataRef=useRef(null);
  const engineRef=useRef(null);
  const intervalRef=useRef(null);
  const tickRef=useRef(0);

  // Phase 1: Generate + Optimize
  const generate=useCallback(()=>{
    setPhase('optimizing');setProgress(0);setTrades([]);setSig(null);setCap(1000000);setTick(0);setReopt(0);setParamLog([]);
    setM({pnl:0,sh:0,pf:0,wr:0,n:0,dd:0,ap:0,sl:0,mh:0,zr:0});
    setTimeout(()=>{
      setProgress(10);
      const data=generateData(TOTAL);
      dataRef.current=data;
      setProgress(30);
      setTimeout(()=>{
        const{best,all}=gridSearch(data,TRAIN,0);
        setOptResult(best);setTopResults(all);
        setParams({sT:best.sT,pT:best.pT,zT:best.zT,vA:best.vA,zL:120,vL:30,sL:15,mH:20,zE:0.5});
        setProgress(100);
        setPhase('ready');
      },100);
    },100);
  },[]);

  // Auto-generate on mount
  useEffect(()=>{generate();},[generate]);

  // Phase 2: Live trading
  const startTrading=useCallback(()=>{
    const p=params;
    engineRef.current=new LiveEngine(p);
    tickRef.current=0;
    setPhase('trading');
  },[params]);

  useEffect(()=>{
    if(phase!=='trading')return;
    intervalRef.current=setInterval(()=>{
      const t=tickRef.current;
      if(t>=LIVE){clearInterval(intervalRef.current);setPhase('done');return;}
      const e=engineRef.current,d=dataRef.current;
      const idx=TRAIN+t;
      const a=d.Alpha[idx],b=d.Beta[idx],g=d.Gamma[idx];
      const r=e.tick(a,b,g);

      // Adaptive re-optimization every 500 live ticks
      if(t>0&&t%500===0){
        const rc=e.trades.slice(-20);
        if(rc.length>=8){
          const rwr=rc.filter(x=>x.net>0).length/rc.length;
          const old={zT:e.p.zT,vA:e.p.vA,pT:e.p.pT};
          const np={...e.p};
          let action='none';
          if(rwr<0.55){np.zT=Math.min(+(np.zT+0.15).toFixed(2),3.5);np.vA=Math.min(+(np.vA+0.15).toFixed(2),3);np.pT=Math.min(np.pT+1,6);action='tighten';}
          else if(rwr>0.85){np.zT=Math.max(+(np.zT-0.1).toFixed(2),1.5);np.vA=Math.max(+(np.vA-0.1).toFixed(2),1);np.pT=Math.max(np.pT-1,2);action='loosen';}
          if(action!=='none'){
            const changes=[];
            if(old.zT!==np.zT) changes.push({param:'Z-thresh',from:old.zT,to:np.zT});
            if(old.vA!==np.vA) changes.push({param:'Vol-adj',from:old.vA,to:np.vA});
            if(old.pT!==np.pT) changes.push({param:'Persist',from:old.pT,to:np.pT});
            if(changes.length>0) setParamLog(prev=>[...prev,{tick:TRAIN+t,action,wr:Math.round(rwr*1000)/10,changes}]);
          }
          e.p=np;setParams(prev=>({...prev,sT:np.sT,pT:np.pT,zT:np.zT,vA:np.vA}));setReopt(c=>c+1);
        }
      }
      setPrices({a:+a.toFixed(2),b:+b.toFixed(2),g:+g.toFixed(2)});
      setSpread(r.s);setFilters(r.f||{});setCap(Math.round(e.cap*100)/100);
      setM(e.metrics());setTrades([...e.trades]);if(r.sig)setSig(r.sig);
      setZs(r.z||'—');setVa(r.va||'—');tickRef.current=t+1;setTick(t+1);
    },speed);
    return()=>clearInterval(intervalRef.current);
  },[phase,speed]);

  const F=(v,d=2)=>typeof v==='number'?v.toFixed(d):String(v);
  const pc=m.pnl>=0?'#22c55e':'#ef4444';
  const Pill=({on,l})=><span style={{display:'inline-block',padding:'2px 8px',borderRadius:4,fontSize:11,fontWeight:600,background:on?'#22c55e22':'#ef444422',color:on?'#22c55e':'#ef4444',border:`1px solid ${on?'#22c55e44':'#ef444444'}`}}>{l}</span>;
  const St=({l,v,c})=><div style={{background:'#111',borderRadius:8,padding:'10px 14px',minWidth:80}}><div style={{fontSize:10,color:'#888',textTransform:'uppercase',letterSpacing:1}}>{l}</div><div style={{fontSize:18,fontWeight:700,color:c||'#e2e8f0',marginTop:2}}>{v}</div></div>;

  // ── OPTIMIZING PHASE ──
  if(phase==='init'||phase==='optimizing'){
    return(<div style={{fontFamily:'ui-monospace,SFMono-Regular,Menlo,monospace',background:'#0a0a0a',color:'#e2e8f0',padding:32,minHeight:'100vh',display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center'}}>
      <h1 style={{fontSize:24,fontWeight:700,marginBottom:8}}>arb engine <span style={{color:'#22c55e'}}>v4</span></h1>
      <p style={{color:'#64748b',fontSize:13,marginBottom:24}}>Generating {TOTAL.toLocaleString()} ticks & optimizing on first {TRAIN.toLocaleString()}...</p>
      <div style={{width:300,height:8,background:'#1e1e1e',borderRadius:4,overflow:'hidden'}}>
        <div style={{width:`${progress}%`,height:'100%',background:'#22c55e',transition:'width 0.3s',borderRadius:4}}/></div>
      <p style={{color:'#64748b',fontSize:12,marginTop:12}}>{progress<30?'Generating GBM data...':progress<100?'Running grid search (256 combinations)...':'Done!'}</p>
    </div>);
  }

  // ── READY / TRADING / DONE ──
  return(<div style={{fontFamily:'ui-monospace,SFMono-Regular,Menlo,monospace',background:'#0a0a0a',color:'#e2e8f0',padding:16,minHeight:'100vh',fontSize:13}}>
    {/* Header */}
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:16}}>
      <div><h1 style={{margin:0,fontSize:20,fontWeight:700}}>arb engine <span style={{color:'#22c55e'}}>v4</span></h1>
        <span style={{fontSize:11,color:'#64748b'}}>{TOTAL.toLocaleString()} ticks · {TRAIN.toLocaleString()} train · {LIVE.toLocaleString()} live · random seed</span></div>
      <div style={{display:'flex',gap:8,alignItems:'center'}}>
        {phase==='trading'&&<select value={speed} onChange={e=>setSpeed(+e.target.value)} style={{background:'#1e1e1e',color:'#e2e8f0',border:'1px solid #333',borderRadius:4,padding:'4px 8px',fontSize:12}}>
          <option value={100}>1x</option><option value={50}>2x</option><option value={30}>3x</option><option value={10}>10x</option><option value={3}>30x</option></select>}
        {phase==='ready'&&<button onClick={startTrading} style={{background:'#22c55e',color:'#000',border:'none',borderRadius:6,padding:'8px 20px',fontWeight:700,cursor:'pointer'}}>start trading</button>}
        {(phase==='trading'||phase==='done')&&<span style={{background:phase==='done'?'#f59e0b22':'#22c55e22',color:phase==='done'?'#f59e0b':'#22c55e',padding:'6px 12px',borderRadius:6,fontSize:12,fontWeight:600}}>{phase==='done'?'COMPLETE':'LIVE'} · {tick.toLocaleString()}/{LIVE.toLocaleString()}</span>}
        <button onClick={generate} style={{background:'#1e1e1e',color:'#94a3b8',border:'1px solid #333',borderRadius:6,padding:'8px 14px',fontSize:12,cursor:'pointer'}}>new data</button>
      </div></div>

    {/* Metrics */}
    <div style={{display:'flex',gap:8,flexWrap:'wrap',marginBottom:12}}>
      <St l="Capital" v={`$${cap.toLocaleString()}`}/><St l="P&L" v={`$${F(m.pnl)}`} c={pc}/>
      <St l="Sharpe" v={F(m.sh)} c={m.sh>0?'#22c55e':'#ef4444'}/><St l="PF" v={F(m.pf)} c={m.pf>1?'#22c55e':'#ef4444'}/>
      <St l="Win%" v={`${F(m.wr)}%`} c={m.wr>60?'#22c55e':m.wr>40?'#f59e0b':'#ef4444'}/><St l="Trades" v={m.n}/>
      <St l="Stops" v={m.sl} c='#ef4444'/><St l="MaxDD" v={`${F(m.dd,3)}%`} c='#f59e0b'/>
    </div>

    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,marginBottom:12}}>
      {/* Prices */}
      <div style={{background:'#111',borderRadius:8,padding:14}}>
        <div style={{fontSize:11,color:'#64748b',marginBottom:8,fontWeight:600}}>LIVE PRICES</div>
        <div style={{display:'flex',gap:16}}>
          {[['Alpha',prices.a,'#3b82f6'],['Beta',prices.b,'#ef4444'],['Gamma',prices.g,'#22c55e']].map(([n,p,c])=>
            <div key={n}><span style={{color:'#64748b',fontSize:11}}>{n}</span><div style={{fontSize:20,fontWeight:700,color:c}}>${F(p,2)}</div></div>)}
          <div><span style={{color:'#64748b',fontSize:11}}>Spread</span><div style={{fontSize:20,fontWeight:700,color:'#f59e0b'}}>{spread} bps</div></div>
        </div></div>
      {/* Filters */}
      <div style={{background:'#111',borderRadius:8,padding:14}}>
        <div style={{fontSize:11,color:'#64748b',marginBottom:8,fontWeight:600}}>FILTERS</div>
        <div style={{display:'flex',gap:6,flexWrap:'wrap'}}>
          <Pill on={filters.f1} l="F1 Spread"/><Pill on={filters.f2} l="F2 Cost"/><Pill on={filters.f3} l="F3 Persist"/><Pill on={filters.f4} l="F4 Z-score"/><Pill on={filters.f5} l="F5 Vol-adj"/>
          {filters.inT?<span style={{background:'#f59e0b22',color:'#f59e0b',padding:'2px 8px',borderRadius:4,fontSize:11,fontWeight:600}}>IN TRADE</span>:null}</div>
        <div style={{display:'flex',gap:16,marginTop:8,fontSize:11,color:'#94a3b8'}}><span>z: <b style={{color:'#e2e8f0'}}>{zs}</b></span><span>vol-adj: <b style={{color:'#e2e8f0'}}>{va}</b></span></div>
      </div></div>

    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,marginBottom:12}}>
      {/* Parameters */}
      <div style={{background:'#111',borderRadius:8,padding:14}}>
        <div style={{display:'flex',justifyContent:'space-between',marginBottom:8}}>
          <span style={{fontSize:11,color:'#64748b',fontWeight:600}}>PARAMETERS {phase==='ready'?'(from 50K optimization)':''}</span>
          {reopt>0&&<span style={{fontSize:10,color:'#f59e0b'}}>adapted {reopt}x</span>}</div>
        {params&&<div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:4,fontSize:12}}>
          {[['Spread',params.sT+' bps'],['Persist',params.pT],['Z-thresh',F(params.zT,2)],['Vol-adj',F(params.vA,2)],['StopLoss','15 bps'],['MaxHold','20 ticks'],['Z-look','120'],['Z-exit','0.5']].map(([k,v])=>
            <div key={k} style={{display:'flex',justifyContent:'space-between',padding:'2px 0',borderBottom:'1px solid #1a1a1a'}}>
              <span style={{color:'#64748b'}}>{k}</span><span style={{fontWeight:600}}>{v}</span></div>)}</div>}
        {optResult&&phase==='ready'&&<div style={{marginTop:10,padding:8,background:'#0a0a0a',borderRadius:6,fontSize:11}}>
          <div style={{color:'#64748b',marginBottom:4}}>Training result (50K ticks):</div>
          <div style={{color:'#94a3b8'}}>Sharpe: <b style={{color:'#22c55e'}}>{optResult.sharpe}</b> · Trades: <b>{optResult.n}</b> · WR: <b>{optResult.wr}%</b> · PnL: <b style={{color:'#22c55e'}}>${optResult.pnl.toLocaleString()}</b></div>
        </div>}</div>
      {/* Signal */}
      <div style={{background:'#111',borderRadius:8,padding:14}}>
        <div style={{fontSize:11,color:'#64748b',marginBottom:8,fontWeight:600}}>LAST SIGNAL</div>
        {sig?sig.type==='entry'?<div><div style={{color:'#22c55e',fontSize:16,fontWeight:700}}>▲ ENTRY</div>
          <div style={{fontSize:12,color:'#94a3b8',marginTop:4}}>Buy <b style={{color:'#e2e8f0'}}>{sig.buy}</b> → Sell <b style={{color:'#e2e8f0'}}>{sig.sell}</b></div>
          <div style={{fontSize:12,color:'#94a3b8'}}>Spread: {sig.s} bps · z: {sig.z}</div></div>
          :<div><div style={{color:sig.trade.net>0?'#22c55e':'#ef4444',fontSize:16,fontWeight:700}}>▼ EXIT — {sig.trade.reason}</div>
          <div style={{fontSize:12,color:'#94a3b8',marginTop:4}}>{sig.trade.be}→{sig.trade.se} · {sig.trade.hold} ticks</div>
          <div style={{fontSize:14,fontWeight:700,color:sig.trade.net>0?'#22c55e':'#ef4444',marginTop:2}}>{sig.trade.net>0?'+':''}${sig.trade.net.toFixed(2)}</div></div>
          :<div style={{color:'#64748b',fontSize:12}}>{phase==='ready'?'Click Start Trading':'Waiting for signal...'}</div>}
        {phase==='ready'&&<div style={{marginTop:12,padding:8,background:'#0a0a0a',borderRadius:6,fontSize:11}}>
          <div style={{color:'#64748b',marginBottom:4}}>Exit breakdown:</div>
          <div style={{display:'flex',gap:12,fontSize:11}}>
            <span style={{color:'#22c55e'}}>z-revert: {m.zr}</span>
            <span style={{color:'#ef4444'}}>stop-loss: {m.sl}</span>
            <span style={{color:'#f59e0b'}}>max-hold: {m.mh}</span></div></div>}
      </div></div>

    {/* Exit Breakdown (during trading) */}
    {phase!=='ready'&&<div style={{background:'#111',borderRadius:8,padding:'10px 14px',marginBottom:12,display:'flex',justifyContent:'space-between',alignItems:'center'}}>
      <span style={{fontSize:11,color:'#64748b',fontWeight:600}}>EXIT BREAKDOWN</span>
      <div style={{display:'flex',gap:16,fontSize:12}}>
        <span style={{color:'#22c55e'}}>z-revert: <b>{m.zr}</b></span>
        <span style={{color:'#ef4444'}}>stop-loss: <b>{m.sl}</b></span>
        <span style={{color:'#f59e0b'}}>max-hold: <b>{m.mh}</b></span></div></div>}

    {/* Parameter Change Log */}
    {paramLog.length>0&&<div style={{background:'#111',borderRadius:8,padding:14,marginBottom:12}}>
      <div style={{fontSize:11,color:'#64748b',marginBottom:8,fontWeight:600}}>PARAMETER ADAPTATION LOG ({paramLog.length} changes)</div>
      <div style={{maxHeight:180,overflowY:'auto'}}>
        <table style={{width:'100%',fontSize:11,borderCollapse:'collapse'}}>
          <thead><tr style={{color:'#64748b',borderBottom:'1px solid #222'}}>
            {['#','Tick','Action','Win Rate','Parameter','Before','After','Change'].map(h=><th key={h} style={{padding:'4px 6px',textAlign:'left',fontWeight:600}}>{h}</th>)}
          </tr></thead>
          <tbody>{[...paramLog].reverse().map((log,i)=>
            log.changes.map((ch,j)=><tr key={`${i}-${j}`} style={{borderBottom:'1px solid #1a1a1a'}}>
              {j===0&&<td style={{padding:'3px 6px',color:'#64748b'}} rowSpan={log.changes.length}>{paramLog.length-i}</td>}
              {j===0&&<td style={{padding:'3px 6px'}} rowSpan={log.changes.length}>{log.tick.toLocaleString()}</td>}
              {j===0&&<td style={{padding:'3px 6px'}} rowSpan={log.changes.length}>
                <span style={{padding:'1px 6px',borderRadius:3,fontSize:10,
                  background:log.action==='tighten'?'#ef444422':'#22c55e22',
                  color:log.action==='tighten'?'#ef4444':'#22c55e'}}>{log.action}</span></td>}
              {j===0&&<td style={{padding:'3px 6px'}} rowSpan={log.changes.length}>{log.wr}%</td>}
              <td style={{padding:'3px 6px',color:'#94a3b8'}}>{ch.param}</td>
              <td style={{padding:'3px 6px'}}>{ch.from}</td>
              <td style={{padding:'3px 6px',fontWeight:600,color:ch.to>ch.from?'#ef4444':'#22c55e'}}>{ch.to}</td>
              <td style={{padding:'3px 6px',fontSize:10,color:ch.to>ch.from?'#ef4444':'#22c55e'}}>
                {ch.to>ch.from?'▲':'▼'} {Math.abs(+(ch.to-ch.from).toFixed(2))}</td>
            </tr>))}</tbody></table>
      </div></div>}

    {/* Top 10 Grid Search Results (only in ready phase) */}
    {phase==='ready'&&topResults.length>0&&<div style={{background:'#111',borderRadius:8,padding:14,marginBottom:12}}>
      <div style={{fontSize:11,color:'#64748b',marginBottom:8,fontWeight:600}}>TOP 10 PARAMETER COMBINATIONS (by Sharpe)</div>
      <table style={{width:'100%',fontSize:11,borderCollapse:'collapse'}}>
        <thead><tr style={{color:'#64748b',borderBottom:'1px solid #222'}}>
          {['Rank','Spread','Persist','Z-thresh','Vol-adj','Sharpe','Trades','P&L','Win%','PF'].map(h=><th key={h} style={{padding:'4px 6px',textAlign:'left',fontWeight:600}}>{h}</th>)}
        </tr></thead>
        <tbody>{topResults.map((r,i)=><tr key={i} style={{borderBottom:'1px solid #1a1a1a',background:i===0?'#22c55e08':'transparent'}}>
          <td style={{padding:'3px 6px',color:i===0?'#22c55e':'#64748b',fontWeight:i===0?700:400}}>{i===0?'★ 1':i+1}</td>
          <td style={{padding:'3px 6px'}}>{r.sT}</td><td style={{padding:'3px 6px'}}>{r.pT}</td>
          <td style={{padding:'3px 6px'}}>{r.zT}</td><td style={{padding:'3px 6px'}}>{r.vA}</td>
          <td style={{padding:'3px 6px',color:r.sharpe>0?'#22c55e':'#ef4444',fontWeight:600}}>{r.sharpe}</td>
          <td style={{padding:'3px 6px'}}>{r.n}</td>
          <td style={{padding:'3px 6px',color:r.pnl>0?'#22c55e':'#ef4444'}}>${r.pnl.toLocaleString()}</td>
          <td style={{padding:'3px 6px'}}>{r.wr}%</td><td style={{padding:'3px 6px'}}>{r.pf}</td>
        </tr>)}</tbody></table></div>}

    {/* Order Book */}
    <div style={{background:'#111',borderRadius:8,padding:14}}>
      <div style={{fontSize:11,color:'#64748b',marginBottom:8,fontWeight:600}}>ORDER BOOK ({trades.length})</div>
      <div style={{maxHeight:280,overflowY:'auto'}}>
        <table style={{width:'100%',fontSize:11,borderCollapse:'collapse'}}>
          <thead><tr style={{color:'#64748b',borderBottom:'1px solid #222'}}>
            {['#','Entry','Exit','Hold','Pair','Spread','P&L','Exit','Capital'].map(h=><th key={h} style={{padding:'4px 6px',textAlign:'left',fontWeight:600}}>{h}</th>)}
          </tr></thead>
          <tbody>{[...trades].reverse().map((t,i)=><tr key={i} style={{borderBottom:'1px solid #1a1a1a'}}>
            <td style={{padding:'3px 6px',color:'#64748b'}}>{trades.length-i}</td>
            <td style={{padding:'3px 6px'}}>{t.entry}</td><td style={{padding:'3px 6px'}}>{t.exit}</td><td style={{padding:'3px 6px'}}>{t.hold}</td>
            <td style={{padding:'3px 6px'}}>{t.be}→{t.se}</td><td style={{padding:'3px 6px'}}>{t.es}</td>
            <td style={{padding:'3px 6px',color:t.net>0?'#22c55e':'#ef4444',fontWeight:600}}>{t.net>0?'+':''}${t.net.toFixed(2)}</td>
            <td style={{padding:'3px 6px'}}><span style={{padding:'1px 6px',borderRadius:3,fontSize:10,
              background:t.reason==='z_revert'?'#22c55e22':t.reason==='stop_loss'?'#ef444422':'#f59e0b22',
              color:t.reason==='z_revert'?'#22c55e':t.reason==='stop_loss'?'#ef4444':'#f59e0b'}}>{t.reason}</span></td>
            <td style={{padding:'3px 6px'}}>${t.cap.toLocaleString()}</td>
          </tr>)}</tbody></table>
        {!trades.length&&<div style={{textAlign:'center',padding:20,color:'#64748b'}}>{phase==='ready'?'Trades will appear here after you start':'No trades yet'}</div>}
      </div></div>
  </div>);
}
