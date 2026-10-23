import cv2, numpy as np, json, math
rows=[]
for i in range(442):
    cap=cv2.VideoCapture(f"work/prism/clipsF/c{i:03d}.mp4"); n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if n<4: rows.append(dict(i=i,gamma=1.0,satf=1.0)); continue
    L=[];S=[]
    for k in np.linspace(2,max(3,n-3),6).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES,int(k)); ok,f=cap.read()
        if not ok: continue
        L.append(cv2.cvtColor(f,cv2.COLOR_BGR2GRAY).mean()/255); S.append(cv2.cvtColor(f,cv2.COLOR_BGR2HSV)[...,1].mean())
    m=float(np.mean(L)); sat=float(np.mean(S)); t=min(max(0.427,m*0.7),m*1.3)
    e=min(max(math.log(t)/math.log(max(m,0.02)),0.6),1.5)
    rows.append(dict(i=i,gamma=round(1/e,3),satf=round(min(1.0,150/sat) if sat>150 else 1.0,2)))
json.dump(rows,open("work/prism/col_all.json","w"))
g=np.array([r["gamma"] for r in rows]); print("clips",len(rows),"gamma min/med/max",g.min(),np.median(g),g.max(),"| satf<1:",sum(r["satf"]<1 for r in rows))
