from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import ListSortOrder
import json
import re
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI()

project = AIProjectClient(
    credential=DefaultAzureCredential(),
    endpoint="https://aura-india.services.ai.azure.com/api/projects/firstProject")

agent = project.agents.get_agent("asst_YqNJrghF1OknjXr1V1Bn3nZM")
thread = project.agents.threads.get("thread_0eBDPTJsjtcVIoGYUVrNdJy2")

@app.post("/recommend")
async def recommend(request: Request):
    customer_profile = await request.json()
    customer_email = customer_profile.get("email")
    # Send the customer profile as the message content
    message = project.agents.messages.create(
        thread_id=thread.id,
        role="user",
        content=json.dumps(customer_profile)
    )
    run = project.agents.runs.create_and_process(
        thread_id=thread.id,
        agent_id=agent.id)
    if run.status == "failed":
        return JSONResponse(status_code=500, content={"status": "failed", "error": str(run.last_error)})
    messages = list(project.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING))
    # Find the latest assistant message with a recommendation table
    recommendation_table = None
    for message in reversed(messages):
        if message.role == "assistant":
            text = message.text_messages[-1].text.value
            if "| Product Name" in text and "| Probability" in text:
                recommendation_table = text
                break
    recommendations = []
    if recommendation_table:
        lines = recommendation_table.splitlines()
        data_lines = [line for line in lines if "|" in line and not line.strip().startswith("|-")]
        for line in data_lines[1:]:  # Skip header
            cols = [col.strip() for col in line.strip().split("|")[1:-1]]
            if len(cols) < 4:
                continue
            product = cols[0]
            owns_it = cols[1]
            probability = cols[2]
            reason = cols[3]
            if owns_it.lower() == "yes":
                continue  # Skip products already owned
            try:
                probability_value = float(probability)
            except ValueError:
                probability_value = probability  # e.g., "Already owns"
            recommendations.append({
                "product": product,
                "probability": probability_value,
                "reason": reason
            })
    output = {
        "customer_email": customer_email,
        "recommendations": recommendations
    }
    return JSONResponse(content=output)

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)