// Official, unmetered Bluesky live tail. Bounded, no dependencies, no retries.
import fs from 'node:fs';
import path from 'node:path';
const output=process.argv[2];
if(!output)throw new Error('Private output file required');
const start=Date.now(), terms=['blueberr','arándano','arandano','mirtilo','蓝莓','ブルーベリー'];
const url='wss://jetstream.us-east.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents?collections=app.bsky.feed.post&kinds=commit';
const result={version:1,candidate:'bluesky-jetstream-v2',endpoint:url,started_at:new Date().toISOString(),state:'blocked',frames:0,bytes:0,matched_events:[],connected:false,cash_usd:0,credits:0,limits:{seconds:30,frames:5000,bytes:10000000,matches:10},window_exception:'30-second live tail, not the shared 30-day search interval'};
let done=false;
function finish(reason){if(done)return;done=true;clearTimeout(timer);result.reason=reason;result.finished_at=new Date().toISOString();result.duration_ms=Date.now()-start;result.state=result.connected?'live-tested':'blocked';fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify(result,null,2));try{socket.close();}catch{};console.log(JSON.stringify({state:result.state,connected:result.connected,frames:result.frames,bytes:result.bytes,matches:result.matched_events.length,reason,cash_usd:0}));setTimeout(()=>process.exit(0),1000);}
const socket=new WebSocket(url,['xrpc.v1.json']);
const timer=setTimeout(()=>finish('Time ceiling reached; limited live sample'),30000);
socket.addEventListener('open',()=>{result.connected=true;});
socket.addEventListener('message',event=>{
  const text=String(event.data);result.frames++;result.bytes+=Buffer.byteLength(text);
  if(result.bytes>result.limits.bytes||text.length>2000000){finish('Byte ceiling reached');return;}
  try{const e=JSON.parse(text).payload;if(e&&e.collection==='app.bsky.feed.post'&&['create','update'].includes(e.operation)&&typeof e.record?.text==='string'&&terms.some(t=>e.record.text.toLocaleLowerCase().includes(t)))result.matched_events.push(e);}catch{result.malformed=(result.malformed||0)+1;}
  if(result.frames>=result.limits.frames||result.matched_events.length>=result.limits.matches)finish('Frame/result ceiling reached');
});
socket.addEventListener('error',()=>finish('WebSocket connection failed; no success or entitlement inferred'));
socket.addEventListener('close',()=>finish('Stream closed; bounded sample only'));
