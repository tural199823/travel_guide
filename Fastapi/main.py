from fastapi import FastAPI,WebSocket
from fastapi.responses import HTMLResponse
from agent.agent import agent
from pydantic import BaseModel
#from template import html
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
app = FastAPI()

class ChatInput(BaseModel):
    message: str
    thread_id: str

@app.get("/")
async def get():
    return {"message": "API is running"}


# New method
@app.websocket("/ws/{thread_id}")    
async def websocket_endpoint(websocket: WebSocket, thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    await websocket.accept()
    
    while True:
        data = await websocket.receive_text()
        
        async for message, event in agent.astream(
            {"messages": [HumanMessage(content=data)]}, 
            config=config,
            stream_mode="messages"
        ):
            if isinstance(message, AIMessage) and message.content:
                await websocket.send_text(message.content)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)