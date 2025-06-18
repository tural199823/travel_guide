from fastapi import FastAPI
from agent import agent
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

app = FastAPI()

class ChatInput(BaseModel):
    messages: list[str]
    thread_id: str

@app.post("/chat")
async def chat(input: ChatInput):
    config = {"configurable": {"thread_id": "1"}}
    response = await agent.invoke({"messages": [HumanMessage(content=input.messages)]}, config=config)
    return response["messages"][-1].content


# # Interactive CLI for the travel assistant agent

# config = {"configurable": {"thread_id": "1"}}

# while True:
#     user_input = input("You: ")
#     if user_input.lower() in ["exit", "quit"]:
#         break
   
#     # Just send the current message - let the agent handle history
#     response = agent.invoke({"messages": [HumanMessage(content=user_input)]}, config=config)
    
#     # Print the last message from the agent
#     if "messages" in response:
#         last_message = response["messages"][-1]
#         print("Bot:", last_message.content)