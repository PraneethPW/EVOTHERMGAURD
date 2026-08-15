import cv2, numpy as np
from pathlib import Path
from app.core.config import settings

RISK_CLASSES=["NORMAL","WARNING","HIGH_RISK","CRITICAL"]
class ModelService:
    """Singleton facade. Demo uses reproducible image statistics; trained is checkpoint-ready."""
    version="baseline-heuristic-v1"
    def status(self): return {"mode": settings.model_mode, "validated": settings.model_mode == "trained", "version": self.version}
    def predict(self, rgb_path:Path, thermal_path:Path, environment:dict):
        thermal=cv2.imread(str(thermal_path),cv2.IMREAD_GRAYSCALE)
        if thermal is None: raise ValueError("Thermal image could not be decoded")
        p95=float(np.percentile(thermal,95))/255
        mean=float(thermal.mean())/255
        spread=float(thermal.std())/255
        hotspot_threshold=max(float(np.percentile(thermal,90)), float(thermal.mean()+thermal.std()))
        hotspot_ratio=float(np.mean(thermal>=hotspot_threshold))
        blurred=cv2.GaussianBlur(thermal,(31,31),0)
        local_contrast=float(np.percentile(cv2.absdiff(thermal,blurred),95))/255
        ambient=max(0,min(1,(environment["ambient_temperature"]-20)/60))
        humidity=max(0,min(1,environment["humidity"]/100))
        score=min(.98,max(.02,.30*p95+.18*mean+.16*spread+.20*local_contrast+.08*min(1,hotspot_ratio*10)+.06*ambient+.02*humidity))
        thresholds=[.33,.50,.68]
        idx=0 if score<thresholds[0] else 1 if score<thresholds[1] else 2 if score<thresholds[2] else 3
        centers=np.array([.20,.41,.59,.79]); distance=np.abs(centers-score); weights=np.exp(-distance*8); probs=weights/weights.sum()
        return {"risk_level":RISK_CLASSES[idx],"confidence":round(score,4),"class_probabilities":{k:round(float(v),4) for k,v in zip(RISK_CLASSES,probs)},"model_version":self.version,"evidence":{"output_type":"HEURISTIC_RISK_SCORE","heuristic_score":round(score,4),"thermal_intensity_mean":round(mean,4),"thermal_intensity_p95":round(p95,4),"thermal_texture_spread":round(spread,4),"hotspot_region_proportion":round(hotspot_ratio,4),"local_hotspot_contrast":round(local_contrast,4),"environment_normalization":{"ambient":round(ambient,4),"humidity":round(humidity,4)},"mode_note":"Deterministic heuristic baseline derived from submitted pixels and context; not engineering validated."}}
model_service=ModelService()
