/* Original CodeLab renderer. Draws validated data; never evaluates user or AI code. */
(() => {
  'use strict';
  const palettes = {
    lagoon: {bg:'#0b1d2c',ink:'#bceedd',accent:'#f4d29d',dim:'#3b7380',water:'#153744'},
    sunrise: {bg:'#291e2b',ink:'#ffc9ac',accent:'#f0dfb0',dim:'#946580',water:'#493044'},
    mint: {bg:'#102d2c',ink:'#c0f1b5',accent:'#f0d990',dim:'#518d7c',water:'#1c4640'}
  };
  function mount(host, trace, options={}) {
    let frame=0, playing=Boolean(options.autoPlay), speed=1, last=0, scheme=options.palette||'lagoon';
    const total=trace.scene==='route'?Math.max(1,trace.visited.length+trace.path.length):trace.frames.length;
    const notify=()=>options.onFrame?.(frame,total,playing);
    host.replaceChildren();
    const sketch=new p5(p=>{
      let canvas,drawn='';
      p.setup=()=>{canvas=p.createCanvas(Math.max(1,host.clientWidth),Math.max(1,host.clientHeight));canvas.parent(host);canvas.elt.setAttribute('aria-hidden','true');p.pixelDensity(Math.min(2,window.devicePixelRatio||1));p.frameRate(30);notify();};
      function label(text,x,y,size=12,color){p.noStroke();p.fill(color);p.textSize(size);p.textFont('monospace');p.text(text,x,y);}
      function water(c){
        p.background(c.bg);
        const ctx=p.drawingContext,gradient=ctx.createRadialGradient(p.width*.55,p.height*.38,0,p.width*.5,p.height*.5,p.width*.65);
        gradient.addColorStop(0,c.water);gradient.addColorStop(1,c.bg);ctx.fillStyle=gradient;ctx.fillRect(0,0,p.width,p.height);
      }
      function ocean(c){
        p.stroke(c.dim+'35');p.strokeWeight(.7);
        for(let x=0;x<=1000;x+=50)p.line(x,0,x,650);
        for(let y=0;y<=650;y+=50)p.line(0,y,1000,y);
        p.noFill();p.stroke(c.ink+'12');p.strokeWeight(1);
        for(let j=0;j<5;j++){p.beginShape();for(let x=0;x<=1000;x+=10)p.vertex(x,260+j*34+Math.sin(x/140+j)*48);p.endShape();}
        const current=trace.frames[frame],prev=trace.frames[Math.max(0,frame-1)];
        for(let i=0;i<current.length;i++){
          p.noFill();p.stroke(c.ink+'30');p.strokeWeight(1.4);p.beginShape();
          for(let f=Math.max(0,frame-10);f<=frame;f++)p.vertex(...trace.frames[f][i]);p.endShape();
          const [x,y]=current[i],angle=frame?Math.atan2(y-prev[i][1],x-prev[i][0]):-i*.27;
          p.push();p.translate(x,y);p.rotate(angle);p.noStroke();
          p.fill(c.ink+'13');p.ellipse(0,0,46,32);
          p.fill(i%5===0?c.accent:c.ink);p.beginShape();p.vertex(15,0);p.bezierVertex(5,-8,-5,-9,-11,-2);p.vertex(-19,-7);p.vertex(-17,0);p.vertex(-19,7);p.vertex(-11,2);p.bezierVertex(-5,9,5,8,15,0);p.endShape(p.CLOSE);
          p.fill(c.bg);p.circle(8,-1.5,2.5);p.pop();
        }
        label('FOLLOW A RULE. FIND A RHYTHM.',34,42,10,c.dim);
        label(String(current.length).padStart(2,'0')+' / SWIMMERS',34,620,10,c.dim);
      }
      function sorting(c){
        const state=trace.frames[frame],n=state.values.length,slot=840/n,base=520;
        p.stroke(c.dim+'65');p.strokeWeight(1);p.line(70,base,930,base);
        for(let line=0;line<4;line++){p.stroke(c.dim+'25');p.line(70,base-line*110,930,base-line*110);}
        state.values.forEach((value,i)=>{
          const x=80+i*slot,h=value*3.5,active=state.focus.includes(i),color=active?c.accent:c.ink;
          p.noStroke();p.fill(color+'19');p.rect(x-3,base-h-8,slot*.67+6,h+16,10);
          p.fill(color+(active?'d9':'88'));p.rect(x,base-h,slot*.67,h,5);
          p.fill(color);p.circle(x+slot*.335,base-h-15,active?9:5);
          label(String(value),x+slot*.2,base+29,14,color);label(String(i).padStart(2,'0'),x+slot*.2,base+53,9,c.dim);
        });
        label('A LITTLE MORE ORDER, ONE STEP AT A TIME.',80,65,10,c.dim);
        label(state.focus.length?(state.swapped?'SWAP / 交换位置':'COMPARE / 比较数值'):'INITIAL / 初始排列',80,112,15,c.ink);
      }
      function route(c){
        const cell=43,ox=198,oy=105,walls=new Set(trace.walls.map(x=>x.join(','))),limit=Math.min(frame+1,trace.visited.length);
        const seen=new Set(trace.visited.slice(0,limit).map(x=>x.join(',')));
        p.noStroke();
        for(let y=0;y<10;y++)for(let x=0;x<14;x++){
          const px=ox+x*cell,py=oy+y*cell,key=x+','+y;
          p.fill(c.dim+'18');p.rect(px+2,py+2,cell-4,cell-4,5);
          if(walls.has(key)){p.fill(c.dim+'a0');p.beginShape();p.vertex(px+9,py+31);p.vertex(px+14,py+12);p.vertex(px+23,py+7);p.vertex(px+34,py+20);p.vertex(px+31,py+33);p.endShape(p.CLOSE);}
          else if(seen.has(key)){p.fill(c.ink+'50');p.circle(px+cell/2,py+cell/2,8);}
        }
        const pathCount=Math.max(0,frame-trace.visited.length+1),path=trace.path.slice(0,pathCount+1);
        if(pathCount>0&&path.length){p.stroke(c.accent);p.strokeWeight(3);p.noFill();p.beginShape();for(const [x,y] of path)p.vertex(ox+(x+.5)*cell,oy+(y+.5)*cell);p.endShape();}
        const boat=pathCount>0&&path.length?path[path.length-1]:[0,9];
        p.push();p.translate(ox+(boat[0]+.5)*cell,oy+(boat[1]+.5)*cell);p.noStroke();p.fill(c.accent);p.triangle(-9,5,9,5,0,12);p.triangle(0,-12,0,3,9,3);p.stroke(c.accent);p.line(0,-13,0,6);p.pop();
        p.noStroke();p.fill(c.accent);p.rect(ox+13.5*cell-4,oy+12,8,20,2);p.triangle(ox+13.5*cell-9,oy+12,ox+13.5*cell+9,oy+12,ox+13.5*cell,oy+4);
        label('FIND YOUR WAY THROUGH THE UNKNOWN.',198,62,10,c.dim);
        label('EXPLORED '+String(limit).padStart(3,'0')+' / ROUTE '+Math.max(0,trace.path.length-1)+' STEPS',198,582,11,c.ink);
      }
      p.draw=()=>{
        if(document.hidden)return;
        const now=p.millis();
        if(playing&&!document.hidden&&now-last>1000/(trace.scene==='ocean'?18:8)/speed){last=now;if(frame<total-1)frame++;else playing=false;notify();}
        const stamp=[frame,scheme,p.width,p.height].join(':');if(stamp===drawn)return;drawn=stamp;
        const c=palettes[scheme]||palettes.lagoon;water(c);
        const scale=Math.min(p.width/1000,p.height/650);p.push();p.translate((p.width-1000*scale)/2,(p.height-650*scale)/2);p.scale(scale);
        if(trace.scene==='ocean')ocean(c);else if(trace.scene==='sorting')sorting(c);else route(c);p.pop();
      };
    });
    const observer=new ResizeObserver(()=>{if(sketch.width)sketch.resizeCanvas(Math.max(1,host.clientWidth),Math.max(1,host.clientHeight));});observer.observe(host);
    return {
      seek(value){frame=Math.max(0,Math.min(total-1,Number(value)||0));playing=false;notify();},
      toggle(){if(frame===total-1)frame=0;playing=!playing;last=0;notify();},
      pause(){playing=false;notify();},
      setSpeed(value){speed=Math.max(.5,Math.min(2,Number(value)||1));},
      palette(value){scheme=value;},
      image(){return host.querySelector('canvas')?.toDataURL('image/png');},
      destroy(){observer.disconnect();sketch.remove();},
      total
    };
  }
  window.CodeLabCanvas={mount};
})();
