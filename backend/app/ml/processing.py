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


def localization_overlay(rgb, heatmap, learned=True):
    """Render a heatmap plus an explicit inspection region for the operator."""
    height,width=rgb.shape[:2]
    heatmap=cv2.resize(np.asarray(heatmap,dtype=np.float32),(width,height))
    heatmap=np.nan_to_num(heatmap,nan=0.0,posinf=1.0,neginf=0.0)
    heatmap=(heatmap-heatmap.min())/(heatmap.max()-heatmap.min()+1e-8)
    colored=cv2.applyColorMap(np.uint8(heatmap*255),cv2.COLORMAP_JET)
    overlay=cv2.addWeighted(rgb,.62,colored,.38,0)
    threshold=max(.5,float(np.percentile(heatmap,85)))
    mask=np.uint8(heatmap>=threshold)*255
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((9,9),np.uint8))
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        contour=max(contours,key=cv2.contourArea)
        x,y,w,h=cv2.boundingRect(contour)
    else:
        x,y,w,h=width//3,height//3,width//3,height//3
    center=(x+w//2,y+h//2); radius=max(24,int(max(w,h)*.58))
    accent=(0,255,255) if learned else (0,165,255)
    cv2.rectangle(overlay,(x,y),(x+w,y+h),accent,2)
    cv2.circle(overlay,center,radius,accent,2)
    label="GRAD-CAM / INSPECT THIS AREA" if learned else "THERMAL SALIENCY / BASELINE ONLY"
    label_y=max(28,y-12)
    cv2.rectangle(overlay,(max(0,x-4),label_y-22),(min(width-1,x+330),label_y+7),(7,12,17),-1)
    cv2.putText(overlay,label,(x,label_y),cv2.FONT_HERSHEY_SIMPLEX,.55,accent,1,cv2.LINE_AA)
    return overlay,{"bounding_box":{"x":x,"y":y,"width":w,"height":h},"center":{"x":center[0],"y":center[1]},"radius":radius,"threshold":round(threshold,4),"instruction":"Inspect this highlighted area.","localization_method":"true_gradcam" if learned else "thermal_saliency_baseline"}


def baseline_saliency_overlay(rgb, thermal):
    gray=cv2.cvtColor(thermal,cv2.COLOR_BGR2GRAY)
    return localization_overlay(rgb,gray.astype(np.float32)/255.0,learned=False)
