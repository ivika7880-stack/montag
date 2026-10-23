import numpy as np, soundfile as sf
y,sr=sf.read("work/prism/voice_full.wav",dtype="float32")
a=984.690; N=6; ia=int(round(a*sr)); ib=ia+int(round(N/30*sr)); xf=int(sr*0.005)
w=np.linspace(0,np.pi/2,xf).astype(np.float32); fo,fi=np.cos(w),np.sin(w)
if y.ndim==2: fo,fi=fo[:,None],fi[:,None]
seam=y[ia:ia+xf]*fo+y[ib:ib+xf]*fi
z=np.concatenate([y[:ia],seam,y[ib+xf:]])
sf.write("work/prism/voice_cut.wav",z,sr,subtype="FLOAT")
print("removed %.4f s -> %.3f s"%((len(y)-len(z))/sr,len(z)/sr))
