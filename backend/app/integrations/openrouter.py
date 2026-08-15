import httpx
from app.core.config import settings

def fallback_explanation(payload:dict):
    return (f"Risk assessment: {payload['risk_level'].replace('_',' ').title()} at {payload['confidence']:.1%} heuristic confidence. "
            "Review the model-attributed region alongside the submitted environmental context before making an engineering decision.")

async def explain(payload:dict, question:str):
    fallback=fallback_explanation(payload)
    if not settings.openrouter_api_key: return fallback,"deterministic-fallback"
    prompt="Use ONLY supplied data. Do not invent temperatures, causes, probabilities, or history. Clearly separate model evidence from recommended operator follow-up.\nDATA:\n"+str(payload)+"\nQUESTION:\n"+question
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.5, connect=1.5)) as client:
            r=await client.post(settings.openrouter_base_url+"/chat/completions",headers={"Authorization":f"Bearer {settings.openrouter_api_key}"},json={"model":settings.openrouter_model,"messages":[{"role":"user","content":prompt}]}); r.raise_for_status(); return r.json()["choices"][0]["message"]["content"],settings.openrouter_model
    except Exception: return fallback,"deterministic-fallback"
