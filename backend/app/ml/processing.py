from pathlib import Path
import cv2, numpy as np

def preprocess(path:Path, output:Path, thermal=False):
    image=cv2.imread(str(path));
    if image is None: raise ValueError("Image decoding failed")
    image=cv2.resize(image,(512,512),interpolation=cv2.INTER_AREA)
    image=cv2.fastNlMeansDenoisingColored(image,None,5,5,7,21)
    lab=cv2.cvtColor(image,cv2.COLOR_BGR2LAB); l,a,b=cv2.split(lab); l=cv2.createCLAHE(clipLimit=2.0,tileGridSize=(8,8)).apply(l); image=cv2.cvtColor(cv2.merge([l,a,b]),cv2.COLOR_LAB2BGR)
    cv2.imwrite(str(output),image); return image
def register(rgb, thermal):
    gray_a=cv2.cvtColor(rgb,cv2.COLOR_BGR2GRAY); gray_b=cv2.cvtColor(thermal,cv2.COLOR_BGR2GRAY); orb=cv2.ORB_create(500); ka,da=orb.detectAndCompute(gray_a,None); kb,db=orb.detectAndCompute(gray_b,None)
    if da is None or db is None: return cv2.resize(thermal,(rgb.shape[1],rgb.shape[0])),"low_confidence",0.0
    matches=cv2.BFMatcher(cv2.NORM_HAMMING,crossCheck=True).match(da,db)
    if len(matches)<8: return cv2.resize(thermal,(rgb.shape[1],rgb.shape[0])),"low_confidence",len(matches)/100
    src=np.float32([ka[m.queryIdx].pt for m in matches]).reshape(-1,1,2); dst=np.float32([kb[m.trainIdx].pt for m in matches]).reshape(-1,1,2); h,mask=cv2.findHomography(dst,src,cv2.RANSAC,5.0)
    if h is None: return cv2.resize(thermal,(rgb.shape[1],rgb.shape[0])),"low_confidence",0.0
    return cv2.warpPerspective(thermal,h,(rgb.shape[1],rgb.shape[0])),"registered",float(mask.mean())
def fuse(rgb, thermal):
    th=cv2.applyColorMap(cv2.cvtColor(thermal,cv2.COLOR_BGR2GRAY),cv2.COLORMAP_INFERNO); return cv2.addWeighted(rgb,.65,th,.35,0)
def gradcam_overlay(rgb, thermal):
    heat=cv2.applyColorMap(cv2.cvtColor(thermal,cv2.COLOR_BGR2GRAY),cv2.COLORMAP_JET); return cv2.addWeighted(rgb,.58,heat,.42,0)
