import React, {useEffect, useMemo, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './styles.css';

const API='http://localhost:8000/api';
const positions={0:[80,220],1:[220,110],2:[220,330],3:[390,110],4:[390,330],5:[550,220],6:[700,130],7:[700,310],8:[700,220],9:[550,400]};
const edges={L01:[0,1],L02:[0,2],L13:[1,3],L24:[2,4],T3:[3,5],T4:[4,5],L56:[5,6],L57:[5,7],L58:[5,8],L59:[5,9],TIE:[4,3]};

async function api(path, opts={}){const r=await fetch(API+path,{headers:{'Content-Type':'application/json'},...opts});if(!r.ok)throw new Error(await r.text());return r.json()}

function GridMap({state}){
  const failed=state?.failure;
  const lines=state?.lines||[];
  return <svg viewBox="0 0 800 460" className="gridmap">
    {lines.map(l=>{const [x1,y1]=positions[l.from_bus], [x2,y2]=positions[l.to_bus]; const [ox,oy]=l.tie?[0,0]:[0,0]; return <line key={l.id} x1={x1+ox} y1={y1+oy} x2={x2} y2={y2} className={`edge ${l.in_service?'on':'off'} ${failed===l.id?'failed':''} ${l.tie?'tie':''}`}/>})}
    {(state?.buses||[]).map(b=>{const [x,y]=positions[b.id];let c=b.id===0?'#1976d2':b.critical?'#7252b8':b.kind==='transformer'?'#ef7d22':'#169c72';if(failed==='T3'&&b.id===3)c='#d64545';return <g key={b.id}><circle cx={x} cy={y} r={b.id===0?28:24} fill={c} stroke="#fff" strokeWidth="4"/><text x={x} y={y+4} textAnchor="middle" fill="#fff" fontWeight="800" fontSize="12">{b.id===0?'SS1':b.name.replace('Transformer ','T')}</text><text x={x} y={y+44} textAnchor="middle" className="nlabel">{b.name}</text></g>})}
  </svg>
}

function App(){
 const [state,setState]=useState(null),[plans,setPlans]=useState([]),[best,setBest]=useState(null),[selected,setSelected]=useState('Plan C — Critical First'),[message,setMessage]=useState(''),[risk,setRisk]=useState(null);
 const load=async()=>setState(await api('/grid'));
 useEffect(()=>{load()},[]);
 const inject=async()=>{const s=await api('/fail',{method:'POST',body:JSON.stringify({line_id:'T3'})});setState(s);const p=await api('/plans');setPlans(p.plans);setBest(p.best);setSelected(p.best.plan);const pred=await api('/predict?line_id=T3&load_scale=1');setRisk(pred);setMessage('Transformer T3 failure injected. AI impact prediction: '+pred.risk+' risk.');};
 const reset=async()=>{setState(await api('/reset'));setPlans([]);setBest(null);setRisk(null);setMessage('Grid reset to normal operation.');};
 const simulate=async()=>{const r=await api('/simulate',{method:'POST',body:JSON.stringify({plan:selected})});setMessage(`${r.plan} simulated: ${r.load_served_pct}% load served, ${r.critical_served_pct}% critical load served.`)};
 const apply=async()=>{const s=await api('/apply',{method:'POST',body:JSON.stringify({plan:selected})});setState(s);setMessage(`${selected} applied inside the simulation.`)};
 const metrics=state?.metrics||{};
 return <div className="app">
  <header><div className="brand"><div className="logo">G</div><div><h1>Grid AI</h1><p>Emergency Power Recovery Decision Support</p></div></div><div className="status"><span/> Simulation Online</div></header>
  <main><div className="top"><div><h2>Emergency Control Center</h2><p>Predict impact • Test recovery options • Protect critical services</p></div><div className="actions"><button className="warning" onClick={inject}>⚠ Inject T3 Failure</button><button onClick={reset}>↺ Reset</button></div></div>
   {message&&<div className="message">{message}</div>}
   <div className="layout">
    <section className="card mapcard"><div className="cardhead"><h3>Live Grid Model</h3><span className={`pill ${state?.failure?'danger':'ok'}`}>{state?.failure?'FAULT DETECTED':'NORMAL OPERATION'}</span></div><div className="mapwrap"><GridMap state={state}/></div><div className="legend"><span><i className="green"/>Healthy</span><span><i className="purple"/>Critical</span><span><i className="red"/>Failure</span><span><i className="blue"/>Source</span></div></section>
    <section className="side">
      <div className="card"><div className="cardhead"><h3>Grid Health</h3><span className={`pill ${state?.failure?'danger':'ok'}`}>{state?.failure?'AT RISK':'HEALTHY'}</span></div>{risk&&<div className="riskbar"><b>AI IMPACT RISK: {risk.risk}</b><span>{Math.round(risk.probability*100)}% confidence</span></div>}<div className="metrics"><Metric label="Load Served" value={`${metrics.load_served_pct??100}%`} /><Metric label="Critical Loads" value={`${metrics.critical_served_pct??100}%`} /><Metric label="Overloaded Lines" value={metrics.overloaded_lines??0}/><Metric label="Unserved Power" value={`${metrics.unserved_mw??0} MW`}/></div></div>
      <div className="card"><div className="cardhead"><h3>Recovery Plans</h3><span className="pill">WHAT-IF</span></div><div className="plans">{plans.length===0?<p className="empty">Inject a failure to generate recovery plans.</p>:plans.map(p=><div className={`plan ${selected===p.plan?'selected':''}`} onClick={()=>setSelected(p.plan)} key={p.plan}><div><b>{p.plan}</b><small>{p.actions.length? p.actions.join(' + '):'No intervention'}</small></div><strong>{p.load_served_pct}%</strong></div>)}</div>{best&&<div className="recommend"><small>AI RECOMMENDATION</small><h4>{best.plan}</h4><p>Protect critical loads first, avoid overloads, and minimize total unserved power.</p><div className="row"><button onClick={simulate}>▶ Simulate</button><button className="secondary" onClick={apply}>✓ Apply in Demo</button></div></div>}</div>
      <div className="card"><div className="cardhead"><h3>Decision Flow</h3><span className="pill">LIVE</span></div><div className="timeline"><Step title="Failure detected" text={state?.failure?'T3 failed':'Waiting for failure'}/><Step title="Impact analysed" text={state?.failure?'Critical loads evaluated':'—'}/><Step title="Plans generated" text={plans.length?`${plans.length} recovery plans`:'—'}/><Step title="Best action" text={best?best.plan:'Ready'}/></div></div>
    </section>
   </div>
  </main>
 </div>
}
function Metric({label,value}){return <div className="metric"><small>{label}</small><b>{value}</b></div>}
function Step({title,text}){return <div className="step"><span></span><div><b>{title}</b><small>{text}</small></div></div>}
createRoot(document.getElementById('root')).render(<App/>);
