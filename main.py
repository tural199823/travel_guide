# from fastapi import FastAPI
# from agent.agent import agent
# from pydantic import BaseModel
# from langchain_core.messages import HumanMessage

# app = FastAPI()

# class ChatInput(BaseModel):
#     message: str
#     thread_id: str

# @app.post("/chat")  # Changed to POST
# async def chat(input: ChatInput):
#     config = {"configurable": {"thread_id": input.thread_id}}
#     response = await agent.ainvoke({"messages": [HumanMessage(content=input.message)]}, config=config)
#     return {"Bot": response["messages"][-1].content}

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000


from fastapi import FastAPI,WebSocket
from fastapi.responses import HTMLResponse
from agent.agent import agent
from pydantic import BaseModel
from template import html
from langchain_core.messages import HumanMessage

app = FastAPI()

class ChatInput(BaseModel):
    message: str
    thread_id: str

# @app.post("/chat")  # Changed to POST
# async def chat(input: ChatInput):
#     config = {"configurable": {"thread_id": input.thread_id}}
#     response = await agent.ainvoke({"messages": [HumanMessage(content=input.message)]}, config=config)
#     return {"Bot": response["messages"][-1].content}

# Streaming
# Serve the HTML chat interface
@app.get("/")
async def get():
    return HTMLResponse(html)

# WebSocket endpoint for real-time streaming
@app.websocket("/ws/{thread_id}")     
async def websocket_endpoint(websocket: WebSocket, thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        # async for chunk in agent.astream({"messages": [data]}, config=config, stream_mode="updates"):
        #     await websocket.send_text(str(chunk))
        async for message,event in agent.astream({"messages": [data]}, config=config, stream_mode="messages"):
        # async for message in agent.ainvoke({"messages": [data]}, config=config, stream_mode="messages"):
            await websocket.send_text(message.content)
        # await websocket.send_text(str(event))




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)