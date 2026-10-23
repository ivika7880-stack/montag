import subprocess, numpy as np, glob, os, cv2, sys
ff=glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\**\ffmpeg.exe"),recursive=True)[0]
src,crop=sys.argv[1],sys.argv[2]           # crop like 576:180:0:900  (w:h:x:y)
p=subprocess.Popen([ff,"-v","error","-i",src,"-an","-vf","crop=%s,scale=288:90,format=bgr24"%crop,"-f","rawvideo","-"],stdout=subprocess.PIPE)
n=288*90*3; hf=[];sat=[]
while True:
    b=p.stdout.read(n)
    if len(b)<n: break
    im=np.frombuffer(b,np.uint8).reshape(90,288,3); g=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
    hf.append(float(np.abs(cv2.Laplacian(g,cv2.CV_32F)).mean())); hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV); sat.append(float(((hsv[...,1]>120)&(hsv[...,2]>70)).mean()))
hf=np.array(hf); sat=np.array(sat)
bad=np.where((hf>3.5)|(sat>0.005))[0]
print("frames",len(hf),"max hf %.2f max sat %.4f bad frames %d"%(hf.max(),sat.max(),len(bad)), ("first bad at %.1fs"%(bad[0]/30)) if len(bad) else "")
sys.exit(1 if len(bad) else 0)
